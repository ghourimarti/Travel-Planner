"""Register this stack's Redis instances in RedisInsight, idempotently.

WHY THIS EXISTS
---------------
RedisInsight ships with an empty database list, and this stack runs TWO Redis
instances that are easy to confuse:

    voyantra-app        the application's Redis - cache, Celery broker AND result
                        backend, the daily-spend accumulator, rate-limit windows
    voyantra-langfuse   Langfuse's own Redis - queues for trace ingestion

Adding them by hand after every bring-up is the kind of chore that quietly stops
happening, and then nobody looks at Redis at all. Worse, `FLUSHDB` on the wrong one of
these two is the difference between "dropped some cached lookups" and "destroyed the
task queue and the cost control" - so the names matter as much as the connection.

IDEMPOTENT by name: it lists what is registered, adds only what is missing, and says
which case applied. Safe to run on every `make up-obs`.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

PORT = os.environ.get("REDISINSIGHT_PORT", "3012")
BASE = f"http://localhost:{PORT}"

#: Read from the GUI_* block .env already carries. Those variables existed purely as
#: INSTRUCTIONS for typing the connection in by hand ("RedisInsight -> Add Redis
#: database"); this reads the same values and does it for you, so the documentation and
#: the automation can never drift apart.
#:
#: Hosts are compose SERVICE names: they are resolved from inside the RedisInsight
#: container, not from this machine. `localhost` would point RedisInsight at itself.
DATABASES = [
    {
        "name": "voyantra-app",
        "host": os.environ.get("GUI_APP_REDIS_HOST", "redis"),
        "port": int(os.environ.get("GUI_APP_REDIS_PORT", "6379")),
        "db": 0,
    },
    {
        "name": "voyantra-langfuse",
        "host": os.environ.get("GUI_LANGFUSE_REDIS_HOST", "langfuse-redis"),
        "port": int(os.environ.get("GUI_LANGFUSE_REDIS_PORT", "6379")),
        "db": 0,
        # langfuse-redis runs with --requirepass. Without this the API answers
        # HTTP 424 (failed dependency) - it accepts the definition only if it can
        # actually connect, which is a good API and a confusing error to read.
        "password": os.environ.get("LANGFUSE_REDIS_PASSWORD", "langfuse-redis"),
    },
]


def _req(method: str, path: str, body: dict | None = None, timeout: int = 15):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method=method,
        headers={"content-type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def wait_for_api(timeout_s: int = 90) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        code, _ = _req("GET", "/api/databases")
        if code == 200:
            return True
        time.sleep(3)
    return False


def ensure_agreements() -> None:
    """Accept the agreements, because ENCRYPTION depends on them.

    This is not about the EULA dialog. RedisInsight picks its encryption strategy from
    `settings.agreements.encryption`:

        true      -> KEY strategy (or keytar)
        false     -> PLAIN
        undefined -> throws UnsupportedEncryptionStrategyException

    A fresh install has `agreements: null`, so storing ANY database password fails with
    `500 {"message":"Unsupported encryption strategy"}` — which reads like a broken
    encryption key and is actually an unaccepted agreement. langfuse-redis runs with
    --requirepass, so without this it can never be registered at all.

    Analytics and notifications are set to false deliberately: this runs unattended, and
    opting a user into telemetry on their behalf is not ours to do.
    """
    code, settings = _req("GET", "/api/settings")
    if code != 200 or not isinstance(settings, dict):
        return
    agreements = settings.get("agreements") or {}
    if agreements.get("encryption") is True:
        return
    code, _ = _req("PATCH", "/api/settings", {
        "agreements": {
            "eula": True,
            "analytics": False,
            "encryption": True,
            "notifications": False,
        },
    })
    print(f"  RedisInsight: agreements accepted (encryption enabled) - HTTP {code}")


def main() -> int:
    if not wait_for_api():
        # Never fail a bring-up over a GUI convenience — but never claim success either.
        print(f"  RedisInsight: not reachable on {BASE} - skipped (is the obs tier up?)")
        return 0

    ensure_agreements()
    code, existing = _req("GET", "/api/databases")
    have = {d.get("name") for d in existing} if isinstance(existing, list) else set()

    added, kept, failed = [], [], []
    for spec in DATABASES:
        name = spec["name"]
        if name in have:
            kept.append(name)
            continue
        code, resp = _req("POST", "/api/databases", spec, timeout=30)
        if code in (200, 201):
            added.append(name)
        else:
            hint = " - wrong password?" if code == 424 else ""
            failed.append(f"{name} (HTTP {code}{hint})")

    for n in added:
        print(f"  RedisInsight: registered {n}")
    if kept:
        print(f"  RedisInsight: already registered - {', '.join(kept)}")
    if failed:
        print(f"  RedisInsight: FAILED to register - {', '.join(failed)}")

    # VERIFY, do not assume. This is the same discipline the inspection scripts use:
    # a registration that silently did not land is worse than none, because you would
    # go looking in an empty GUI and blame RedisInsight.
    code, final = _req("GET", "/api/databases")
    names = sorted(d.get("name") for d in final) if isinstance(final, list) else []
    print(f"  RedisInsight: {len(names)} database(s) registered -> {names}")
    print(f"  Open it at {BASE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
