# GPU venue — bring-up, verification, teardown

A local inference engine is a **venue** in the serving chain, not a replacement for
it. This document is the runbook for making that venue real on this machine and
for proving it actually serves.

Two rules govern everything below, and both were learned the expensive way:

> **A liveness check is not a capacity check.** A container that is `Up`, a
> `/health` that returns 200, and a model list that renders are three green
> signals that say nothing about whether the engine can generate a token.
>
> **Declared is not working.** A chain entry naming an engine you did not start
> costs every request its connect timeout and then quietly hands the answer to a
> hosted venue you pay for.

---

## 0. Hardware reality on this machine

| | |
|---|---|
| GPU | NVIDIA GeForce RTX 3060, **12 GB**, compute capability 8.6 |
| Passthrough | verified — `nvidia-smi` runs **inside** a container |
| Docker VM (WSL2) | 21.5 GiB |
| Engine images | `vllm/vllm-openai` (30.8 GB) and `lmsysorg/sglang` (47 GB), already pulled |
| Model | `Qwen/Qwen2.5-7B-Instruct-AWQ` — INT4, ~5.5 GB of weights, **not gated** |

A 12 GB card fits **one** 7B model at INT4 with an 8k KV cache. It does not fit
two. See §4.

---

## 1. Bring-up, in the five stages it actually takes

```bash
make sglang-up          # engine only (SGLang is the default)
make vllm-up            # engine only (vLLM)
make up-sglang          # whole app served by SGLang
make up-vllm            # whole app served by vLLM
```

Each `-up` runs the same sequence, and **waits for SERVING, not for the container
to exist**:

```
preflight (VRAM fits?) -> image (pull if absent) -> container -> weights -> load -> SERVE
```

`docker compose up -d --wait` on its own reports success the moment the container
is created — while the engine still has 5.5 GB of weights to load and answers
nothing. The healthcheck in `docker-compose.gpu.yml` therefore polls the engine's
own `/health`, with a **900 s `start_period`** covering a cold load.

### Disable Xet, or the download silently transfers nothing

`huggingface_hub` 1.x ships `hf_xet` and uses the Xet chunk backend **by default**.
On this network it hangs: the process stays alive, writes 0-byte `.incomplete`
placeholders, and moves no data at all — forever. Measured A/B, same container,
same token, same file:

| | throughput |
|---|---|
| Xet enabled (the default) | **0 MB in 120 s** |
| `HF_HUB_DISABLE_XET=1` | 21 MB in 90 s (≈0.23 MB/s, matches raw `curl`) |

`scripts/ensure_weights.sh` sets it. If you pull weights any other way, set it
yourself — this failure is invisible, because a hung Xet transfer and a slow link
look identical from the outside.

It is **not** a rate-limit problem, and a token does not fix it: authenticating
moved throughput from 0.19 to 0.23 MB/s, i.e. nothing. Set `HF_TOKEN` for gated
repos, not for speed.

### First boot downloads ~5.5 GB and must not be interrupted

`huggingface_hub` does **not** resume across process restarts. Each new process
writes `<blob>.<session-id>.incomplete` with a **fresh** session id and starts that
file from byte zero, orphaning the previous partial. So a "retry" is not a resume —
it throws away everything downloaded so far.

That makes a stall detector actively dangerous. An early version of
`ensure_weights.sh` killed transfers on sustained silence and drove net progress on
a 4 GB blob to **exactly zero** across three cycles, while the un-babysat engine had
managed 612 MB on its own. It now reports quiet windows and never kills.

Watch it rather than retrying it:

```bash
docker logs -f tp-sglang
docker exec tp-sglang du -sh /root/.cache/huggingface
```

Both engines share **one** cache volume (`tp_hf_cache`) — one download, either
engine. `make downv` keeps it deliberately; only `make clean-models` removes it.

---

## 2. Verify it actually generates

Liveness first, then the check that matters:

```bash
# 1. up? (liveness — NOT capacity)
curl -s localhost:3020/health
curl -s localhost:3020/v1/models | python -m json.tool

# 2. does it GENERATE? (the real check)
curl -s localhost:3020/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"Qwen/Qwen2.5-7B-Instruct-AWQ",
       "messages":[{"role":"user","content":"Name three things to do in Kyoto."}],
       "max_tokens":80}'

# 3. in a browser, unguarded
make webui        # http://localhost:3021

# 4. how fast, really
make bench-engine # TTFT / TPOT / tok-s

# 5. is the APP using it?
make which-engine
```

`make webui` is deliberately the **unguarded** path — no retrieval, no POI
grounding, no itinerary schema. Judging *engine* quality there and *product*
quality in the web app is what stops a bad retrieval config from being blamed on
the model.

---

## 3. Wiring it into the serving chain

The chain is **opt-in**. `SERVING_CHAIN` ships empty, which keeps the legacy
per-tier order (OpenAI first) — so adding a GPU changes nothing until you say so.

```
SERVING_CHAIN=local-sglang,groq,openai
```

* tried left to right; the first reachable leg answers
* a leg with no URL or key is **skipped with a warning naming it**, never a
  silent downgrade
* `openai` goes last **because it is the one you pay for** — it will still answer
  when everything free is down, and the moment it starts serving, cost stops
  reading `$0`. That transition is how you learn a local engine died.

`sglang` on its own is **rejected at startup**: it is an *engine*, not a venue.
The error names the fix (`local-sglang`). That mistake otherwise surfaces as a
container exiting 3 behind a "dependency failed to start" message that identifies
nothing.

`make up-sglang` **exports** `SERVING_CHAIN` for that invocation, because the
shell environment beats `env_file` for compose interpolation. Without the export
the target prints one chain while the container runs another — and a knob that
reports a value it does not apply is worse than no knob, because it is believed.

