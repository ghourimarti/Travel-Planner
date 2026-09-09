# Inspection — the full manual

The extended companion to **[INSPECTION.md](INSPECTION.md)**. That file is the battery you
work through; this one explains **every instrument from zero**, every metric, every panel,
and every trace shape.

Read Parts 0–4 once. After that Part 5 is the thing you keep open.

Every number here was measured on this deployment. Nothing is estimated. Where something is
unverified it is marked ⏳.

---

# Part 0 — Four instruments, four different questions

They do not overlap, and using the wrong one is the main reason this feels confusing.

| tool | port | the question it answers | scope |
|---|---|---|---|
| **Prometheus** | 3009 | *How often, how fast, how much — across ALL runs?* | aggregate numbers |
| **Grafana** | 3010 | the same numbers, drawn, with targets marked | aggregate, visual |
| **Jaeger** | 3007 | *Where did the time go on THIS run?* | one run, timing |
| **Langfuse** | 3013 | *What did the model SEE and SAY?* | one call, content |

> **A slow itinerary is a Jaeger problem. A bad itinerary is a Langfuse problem.**
>
> **Prometheus tells you that something changed. It can never tell you why.**

Prometheus is a counter store. It knows twelve runs were `degraded`; it knows nothing about
what they said. Jaeger keeps timings and structure. Langfuse keeps content — the prompt, the
completion, the token counts — which is why it is the only place a *quality* problem can be
diagnosed.

## 0.1 The asynchronous shape of this app

`POST /plan` returns **202 + `run_id`** and a **Celery worker** does the work. Three
consequences:

**Two metrics endpoints.**

| job | endpoint | carries |
|---|---|---|
| `tp-api` | `api:8000/metrics` (host 3004) | `tp_dispatch`, `tp_rate_limit_events` |
| `tp-worker` | `worker:3005/metrics` | **the other 14 metrics** |

**Two Jaeger services, but ONE trace.** Celery's OTel instrumentation propagates context
through the queue, so a plan is a single 13-span trace spanning both. See Part 3.6.

**Langfuse is an OTel exporter on the same TracerProvider** (`tracing.py::_add_langfuse_exporter`),
not a second SDK. It receives the same spans.

## 0.2 The readings that fool everyone

1. **Empty is not zero.** `rate()` of a counter that has not moved is `0`;
   `histogram_quantile` over all-zero buckets is **NaN**. On a quiet box, rate-based panels
   go blank. That is arithmetic, not a fault.
2. **`$0.00` is CORRECT when self-hosted.** Above zero means a hosted leg served.
3. **`venues: []` means no model ran.** Absence is the evidence of no spend.
4. **The corpus is 5 cities / 26 points.** Anything else measures coverage, not quality.

---

# Part 1 — Prometheus, all 16 metrics

## 1.0 Three metric types, and why it matters

A **counter** only ever increases (`tp_runs_total`). A raw counter is a meaningless
staircase, so you almost always wrap it in `rate()`, which converts it to a per-second speed.

A **gauge** goes up and down and is read directly (`tp_venue_circuit_state`).

A **histogram** stores counts per bucket, never individual values
(`tp_run_duration_seconds`). You read it with `histogram_quantile`, which **interpolates
inside** whichever bucket the percentile falls into. Its precision is bounded by the bucket
edges, so with few samples it snaps to them. **Treat any percentile built on under ~20
samples as noise.**

Counter names omit `_total`; `prometheus_client` appends it on exposition. So the code says
`tp_runs` and you query `tp_runs_total`.

## 1.1 Outcome and quality

### `tp_runs_total{status}` — *worker*
**What** one increment per finished run, labelled by terminal status.
**Tells you** throughput and failure rate.
**Why** it is the coarsest health signal, and deliberately coarse: it says nothing about
whether the itinerary was any good.
```promql
sum(tp_runs_total) by (status)                    # totals since restart
sum(rate(tp_runs_total[5m])) by (status)          # per-second, recent
```
**Bad value** a rising `failed` share. **Gotcha** a run that honestly declines is
`succeeded` — declining correctly is success. Quality lives in `tp_itinerary_outcome`.

