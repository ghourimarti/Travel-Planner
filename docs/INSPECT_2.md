# Round 2 — Retrieval, the corpus boundary, and grounding quality

**Round 1 ([INSPECT.md](INSPECT.md)) asked "does each component work".** This round asks a
narrower and harder question:

> **Is the RAG actually retrieving anything, and where does it honestly run out?**

Every query here is new. None appear in Round 1. The theme is the **retrieval layer** —
the corpus, the funnel, the thresholds, and the three different ways this app can return
"nothing useful", which cost different amounts and mean different things.

Read [INSPECT.md §0–§2](INSPECT.md) once for the instrument setup, the state ledger and the
`tp-api` / `tp-worker` split. This document assumes it.

```bash
make cache-clear && make kill-status      # must print ENABLED + floor true
```

---

## The facts this round is built on

Measured on this deployment:

```
corpus            26 POIs across 5 cities
RETRIEVAL_TOP_K   20      fetch this many candidates
RERANK_TOP_K      8       keep this many after reranking
embedder          text-embedding-3-large, dim 1024
indexed_vectors   0       26 points is below Qdrant's HNSW threshold -> brute force
```

**Everything else in the world degrades honestly.** That is *coverage*, not a retrieval
fault, and confusing the two is the single most common way to conclude this RAG is broken
when it is telling the truth.

### The three ways this app returns "nothing useful"

This distinction is the spine of the whole round. They look similar in the UI and cost
wildly different amounts:

| outcome | what happened | model called? | cost | `venues` |
|---|---|---|---|---|
| **not_found** | geocoding failed — the place does not exist | **NO** | $0 | `[]` |
| **degraded** | geocoded fine, but no POIs there | **YES** — it writes an intro | paid | `['local-sglang']` |
| **grounded, thin** | geocoded, few POIs, an itinerary anyway | **YES** | paid | `['local-sglang']` |

> **`venues: []` separates the free one from the paid ones.** Nothing else does.

---

## R2-Q1 · The corpus boundary, both sides of it

**PRECONDITION** clean. **RUN** — the same interest, one city inside the corpus and one
outside, back to back:

```bash
for C in Kyoto Reykjavik; do
  curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
    -d "{\"city\":\"$C\",\"interests\":[\"temples\"],\"days\":1}"
done
```

**EXPECT** Kyoto grounded with real POIs. Reykjavik geocodes **successfully** — it is a real
city — and then finds nothing in a 5-city corpus. **That is the interesting case.**

#### 📊 Prometheus
```promql
sum by (kind) (tp_itinerary_outcome_total)          # grounded +1 AND degraded +1
histogram_quantile(0.5, sum(rate(tp_retrieval_results_bucket[5m])) by (le))
```
The retrieval histogram is the point: Kyoto contributes a healthy sample, Reykjavik a **near-
zero** one. A median that collapses toward zero as you add out-of-corpus cities is the corpus
boundary made numeric.

#### 📈 Grafana
§2 *POIs returned per retrieval* **drops**. §2 *Itinerary outcomes* grows a `degraded` line
next to `grounded`. §0 *Runs/sec* is unchanged — **both runs succeeded**, which is why
throughput panels can never tell you about quality.

#### 🔍 Jaeger
Both traces have `agent.gather`. Compare their **widths**: Reykjavik's is shorter, because
there was less to score. Both still contain `llm.complete` — **the model was called for
both**, which is exactly what makes `degraded` cost money.

#### 💰 Langfuse
**Two generations for Reykjavik too.** Cost is non-zero on a hosted leg. This is the round's
commercial point: an out-of-corpus city is **not free**.

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select request->>'city', result->>'grounded', jsonb_array_length(coalesce(result->'days','[]')), result->'venues', warnings from runs order by created_at desc limit 2"
```

**PASS** = Kyoto grounded with named venues; Reykjavik honest — a warning, few or no items,
and **no invented Icelandic landmarks**.

**RESTORE** none.

---

## R2-Q2 · The funnel — 20 candidates in, 8 out

**RUN** city `Kyoto`, interests `temples, food, museums, nature` — four interests, to give
retrieval the widest possible net.

**EXPECT** more candidates fetched, still at most 8 kept.

#### 📊 Prometheus
```promql
tp_retrieval_results_bucket        # where the sample lands relative to RETRIEVAL_TOP_K=20
tp_retrieval_results_sum / tp_retrieval_results_count     # the running mean
```

#### 📈 Grafana
§2 *POIs returned per retrieval* should rise versus a single-interest query. **If it does
not, interests are not widening the search** — which would mean the interest field is
decorative.

#### 🔍 Jaeger
Open `agent.gather` and read its attributes. **The funnel is `RETRIEVAL_TOP_K=20` →
`RERANK_TOP_K=8`.** Seeing 20 fetched and 8 kept is the design working; seeing 20 → 20 means
reranking is not trimming and the prompt is carrying noise.

#### 💰 Langfuse
Compare `usage.input` against R2-Q1's Kyoto run. **More retrieved context = a bigger prompt =
more money.** This is where "just retrieve more" stops being free.

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select jsonb_array_length(jsonb_path_query_array(result->'days','\$[*].items[*]')) as items from runs order by created_at desc limit 1"
```

