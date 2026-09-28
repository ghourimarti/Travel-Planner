# Round 3 — Cost, tiers, and venue economics

**Round 1 asked "does it work". Round 2 asked "is retrieval honest".** This round asks the
question a client actually pays for:

> **What does each run cost, at which tier, on which venue — and can I control that?**

Every query is new. The theme is money: how one run splits across **two capability tiers**,
how the chain routes each tier, how spend is attributed, and the several ways cost accounting
can silently be wrong while every dashboard stays green.

Read [INSPECT.md §0–§2](INSPECT.md) first for the instrument setup and state ledger.

```bash
make cache-clear && make kill-status      # must print ENABLED + floor true
```

---

## The fact this whole round rests on

**One plan makes TWO model calls, at TWO different tiers:**

| stage | tier | code |
|---|---|---|
| `agent.compose` | **`Tier.MID`** | `nodes.py:288` |
| `agent.critic` | **`Tier.FRONTIER`** | `critic.py:44` |

Confirmed live:
```promql
sum(tp_llm_calls_total) by (tier, provider)
  {provider="local-sglang", tier="mid"}      = 5
  {provider="local-sglang", tier="frontier"} = 4
  {provider="groq",         tier="mid"}      = 4
  {provider="groq",         tier="frontier"} = 4
```

`mid` and `frontier` counts move **together**, one of each per run. If they ever diverge,
either the critic is being skipped or compose is retrying.

### The price table (`models.py`, USD per 1M tokens)

| model | input | output | tier |
|---|---|---|---|
| `gpt-4o-mini` | 0.15 | 0.60 | cheap |
| `gpt-4o` | **2.50** | **10.00** | mid, frontier |
| `qwen/qwen3.8-27b` (Groq) | 0.80 | 4.00 | cheap, mid, frontier |
| `claude-sonnet-4-6` | 3.00 | 15.00 | mid |
| `claude-opus-4-8` | 5.00 | 25.00 | frontier |
| **any local venue** | **0** | **0** | all |

⚠️ **An unpriced model returns `(0.0, 0.0)` and silently UNDER-reports spend.** Keep every
routed model in `MODEL_PRICING`, or your cost dashboard becomes a fiction that always reads
low. This is the most dangerous line in this document.

Per-itinerary cap: `MAX_COST_USD=0.30`.

---

## R3-Q1 · Watch one run split across two tiers

**RUN** — snapshot, plan, snapshot:
```bash
before=$(curl -s "http://localhost:3009/api/v1/query?query=sum(tp_llm_calls_total)by(tier)")
curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
  -d '{"city":"Porto","interests":["port wine"],"days":1}'
sleep 20
curl -s "http://localhost:3009/api/v1/query?query=sum(tp_llm_calls_total)by(tier)" | python -m json.tool
```

**EXPECT** `mid` **+1** and `frontier` **+1**. Not two of one.

#### 📊 Prometheus
```promql
sum by (tier) (tp_llm_calls_total)
sum by (tier, direction) (tp_llm_tokens_total)
sum by (tier) (tp_llm_cost_usd_total)
```
**The tier label is the one that maps spend to intent.** `frontier` is the critic — you are
paying flagship prices to review a draft, and this is where you decide whether that is worth
it.

#### 📈 Grafana
§1 *Which venue served, over time* shows the venue but **not the tier**. §3 *Stage latency*
is the proxy: `compose` and `critic` are the two model calls, and their widths are where the
tiers live.

#### 🔍 Jaeger
The clearest view of all. **Two `llm.complete` spans** — one nested under `agent.compose`,
one under `agent.critic`. Open each and read `llm.tier` in the attributes.