### `tp_itinerary_outcome_total{kind}` — *worker*
**What** `grounded` · `degraded` · `not_found`.
**Tells you** what the user actually got.
**Why** `succeeded/failed` is too coarse: an honest "no POIs here" and a fully grounded
itinerary are **both** `succeeded`. Collapsing them is how silent quality loss stays silent.
```promql
sum(rate(tp_itinerary_outcome_total[5m])) by (kind)
```
**Bad value** `degraded` rising while errors stay flat — that is quality dropping with every
other dashboard green.
- `grounded` — built from retrieved POIs
- `degraded` — the city geocoded but nothing usable came back
- `not_found` — geocoding failed and we said so

### `tp_retrieval_results` *(histogram, no labels)* — *worker*
**What** POIs returned per retrieval.
**Tells you** how much grounding material each plan actually had.
**Why** `tp_itinerary_outcome` records *that* a run was degraded; this quantifies *how far*.
```promql
histogram_quantile(0.50, sum(rate(tp_retrieval_results_bucket[5m])) by (le))
```
**Bad value** p50 falling toward 0 means the corpus or Overpass is failing, and the
itineraries above it rest on far less evidence than they appear to.

### `tp_critic_revisions_total` *(no labels)* — *worker*
**What** corrective re-composes the critic triggered.
**Why** the critic is the safety net over a small local model.
**Gotcha** **zero forever is suspicious, not reassuring.** Check
`tp_stage_duration_seconds_count{stage="critic"}` is rising: that proves the critic *ran*.
A critic that never runs and a critic that never finds anything look identical here.

## 1.2 Latency

### `tp_run_duration_seconds` *(histogram)* — *worker*
**What** wall-clock seconds for a whole run.
**Why** the NFR is stated on this: **p50 < 20s · p95 < 45s · p99 < 75s**.
```promql
histogram_quantile(0.95, sum(rate(tp_run_duration_seconds_bucket[5m])) by (le))
```
**Gotcha** it **mixes venues**. A local engine and Groq differ by an order of magnitude, so
this number moves when the *chain shifts*, not when performance changes — and it can never
name the slow leg. That is what the next metric is for.

### `tp_venue_latency_seconds{provider}` *(histogram)* — *worker*
**What** seconds per **LLM call**, attributed to the venue that served it.
**Tells you** which leg is slow.
**Why** run duration averages over whichever venue answered. Measured here: `local-sglang`
TTFT p50 **50 ms**, `local-vllm` **33 ms**, `groq` **351 ms** — invisible in run duration.
```promql
histogram_quantile(0.95, sum(rate(tp_venue_latency_seconds_bucket{provider="groq"}[5m])) by (le))
```

### `tp_stage_duration_seconds{stage}` *(histogram)* — *worker*
**What** per-stage seconds: `geocode` · `gather` · `compose` · `critic`.
**Why** **this is the metric that tells you what to optimise.**
Measured on one real run: geocode **2.3 ms** · gather **1194.5 ms** · compose **1985.7 ms**
· critic **339.5 ms**.
```promql
histogram_quantile(0.95, sum(rate(tp_stage_duration_seconds_bucket[5m])) by (le, stage))
```
**Gotcha** recorded in a `finally`, so a stage that **raises** still reports how long it
burned. Timing only the happy path makes a slow failure look instantaneous.

## 1.3 Cost — the tripwire

### `tp_llm_cost_usd_total{provider}` — *worker*
**What** cumulative USD per venue.
**Why** **the `provider` label is what separates free from billed.** A local venue records
`0`; a hosted one records real money.
```promql
sum(tp_llm_cost_usd_total) by (provider)
```
**Gotcha** `0` is **recorded, never skipped**. Absent and zero are different facts on a spend
dashboard: absent means nothing served, zero means something served for free.

### `tp_run_cost_usd` *(histogram)* — *worker*
**What** cost per itinerary, against the **$0.30 cap**.
**Why** makes the per-itinerary budget a dashboard rather than a spreadsheet.

### `tp_llm_tokens_total{provider,direction}` — *worker*
**What** tokens, split `input`/`output`, per venue.
**Why** output tokens dominate cost on hosted venues and dominate *latency* on local ones.
```promql
sum(rate(tp_llm_tokens_total[5m])) by (provider, direction)
```

### `tp_llm_calls_total{tier,provider}` — *worker*
**What** successful completions by tier and venue.
**Why** the `tier` label shows the routing working: `compose` runs on **MID**, `critic` on
**FRONTIER**, and the eval judge on **CHEAP**. Seeing FRONTIER traffic with no critic
revisions means the critic ran and approved.