**PASS** = more interests produce a wider retrieval but never more than `RERANK_TOP_K` items
per day.

**RESTORE** none.

---

## R2-Q3 · Does the interest field actually steer retrieval?

**RUN** the same city, two opposite interests:
```bash
for I in temples food; do
  curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
    -d "{\"city\":\"Kyoto\",\"interests\":[\"$I\"],\"days\":1}"
done
```

**EXPECT** **different venues.** `temples` should surface Kiyomizu-dera / Kinkaku-ji /
Fushimi Inari; `food` should surface Nishiki Market and similar.

#### 📊 Prometheus
Identical counters for both. **Prometheus cannot answer this question at all** — it counts
runs, not relevance. Noted deliberately: knowing which tool *cannot* help is half the skill.

#### 📈 Grafana
Also nothing. Two grounded runs look identical on every panel.

#### 🔍 Jaeger
Two structurally identical traces. Timing tells you nothing about relevance.

#### 💰 Langfuse
Cost and tokens, nothing about content. **Langfuse here records no prompt and no completion**
(INSPECT.md §1.2), so it cannot answer this either.

#### 🗄️ Postgres — **the only instrument that can answer this**
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select request->'interests', jsonb_path_query_array(result->'days','\$[*].items[*].name') from runs order by created_at desc limit 2"
```

> **This query exists to prove a point about instruments.** Four observability tools, and not
> one of them can tell you whether retrieval returned relevant results. That is a **content**
> question, and on this deployment content lives in Postgres. Any inspection routine that
> only watches dashboards will never catch a relevance regression.

**PASS** = the two item lists differ, and each matches its interest.
**FAILURE** = identical items for both — the interest field is being ignored.

**RESTORE** none.

---

## R2-Q4 · Day-count scaling — does more days mean more content or padding?

**RUN**
```bash
for D in 1 3 7; do
  curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
    -d "{\"city\":\"Kyoto\",\"interests\":[\"temples\"],\"days\":$D}"
done
```

**EXPECT** — with only 26 POIs across 5 cities, Kyoto's slice is small. `_build_days()` caps
days at the number of POIs it can ground, so **a 7-day request should NOT produce 7 padded
days**.

#### 📊 Prometheus
```promql
histogram_quantile(0.95, sum(rate(tp_run_duration_seconds_bucket[5m])) by (le))
```
Longer trips take longer, but **not linearly** — the model call dominates, not the day count.

#### 📈 Grafana
§0 *Run p95* rises modestly. §3 *Stage latency* — `compose` grows; `geocode` and `gather` do
not, because retrieval happens **once** regardless of trip length.

#### 🔍 Jaeger
Compare the three traces side by side. `agent.gather` stays the same width; `agent.compose`
widens. **That shape is the proof retrieval is not repeated per day.**

#### 💰 Langfuse
`usage.output` grows with day count; `usage.input` barely moves. **Longer trips cost more in
completion, not prompt.**

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select request->>'days' requested, jsonb_array_length(result->'days') delivered, warnings from runs order by created_at desc limit 3"
```

**PASS** = `delivered <= requested`, and when it is fewer, **a warning explains why**.
**FAILURE** = 7 days delivered with the same 5 POIs repeated — padding, dressed as content.

**RESTORE** none.

---

## R2-Q5 · Cache-key versioning — invalidation without a FLUSHDB

**PRECONDITION** clean. This query changes state; read the restore first.

**RUN**
```bash
make cache-prefix          # the prefix the RUNNING app computes: v1.v1.v1
make cache-ls              # what is cached under it
```
Then plan `Kyoto`, and inspect the keys:
```bash
docker exec p3-ai-travel-planner-redis-1 redis-cli --scan --pattern 'v1.v1.v1:*'
```

**EXPECT** keys shaped `{PROMPT_VERSION}.{CORPUS_VERSION}.{INDEX_VERSION}:{tool}:...`, e.g.
`v1.v1.v1:geo:kyoto`.

#### 📊 Prometheus
```promql
sum by (tool, result) (rate(tp_cache_events_total[5m]))
```

#### 📈 Grafana
§3 *Cache events by tool* — watch `geo` and `wx` move; `route` only for a trip; `pois`
depending on the path taken.

#### 🔍 Jaeger
A cache hit **does not remove a span** here — the tool call still happens, it just returns
fast. Compare `agent.geocode` width on a hit versus a miss.

#### 💰 Langfuse
Unchanged. **Tool caching never affects model cost**, which is the entire point of
INSPECT.md's Q2.

