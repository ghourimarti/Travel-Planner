# Round 6 — The frontend contract and the edge

Rounds 1–5 tested the system from the **inside**, with `curl` and `psql`. This round tests it
the way a user meets it:

> **What does the browser actually receive, and what happens at the boundary between it and
> everything you have been inspecting?**

Every query is new. This is the round where the four monitoring tools are **least** useful and
the browser's own devtools are most useful — and knowing *which* instrument answers *which*
question is the point of the whole series.

Read [INSPECT.md §0–§2](INSPECT.md) first.

```bash
make cache-clear && make kill-status      # must print ENABLED + floor true
```

**Ports for this round:** web **3006**, API **3004**, Jaeger **3007**, Grafana **3010**,
Flower **3011**, Langfuse **3013**.

---

## The architecture this round tests: the BFF

The browser **never** calls FastAPI. It calls same-origin Next.js route handlers, which call
FastAPI server-side. From `next.config.mjs`:

> *"The browser never calls the FastAPI backend directly — it goes through our BFF route
> handlers (so Auth0 access tokens stay server-side)."*

```
browser ──▶ localhost:3006/api/plan   (Next route handler, server)
                    └──▶ api:8000/plan  + Authorization: Bearer …
```

**Three things this buys, each testable below:** the access token never reaches JavaScript
(R6-Q1); `EventSource` gets authentication it cannot otherwise carry (R6-Q2); and the backend
needs no CORS policy at all (R6-Q7).

---

## R6-Q1 · Prove the token never reaches the browser

**RUN** — in the browser at <http://localhost:3006/app>, open devtools **Network**, then plan
a trip to **Vienna** for 2 days, interests *coffee houses*.

**EXPECT** in the Network tab:

| request | origin | Authorization header? |
|---|---|---|
| `POST /api/plan` | `localhost:3006` | ❌ **none** |
| `GET /api/runs/{id}/stream` | `localhost:3006` | ❌ **none** |
| anything to `:3004` | — | **there is none** |

**Then check from the console:**
```js
document.cookie          // session cookie only — httpOnly ones won't even show
localStorage             // no token
```

**The mechanism** — `lib/api.ts` opens with `import "server-only"`, which makes the build
**fail** if that module is ever imported into a client component. The token path is enforced by
the compiler, not by discipline.

#### 📊 Prometheus
```promql
sum by (endpoint, outcome) (rate(tp_dispatch_total[5m]))
```
`tp_dispatch_total{endpoint="plan",outcome="queued"}` moves — **the request did arrive**, just
not from the browser.

#### 📈 Grafana
§2 *API dispatch outcomes* — identical to a `curl` run. **The backend cannot tell a browser
from a script, and should not be able to.**

#### 🔍 Jaeger
One `POST /plan` span on `tp-api`. ⚠️ **The BFF hop is invisible** — Next.js is not
instrumented, so the trace begins at FastAPI. **A slow BFF would look like a fast backend and
a slow user.** The gap between what devtools shows (`POST /api/plan` total) and what Jaeger
shows (`POST /plan` duration) is that uninstrumented hop, and subtracting them is the only way
to measure it.

#### 💰 Langfuse
Two generations, indistinguishable from a `curl` run.

#### 🌐 Browser devtools — **the only instrument that can answer this question**
No other tool in the stack can see what the browser did or did not send.

**PASS** = no `Authorization` header anywhere in the Network tab, no token in storage.

**RESTORE** none.

---

## R6-Q2 · Watch the stream — four nodes, and one honest lie

**RUN** — plan **Cusco**, 3 days, interests *ruins, markets*. On the run page, keep devtools
open on the `stream` request and watch the **EventStream** tab.

**EXPECT** a sequence of `data:` frames:
```
{"type":"status","status":"queued"}
{"type":"node","node":"geocode"}
{"type":"node","node":"gather"}
{"type":"node","node":"compose"}
{"type":"node","node":"critic"}
{"type":"done"}
```

**The four nodes are `AGENT_NODES = ["geocode","gather","compose","critic"]`** — the same four
stages as the `tp_stage_duration_seconds` metric and the same four spans in Jaeger. **One
vocabulary across the UI, the metrics and the traces**, which is why a user's screenshot can
be matched to a Grafana panel.

**Now the honest lie.** `use-run-stream.ts:advance()`:

