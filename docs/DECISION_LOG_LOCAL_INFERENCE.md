# Decision Log — Local Inference Engines (vLLM / SGLang)

> **Supplement to [`DECISION_LOG.md`](./DECISION_LOG.md), not a replacement.** That file records the
> 22 decisions the shipped system was built on and stays authoritative for everything it covers.
> This file records the decisions added when a **self-hosted inference engine** became the first
> leg of the serving chain: three NEW decisions (D23–D25) and six AMENDMENTS to existing ones.
>
> **Status:** design agreed, implementation in progress.
> **Constraint that shapes everything here:** the app is already complete and working. Every change
> below is **additive with a zero-change default** — with no `CHAIN_*` variable set, the gateway
> resolves exactly the routing it uses today.

---

## 0. The measured hardware context

Not assumed — read off the target machine before any decision was made.

| Property | Measured value | Consequence for the design |
|---|---|---|
| GPU | **NVIDIA GeForce RTX 3060, 12,288 MiB** | 7–8B class at INT4 is the ceiling. FP16 of an 8B model (~16 GB) does not fit. |
| Compute capability | **8.6 (Ampere)** | ✅ AWQ / GPTQ INT4 with Marlin kernels. ❌ **FP8 requires sm_89+ (Ada)** — unavailable, so FP8 quantization is off the table. |
| Driver | 591.86 | Current enough for both engine images. |
| Docker runtime | **`nvidia` present** | GPU containers work; no host reconfiguration needed. |
| **VRAM free at rest** | **1,024 MiB of 12,288** | 🔴 **11 GB is held by the Windows desktop** (Chrome ×2, VS Code, WhatsApp, Edge WebView, NVIDIA Overlay, Docker Desktop, Explorer, Radeon Software). An engine started in this state is OOM-killed before it serves. |

That last row is the single most important operational fact in this document, and it is why the
memory preflight in **D25** is mandatory rather than a nicety.

---

## 1. What is being added, in one line

```
CHAIN_*  =  local (vLLM | SGLang, one at a time)  →  groq  →  openai
```

An ordered, **per-call-point** fallback array, configured in `.env`, where the first reachable leg
answers and any leg without a URL or key is silently skipped.

---

# NEW DECISIONS

## Decision 23: Local inference engine — vLLM and SGLang, one at a time

**Question.** Which self-hosted engine serves the local leg, on which model, and may both run at once?

**Options considered.**

| Option | Pros | Cons | Fits a 12 GB desktop GPU? |
|---|---|---|---|
| **A — vLLM only** | Mature, best-known throughput, continuous batching | One engine = one failure mode to learn | Y |
| **B — SGLang only** | Very fast structured/JSON decoding (RadixAttention) | Smaller ecosystem | Y |
| **C — Both, selectable, ONE at a time** | Two real options; a genuine engine comparison; either can cover the other's fault | Two weight downloads; the selector must be enforced | **Y — chosen** |
| D — Both running simultaneously | Engine-fault failover without leaving the box | 2 × weights + 2 × KV cache on one 12 GB card; measured on the reference project as a wedge, not an error | **N** |

**Decision.** **Option C.** Exactly one local engine runs at a time, chosen by `SERVING_ENGINE`
(or named explicitly in a chain entry as `local-vllm` / `local-sglang`).

| Engine | Model | Approx. weights | Notes |
|---|---|---|---|
| **vLLM** | `Qwen/Qwen2.5-7B-Instruct-AWQ` | ~5.5 GB | INT4 AWQ, Ampere-friendly, proven on 12 GB |
| **SGLang** | `hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4` | ~5.7 GB | ⚠️ **gated on Hugging Face** — needs `HF_TOKEN` + accepted licence |

**Reasoning.** Two engines give a real comparison and a second option when one has a bad build;
running them *together* does not, because a single GPU is a single failure domain — both legs die
with the card. Independence only begins at the hosted legs, which is why `groq` and `openai` sit
below `local` in every chain.