#### 🗄️ Redis
```bash
docker exec p3-ai-travel-planner-redis-1 redis-cli ttl v1.v1.v1:geo:kyoto
```

> **Why version-prefixed keys instead of `FLUSHDB`.** Bumping `INDEX_VERSION` orphans every
> old entry and lets its TTL reap it. `FLUSHDB` would also destroy the Celery broker, the
> result backend, the daily-spend accumulator and the rate-limit windows — all in the same
> Redis.

**RESTORE** `make cache-clear` (scoped — spend, Celery and rate limits survive).

---

## R2-Q6 · POI quality — what is actually in the corpus?

**RUN**
```bash
curl -s "http://localhost:3003/collections/pois" | python -m json.tool | head -20
docker exec p3-ai-travel-planner-worker-1 python -c \
 "import asyncio;from tp_retrieval.vectorstore import QdrantStore;print(asyncio.run(QdrantStore.from_settings(dim=1024).read_meta()))"
```
Then browse the points in the **Qdrant dashboard**: <http://localhost:3003/dashboard>.

**EXPECT** 26 points, `status: green`, `indexed_vectors_count: 0`.

#### 📊 Prometheus
Qdrant is not scraped by this Prometheus. **Its health is visible only through the app** —
`tp_errors_total` and `tp_retrieval_results`.

#### 📈 Grafana
§2 *POIs returned per retrieval* is the proxy. A corpus problem shows up here as a falling
median long before anything errors.

#### 🔍 Jaeger
`agent.gather` completes normally even on a bad corpus. **A trace cannot see quality.**

#### 💰 Langfuse
Nothing.

#### 🗄️ Qdrant dashboard — the actual instrument
Open the `pois` collection and read some payloads.

> ⚠️ **Known finding: the fallback POI source returns events, not only places.** A real run
> produced *"2018 Osaka earthquake"* as a point of interest. `indexed_vectors_count: 0` is
> correct at 26 points — below Qdrant's HNSW threshold, search is brute force — but it means
> **retrieval latency here says nothing about latency at scale.**

**PASS** = 26 points, green, embedder stamp present.

**RESTORE** none.

---

## R2-Q7 · Degraded versus not_found — the distinction that costs money

**RUN** three cities chosen to land in three different outcomes:
```bash
for C in Kyoto Reykjavik Zzyzxville; do
  curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
    -d "{\"city\":\"$C\",\"interests\":[\"temples\"],\"days\":1}"
done
```

**EXPECT**

| city | outcome | model called | venues |
|---|---|---|---|
| Kyoto | grounded | yes | `['local-sglang']` |
| Reykjavik | **degraded** | **yes** | `['local-sglang']` |
| Zzyzxville | **not_found** | **no** | `[]` |

#### 📊 Prometheus
```promql
sum by (kind) (tp_itinerary_outcome_total)     # all three kinds should move
tp_llm_calls_total                             # +2 for grounded, +2 for degraded, +0 for not_found
```
**The token counter is the audit trail.** Two of these three cost money; one did not.

#### 📈 Grafana
§2 *Itinerary outcomes* shows all three lines at once — the only query in any round that
produces that.

#### 🔍 Jaeger
**Count the spans.** 13 for Kyoto and Reykjavik, **11 for Zzyzxville** — no `llm.complete`.
> Span count alone tells you whether you paid.

#### 💰 Langfuse
Two generations for Kyoto, two for Reykjavik, **none for Zzyzxville**.

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select request->>'city', result->>'grounded', result->'venues', cost_usd, warnings from runs order by created_at desc limit 3"
```

> **Why this matters at scale.** Every plausible-but-absent city pays full prompt price to
> produce a degraded plan. On a 5-city corpus that is most of the world. If a cost line ever
> looks wrong, this is the query that explains it — and `make verify-all` separates the two
> automatically.

**RESTORE** none.

---

## What this round proves

| claim | evidence |
|---|---|
| Retrieval genuinely runs | R2-Q2's funnel, 20 → 8 |
| Interests steer it | R2-Q3's differing item lists |
| The corpus boundary is honest | R2-Q1, R2-Q7 — degraded, not fabricated |
| Trip length does not pad | R2-Q4 — `delivered <= requested`, with a warning |
| Cache invalidation is surgical | R2-Q5 — version prefix, never `FLUSHDB` |
| The index is what it claims | R2-Q6 — embedder stamp, 26 points |

**And the uncomfortable one:** R2-Q3 shows that **no dashboard in this stack can detect a
relevance regression.** Prometheus counts, Grafana draws, Jaeger times, Langfuse bills —
none of them read the answer. Only Postgres holds the content. Any monitoring story that
stops at the four tools has a blind spot exactly where quality lives.

```bash
make verify-all      # judges the runs this round produced, including the wrong-anchor check
```