### Circuit breaker

Failover alone is not enough. Without a breaker a dead local engine is retried on
**every** request, so one free leg being down becomes latency on 100% of traffic.

```
CIRCUIT_FAILURE_THRESHOLD=3      consecutive TRANSIENT failures -> leg opens
CIRCUIT_COOLDOWN_SECONDS=30      then exactly ONE probe is admitted
```

A `4xx` does **not** count against a venue — that is our bad request and fails
identically everywhere.

---

## 4. One engine at a time — this is not a preference

vLLM asks `0.80` of the card and SGLang `0.70`. That is 150% of an RTX 3060, and
it does **not** fail fast: vLLM wedges at `Starting to load model` with no error
line, because a CUDA allocator waiting on memory that will never arrive has
nothing to report.

The two memory flags are **not** the same knob:

| Engine | Flag | Means |
|---|---|---|
| vLLM | `--gpu-memory-utilization` | fraction of **FREE** memory, fits inside it |
| SGLang | `--mem-fraction-static` | fraction of **TOTAL**, ignores what is resident |

Copying vLLM's `0.80` into SGLang OOM-kills it on a desktop GPU — and the crash
arrives *late*, after it has been serving happily, the moment someone opens
another browser tab. `0.70` leaves headroom for the desktop.

They are also **not independent failure domains**: both die with the GPU. Listing
both local legs buys protection against an engine fault (crash, OOM, bad build)
and nothing else. A hosted leg still belongs last.

`make up-engine` removes the engine it is *not* using before starting the one it
is, because `docker compose up` with a different profile does not stop containers
outside that profile.

---

## 5. When it will not start

`scripts/engine_preflight.sh` refuses in ~2 seconds rather than letting you
discover the problem via exit 137 after twenty minutes. It sizes the need from the
checkpoint (`weights x1.4 + 1.5 GB runtime`) and, when another container holds the
card, **names that container and prints the command to stop it**.

`scripts/engine_failed.sh` runs on a failed start and **inspects** the container
rather than asserting a cause:

| State | Meaning |
|---|---|
| `running` | genuine timeout — still loading. Watch it; do not interrupt a download. |
| exit `137` / `OOMKilled` | out of memory — GPU VRAM *or* the WSL2 host-RAM ceiling |
| other non-zero | crash — last 40 log lines printed |
| gone | never created, or removed after failing |

A diagnostic that guesses is worse than none: the obvious version asserts "still
running, this is a timeout", and the one time it matters the container has been
SIGKILLed, sending you to tail logs that no longer exist.

---

## 6. Teardown

```bash
make sglang-down     # stop the engine; weights + image kept
make down-engine     # stop EVERY engine, whichever is selected
make clean-models    # DESTRUCTIVE: delete the shared ~5.5 GB weight cache
```

`make downv` wipes app data volumes but **keeps** `tp_hf_cache`: weights are
immutable published artifacts, not state, and re-downloading costs one
uninterrupted 5.5 GB run.

### ⚠ Never `docker volume prune`

A volume counts as "dangling" the moment no container references it — and
`docker compose down` *removes containers*. On this machine **547 of 565 volumes
report as dangling**, including:

* `tp_overpass_db` — the **2–4 hour** OSM import
* other projects' ingested corpora and their Langfuse Postgres/ClickHouse/MinIO

Safe reclaim is `docker builder prune` plus dangling **images**. Neither touches a
volume.

Note also that reclaiming space *inside* Docker does not return it to Windows:
Docker Desktop's VHDX does not shrink on its own and needs a separate compact.

---

## 7. Measuring, not guessing

```bash
make bench-engine     # the local engine named by ENGINE=
make bench-groq       # same harness, hosted
make bench-openai     # same harness, hosted (COSTS MONEY)
```

`scripts/bench_venue.py` reports:

| Metric | What it answers |
|---|---|
| **TTFT** | time to first token — what the user perceives as "did it hang?" |
| **TPOT** | time per output token — the streaming cadence after the first |
| **tok/s** | throughput — the number a spec sheet quotes |

TTFT is only meaningful on a **streamed** request, so the harness always streams.
A cold first request is measured and **discarded** as warmup: it pays for CUDA
graph capture and allocator warmup, a state the venue is in exactly once.

A venue can win one metric and lose another — report both.

### Measured on this machine — 2026-09-07

`Qwen2.5-7B-Instruct-AWQ` on an RTX 3060 12 GB, SGLang, `mem-fraction-static=0.55`,
`context_len=8192`, `max_total_num_tokens=11881`. 5 measured requests, warmup discarded:

| Metric | p50 | p95 |
|---|---|---|
| TTFT | **50 ms** | 559 ms |
| TPOT | **15.2 ms** | 15.7 ms |
| throughput | **60.8 tok/s** mean | |

Cold start with weights already local: **360 s** to healthy (load + CUDA graph capture).
A full single-city itinerary end-to-end: **17 s at $0.00**, against 15 s at $0.0025 on
OpenAI — so going local cost ~2 s of wall clock and removed the per-itinerary charge.

The p95 TTFT is the *first* request after idle; every subsequent one sits at ~50 ms.
That gap is the CUDA-graph/allocator warmup, and it is why the harness discards a
warmup run rather than averaging it in.

> **The Groq leg is dead as configured.** `llama-3.1-8b-instant` and
> `llama-3.3-70b-versatile` both return **404** — Groq decommissioned them. Until
> `TIER_ROUTING` is updated, the middle leg of every chain is a no-op and traffic
> falls straight through to the paid OpenAI leg.