#### 💰 Langfuse
**Two generations**, and `metadata.attributes.llm.tier` distinguishes them:
```
llm.tier=mid       llm.provider=…  llm.input_tokens=…  llm.cost_usd=…
llm.tier=frontier  llm.provider=…  llm.input_tokens=…  llm.cost_usd=…
```
**This is the single best screen in the stack for a cost conversation.**

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select cost_usd, result->'venues' from runs order by created_at desc limit 1"
```
The run's `cost_usd` must equal the **sum** of its two generations in Langfuse.

**PASS** = `mid +1`, `frontier +1`, and the two ledgers agree.

**RESTORE** none.

---

## R3-Q2 · Route the tiers to different venues

**PRECONDITION** clean. ⚠️ **This recreates containers. Read the restore first.**

`CHAIN_CHEAP` / `CHAIN_MID` / `CHAIN_FRONTIER` override `SERVING_CHAIN` **per tier**. They
are empty by default, so every tier follows one chain.

**RUN** — send the critic to a hosted venue while compose stays local:
```bash
CHAIN_MID=local-sglang,groq CHAIN_FRONTIER=groq,openai \
docker compose -f docker-compose.data.yml -f docker-compose.app.yml \
  -f docker-compose.observability.yml up -d --no-deps --force-recreate api worker
curl -s --retry 10 --retry-delay 3 --retry-all-errors -o /dev/null localhost:3004/health
docker exec p3-ai-travel-planner-worker-1 sh -c 'echo "MID=$CHAIN_MID FRONTIER=$CHAIN_FRONTIER"'
make cache-clear
curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
  -d '{"city":"Porto","interests":["port wine"],"days":1}'
```

**EXPECT** the run's `venues` now contains **two different venues** — the local engine for
compose, a hosted one for the critic. Cost is no longer `$0.00`.

#### 📊 Prometheus
```promql
sum by (tier, provider) (tp_llm_calls_total)
```
**The pair `{tier="mid",provider="local-sglang"}` and `{tier="frontier",provider="groq"}` is
the proof the override took.** If both tiers still show one provider, the env did not reach
the worker.

#### 📈 Grafana
§1 — **two venue blocks light up for a single run.** Before this query, only one did.
§1 *Tokens/sec by venue* splits across two providers.

#### 🔍 Jaeger
The two `llm.complete` spans now carry **different `llm.provider` attributes**. Same trace,
two vendors.

#### 💰 Langfuse
Two generations with different `llm.provider` and **different `calculatedTotalCost`** — one
zero, one not. This is the screen that makes tiered routing legible to a finance person.

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select result->'venues', cost_usd from runs order by created_at desc limit 1"
```

> **Why this matters commercially.** It lets you spend flagship money only where quality is
> decided — the critic — and run the bulk generation free on your own GPU. That is the
> argument for self-hosting *and* keeping a hosted rung, in one run.

**RESTORE**
```bash
make up-app
docker exec p3-ai-travel-planner-worker-1 sh -c 'echo "MID=$CHAIN_MID FRONTIER=$CHAIN_FRONTIER"'   # both EMPTY
make kill-status
```

---

## R3-Q3 · The same query on three venues — a like-for-like price comparison

**RUN** — force each leg in turn using the blackhole method from [INSPECT.md §8](INSPECT.md),
clearing the cache between each so nothing is reused. Or simply:
```bash
make inspect ENGINE=sglang        # the ladder does exactly this, ~12 min, self-restoring
```

**MEASURED on this deployment**, same single-city plan:

| venue | cost | note |
|---|---|---|
| `local-sglang` | **$0.000000** | GPU-hours, not tokens |
| `groq` | **$0.000772** | qwen3.8-27b at 0.80 / 4.00 |
| `openai` | **$0.002197** | gpt-4o at 2.50 / 10.00 |

**Groq is ~2.8× cheaper than OpenAI on the tiers this app actually uses.**

> 📝 **A correction worth carrying.** An earlier analysis claimed OpenAI was ~6× cheaper. It
> compared OpenAI's **cheap** model (`gpt-4o-mini`, 0.15/0.60) against Groq's **mid** price —
> different tiers, meaningless comparison. This app's compose runs at MID and its critic at
> FRONTIER, and **on both of those, Groq wins.** Always compare within a tier.