```ts
if (completed in next) next[completed] = "done";
const following = AGENT_NODES[idx + 1];
if (following && next[following] === "pending") next[following] = "running";
```

A `node` event says a stage **finished**. The UI marks it done **and marks the next one
running** — *before any event says it started.* The backend never claimed that.

> **Is that wrong?** No — and it is worth being able to say why. The stages are strictly
> sequential, so "geocode finished" **entails** "gather is next". The alternative is a UI that
> shows nothing happening between two events several seconds apart, which reads as *frozen*.
> **The UI is inferring, and its inference is sound because the graph is linear.** Add a
> conditional branch to the graph and this optimism becomes a bug — that is the trade, stated
> plainly.

#### 📊 Prometheus
```promql
histogram_quantile(0.95, sum(rate(tp_stage_duration_seconds_bucket[5m])) by (le, stage))
```
**The same four stage names.** The gap the UI fills with an optimistic "running" is exactly the
duration this panel measures.

#### 📈 Grafana
§3 *Stage latency p95* — one line per node. **Watch the UI and this panel together: the
stage the spinner sits on longest is the tallest line here.**

#### 🔍 Jaeger
Four child spans under `run/tp_worker.tasks.plan_task`, same names, same order. **Jaeger is
ground truth for when a stage actually started**; the UI is an approximation of it.

#### 💰 Langfuse
`llm.complete` sits inside `compose` and `critic` — the two nodes the user waits longest on.

#### 🌐 Browser devtools
The **EventStream** tab is the only place to see the frames as sent. ⚠️ SSE frames are
separated by a **blank line**; a bare `data:` with no payload is a keep-alive, not an event.

**PASS** = four node events in order, ending in `done`, with the UI one step ahead.

**RESTORE** none.

---

## R6-Q3 · Reload mid-run, and reload after — two different code paths

**RUN**
```bash
# start one, then IMMEDIATELY open its page and hard-reload twice
curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
  -d '{"city":"Hanoi","interests":["street food"],"days":2}'
```
Open `http://localhost:3006/app/runs/<run_id>`, reload while it is still running, then reload
again after it finishes.

**EXPECT** — the run continues and completes in **both** cases, with no duplicate work.

**Two distinct paths in `stream_run`:**

```python
yield _sse({"type": "status", "status": record.status})
if record.status in _TERMINAL:      # already finished — send result, don't wait for the bus
    yield _sse({"type": record.status, "result": record.result, "error": record.error})
    return
async for event in subscribe(run_id): ...
```

- **Mid-run reload** → status frame, then live events from the pub/sub bus.
- **Post-run reload** → status frame, then the stored result **immediately**, and the stream
  closes. **No waiting on a bus that will never publish again** — which is what a naive
  implementation does, leaving the page spinning forever on a finished run.

**And the client closes the loop:** `finalize()` closes the `EventSource` and does a one-shot
`GET /api/runs/{id}` for the full record. **The stream carries progress; the fetch carries the
itinerary.** Two channels, each doing what it is good at.

#### 📊 Prometheus
```promql
sum(rate(tp_runs_total[5m]))
```
**Must not move on a reload.** A reload that re-dispatched would show a second run — the bug
this query rules out.

#### 📈 Grafana
§0 *Runs/sec* — one bump per plan, regardless of reloads.

#### 🔍 Jaeger
**One** `run/…plan_task` trace, several `GET /runs/{id}/stream` spans — one per reload.
**Reconnects are cheap and visible; re-runs would be neither.**