**Trade-off accepted — different weights per engine.** Choosing Qwen for vLLM and Llama for SGLang
means **two downloads (~11 GB of disk) and no shared weight cache**, and — more importantly — an
engine benchmark now compares *model + engine together*, not the engine alone. That is a deliberate
choice for "two genuinely different local options"; if apples-to-apples engine benchmarking ever
matters more, point both at the same model ID and the comparison becomes valid again.

**⚠️ The memory flags are NOT interchangeable.** This is the trap that OOM-kills a working engine
hours after it starts serving:

| Engine | Flag | Semantics |
|---|---|---|
| vLLM | `--gpu-memory-utilization` | fraction of **FREE** memory — it measures what is available and fits inside it |
| SGLang | `--mem-fraction-static` | fraction of **TOTAL** memory — it ignores whatever is already resident |

On this machine the desktop holds ~11 GB *and fluctuates*. Copying vLLM's `0.80` into SGLang's flag
asks for 9.8 GB of a card that has 1 GB free, and the crash arrives whenever someone opens another
browser tab. The two values are therefore configured independently and computed against **measured
free VRAM**, not against 12 GB.

**Reversibility.** Easy — engine choice is one environment variable plus a compose profile.

---

## Decision 24: The serving-chain contract — per-call-point fallback arrays

**Question.** How is failover order expressed, and where does it live?