#### 📊 Prometheus
```promql
sum by (provider) (tp_llm_cost_usd_total)
sum by (provider, direction) (tp_llm_tokens_total)
```
Divide cost by tokens per provider and check it matches `MODEL_PRICING`. **If it does not,
either a model is unpriced or a price has drifted.**

#### 📈 Grafana
§1 per-venue *spend* stats side by side — the whole point of one row per venue. §4
*Cumulative spend by venue*.

#### 🔍 Jaeger
Compare `llm.complete` **widths** across venues. Latency and price are independent axes:
the cheapest leg is not always the slowest.

#### 💰 Langfuse
Filter by `llm.provider` and compare `calculatedTotalCost` for equivalent token counts.

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select result->'venues', count(*), round(avg(cost_usd)::numeric,6) from runs where result->'venues' is not null group by 1 order by 2 desc"
```
**Your real average cost per venue, from your own history.**

**RESTORE** the drill restores itself and verifies it. Confirm:
```bash
docker exec p3-ai-travel-planner-worker-1 cat /etc/hosts     # no 127.0.0.1 app lines
```

---

## R3-Q4 · Do the two cost ledgers agree?

There are **two independent records of spend**, written by different code paths:

| ledger | where | who writes it |
|---|---|---|
| the **breaker's** total | Redis `spend:usd:<UTC date>` | `record_spend()` in the gateway |
| the **caller's** cost | `runs.cost_usd` + Langfuse | the response and the OTel span |

**RUN**
```bash
DAY=$(date -u +%F)
docker exec p3-ai-travel-planner-redis-1 redis-cli get spend:usd:$DAY
curl -s "http://localhost:3009/api/v1/query?query=sum(tp_llm_cost_usd_total)" | python -m json.tool
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -tAc \
 "select round(sum(cost_usd)::numeric,6) from runs where created_at::date = current_date"
```

**EXPECT** the Redis key and today's Postgres sum to track each other.

**MEASURED on the ladder**, per paid rung:

| leg | cost to caller | delta to `spend:usd:*` |
|---|---|---|
| groq | `$0.000772` | `+0.000772` |
| openai | `$0.002197` | `+0.002197` |

#### 📊 Prometheus
`sum(tp_llm_cost_usd_total)` — the §0 *Spend today* panel reads exactly this.

#### 📈 Grafana
§0 *Spend today (all venues)* against §4 *Cumulative spend by venue*. **If these disagree
with the Redis key, one ledger is lying.**

#### 🔍 Jaeger
`llm.cost_usd` on each `llm.complete` span — a third, per-call view.

#### 💰 Langfuse
Sum `calculatedTotalCost` for today.

#### 🗄️ Redis
```bash
docker exec p3-ai-travel-planner-redis-1 redis-cli ttl spend:usd:$(date -u +%F)   # ~48h
```

> ⚠️ **This is how a dead cost control was found.** `record_spend()` existed and **nothing
> called it** — the Redis key was never written, so `DAILY_SPEND_LIMIT_USD` could never trip
> at any value, while the caller-side cost looked perfectly correct. **One ledger reading
> zero while the other reads normally is the exact signature.** Cross-checking two
> independent paths is the only thing that catches it.
>
> ⚠️ **Durability:** `appendonly no`, save points at 3600s/1 change. Up to an hour of
> accumulation can be lost on an unclean stop. Do not treat the daily cap as accounting.

**RESTORE** none.

---

## R3-Q5 · The per-itinerary cap

`MAX_COST_USD=0.30` bounds a **single** itinerary, independently of the daily breaker.

**RUN** — a trip is the most expensive shape this app produces:
```bash
curl -s -X POST localhost:3004/trip -H 'content-type: application/json' \
  -d '{"cities":["Porto","Braga","Coimbra","Faro","Seville"],"interests":["port wine","food","museums"],"days":10}'