#### 💰 Langfuse
Generation count unchanged by reloads. **If reloading a page doubled your model spend you
would find it here first** — and this is the check that proves it does not.

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select id, status from runs where request->>'city'='Hanoi' order by created_at desc limit 3"
```
**One row.**

**PASS** = one run, one trace, one bill, any number of reloads.

**RESTORE** none.

---

## R6-Q4 · The three refusals, and the three different sentences

The UI distinguishes three failure modes by status code (`plan-form.tsx:106-115`). **Most
apps show one generic error for all three.** Test each.

### (a) 503 — planning disabled
```bash
make kill-on         # switch ON = planning DISABLED (the naming is the Makefile's)
```
Plan **Split**, 2 days, in the UI.

**EXPECT** exactly: *"Planning is temporarily disabled. Please try again shortly."*

#### 📊 Prometheus
```promql
sum by (outcome) (rate(tp_dispatch_total{endpoint="plan"}[5m]))
```
`outcome="disabled"` increments. **No run row is written** — so §0 *Runs/sec* stays flat.

#### 📈 Grafana
§2 *API dispatch outcomes* is **the only panel where a refused request appears at all.**
This is the concrete reason that panel exists.

#### 🔍 Jaeger
A `POST /plan` span with **503**, and **no `tp-worker` trace after it** — a refusal shaped
exactly like R4-Q4's orphan, but *intentional and recorded*.

#### 💰 Langfuse
Nothing. No model, no cost — the switch worked.

**RESTORE**
```bash
make kill-off && make kill-status     # MUST print ENABLED before you continue
```
⚠️ **This is the restore step the old inspection docs left ambiguous.** `kill-on` disables,
`kill-off` re-enables, and **nothing else in this round works until `kill-status` prints
ENABLED.** Every subsequent query would otherwise report a 503 and you would debug the wrong
thing.

### (b) 429 — rate limited
```bash
for i in $(seq 1 70); do
  curl -s -o /dev/null -w "%{http_code} " -X POST localhost:3004/plan \
    -H 'content-type: application/json' \
    -d '{"city":"Tallinn","interests":["old town"],"days":1}'
done; echo
```
**EXPECT** `202` up to the per-minute limit, then `429`. In the UI the message is
*"You've hit the rate limit. Please wait a moment."*

#### 📊 Prometheus
```promql
sum by (scope, outcome) (rate(tp_rate_limit_events_total[5m]))
```
**Three scopes** — `tenant_min`, `tenant_day`, `ip_min` — and **the strictest wins**
(`main.py:89`): *"a per-tenant limit alone is defeated by rotating the session cookie."*
**Watch which scope refused.** If `ip_min` fires, one machine is the problem; if `tenant_min`
fires, one account is.

#### 📈 Grafana
§2 *Rate limiting by scope* — the refusals appear here **and** in *API dispatch outcomes* as
`rate_limited`. **Two panels, one event, deliberately: one tells you who, the other tells you
how many.**

#### 🔍 Jaeger
429 spans, very short. **Compare their duration to an accepted dispatch** — measured refuse
**5.27 ms** vs accept **244 ms**. A refusal costs ~2% of an acceptance, which is the entire
point of refusing early.

#### 💰 Langfuse
Nothing for the refused ones — **rate limiting is a cost control before it is a fairness
control.**

**RESTORE** wait 60 s for the window to roll.

### (c) 502 — the backend is gone
```bash
docker stop p3-ai-travel-planner-api-1
```
Plan anything in the UI.

**EXPECT** the BFF's own fallback — `{"error": "failed to dispatch plan"}` with **502**,
rendered as that text. **Not a stack trace, not a blank page.**

> **Read the three together.** 503 = *we turned it off*. 429 = *you asked too much*. 502 =
> *we are broken*. Three different truths deserve three different sentences, and a user who
> reads "temporarily disabled" and comes back in five minutes has been told something useful.

#### 📊 Prometheus
⚠️ **Nothing.** The API is down, so `/metrics` is down. **Prometheus cannot report on its own
absence** — check the *Targets* page (<http://localhost:3009/targets>) for `tp-api` DOWN.

#### 📈 Grafana
All API panels go blank. ⚠️ **Blank renders identically to zero traffic** — the trap named in
INSPECT.md §5.2, met live.

#### 🔍 Jaeger
No new spans. The worker's are unaffected — **it is still draining its queue**, which is the
asynchronous architecture doing its job while the front door is shut.

**RESTORE**
```bash
docker start p3-ai-travel-planner-api-1
curl -s --retry 20 --retry-delay 3 --retry-all-errors localhost:3004/health
```
⚠️ **Counters reset.** §1 goes back to *"not served since restart"*.

---

## R6-Q5 · Kill the stream, keep the answer

**PRECONDITION** none.

**RUN** — start a plan for **Valparaíso**, 2 days, and while the run page is showing progress:
```bash
docker restart p3-ai-travel-planner-api-1
```

**EXPECT** — progress stops, then the finished itinerary **still appears**.

**Why:** `source.onerror` does not retry. It calls `finalize()`, which closes the stream and
does a one-shot `GET /api/runs/{id}`.

```ts
// The BFF emits one finite stream; on transport error stop retrying and
// fall back to a one-shot fetch of the final record.
```

> **This is the single most important line of frontend code in the app.** `EventSource`
> auto-reconnects by default, and a default reconnect against a *finite* stream produces an
> infinite loop of requests that each return the same terminal frame. Opting out and falling
> back to a fetch is the correct handling of a stream that is allowed to end.

**And the BFF never propagates a stream failure as an HTTP error** — look at the catch in
`api/runs/[id]/stream/route.ts`: it returns **200** with an SSE `error` frame, because a
non-200 on an `EventSource` triggers exactly the retry storm above.

#### 📊 Prometheus
The run completes: `tp_runs_total{status="succeeded"}` increments **even though no browser was
listening.** **The work is not tied to the viewer** — that is what the 202 + `run_id` contract
buys.

#### 📈 Grafana
§0 *Runs/sec* shows the completion normally.

#### 🔍 Jaeger
The `stream` span ends early with an error; the `plan_task` span completes normally.
**Two independent lifetimes, visible side by side** — the clearest picture of async in the
whole series.

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select status, result is not null as has_itinerary from runs order by created_at desc limit 1"
```
`succeeded | t` — **the answer was stored whether or not anyone was watching.**