**Options considered.**
- **A — Hardcoded routing table in Python** (today's `TIER_ROUTING`): simple, type-checked; but
  changing the order needs a code edit and redeploy, and the running order is invisible from `.env`.
- **B — One global `SERVING_CHAIN`** (the reference project's model): whole policy in one line;
  but this system is **tiered** — one line cannot say "local for the cheap fan-out, frontier for the
  planner".
- **C — One ordered array PER CALL-POINT** — chosen.

**Decision.** **Option C.** Each tier gets its own ordered array. Entry form is `venue[:model]`,
tried left to right; a leg whose URL or key is missing is **skipped**, never a runtime 401.

```bash
CHAIN_CHEAP=local,groq:llama-3.1-8b-instant,openai:gpt-4o-mini
CHAIN_MID=local,groq:llama-3.3-70b-versatile,openai:gpt-4o
CHAIN_FRONTIER=openai:gpt-4o,anthropic:claude-opus-4-8,groq:llama-3.3-70b-versatile
SERVING_ENGINE=sglang
```

| Grammar | Meaning |
|---|---|
| `local` | the engine named by `SERVING_ENGINE` |
| `local-vllm` / `local-sglang` | that engine explicitly, regardless of `SERVING_ENGINE` |
| `groq` / `openai` / `anthropic` | hosted venue, tier's default model |
| `venue:model` | that venue, overriding the model for this call-point |

**Why a list and not priority numbers.** Numbers split identity from order into two places that can
disagree, and inserting a leg means renumbering the rest.

**Why the FRONTIER default has no `local` leg.** A single loaded 7–8B model serves *every* tier
identically — it cannot be three different models. Putting `local` first on FRONTIER therefore hands
**multi-city planning and the critic** to a 7B, which is exactly where itinerary quality is decided.
The shipped default keeps FRONTIER hosted; going fully local is a one-line edit
(`CHAIN_FRONTIER=local,openai:gpt-4o`) whose quality cost the eval gate (D19) will measure rather
than hide.

**Why hosted legs stay last, and why one is PAID.** `openai` is the leg that still answers when
everything free is down. It is also the tripwire: the moment it starts serving,
`tp_llm_calls{provider="openai"}` climbs and cost per itinerary stops reading ~$0 — which is how a
dead local engine is discovered long before a user reports slowness.

**Backward compatibility (load-bearing).** With **no `CHAIN_*` set**, the resolver returns today's
exact `TIER_ROUTING` order. An existing `.env` behaves byte-identically; this is what makes the
change safe to land on a working system.

**Trade-offs accepted.** Three variables instead of one; a parser and its tests to maintain; and a
chain naming an engine that is not running costs every request a connect timeout before failing over
(mitigated by the Makefile making engine + chain one decision, D25).

**Reversibility.** Easy — delete the `CHAIN_*` lines and the system reverts to the hardcoded table.

---

## Decision 25: GPU lifecycle — preflight, weights, profiles, and scale-to-zero

**Question.** How do the engines get started, kept fed with weights, and prevented from costing money?

**Decision — four mechanisms.**

**1. Memory preflight, mandatory.** Before any engine starts, compare measured **free** VRAM against
the model's weight size plus a KV-cache floor, and refuse with a sentence that names the fix rather
than letting CUDA emit `out of memory` ten minutes into a load. Overridable with `SKIP_MEM_CHECK=1`.
On this machine — 1 GB free — the preflight is the difference between a clear message and a
mystifying wedge.

**2. Engine and chain are ONE decision.** A `make` variable selects the compose profile *and* exports
the chain together. Starting vLLM while the chain names `local-sglang` is the commonest way to
believe you are running a self-hosted engine while a hosted one quietly answers and bills every
request. Selecting one engine also stops the other, enforcing D23's "one at a time".

**3. Weights are cached and never wiped casually.** Model weights are immutable published artifacts,
not application state, so they survive the destructive `downv` and are removed only by an explicit
`clean-models`. `huggingface_hub` does **not resume across process restarts**, so an interrupted pull
restarts from byte zero — the download must be one uninterrupted run, and an unauthenticated Hub pull
is throttled, which is why `HF_TOKEN` is strongly recommended (and *required* for the gated Llama).

**4. On EKS: a GPU node group that scales to zero.** With taints + tolerations, `nvidia.com/gpu`
resource requests, the NVIDIA device-plugin DaemonSet, a GPU-optimized AMI, and `min=0`.

**⚠️ Phase-1 NFR amendment (explicit, not buried).** The original cost target was **≤ $50/month idle**.
A GPU node group breaks that by an order of magnitude:

| Instance | GPU | On-demand | Always-on / month |
|---|---|---|---|
| g4dn.xlarge | T4 16 GB | ~$0.53/hr | **~$380** |
| g5.xlarge | A10G 24 GB | ~$1.01/hr | **~$730** |

The NFR is therefore amended to: **"≤ $50/month idle, EXCLUDING the ephemeral GPU pool, which is
scaled to zero except during a demo or load test."** Architecting the GPU path is the portfolio
artifact; leaving it running is the bill.

**Reversibility.** Easy locally (stop a container); Moderate on EKS (a node group + Helm values).

---

# AMENDMENTS TO EXISTING DECISIONS

## D4 — LLM provider & model-tiering  *(amended)*

Unchanged: tiering exists, cheap-first, frontier on the quality-critical steps; the gateway remains
the anti-corruption layer over vendors.

**Amended:** the chain is no longer a hardcoded table but a **per-call-point array read from `.env`**
(D24), and it gains a **local leg ahead of the hosted ones**. `Provider` grows two members,
`local-vllm` and `local-sglang`.

**Why the local leg is nearly free to add:** vLLM and SGLang both serve an **OpenAI-compatible**
`/v1/chat/completions`. The existing `OpenAIProvider` is reused with a different `base_url` — no new
SDK, no new adapter logic, and the gateway's existing walk-the-chain-on-retryable-error loop already
does the failover.

## D12 — Inference serving  *(amended — the substantive one)*

**Was:** "Hosted provider APIs behind the gateway. vLLM self-host = documented scale-out path,
designed for but not built in v1."

**Now:** **Hybrid.** A self-hosted engine is the *preferred* leg where configured, with hosted APIs
as the fallback that underwrites the SLO. Hosted-only remains the correct configuration on any host
without a GPU — and is what an unset `CHAIN_*` still produces.

**Reasoning for the change.** The original rejection of self-hosting rested on "idle GPU breaks the
≤$50/mo budget", which is true of a *rented cloud* GPU and false of a card already sitting in the
developer's machine. Local inference turns the highest-volume, lowest-difficulty calls (the per-city
tool-argument and summarization fan-out) from metered tokens into electricity, while the
quality-critical planner and critic stay on a frontier model.

## D13 — Observability  *(amended)*

**No metric signature changes.** The venue rides the **existing** `provider` label on
`tp_llm_calls` — values simply gain `local-vllm` / `local-sglang`. Adding a new `engine` label would
have changed the series identity and broken existing Grafana panels and alerts; reusing `provider`
costs nothing and every dashboard keeps working.

**Added:**
- A **"who actually answered"** prover, because guessing is not verification. It reports the
  configured chain, the resolved chain, which engines are reachable, and which venue served a live
  probe query — asking each engine **separately**, since a shared model ID cannot distinguish them.
- The API response carries **`venue`**, not just `model_id`. A model name is actively misleading
  about who answered (Groq serves a model literally called `openai/gpt-oss-20b`).
- A **silent-failover alert**: hosted `tp_llm_calls` climbing while the chain says local-first means
  the local engine died.

## D19 — Evaluation  *(amended)*

Every eval record now carries the **venue that served it**, and the report groups by venue. Two
additions:
- **Local-vs-hosted quality delta** — not just latency. The whole premise of the local leg is that a
  7–8B is good enough *for the steps it serves*; that claim gets measured, not asserted.
- **Engine benchmarks** (TTFT, tokens/sec, p99) per engine — with D23's caveat that different weights
  make this a model+engine comparison.

## D20 — Cost controls  *(amended)*

Local tokens have **no marginal price**, and `cost_usd()` returns `0.0` for an unpriced model. Today
that path is flagged in code as *under-reporting spend* — for a local model it is **correct**, so
local model IDs are priced **explicitly at `(0.0, 0.0)`** with a comment stating the intent, rather
than falling through the unknown-model branch where a genuine pricing omission also lands.

**The consequence that matters:** with local serving, cost per itinerary collapses toward $0 — which
would let the `$0.30` gate pass **trivially** and mask a hosted-cost regression. The gate therefore
becomes **venue-aware**: a run served locally is not evidence that the hosted path is within budget.
GPU cost is *fixed* (hardware, or node-hours on EKS), not per-token, and is tracked separately.

## D21 — Failure-mode & degradation  *(amended)*

New legs bring new failure modes, each with defined behaviour:

| Failure | Detection | Behaviour |
|---|---|---|
| Engine container down | connection refused | skip the leg → next in chain |
| Engine **up but still loading weights** | health OK, completions fail | treated as retryable → next leg. *A container that exists is not an engine that serves.* |
| Engine OOM mid-run (D23's flag trap) | 500 / connection reset | circuit breaker opens → hosted leg |
| **Model-ID mismatch** (engine loaded X, API asks for Y) | 404 | leg fails → **silent** hosted failover — the exact trap D13's prover exists to catch |
| GPU absent | no `nvidia` runtime | local legs skipped entirely; chain is hosted-only |

A **per-leg circuit breaker** (`CIRCUIT_FAILURE_THRESHOLD`, `CIRCUIT_COOLDOWN_SECONDS`) stops the
chain hammering a leg that is reliably failing, since every dead-leg attempt costs a connect timeout
on the request path.

---

# Summary

| # | Decision | Pick | Prod-grade | Gap closed | Reversibility |
|---|---|---|---|---|---|
| **D23** | Local engine | vLLM+Qwen / SGLang+Llama, **one at a time** | Yes | ✅ self-hosted serving | Easy |
| **D24** | Chain contract | Per-call-point arrays in `.env`, `venue[:model]` | Yes | ✅ config-as-policy | Easy |
| **D25** | GPU lifecycle | Preflight + engine-is-chain + weight cache + scale-to-zero | Yes | ✅ GPU ops / cost eng | Easy → Moderate |
| D4 | Tiering | + local leg, chain from env | Yes | ✅ | Easy |
| D12 | Serving | hosted-only → **hybrid local-first** | Yes | ✅ inference serving | Easy |
| D13 | Observability | venue on existing `provider` label + failover prover | Yes | ✅ | Easy |
| D19 | Eval | venue-aware + local-vs-hosted quality delta | Yes | ✅ | Easy |
| D20 | Cost | local priced `(0,0)` explicitly; gate venue-aware | Yes | ✅ | Easy |
| D21 | Failure | 5 new engine failure modes + per-leg breaker | Yes | ◑ | Easy |

**Three properties this design holds onto:**

1. **Zero-change default.** No `CHAIN_*` set ⇒ today's exact behaviour. The working app cannot
   regress by installing this.
2. **No new adapter.** vLLM and SGLang are OpenAI-compatible; the existing provider is reused with a
   different `base_url`.
3. **Silent failover is treated as the primary hazard**, not an edge case — because the failure mode
   of self-hosting is not an outage, it is *paying for tokens while believing you are not*.

---

# SESSION AMENDMENTS — 2026-09-02

Recorded after implementation, because two things diverged from what was written
above and a decision log that does not match the code is worse than none.

## D24 — serving-chain contract *(amended: Option C -> Option B+C hybrid)*

**What changed.** D24 chose Option C (per-call-point arrays) and explicitly
rejected Option B (one global `SERVING_CHAIN`) on the grounds that a tiered
system cannot express itself in one line.

Implementation began against Option B — a single `SERVING_CHAIN`, matching the
reference project and the instruction given this session. That was a genuine
process failure on my part: I coded before re-reading the approved decision. It
was caught by reading D24 during a status review, not by anything automated.

**Resolved as a HYBRID, chosen deliberately:**

```bash
SERVING_CHAIN=local-sglang,groq,openai      # baseline for EVERY tier
CHAIN_FRONTIER=openai:gpt-4o                # overrides the baseline, this tier only
```

| Precedence | Source |
|---|---|
| 1 (narrowest) | `CHAIN_CHEAP` / `CHAIN_MID` / `CHAIN_FRONTIER` |
| 2 | `SERVING_CHAIN` |
| 3 (fallback) | the hardcoded `TIER_ROUTING` table — unchanged legacy behaviour |

An empty or whitespace override means *not set*, so clearing one falls back
rather than producing an empty chain.

**Why the hybrid rather than either alone.** One line is the whole policy most of
the time, and three variables to say it is noise. But D24's quality argument
stands and is the load-bearing part: a single loaded 7-8B model serves *every*
tier identically, so a global chain puts it on FRONTIER too — handing multi-city
planning and the critic to a 7B, which is exactly where itinerary quality is
decided. The override exists so that cannot happen by accident.

`test_the_d24_quality_guarantee_local_cheap_hosted_frontier` pins it: local on
CHEAP, hosted on FRONTIER, asserting the 7B was **not** called for FRONTIER.

**Grammar implemented:** `local`, `local-vllm`, `local-sglang`, `groq`, `openai`,
`anthropic`, and `venue:model` overrides. A bare `sglang` is rejected at startup
with an error naming the fix (`local-sglang`), because that mistake otherwise
surfaces as a container exiting non-zero behind "dependency failed to start".

**Backward compatibility (verified):** with no chain variables set, the resolver
returns the exact `TIER_ROUTING` order. The 128-test baseline passed unchanged
throughout.

## D13 — observability *(amended: the metrics now exist and are WRITTEN)*

Three series added, and wired at the one place that knows both the usage and the
venue that produced it:

| Metric | Labels | Why |
|---|---|---|
| `tp_llm_tokens_total` | `provider`, `direction` | tokens attributed to the venue that ACTUALLY served |
| `tp_llm_cost_usd_total` | `provider` | spend per venue — **recorded even when 0.0** |
| `tp_venue_circuit_state` | `provider` | 0 closed / 1 half-open / 2 open |

Two rules encoded, both from failures this codebase has already had:

* **0.0 is recorded, never skipped.** Guarding on `if cost_usd:` would mean a
  self-hosted venue never appears on a spend dashboard, making "free" and "not
  measured" indistinguishable — which is exactly when a silent failover hides.
* **Every leg's breaker state is published, not just the one that moved.** A gauge
  written only on change leaves untouched legs reporting a stale value forever.

`test_venue_metrics_are_actually_emitted` asserts the CALL happens. A metric that
is declared, exported and charted but never incremented scrapes cleanly as 0 —
indistinguishable from "nothing happened".

## NEW — venue on the response contract

`Itinerary.venues` and `TripItinerary.venues` carry the venues that produced the
result, accumulated across the composer, the critic (which may run on a different
tier and therefore a different venue), and — for trips — unioned across cities.

A model id cannot answer this: both local engines serve the same model id, and
Groq serves models named after other vendors. Without the field, "did the GPU
actually serve this, or did we quietly pay a hosted leg?" is answerable only from
logs, which is not verification.

It rides in the existing `result` JSON column, so **no database migration**.

**Verified end to end 2026-09-02** with a real run (Kyoto, 1 day, 5 POIs,
$0.0066, 1 critic correction): `venues: ['openai']`, surviving
`model_dump(mode="json")` into the API read-model.

## Circuit breaker — as built

Per-venue, in-process, CLOSED / OPEN / HALF_OPEN. Defaults 3 consecutive
transient failures, 30s cooldown, then exactly ONE probe.

* Only **transient** faults count. A 4xx is our bad request and fails identically
  everywhere, so opening a venue for it would punish the venue for our bug.
* HALF_OPEN admits one caller; letting the full request rate through the instant
  a cooldown expires is how a recovering engine gets knocked straight back over.
* In-process per worker is the accepted trade: a shared breaker would coordinate
  replicas better but puts a network call on every request's hot path.

## STATUS — what is verified, and what is not

Honesty about this matters more than the tick-count, and the distinction is
**written vs executed**.

| Verified by running it | |
|---|---|
| GPU passthrough | `nvidia-smi` inside a container |
| `engine_preflight.sh` | refused correctly, named the container holding the card |
| Chain resolution, breaker, per-tier split | 22 unit tests |
| Metrics emitted | live `/metrics` scrape shows all three families |
| App still works | `/health` 200, real plan run end to end |
| Backward compatibility | 128-test baseline unchanged |

| Written but NEVER EXECUTED | why |
|---|---|
| `docker-compose.gpu.yml` (`up`) | no engine container has ever been created |
| `make sglang-up` / `vllm-up` | dry-run only |
| `LocalEngineProvider` against a real engine | unit-tested with fakes only |
| `bench_venue.py` | **zero real TTFT/TPOT/tok-s numbers exist** |
| `engine_failed.sh` | syntax-checked only |
| `start_period: 900s`, `SGLANG_MEM_FRACTION=0.70` | inherited/guessed, not measured here |

**Root cause of the gap, stated plainly:** the GPU is held by another project on
this machine, and stopping it was out of scope. Every claim about local inference
above is therefore a claim about *code that should work*, not about an engine that
has served a request. Nothing here should be described as proven until
`make sglang-up` has run and `make bench-engine` has produced numbers.

## Still open

* `ensure_weights.sh` — not written. Concurrent `docker run` downloaders can
  corrupt one HF cache; the compose healthcheck does not cover that race.
* EKS GPU node group (Terraform/Helm, scale-to-zero) — not started.
* `.env` ships `SERVING_CHAIN=` empty, so local inference is **inert** until
  enabled. `make up-sglang` sets it per-invocation.