```

**EXPECT** it completes, and `cost_usd` stays well under `$0.30` — on a local engine it is
`$0.00`. The cap exists for the day the chain falls through to a hosted leg.

#### 📊 Prometheus
```promql
histogram_quantile(0.95, sum(rate(tp_run_cost_usd_bucket[5m])) by (le))
```

#### 📈 Grafana
§0 *Cost / itinerary p95 (cap $0.30)* — **the threshold colour is the verdict.**

#### 🔍 Jaeger
`trip.plan` with one `agent.plan` subtree per city — **five subtrees, ten model calls**, and
they overlap horizontally because the cities run concurrently.

#### 💰 Langfuse
**Ten generations** for a 5-city trip. Sum them and compare to the run's `cost_usd`.

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select cost_usd, jsonb_array_length(result->'cities') cities, result->'failed_cities' from runs where kind='trip' order by created_at desc limit 1"
```

> **The two caps answer different questions.** `MAX_COST_USD` stops **one** runaway request.
> `DAILY_SPEND_LIMIT_USD` stops **a thousand cheap ones**. Neither substitutes for the other,
> and a system with only the per-request cap can be bled dry at $0.002 a time.

**RESTORE** none.

---

## R3-Q6 · What a free run and a paid run look like side by side

**RUN** the same city twice — once with the engine serving, once with it blackholed:
```bash
make cache-clear
curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
  -d '{"city":"Porto","interests":["port wine"],"days":1}'          # local, $0

docker exec -u root p3-ai-travel-planner-worker-1 sh -c 'echo "127.0.0.1 sglang" >> /etc/hosts'
sleep 8
docker exec p3-ai-travel-planner-worker-1 python -c "import socket;print(socket.gethostbyname('sglang'))"   # MUST be 127.0.0.1
make cache-clear
curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
  -d '{"city":"Porto","interests":["port wine"],"days":1}'          # hosted, paid
```

**EXPECT** identical itineraries, different `venues` and very different `cost_usd`.

#### 📊 Prometheus
`sum by (provider) (tp_llm_cost_usd_total)` — one provider at 0, one climbing.

#### 📈 Grafana
§1 — **the handoff, drawn.** *Which venue served, over time* shows one line stopping and
another starting. **That picture is an outage and its mitigation in a single chart**, and it
is the most persuasive panel in the dashboard.

#### 🔍 Jaeger
Same 13-span shape, different `llm.provider`. **The structure of a run does not change when
the vendor does** — which is the architectural claim this app makes.

#### 💰 Langfuse
Two pairs of generations, one pair free, one pair billed.

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select result->'venues', cost_usd, left(result->>'summary',60) from runs order by created_at desc limit 2"
```
**Read both summaries.** Comparable quality at very different prices is the entire
justification for self-hosting.

**RESTORE** — ⚠️ **`sed -i` cannot do this.** `/etc/hosts` is a bind mount; sed's
temp-file-and-rename is denied and removes nothing while appearing to succeed:
```bash
docker exec -u root p3-ai-travel-planner-worker-1 sh -c \
 "grep -vxF -e '127.0.0.1 sglang' /etc/hosts > /tmp/h; cat /tmp/h > /etc/hosts"
docker exec p3-ai-travel-planner-worker-1 python -c "import socket;print(socket.gethostbyname('sglang'))"
#  MUST NOT be 127.0.0.1
```

---

## What this round proves

| claim | evidence |
|---|---|
| One run uses two tiers | R3-Q1 — `mid +1`, `frontier +1` |
| Tiers can be routed independently | R3-Q2 — two venues in one run |
| Self-hosting is genuinely free | R3-Q3 — `$0.000000`, recorded not skipped |
| Groq beats OpenAI on the tiers used | R3-Q3 — 2.8×, within-tier |
| Spend accounting is cross-checked | R3-Q4 — two independent ledgers agree |
| Both caps exist and differ | R3-Q5 — per-request vs per-day |

**The lesson to carry:** cost bugs in an LLM system are **silent**. An unpriced model reports
`$0.00` and looks like a self-hosted win. A dead `record_spend()` leaves the caller-side cost
perfectly correct. Neither shows up as an error, a latency spike or a failed run — **only a
second, independent ledger catches them.**

```bash
make verify-all      # includes the cost-attribution check across all recent runs
```