**PASS** = the itinerary renders after the stream died.

**RESTORE** already restarted; wait for `/health`.

---

## R6-Q6 · When the answer is "no" — does the UI stay honest?

**RUN** in the UI — a place the corpus cannot serve: city **Atlantis**, interests
*underwater ruins*, 2 days.

**EXPECT** — **not** an invented itinerary. A `not_found` outcome, and any warnings rendered
(`itinerary-view.tsx:202`).

**The full chain for one refusal:**

| layer | what it does |
|---|---|
| retrieval | returns nothing usable |
| composer | structural grounding means it **cannot** name a venue it was not given |
| record | `venues: []` — **evidence no model invented anything** |
| metric | `tp_itinerary_outcome_total{kind="not_found"}` |
| UI | shows the honest answer plus warnings |

#### 📊 Prometheus
```promql
sum by (kind) (rate(tp_itinerary_outcome_total[15m]))
```
`kind="not_found"` increments. **The outcome mix is a quality signal, not traffic** — a rising
`not_found` share means the corpus is being asked what it cannot answer, which is a **content**
problem, not a bug.

#### 📈 Grafana
§2 *Itinerary outcomes* and, next to it, *POIs returned per retrieval*.
⚠️ **Retrieval near zero while outcomes stay `grounded` is the wrong-anchor signature** — the
defect that produced a confident itinerary for the *wrong Nara*. **`not_found` here is the
system being correct; `grounded` with zero POIs is the system being wrong.** Same panel pair
tells them apart.

#### 🔍 Jaeger
**11 spans, not 13** — `llm.complete` is **absent**. **The trace shape alone tells you no
model was called**, before you read a single field.

#### 💰 Langfuse
**No new generation.** ⚠️ **A refusal that still shows a generation means the model was asked
and the refusal came from the model** — an entirely different (and more expensive, less
reliable) design. **The absence here is the proof of structural grounding.**

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select result->>'kind' kind, jsonb_array_length(coalesce(result->'venues','[]')) venues,
         result->'warnings' warnings from runs order by created_at desc limit 1"
```
**`venues = 0` is the evidence.** Structural grounding protects against fabrication — but as
the wrong-anchor case showed, **not against a wrong anchor**. Both facts are true, and this
query shows only the first.

**PASS** = honest refusal, 11 spans, no Langfuse generation, `venues = 0`.

**RESTORE** none.

---

## R6-Q7 · The edge — what the internet can reach

**RUN**
```bash
# 1. can a hostile page call the API from a browser?
curl -s -D - -o /dev/null -H "Origin: http://evil.example" localhost:3004/health \
  | grep -i "access-control\|HTTP/"