### `tp_cache_events_total{tool,result}` — *worker*
**What** `tool` ∈ `geo` `wx` `pois` `route`; `result` ∈ `hit` `miss` `skipped` `error`.
**Why** `skipped` is the interesting one: it means the **Redis breaker is open** and lookups
are being bypassed without even trying. Counting those as misses would make an outage look
like a cold cache.
```promql
sum(rate(tp_cache_events_total{result="hit"}[5m]))
  / clamp_min(sum(rate(tp_cache_events_total{result=~"hit|miss"}[5m])), 0.0001)
```
**Gotcha** there is **no response cache**, so a cache hit here never means an LLM call was
avoided. See INSPECTION.md §0.3.

## 1.4 Health

### `tp_venue_circuit_state{provider}` *(GAUGE)* — *worker*
**What** **0 = closed (healthy) · 1 = half-open (one probe admitted) · 2 = OPEN (skipped)**.
**Why** a leg sitting at 2 is not being tried at all — a fallback you believe you have and
do not.
```promql
tp_venue_circuit_state
```

### `tp_errors_total{type}` — *worker*
**What** errors by **class**, never by message.
Types seen here: `llm_transient` (a leg failed and the chain fell through — normal during
failover) · `llm_timeout` · `llm_non_retryable` (**our** bad request, fails identically
everywhere, never the venue's fault) · `postgres_error` · `postgres_circuit_open` ·
`embedder_mismatch`.
**Why classes, not messages** a message label is unbounded cardinality and will eventually
take Prometheus down.

### `tp_rate_limit_events_total{scope,outcome}` — **API**
**What** `scope` ∈ `tenant_min` `tenant_day` `ip_min`; `outcome` ∈ `allowed` `refused`.
**Why** a bare 429 count cannot distinguish *one tenant hammering us* from *one IP minting
tenants*, and those need opposite responses.

### `tp_dispatch_total{endpoint,outcome}` — **API**
**What** `outcome` ∈ `queued` `rate_limited` `disabled`.
**Why** `disabled` is the kill switch or spend breaker refusing — visible **only** here,
because nothing reaches the worker.

---

# Part 2 — Grafana, all 37 panels

## 2.0 Four concepts first

**1. `stat` vs `timeseries`.** A `stat` reduces a query to one number (`lastNotNull`); a
`timeseries` plots it. Sections 0 and 1 are stats; 2–4 are timeseries.

**2. Thresholds are the colour.** `Run p50` turns orange at 20s and red at 45s because those
are the NFR values. **The colour is the verdict** — you are not meant to memorise targets.

**3. `rate(...[5m])` = per second, averaged over 5 minutes.** On an idle box, rate panels go
blank. Widen the time picker before concluding anything is broken.

**4. Counters reset on restart.** `rate()` handles it; cumulative panels restart from zero
and say so.

## 2.1 Section 0 — Is the service healthy right now? *(6 stats)*

| panel | reads | bad value means |
|---|---|---|
| **Run p50 (NFR < 20s)** | median whole-run time | the typical experience is slow |
| **Run p95 (NFR < 45s)** | slowest 5% | p95 ≫ p50 = a queue or a cold path, not uniform slowness |
| **Cost / itinerary p95 (cap $0.30)** | spend per plan | **$0.00 is CORRECT locally.** Above zero = a hosted leg served |
| **Runs / sec** | throughput | |
| **Failure rate** | non-succeeded ÷ all | empty reads `0 — no failed runs`, not "No data" |
| **Spend today (all venues)** | cumulative across venues | compare with `DAILY_SPEND_LIMIT_USD` |

## 2.2 Section 1 — Which venue is answering, and what does it cost? *(16 stats + 2 timeseries)*

Four blocks — `local-sglang`, `local-vllm`, `groq`, `openai` — each with **latency p50**,
**latency p95**, **calls/sec**, **spend**.

**Why per-venue at all:** combined into one histogram, "latency p95" is an average over
whichever venues happened to answer. It moves when the **chain shifts** rather than when
performance changes, and it can never name the slow leg.

**"not served since restart"** is the no-data text and means exactly that. For `groq` and
`openai` it is the genuinely useful statement **your fallbacks are untested** — run the
failover drill and they fill in.

Plus **Which venue served, over time** (the moment a paid leg starts climbing, a free one
died) and **Tokens/sec by venue and direction**.

## 2.3 Section 2 — Is the product refusing what it must? *(4 timeseries)*

| panel | what it proves |
|---|---|
| **Itinerary outcomes** | grounded / degraded / not_found. A rising `degraded` with flat errors **is** silent quality loss |
| **POIs returned per retrieval** | p50 and p95 of grounding material. Falling toward 0 = the corpus or Overpass is failing |
| **Rate limiting by scope** | which scope refused — `tenant_min` bounds burst, `tenant_day` is the budget, `ip_min` closes the cookie-rotation hole |
| **API dispatch outcomes** | `queued` accepted · `rate_limited` refused by quota · `disabled` refused by the kill switch or spend breaker |

## 2.4 Section 3 — Where does the time actually go? *(5 timeseries)*

| panel | how to read it |
|---|---|
| **Stage latency p95** | one line per stage. **The panel that tells you what to optimise.** Measured: compose ≈ 2.0s, gather ≈ 1.2s, critic ≈ 0.34s, geocode ≈ 2ms |
| **End-to-end percentiles vs NFR** | p50/p95/p99 on one axis. Mixes venues — read section 1 alongside |
| **Cache hit rate** | hits ÷ (hits+misses). `skipped` excluded on purpose: those never asked Redis |
| **Cache events by tool** | rising `skipped` = the Redis breaker is open |
| **Critic corrections** | zero forever is suspicious — cross-check the critic stage count |

## 2.5 Section 4 — Are the parts underneath still healthy? *(4 timeseries)*

| panel | how to read it |
|---|---|
| **Serving venue circuit breakers** | 0 closed · 1 half-open · 2 OPEN. A leg stuck at 2 is a fallback you do not have |
| **Errors by type** | `llm_transient` during failover is normal; `llm_non_retryable` is **our** bug |
| **Runs by status** | compare with *Itinerary outcomes* — a run can succeed while producing a degraded itinerary |
| **Cumulative spend by venue** | the line that matters is a paid venue climbing while a free one should be serving |

---

# Part 3 — Jaeger, from zero

## 3.1 What a trace actually is

When work happens, the code marks the start and end of each meaningful operation. Each
marked interval is a **span**: a name, a start time, a duration, a parent, and attributes.
All spans from one unit of work share a **trace ID**, and that collection is a **trace**.

That is the whole idea. Jaeger is not sampling your CPU — it is replaying intervals the code
explicitly recorded. **If something is not wrapped in a span it is invisible**, and that
invisibility is itself readable (3.5).

Open <http://localhost:3007>, choose a service, click Find Traces.

## 3.2 How to READ the waterfall

The picture is not a bar chart, and the two axes mean completely different things. A **real**
trace from this stack:

```
  |<--------------------------- 3724 ms total --------------------------->|
  POST /plan                        [=]                                       38.0 ms
    POST /plan http receive         [ ]                                        0.0 ms
    apply_async/…plan_task           [ ]                                       0.0 ms
    POST /plan http send             [ ]                                       0.0 ms
    run/…plan_task                   [==================================]   3685.8 ms
      agent.plan                       [===============================]    3555.4 ms
        agent.geocode                  [ ]                                     2.3 ms
        agent.gather                   [==========]                         1194.5 ms
        agent.compose                            [=================]        1985.7 ms
          llm.complete                           [=================]        1985.4 ms
        agent.critic                                              [===]      339.5 ms
          llm.complete                                            [===]      339.3 ms
```

**The HORIZONTAL axis is time.** A bar starts where that operation started, relative to the
root, and its width is how long it took. **Position tells you when; length tells you how
long.** `agent.compose` is the widest bar because it is the slowest step, and it sits after
`gather` because it runs after it.

**The VERTICAL axis is NOT time. It is NESTING.** Indentation means "this happened inside
that" — parent/child, i.e. causality. Spans at the same indent are siblings ordered by start
time, but the vertical *distance* between them means nothing.

> The commonest misreading: **a tall trace is not a slow trace.** Tall means many
> operations. **Wide** means slow.

**Sequential vs concurrent, read from the bars.** Bars end-to-end never overlap, so that work
is sequential — which is exactly this pipeline. If two bars **overlap horizontally** they ran
concurrently. In a single-city plan they never should, so an overlap is a finding.

## 3.3 The root span is SHORTER than its child — and that is correct

```
POST /plan        38.0 ms      <- the API returns 202 HERE
  run/…plan_task  3685.8 ms    <- the worker runs for another 3.6 SECONDS
```

In a synchronous app a child can never outlive its parent. Here the HTTP request finishes
while the task it queued keeps going. **If you read the root duration as "the plan took
38ms" you will conclude this app is 100× faster than it is.** Read
`run/tp_worker.tasks.plan_task` for the real figure.

## 3.4 Children do not sum to the parent

```
geocode 2.3 + gather 1194.5 + compose 1985.7 + critic 339.5 = 3522.0 ms
agent.plan                                                  = 3555.4 ms
unaccounted                                                 =   33.4 ms
```

That ~33ms is graph overhead — state handling, checkpointing, anything not explicitly
wrapped. **A small gap is healthy. A large gap is the interesting case**: real time is being
spent somewhere nobody instrumented, and the trace is telling you where to *add a span*, not
where the bug is.

## 3.5 The trace SHAPES — recognise these before reading any number

**Shape A — grounded plan: 13 spans, ~3.7s.** All four `agent.*` stages, and **`llm.complete`
× 2** (one under compose, one under critic).

**Shape B — declined plan: 11 spans.** Same stages, **`llm.complete` entirely ABSENT**.

> Measured: of 8 recent plan traces, 6 were 13-span and 2 were 11-span — and I had run
> exactly 2 declining plans (a nonsense city and an injection-shaped city name). The shapes
> match one-to-one.

**The absence of `llm.complete` is the Jaeger-side proof of `venues: []`.** No model was
called, so nothing was spent. If you ever see a *grounded* itinerary whose trace has no
`llm.complete`, text was produced with no model behind it.

**Shape C — a poll: 3 spans, `GET /runs/{run_id}`, API only.** These are numerous and will
swamp a `tp-api` search.

## 3.6 Which service to search — and why it matters

| search | returns |
|---|---|
| `tp-api` | plan traces **and** every `GET /runs/{id}` poll — the polls dominate |
| `tp-worker` | **only plan traces** — polls never reach the worker |

**Search `tp-worker` to find plans.** It filters the poll noise for free. Both give you the
whole trace; the trace spans both services because Celery propagates context through the
queue.

## 3.7 Spans in this app

| span | what it does | measured |
|---|---|---|
| `POST /plan` | HTTP request; ends at 202 | 38 ms |
| `apply_async/…plan_task` | enqueue onto Celery | ~0 ms |
| `run/…plan_task` | the worker executing the task | 3686 ms |
| `agent.plan` / `trip.plan` | the LangGraph run | 3555 ms |
| `agent.geocode` | city → lat/lon (cached) | **2.3 ms** |
| `agent.gather` | retrieval + POIs + weather | 1194 ms |
| `agent.compose` | build days + the LLM intro | 1986 ms |
| `llm.complete` | one gateway call, incl. failover | 1985 ms |
| `agent.critic` | review, possibly re-compose | 340 ms |

If `agent.geocode` ever dominates, the cache is cold or Nominatim is slow. If `agent.gather`
dominates, look at Qdrant or Overpass. If `agent.compose` dominates, that is **normal** —
it contains the LLM call.

---

# Part 4 — Langfuse

## 4.1 What it is

Jaeger answers *where did the time go*. Langfuse answers **what did the model SEE and SAY**.
Neither can answer the other's question, which is why both exist.

Here it is fed by an **OTel exporter on the same TracerProvider**, so it receives the same
spans — but it keeps the *content* that Jaeger deliberately does not.

## 4.2 Trace vs observation

| | what it is | here |
|---|---|---|
| **trace** | one end-to-end unit of work | one plan |
| **observation** | one step inside it, typed `GENERATION` / `SPAN` | each `llm.complete` |

A grounded plan produces **two generations** (compose + critic). A declined plan produces
**none** — and that absence is the same evidence as `venues: []`.

## 4.3 Reading it when an answer is bad

1. Open the trace for the bad itinerary.
2. How many POIs were retrieved? Zero on a `grounded` result would be a serious bug.
3. **Read the retrieved POIs. Are they about the right city and interests?**
   - Wrong or irrelevant → **retrieval** is at fault. Fix embedding, the corpus, or the query.
   - Correct but the itinerary is poor → **the model** is at fault. Fix the prompt or the venue.
4. Only after step 3 do you know which half of a RAG system to change. Guessing without it is
   how a week goes into prompt tuning when retrieval was returning the wrong city.

## 4.4 The structural-grounding caveat

In this app the model has **less influence than usual**. `_build_days()` is deterministic
code; the LLM writes only the intro paragraph, and that paragraph is **discarded and replaced
by a template** if it names a venue not in the retrieved list.

So a "bad answer" here is almost always a **retrieval** problem. The model cannot put a fake
restaurant in `items` — it never writes `items`.

---

# Part 5 — The battery, deepened

[INSPECTION.md](INSPECTION.md) gives the 18 queries with per-instrument expectations. This
part adds only what does not fit there: what to actually *open* in each tool.

| query | the one thing to open |
|---|---|
| Q1 grounded | Jaeger → `tp-worker` → confirm **13 spans** and compare `agent.compose` width against `agent.gather` |
| Q2 repeat | Prometheus → `tp_cache_events_total` hits rise **while** `tp_llm_calls_total` also rises. That pair is the proof there is no response cache |
| Q3 not-found | Jaeger → confirm **11 spans, no `llm.complete`** |
| Q4 injection | same 11-span shape. The payload never reached a prompt |
| Q5 structural grounding | Langfuse → read the completion, then check `items` does not contain what it invented |
| Q6 multi-city | Jaeger → `trip.plan` root with one `agent.plan` **per city** |
| Q7 critic | Prometheus → `stage="critic"` count rising even when `tp_critic_revisions_total` is flat |
| Q8–10 kill switch | Jaeger → **no worker span at all**; the task was never enqueued |
| Q11–13 rate limits | Grafana §2 → *Rate limiting by scope*, watch **which** line moves |
| Q14 failover | Grafana §1 → the `groq` block fills as `local-sglang` stops; §4 breaker goes to 2 |
| Q15 Redis down | Prometheus → `tp_cache_events_total{result="error"}` then `{result="skipped"}` |
| Q16 Postgres down | `tp_errors_total{type="postgres_error"}` → `postgres_circuit_open` |
| Q17 embedder | the stamp, read straight from Qdrant |
| Q18 SSE | the run page updating progressively |

---

# Part 6 — The failover drill

```bash
python scripts/inspect_stack_sglang.py    # chain local-sglang -> groq -> openai
python scripts/inspect_stack_vllm.py      # chain local-vllm   -> groq -> openai
```

## 6.1 How to take a leg out — only one method tests failover

| method | what it actually proves | restart needed |
|---|---|---|
| Remove it from `SERVING_CHAIN` | the chain config is honoured | yes |
| Blank its API key | unconfigured legs are skipped at boot | yes |
| **Blackhole its hostname** | **a real outage, and the failover after it** | no |

The first two make the leg **absent** — the gateway drops any leg with no URL or key before
the chain is built, so it never fails, it simply is not there. That tests configuration, not
resilience.

| leg | hostname to blackhole |
|---|---|
| `local-sglang` | `sglang` |
| `local-vllm` | `vllm` |
| `groq` | `api.groq.com` |
| `openai` | `api.openai.com` |

## 6.2 PROVE THE FAULT LANDED

The single most important rule here. A pooled HTTP connection consults DNS **only when
opening a new one**, so a request can ride an existing socket straight past `/etc/hosts` and
produce a confident PASS for a chain that was never touched.

The scripts therefore **wait for the pool to drain** and then **verify the hostname actually
resolves to 127.0.0.1 from inside the container**, aborting with *"this step proves nothing"*
if it does not.

> **An unverified fault injection turns a green result into a lie.**

## 6.3 Two more ways to accidentally prove nothing

**Tool caches.** Geocode and weather are cached, so a repeated city skips those lookups. The
scripts clear caches between steps and vary the city. (The *LLM* call is never cached — see
INSPECTION.md §0.3 — so failover itself is always exercised.)

**A declined run has no venue.** `venues: []` gives your failover assertion nothing to
compare. Use in-corpus cities: **tokyo, paris, kyoto, rome, barcelona**.

## 6.4 The ladder

| broken | expected |
|---|---|
| nothing | the local engine serves, cost `$0.00` |
| engine | **groq** serves, cost rises above zero |
| engine + groq | **openai** serves |
| all three | a clean **error** — never a fabricated itinerary |
| restored | the local engine reclaims traffic after the breaker cooldown |

**The last-but-one row is the assertion that matters most.** A planner with no model must
decline. If it ever returns a full itinerary with `venues: []`, something is generating text
with no model behind it and every other guarantee in this project is void.

**Recovery is half the drill.** A chain that fails over and never comes back has merely moved
the outage.

## 6.5 What this drill cannot prove

A DNS blackhole is a **connect** failure. It does not reproduce a venue that accepts the
connection and returns 500s, one that hangs past the timeout, or one that dies mid-stream.

A pass means **"the chain is wired correctly"**. It does not mean every failure mode is
handled.

---

# Part 7 — Executed, 2026-09-09

`make inspect ENGINE=sglang` — `PASS=59 · FAIL=0 · EXIT=0`.

```
ok   engine serves                    venues=['local-sglang'] cost=$0.0
ok   cost attribution                 ['local-sglang'] -> $0.00 (self-hosted, RECORDED)
ok   engine down -> groq              venues=['groq']   cost=$0.000772
ok   spend GREW when groq served      0.0 -> 0.000772 (+0.000772)
ok   engine + groq down -> openai     venues=['openai'] cost=$0.002197
ok   spend GREW when openai served    0.000772 -> 0.0029695 (+0.002197)
ok   all legs down -> clean failure   status=failed venues=[]
ok   local-sglang reclaims traffic after cooldown  |  recovered
ok   dashboard provisioned            37 panels
ok   every panel query executes       37 panels, 0 errors
ok   jaeger service tp-api / tp-worker present
ok   venue breakers closed            {'local-sglang':'0','groq':'0','openai':'0'}
     state restored: /etc/hosts cleaned (VERIFIED), kill switch cleared
```

## 7.1 · An unplanned cross-check that Part 1 could not have predicted

The cost reported to the caller and the delta written to the daily-spend breaker are
**independent code paths**. On every paid rung they now have to agree, and they do:

| Leg | cost to caller | delta to `spend:usd:*` |
|---|---|---|
| groq | `$0.000772` | `+0.000772` |
| openai | `$0.002197` | `+0.002197` |

Before this was asserted, a run could have billed one number while the budget breaker
counted another, and nothing would have noticed.

## 7.2 · What a VOID means here, and why it is not a failure

```
VOID  spend GREW on this run  |  ['local-sglang'] costs $0.00 — a free leg cannot
      move the key. Growth is asserted on the paid rungs of the ladder below.
```

On a local-first chain this happens on **every healthy run**: `$0.00` cannot grow. It is
reported under `PROVES NOTHING, by design (not failures)` and does **not** fail the run.
Every other void still does — redis unreachable, API silent, injection vanished.

> An exit code that is always red on a healthy system is the same disease as a green
> check that proves nothing, inverted: an exit code nobody reads.

## 7.3 · The drill needs the stack to itself

It blackholes DNS inside a live container. Any concurrent `make up` / `make down`
silently invalidates it — three runs died to exactly that. The failure is now diagnosed
rather than described:

```
VOID  engine down -> groq  |  sglang does not resolve to loopback — this step proves
      nothing. the worker was RECREATED mid-run (45460ef591b8 -> a1b2c3d4e5f6): a new
      container gets a fresh /etc/hosts, so the injection went with the old one.
```

The banner now prints `worker container at start: <id>` so the comparison is visible.

## 7.4 · Instruments that lied, and were fixed

| Symptom | Truth |
|---|---|
| `state restored: /etc/hosts cleaned` | it had cleaned **nothing** for two runs — `sed -i` cannot edit a bind-mounted `/etc/hosts` |
| `spend key updated by a run \| 0.0155998 -> 0.0155998` | green with a number that never moved |
| `FAIL … generation was NOT stopped` (HTTP 0) | nothing answered the door; the app was down |
| `FAIL spend GREW when groq served` | redis was unreadable — a **false accusation** against working code |
| `make inspect` exiting 2 on `PASS=59 FAIL=0` | structural voids were counted as failures |

Every one was found by RUNNING the drill, none by reading it.

