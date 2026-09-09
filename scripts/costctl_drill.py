"""Q8 / Q10 from docs/INSPECTION.md — the two cost controls that need a recreate.

    Q8   LLM_ENABLED=false          the STATIC FLOOR. No Redis value can lift it.
    Q10  DAILY_SPEND_LIMIT_USD>0    the AUTOMATIC breaker, on accumulated spend.

Both change container env, so both recreate `api` (and `worker` for Q10) and both are
restored in a `finally` that re-recreates from .env and VERIFIES the app answers again.

On Q10 this tests ENFORCEMENT, not accumulation. Accumulation was already proven on the
failover ladder, where the charged cost and the delta written to the breaker's key
matched to the cent on both paid rungs (+0.000772 groq, +0.002197 openai). Here the key
is seeded directly so the drill does not have to spend real money to cross a threshold —
and the two halves together are what make the breaker credible.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _inspect_common import (  # noqa: E402
    API,
    REDIS,
    Report,
    dexec,
    http,
    post_json,
    section,
    sh,
)

COMPOSE = [
    "docker", "compose",
    "-f", "docker-compose.data.yml",
    "-f", "docker-compose.app.yml",
    "-f", "docker-compose.observability.yml",
]
SETTLE_S = 5.0


def recreate(services: list[str], env: dict[str, str] | None = None) -> tuple[int, str]:
    """Recreate services with optional env overrides.

    Shell env beats .env for compose ${VAR} interpolation — the same mechanism `up-app`
    uses to make ENGINE= authoritative for SERVING_CHAIN.
    """
    import os

    prev = os.environ.copy()
    try:
        os.environ.update(env or {})
        return sh(COMPOSE + ["up", "-d", "--no-deps", "--force-recreate", *services],
                  timeout=420)
    finally:
        os.environ.clear()
        os.environ.update(prev)


def wait_api(timeout_s: int = 180) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        code, _ = http(f"{API}/health", timeout=10)
        if code == 200:
            return True
        time.sleep(3)
    return False


def env_in(container: str, var: str) -> str:
    _, out = dexec(container, ["sh", "-c", f"echo ${var}"])
    return out.strip()


def plan_code() -> int:
    code, _ = post_json(f"{API}/plan",
                        {"city": "Kyoto", "interests": ["temples"], "days": 1})
    return code


def q8_static_floor(r: Report) -> None:
    section("Q8 - static floor: LLM_ENABLED=false")
    api_c = "p3-ai-travel-planner-api-1"
    try:
        recreate(["api"], {"LLM_ENABLED": "false"})
        if not wait_api():
            r.bad("api came back with the floor set", "no /health after 180s")
            return
        seen = env_in(api_c, "LLM_ENABLED")
        if seen != "false":
            r.void("floor reached the container", f"LLM_ENABLED={seen!r} - not applied")
            return
        r.ok("floor reached the container", "LLM_ENABLED=false")

        code = plan_code()
        (r.ok if code == 503 else r.bad)(
            "planning refuses with the floor down",
            f"HTTP {code}" + ("" if code == 503 else " - expected 503"))

        # The floor OUTRANKS the runtime switch: setting the Redis key to "1" must not
        # lift it. That ordering is the whole reason the floor exists.
        dexec(REDIS, ["redis-cli", "set", "planning:enabled", "1"])
        time.sleep(1)
        code = plan_code()
        (r.ok if code == 503 else r.bad)(
            "Redis CANNOT lift the static floor",
            f"HTTP {code}" + ("" if code == 503 else " - the floor was overridden!"))
        dexec(REDIS, ["redis-cli", "del", "planning:enabled"])
    finally:
        recreate(["api"])
        ok = wait_api()
        seen = env_in(api_c, "LLM_ENABLED")
        (r.ok if ok and seen == "true" else r.bad)(
            "floor RESTORED", f"LLM_ENABLED={seen!r} health={'up' if ok else 'DOWN'}")


def q10_spend_breaker(r: Report) -> None:
    section("Q10 - daily spend breaker: DAILY_SPEND_LIMIT_USD")
    api_c = "p3-ai-travel-planner-api-1"
    day = time.strftime("%Y-%m-%d", time.gmtime())
    key = f"spend:usd:{day}"
    _, original = dexec(REDIS, ["redis-cli", "get", key])
    original = original.strip()
    try:
        # Seed spend ABOVE the limit we are about to set. Enforcement is what is under
        # test here; accumulation was proven on the ladder.
        dexec(REDIS, ["redis-cli", "set", key, "5.00"])
        recreate(["api", "worker"], {"DAILY_SPEND_LIMIT_USD": "1.00"})
        if not wait_api():
            r.bad("api came back with the breaker armed", "no /health after 180s")
            return
        seen = env_in(api_c, "DAILY_SPEND_LIMIT_USD")
        if seen != "1.00":
            r.void("limit reached the container", f"DAILY_SPEND_LIMIT_USD={seen!r}")
            return
        r.ok("limit reached the container", "DAILY_SPEND_LIMIT_USD=1.00, spend=5.00")

        code = plan_code()
        (r.ok if code == 503 else r.bad)(
            "breaker REFUSES once the day's spend is breached",
            f"HTTP {code}" + ("" if code == 503 else " - expected 503"))

        # Under the limit, traffic must flow again — a breaker that never closes is a
        # kill switch with extra steps.
        dexec(REDIS, ["redis-cli", "set", key, "0.10"])
        time.sleep(2)
        code = plan_code()
        (r.ok if code == 202 else r.bad)(
            "breaker CLOSES again below the limit",
            f"HTTP {code}" + ("" if code == 202 else " - expected 202"))
    finally:
        if original and original not in ("", "(nil)"):
            dexec(REDIS, ["redis-cli", "set", key, original])
        else:
            dexec(REDIS, ["redis-cli", "del", key])
        recreate(["api", "worker"])
        ok = wait_api()
        seen = env_in(api_c, "DAILY_SPEND_LIMIT_USD")
        (r.ok if ok and seen == "0" else r.bad)(
            "breaker RESTORED", f"DAILY_SPEND_LIMIT_USD={seen!r} health={'up' if ok else 'DOWN'}")


def main() -> int:
    print("\nCOST CONTROL DRILL - Q8 / Q10")
    print("  Both recreate containers with modified env, and both restore from .env.\n")
    r = Report()
    try:
        q8_static_floor(r)
        q10_spend_breaker(r)
    finally:
        section("final state")
        code = plan_code()
        (r.ok if code == 202 else r.bad)("planning works at the end", f"HTTP {code}")
    return r.summary()


if __name__ == "__main__":
    raise SystemExit(main())