# 2. what does the web app send back?
curl -s -D - -o /dev/null localhost:3006/ | grep -iE "content-security|strict-transport|x-frame|x-content-type|x-powered"
```

**MEASURED — result 1:** `HTTP/1.1 200 OK` and **no `Access-Control-*` header at all.**

> **That is the correct outcome, and better than a permissive allowlist.** FastAPI mounts **no
> CORS middleware**, so no origin is ever granted. A browser therefore **cannot** read a
> cross-origin response from the API — the BFF design is enforced by the browser itself, not
> merely by convention. And because the browser is meant to talk only to `localhost:3006`, no
> legitimate request is lost. **The absence of a CORS policy *is* the CORS policy.**

**MEASURED — result 2:** only `X-Powered-By: Next.js`.

| header | present? | what it would prevent |
|---|---|---|
| `Content-Security-Policy` | ❌ | XSS via injected script |
| `Strict-Transport-Security` | ❌ | protocol downgrade |
| `X-Frame-Options` / `frame-ancestors` | ❌ | clickjacking |
| `X-Content-Type-Options: nosniff` | ❌ | MIME confusion |
| `X-Powered-By` | ⚠️ **present** | it advertises the framework — should be removed |

> **The finding.** `next.config.mjs` sets `reactStrictMode`, `output: "standalone"` and one env
> var. **There is no `headers()` block.** For a local dev stack behind `localhost` that is
> unremarkable; **as the last step before a public deployment it is the gap to close**, and it
> closes in about ten lines of config. This round records it as *known and unclosed* rather
> than letting a green dashboard imply otherwise.

**One thing that IS right:** `Cache-Control: private, no-cache, no-store, must-revalidate` on
the app shell. **A cached itinerary page served to the wrong user is the worst bug in this
document, and it cannot happen.**

#### 📊 Prometheus / 📈 Grafana / 🔍 Jaeger / 💰 Langfuse
⚠️ **All four are silent on every question in this section.** Headers, CORS and cache
directives are properties of a *response shape*, not of an event, and none of these tools
inspect response headers. **`curl -D -` is the instrument.**

**PASS** = you can state which headers are missing and why the missing CORS policy is the
right one.

**RESTORE** none.

---

## What this round proves

| claim | evidence |
|---|---|
| The token never reaches the browser | R6-Q1 — no `Authorization`, enforced by `server-only` |
| UI, metrics and traces share one vocabulary | R6-Q2 — the same four node names in all three |
| The UI runs one step ahead, defensibly | R6-Q2 — `advance()`, sound while the graph is linear |
| A finished run replays instantly | R6-Q3 — the `_TERMINAL` short-circuit |
| Reloads never re-run or re-bill | R6-Q3 — one row, one trace, one generation pair |
| Three refusals, three sentences | R6-Q4 — 503 / 429 / 502 |
| A dead stream still delivers the answer | R6-Q5 — `onerror` → one-shot fetch |
| The UI does not invent an itinerary | R6-Q6 — 11 spans, no generation, `venues = 0` |
| No CORS policy is the right policy | R6-Q7 — no origin is ever granted |
| 🟠 **No security headers** | R6-Q7 — no CSP, HSTS, X-Frame-Options, nosniff |

**The theme across six rounds.** Round 4 found a run that never started. Round 5 found data
that never left. Round 6 finds headers that were never sent. **All three are absences** — and
absence is precisely what Prometheus, Grafana, Jaeger and Langfuse are constitutionally unable
to show you, because every one of them records **things that happened**.

That is not a criticism of the four tools; it is the boundary of what they are for. **The
complete picture needs state (the database), shape (the response), and events (the four
tools) — and this series is the argument for checking all three.**

```bash
make verify-all      # state and shape, not just events
```

---

## The six rounds

| round | question | headline finding |
|---|---|---|
| [INSPECT.md](INSPECT.md) | Does it work, end to end? | the full instrument manual |
| [INSPECT_2.md](INSPECT_2.md) | Retrieval and the corpus boundary | grounding protects against fabrication, not a wrong anchor |
| [INSPECT_3.md](INSPECT_3.md) | Cost, tiers and venue economics | three independent cost layers, floor outranks switch |
| [INSPECT_4.md](INSPECT_4.md) | Concurrency, the queue, crash recovery | 🔴 orphaned runs, invisible to all four tools |
| [INSPECT_5.md](INSPECT_5.md) | Data lifecycle, tenancy, privacy | 🔴 deletion misses the checkpoint tables |
| **INSPECT_6.md** | The frontend contract and the edge | 🟠 no security headers at the edge |
