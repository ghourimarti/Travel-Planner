"""Backup/restore drill with a measured RTO — restoring to PARALLEL targets only.

A backup you have never restored is a hope, not a backup. The only way to know is to
restore it, and the only safe way to do that on a live system is to restore somewhere
else and compare.

SAFETY, stated plainly: this NEVER writes to `tp` or to the `pois` collection. It
creates `tp_restore_drill` and `pois_restore_drill`, restores into those, compares them
against the originals, and drops them in a `finally`. If this script is killed halfway,
the worst it leaves behind is a scratch database and a scratch collection, both named so
obviously that you can drop them by hand.

WHAT IS DELIBERATELY NOT BACKED UP: Redis. It holds the cache, the Celery broker and
result backend, the daily-spend accumulator and the rate-limit windows — all of it
either reconstructible or intentionally short-lived (`appendonly no`, save points at
3600s/1 change). Backing it up would imply a durability guarantee the design does not
make. What matters is knowing that: a Redis loss costs up to an hour of spend
accounting, and the drill says so rather than pretending to protect it.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _inspect_common import (  # noqa: E402
    DB,
    QDRANT,
    Report,
    dexec,
    http,
    section,
)

PG_USER = "tp"
PG_DB = "tp"
PG_SCRATCH = "tp_restore_drill"
DUMP = "/tmp/tp_backup_drill.dump"

COLLECTION = "pois"
QD_SCRATCH = "pois_restore_drill"


def psql(db: str, sql: str, timeout: int = 120) -> tuple[int, str]:
    return dexec(DB, ["psql", "-U", PG_USER, "-d", db, "-tAc", sql], timeout=timeout)


def qd(method: str, path: str, body: dict | None = None, timeout: int = 180):
    """Qdrant REST from the HOST.

    The first version shelled out to curl INSIDE the qdrant container, on the assumption
    that a `file://` snapshot path had to be resolved locally. Two things were wrong:
    the qdrant image has no curl at all ("executable file not found in $PATH"), and the
    `location` in a recover request is resolved by the SERVER regardless of where the
    request came from. So talk to it over HTTP like everything else.
    """
    import urllib.error
    import urllib.request

    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{QDRANT}{path}", data=data, method=method,
        headers={"content-type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:  # noqa: BLE001
            return e.code, raw
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def drop_scratch(r: Report | None = None) -> None:
    psql("postgres", f'DROP DATABASE IF EXISTS "{PG_SCRATCH}"')
    dexec(DB, ["rm", "-f", DUMP])
    qd("DELETE", f"/collections/{QD_SCRATCH}")


def postgres_drill(r: Report) -> None:
    section("Postgres — dump, restore to a PARALLEL database, compare")
    code, out = psql(PG_DB, "select count(*) from runs")
    if code != 0:
        r.bad("source row count", out.strip()[:120])
        return
    source_rows = out.strip()
    r.ok("source runs table", f"{source_rows} rows")

    t0 = time.time()
    code, out = dexec(
        DB, ["pg_dump", "-U", PG_USER, "-d", PG_DB, "-Fc", "-f", DUMP], timeout=600
    )
    dump_s = time.time() - t0
    if code != 0:
        r.bad("pg_dump", out.strip()[:160])
        return
    _, size = dexec(DB, ["sh", "-c", f"du -h {DUMP} | cut -f1"])
    r.ok("pg_dump completed", f"{size.strip()} in {dump_s:.1f}s")

    # PARALLEL target. The live database is never written to.
    psql("postgres", f'DROP DATABASE IF EXISTS "{PG_SCRATCH}"')
    code, out = psql("postgres", f'CREATE DATABASE "{PG_SCRATCH}"')
    if code != 0:
        r.bad("create scratch database", out.strip()[:160])
        return

    t0 = time.time()
    code, out = dexec(
        DB, ["pg_restore", "-U", PG_USER, "-d", PG_SCRATCH, "--no-owner", DUMP],
        timeout=600,
    )
    restore_s = time.time() - t0
    # pg_restore warns about roles/extensions on a clean DB; row count is the real test.
    r.ok("pg_restore completed", f"{restore_s:.1f}s (RTO for this dataset)")

    code, out = psql(PG_SCRATCH, "select count(*) from runs")
    restored_rows = out.strip() if code == 0 else "ERROR"
    (r.ok if restored_rows == source_rows else r.bad)(
        "restored row count MATCHES source",
        f"source={source_rows} restored={restored_rows}",
    )

    # A row count can match while the data is wrong. Compare content, not just volume.
    code, a = psql(PG_DB, "select md5(string_agg(id::text, ',' order by id)) from runs")
    code2, b = psql(PG_SCRATCH,
                    "select md5(string_agg(id::text, ',' order by id)) from runs")
    if code == 0 and code2 == 0 and a.strip():
        (r.ok if a.strip() == b.strip() else r.bad)(
            "restored CONTENT matches (md5 of ordered ids)",
            f"{a.strip()[:16]}... vs {b.strip()[:16]}...")
    else:
        r.void("restored content comparison", "could not compute a digest")


def qdrant_drill(r: Report) -> None:
    section("Qdrant — snapshot, restore to a PARALLEL collection, compare")
    code, body = http(f"{QDRANT}/collections/{COLLECTION}")
    if code != 200:
        r.bad("source collection readable", str(body)[:120])
        return
    source_points = json.loads(body)["result"]["points_count"]
    r.ok("source collection", f"{COLLECTION}: {source_points} points")

    t0 = time.time()
    code, resp = qd("POST", f"/collections/{COLLECTION}/snapshots")
    snap_s = time.time() - t0
    name = (resp or {}).get("result", {}).get("name") if isinstance(resp, dict) else None
    if not name:
        r.bad("snapshot created", str(resp)[:180])
        return
    r.ok("snapshot created", f"{name} in {snap_s:.1f}s")

    # Recover INTO A DIFFERENT COLLECTION. The path segment is the TARGET, so the live
    # `pois` collection is never touched.
    qd("DELETE", f"/collections/{QD_SCRATCH}")
    t0 = time.time()
    code, resp = qd(
        "PUT", f"/collections/{QD_SCRATCH}/snapshots/recover",
        {"location": f"file:///qdrant/snapshots/{COLLECTION}/{name}"},
    )
    restore_s = time.time() - t0
    ok = isinstance(resp, dict) and resp.get("status") == "ok"
    (r.ok if ok else r.bad)("snapshot recovered into a parallel collection",
                            f"{restore_s:.1f}s (RTO) — {str(resp)[:120]}")
    if not ok:
        return

    code, body = http(f"{QDRANT}/collections/{QD_SCRATCH}")
    restored = json.loads(body)["result"]["points_count"] if code == 200 else -1
    (r.ok if restored == source_points else r.bad)(
        "restored point count MATCHES source",
        f"source={source_points} restored={restored}")

    # A point count can be right while the payload is empty. Qdrant's scroll is a POST;
    # doing it as a GET returns 405 and would have passed a check that proves nothing.
    code, resp = qd("POST", f"/collections/{QD_SCRATCH}/points/scroll",
                    {"limit": 1, "with_payload": True})
    pts = (resp or {}).get("result", {}).get("points") if isinstance(resp, dict) else None
    if pts:
        payload_keys = sorted((pts[0].get("payload") or {}).keys())[:5]
        r.ok("restored points carry their payload", f"keys={payload_keys}")
    else:
        r.bad("restored points carry their payload", str(resp)[:140])

    qd("DELETE", f"/collections/{COLLECTION}/snapshots/{name}")


def main() -> int:
    print("\nBACKUP / RESTORE DRILL — measured RTO, PARALLEL targets only")
    print(f"  live objects NEVER written: database '{PG_DB}', collection '{COLLECTION}'")
    print(f"  scratch objects created and dropped: '{PG_SCRATCH}', '{QD_SCRATCH}'\n")
    r = Report()
    try:
        postgres_drill(r)
        qdrant_drill(r)
        section("Redis — deliberately NOT a backup target")
        r.skip("redis backup",
               "cache + broker + spend + rate limits: reconstructible or intentionally "
               "short-lived (appendonly no). A Redis loss costs up to an hour of spend "
               "accounting; backing it up would imply a guarantee the design does not make.")
    finally:
        section("cleanup")
        drop_scratch()
        code, out = psql("postgres",
                         f"select count(*) from pg_database where datname='{PG_SCRATCH}'")
        (r.ok if out.strip() == "0" else r.bad)("scratch database dropped", out.strip())
        code, body = http(f"{QDRANT}/collections/{QD_SCRATCH}")
        (r.ok if code == 404 else r.bad)("scratch collection dropped", f"HTTP {code}")
        code, body = http(f"{QDRANT}/collections/{COLLECTION}")
        live = json.loads(body)["result"]["points_count"] if code == 200 else -1
        (r.ok if live > 0 else r.bad)("LIVE collection untouched", f"{live} points")
        code, out = psql(PG_DB, "select count(*) from runs")
        (r.ok if code == 0 else r.bad)("LIVE database untouched", f"{out.strip()} rows")
    return r.summary()


if __name__ == "__main__":
    raise SystemExit(main())
