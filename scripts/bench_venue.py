#!/usr/bin/env python
"""Measure a serving venue: TTFT, TPOT, tok/s.

WHY THIS EXISTS
---------------
"Is the local engine fast?" is not answerable by a health check. A liveness probe
proves a process is reachable; it says nothing about capacity, and the two get
confused constantly. This measures the three numbers that actually describe a
serving venue, and it measures them the way a user experiences them:

    TTFT   time to FIRST token   - what the user perceives as "did it hang?"
    TPOT   time per output token - the streaming cadence after the first token
    tok/s  output tokens / total - the throughput number people quote

TTFT is only meaningful on a STREAMED request. A non-streaming call returns
everything at once, so its "first token" time is just its total time - which is
why this script always streams, even though that makes it more code.

The same harness runs against any OpenAI-compatible endpoint, which is the point:
comparing a local engine to Groq is only fair if both are measured identically.

    uv run python scripts/bench_venue.py --label local-sglang \\
        --base-url http://localhost:3020/v1 --model Qwen/Qwen2.5-7B-Instruct-AWQ

    uv run python scripts/bench_venue.py --label groq \\
        --base-url https://api.groq.com/openai/v1 --model qwen/qwen3.8-27b \\
        --api-key "$GROQ_API_KEY"
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit("httpx is required:  uv run python scripts/bench_venue.py ...")


DEFAULT_PROMPT = (
    "Plan a one-day itinerary in Kyoto for someone interested in temples and food. "
    "Give three stops with a one-line reason for each."
)


@dataclass
class Sample:
    ttft_s: float
    total_s: float
    out_tokens: int

    @property
    def tpot_ms(self) -> float:
        """Milliseconds per output token AFTER the first."""
        if self.out_tokens < 2:
            return float("nan")
        return (self.total_s - self.ttft_s) * 1000.0 / (self.out_tokens - 1)

    @property
    def toks_per_s(self) -> float:
        return self.out_tokens / self.total_s if self.total_s > 0 else float("nan")


def one_request(client: httpx.Client, url: str, headers: dict, body: dict) -> Sample:
    """Stream one completion, timing the first token separately from the rest."""
    started = time.perf_counter()
    ttft: float | None = None
    out_tokens = 0

    with client.stream("POST", url, headers=headers, json=body, timeout=180.0) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            # Count only CONTENT deltas. Role-only and empty deltas are protocol
            # noise; counting them inflates the token count and deflates TPOT.
            if delta.get("content"):
                if ttft is None:
                    ttft = time.perf_counter() - started
                out_tokens += 1

    total = time.perf_counter() - started
    if ttft is None:
        # Served, but produced no content tokens. Reporting 0 here would silently
        # look like an instant response; NaN makes it visible as "not measured".
        ttft = float("nan")
    return Sample(ttft_s=ttft, total_s=total, out_tokens=out_tokens)


def pct(values: list[float], q: float) -> float:
    clean = [v for v in values if v == v]  # drop NaN
    if not clean:
        return float("nan")
    clean.sort()
    k = max(0, min(len(clean) - 1, int(round(q * (len(clean) - 1)))))
    return clean[k]


def main() -> int:
    ap = argparse.ArgumentParser(description="Measure TTFT / TPOT / tok-s for a venue.")
    ap.add_argument("--base-url", required=True, help="OpenAI-compatible base, e.g. http://localhost:3020/v1")
    ap.add_argument("--model", required=True)
    ap.add_argument("--label", default="venue")
    ap.add_argument("--api-key", default=os.environ.get("BENCH_API_KEY", ""))
    ap.add_argument("--n", type=int, default=5, help="measured requests (after warmup)")
    ap.add_argument("--max-tokens", type=int, default=128)
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    a = ap.parse_args()

    url = a.base_url.rstrip("/") + "/chat/completions"
    headers = {"content-type": "application/json"}
    if a.api_key:
        headers["authorization"] = f"Bearer {a.api_key}"
    body = {
        "model": a.model,
        "messages": [{"role": "user", "content": a.prompt}],
        "max_tokens": a.max_tokens,
        "stream": True,
    }

    print(f"\n  venue : {a.label}")
    print(f"  url   : {url}")
    print(f"  model : {a.model}")
    print(f"  n     : {a.n} measured requests, max_tokens={a.max_tokens}\n")

    with httpx.Client() as client:
        # A cold first request pays for CUDA-graph capture, allocator warmup and
        # any lazy load. Including it would describe a state the venue is in
        # exactly once, so it is measured and DISCARDED rather than skipped
        # silently - the number is still interesting when it is huge.
        try:
            warm = one_request(client, url, headers, body)
            print(f"  warmup (discarded): ttft {warm.ttft_s * 1000:7.0f} ms  "
                  f"{warm.out_tokens} tok in {warm.total_s:.2f} s")
        except Exception as exc:
            print(f"  WARMUP FAILED: {type(exc).__name__}: {exc}")
            return 1

        samples: list[Sample] = []
        for i in range(a.n):
            try:
                s = one_request(client, url, headers, body)
            except Exception as exc:
                print(f"  request {i + 1} FAILED: {type(exc).__name__}: {exc}")
                continue
            samples.append(s)
            print(f"  run {i + 1}/{a.n}: ttft {s.ttft_s * 1000:7.0f} ms  "
                  f"tpot {s.tpot_ms:6.1f} ms  {s.toks_per_s:6.1f} tok/s  "
                  f"({s.out_tokens} tok)")

    if not samples:
        print("\n  NO SUCCESSFUL REQUESTS - nothing to report.\n")
        return 1

    ttfts = [s.ttft_s * 1000 for s in samples]
    tpots = [s.tpot_ms for s in samples]
    tps = [s.toks_per_s for s in samples]

    print("\n  " + "=" * 58)
    print(f"  {a.label}  ({len(samples)}/{a.n} succeeded)")
    print("  " + "=" * 58)
    print(f"  TTFT   p50 {pct(ttfts, .50):8.0f} ms   p95 {pct(ttfts, .95):8.0f} ms")
    print(f"  TPOT   p50 {pct(tpots, .50):8.1f} ms   p95 {pct(tpots, .95):8.1f} ms")
    print(f"  tok/s  mean {statistics.fmean([t for t in tps if t == t]):7.1f}")
    print("  " + "=" * 58)
    print("  TTFT is what the user feels. tok/s is what a spec sheet quotes.")
    print("  A venue can win one and lose the other - report both.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
