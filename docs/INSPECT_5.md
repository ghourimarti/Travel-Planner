# Round 5 — Data lifecycle, tenancy, and what "delete" really means

Rounds 1–4 asked whether the system **works**. This round asks:

> **Where does a user's data actually live, who can read it, and what survives a deletion?**

Every query is new, and every one of them is a question a customer, an auditor, or a privacy
regulator asks — none of which any dashboard answers. **This round finds two real defects
that all four observability tools are blind to.**

Read [INSPECT.md §0–§2](INSPECT.md) first.

```bash
make cache-clear && make kill-status      # must print ENABLED + floor true
```

---

## The seven places one plan lands

A single `POST /plan` writes to **seven** stores. Most engineers can name three.

| # | store | what it holds | scoped to a tenant? | expires? |
|---|---|---|---|---|
| 1 | Postgres `runs` | the request **and** the finished itinerary, as JSON | ✅ `tenant_id` column | ❌ never |
| 2 | Postgres `checkpoints` + `_blobs` + `_writes` | in-flight graph state — **the same content** | ❌ **`thread_id` only** | ❌ never |
| 3 | Redis tool cache | geocode / POI / weather / route lookups | ❌ **global** | ✅ TTL |
| 4 | Redis Celery queue | the `run_id` while queued | ❌ | ✅ on consume |
| 5 | Redis spend ledger | cost only, no content | ❌ | ✅ 48 h |
| 6 | Langfuse | model, tokens, cost — **`input`/`output` are `None`** | ❌ | ❌ |
| 7 | Jaeger | span names and timings, no content | ❌ | ⚠️ **in-memory** |

**Store 2 is the one that matters**, and it is the one nobody thinks about.

---

## R5-Q1 · Follow one plan into all seven stores

**RUN**
```bash
RID=$(curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
  -d '{"city":"Lisbon","interests":["azulejos","seafood"],"days":2}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['run_id'])")
echo "run_id=$RID"; sleep 45
```

**EXPECT** a `run_id` that is findable in every store below. Keep `$RID` — the whole round
uses it.

#### 🗄️ Postgres — stores 1 and 2
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select id, tenant_id, status, request->>'city' from runs where id='$RID'"
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select count(*) from checkpoints where thread_id='$RID'"
```
**Both must return rows.** The second table has **no `tenant_id` column at all** — check:
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c "\d checkpoints"
```
Columns: `thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata`.
**There is nowhere to put an owner.** Remember that for R5-Q3.

#### 🗄️ Redis — stores 3, 4, 5
```bash
docker exec p3-ai-travel-planner-redis-1 redis-cli --scan --pattern 'v1*' | head
docker exec p3-ai-travel-planner-redis-1 redis-cli llen celery       # 0 once done
docker exec p3-ai-travel-planner-redis-1 redis-cli --scan --pattern 'spend:*'
```
Keys look like `v1.v1.v1:geo:lisbon` — **the city the user typed, in the key, in plaintext,
with no tenant prefix.** That is R5-Q4.

#### 📊 Prometheus
```promql
sum(tp_runs_total)
```
⚠️ **A counter, not a record.** Prometheus knows *a* run happened; it cannot tell you *which*.
Nothing here is per-user, by design — which is why Prometheus is not a data-subject concern.

#### 📈 Grafana
Nothing identifies this run. Every panel is an aggregate. **Correct, and worth stating in an
audit: the dashboards hold no personal data.**

#### 🔍 Jaeger — store 7
Search `tp-api`, tag `run_id=$RID`. **Span names and timings only** — no itinerary, no city
in the payload.

#### 💰 Langfuse — store 6
Two generations. Open one: `model`, `usage`, `calculatedTotalCost` are populated;
**`input` and `output` are `None`**.
> **This is a privacy feature, whether or not it was designed as one.** Langfuse here is a
> **cost ledger, not a content store** — so a deletion request never has to reach it. Many
> teams discover the opposite about their tracing vendor during an audit.

**PASS** = the run is in 1, 2, 3 and 6; absent from 4; content-free in 6 and 7.

**RESTORE** none.

---

## R5-Q2 · Can one tenant read another's run?

`tenant_id` comes from the token claim `https://tp/tenant`, falling back to `org_id`, then
`"default"` (`auth.py:53`). With auth off, every caller is `LOCAL_PRINCIPAL` — tenant `local`.

**RUN**
```bash
curl -s -o /dev/null -w "own run:      %{http_code}\n" localhost:3004/runs/$RID
curl -s -o /dev/null -w "made-up id:   %{http_code}\n" \
  localhost:3004/runs/00000000-0000-0000-0000-000000000000
curl -s localhost:3004/runs/$RID | python -m json.tool | grep -c tenant_id
```

**EXPECT** `200`, `404`, and **`0`**.

**Two separate properties, both deliberate:**

1. **A cross-tenant id returns 404, not 403** (`runs.py:96`) — *"a run owned by a different
   tenant is treated as absent, so ownership can't be probed."* A 403 would confirm the id
   exists. **404 leaks nothing.**
2. **`tenant_id` is `Field(exclude=True)`** (`runs.py:67`) — it is never serialised into an
   API response. You cannot learn your own tenant id by reading your own run.

#### 📊 Prometheus
```promql
sum by (endpoint, outcome) (rate(tp_dispatch_total[5m]))
```
⚠️ **A cross-tenant probe is invisible here.** `GET /runs` records no dispatch metric, so a
scanner enumerating run ids leaves **no trace in any metric**. That is a genuine gap — it is
not exploitable (uuid4 ids, 404s), but you would not *see* it.

#### 📈 Grafana
Nothing. §2 covers `plan`/`trip` dispatch only.

#### 🔍 Jaeger
`GET /runs/{id}` spans exist with status codes. **Jaeger is the only tool where a burst of
404s from one caller is visible at all** — sort by status, look for a run of 404s.

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select coalesce(tenant_id,'(null)') tenant, count(*) from runs group by 1 order by 2 desc"
```
**Rows with `tenant_id = null` predate auth.** They belong to no one — so `DELETE /me/data`
can never reach them. Worth knowing before you promise complete erasure.

**PASS** = 200 / 404 / 0, and you can explain why the second is 404 rather than 403.

**RESTORE** none.

---

## R5-Q3 · 🔴 Delete your data — then find it still there

**This is the round's headline defect. It is real on this deployment.**

**PRECONDITION** run R5-Q1 so `$RID` exists and is `succeeded`.

**RUN** — count first, delete, then count again:
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select (select count(*) from runs where tenant_id='local') runs,
         (select count(*) from checkpoints where thread_id='$RID') cps"

curl -s -X DELETE localhost:3004/me/data | python -m json.tool

docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select (select count(*) from runs where tenant_id='local') runs,
         (select count(*) from checkpoints where thread_id='$RID') cps"
```

**EXPECT** a `DeletionReceipt` — `{"tenant_id": "local", "runs_deleted": N}` — and `runs = 0`.

**MEASURED — `cps` does NOT go to zero.**

The endpoint is honest about what it does. `runs.py:107`:

```python
async def delete_tenant_data(tenant_id: str) -> int:
    """Erase every run owned by a tenant — the GDPR right-to-be-forgotten path."""
    result = await session.execute(delete(Run).where(Run.tenant_id == tenant_id))
```

**One table.** The receipt says `runs_deleted`, and that is exactly, literally true. But the
**same request and the same itinerary** are also in `checkpoints`, `checkpoint_blobs` and
`checkpoint_writes`, keyed by `thread_id` — which **is** the `run_id` — and those tables
**have no `tenant_id` column to filter on**.

**Prove the content is really there**, not just row counts:
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -tc \
 "select count(*) from checkpoint_blobs where encode(blob,'escape') like '%Kyoto%'"
```
**Measured on this deployment: `1471`.** One thousand four hundred and seventy-one blob rows
containing a user's search term in plaintext, after every `runs` row for it could have been
deleted.

**The scale of the leftovers:**
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select 'runs' t, count(*) from runs
  union all select 'checkpoints', count(*) from checkpoints
  union all select 'checkpoint_blobs', count(*) from checkpoint_blobs
  union all select 'checkpoint_writes', count(*) from checkpoint_writes"
```
**Measured: 696 / 5,690 / 9,052 / 16,215.** The tables nobody deletes from are **thirty times
larger** than the table the deletion endpoint targets.

#### 📊 Prometheus
⚠️ **Completely blind.** No metric counts deletions by row, no metric counts checkpoint rows.

#### 📈 Grafana
⚠️ **Also blind.** A user's data can be deleted, or fail to be deleted, with **zero movement
on any of the 37 panels.**

#### 🔍 Jaeger
A `DELETE /me/data` span exists with its status code. **This is the only tool that shows the
deletion happened at all** — and it shows only that the HTTP call returned 200, not what was
erased.

#### 💰 Langfuse
Unaffected, and **that is fine here** — `input`/`output` are `None`, so there is no content to
erase. Cost rows for a deleted user remain, which is normally defensible as billing records.

#### 🗄️ Postgres
The queries above are the entire evidence base. **Only the database can answer this question.**

> **The finding, stated plainly.** `DELETE /me/data` deletes what it says it deletes. The
> defect is that the **retention story is incomplete**: LangGraph's checkpointer was adopted
> for crash recovery (R4-Q3) and it quietly became a second copy of user content, with no
> owner column and no expiry. The fix is a cascade — delete from the three checkpoint tables
> where `thread_id` is in the tenant's run ids, **before** the `runs` delete — or a retention
> job that drops checkpoints for terminal runs.
>
> **The wider lesson:** in an agentic system, **your framework's persistence layer is a data
> store you are responsible for**, even though you never wrote an INSERT into it.

**RESTORE** — the deletion is real; re-run R5-Q1 if you want a run back. To clear the
orphaned checkpoints:
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "delete from checkpoint_writes where thread_id not in (select id from runs);
  delete from checkpoint_blobs  where thread_id not in (select id from runs);
  delete from checkpoints       where thread_id not in (select id from runs)"
```

---

## R5-Q4 · The shared cache — one tenant warms it, everyone drinks

**RUN**
```bash
curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
  -d '{"city":"Reykjavik","interests":["geothermal"],"days":2}'
sleep 45
docker exec p3-ai-travel-planner-redis-1 redis-cli --scan --pattern '*reykjavik*'
```

**EXPECT** `v1.v1.v1:geo:reykjavik` — **no tenant in the key.**

**Is that a leak?** Work it through rather than reacting:

- **What is cached** is the *answer from a public API* — Nominatim's coordinates for
  Reykjavik. Not the user's itinerary, not their interests, not their identity.
- **What the key reveals** is that *somebody* looked up Reykjavik. Not who.
- **Why it is shared on purpose:** a per-tenant cache would multiply upstream calls by the
  tenant count for data that is **identical for everyone**. Nominatim's coordinates do not
  vary by customer.

> **The correct verdict: shared is right, and it is right because the cached values are
> tenant-independent.** The moment anything user-specific enters this cache — a personalised
> ranking, a saved preference — the key **must** gain a tenant prefix. The line is *"does the
> value depend on who asked?"*, and today it does not.

#### 📊 Prometheus
```promql
sum by (tool, result) (rate(tp_cache_events_total[5m]))
```
Labels are **`tool` names only** (`geo`, `wx`, `pois`, `route`) — never the key. `cache.py`
says why: *"bounded label: the tool name, never the full key."* **A full-key label would put
every city a user searched into Prometheus forever**, and blow up cardinality. Two problems,
one line of defence.

#### 📈 Grafana
§3 *Cache events by tool*. Aggregate, no keys — consistent with R5-Q1's finding that the
dashboards hold no personal data.

#### 🔍 Jaeger
Tool spans name the tool, not the key.

#### 🗄️ Redis
```bash
docker exec p3-ai-travel-planner-redis-1 redis-cli --scan --pattern 'v1*' | wc -l
```
⚠️ **This is the one place a user's search terms are readable in plaintext**, to anyone with
Redis access. Redis is on the internal network only — which is the control that makes it
acceptable.

**PASS** = shared keys, tool-only labels, and you can defend both.

**RESTORE** none.

---

## R5-Q5 · What expires, and what never does

**RUN**
```bash
for k in $(docker exec p3-ai-travel-planner-redis-1 redis-cli --scan --pattern 'v1*' | head -6); do
  printf "%-45s ttl=%s\n" "$k" \
    "$(docker exec p3-ai-travel-planner-redis-1 redis-cli ttl "$k")"
done
```

**EXPECT** — from `cache.py:26-29`:

| tool | TTL | why that number |
|---|---|---|
| `geo` | **30 days** | a city's coordinates do not move |
| `pois` | **7 days** | venues open and close slowly |
| `wx` | **6 hours** | a forecast older than that is wrong, not stale |
| `route` | **7 days** | roads change slowly |

**Measured:** `v1.v1.v1:geo:tokyo` → `ttl = 2587280` ≈ **29.9 days**. The 30-day TTL is real.

> **TTLs are a correctness decision before they are a cost decision.** A 30-day weather cache
> would be *cheap* and *wrong*. Each number encodes how fast the underlying world changes, and
> that is the only defensible way to choose one.

**Now the other side:**

| store | expiry |
|---|---|
| Redis tool cache | ✅ 6 h – 30 d |
| Redis spend ledger | ✅ 48 h (`_SPEND_TTL`, "comfortably longer than the window it covers") |
| Postgres `runs` | ❌ **never** |
| Postgres checkpoints ×3 | ❌ **never** |
| Prometheus | ✅ 15 days (default; no `--storage.tsdb.retention.time` is set) |
| Jaeger | ⚠️ **in-memory** — `all-in-one` with no storage backend |
| Langfuse | ❌ never |

#### 🔍 Jaeger — verify the volatile one
```bash
docker restart p3-ai-travel-planner-jaeger-1 && sleep 10
```
Then reload the UI. **Every trace is gone.** `jaegertracing/all-in-one:latest` with no
`SPAN_STORAGE_TYPE` keeps spans in RAM, capped, and drops them on restart.
> **Correct for local development, and a trap if you ever reason about last week's latency.**
> Jaeger here answers *"what did that run just do?"* — never *"what changed since Tuesday?"*
> That question belongs to Prometheus, which is exactly why both exist.

#### 📊 Prometheus
```promql
sum(tp_runs_total)
```
Survives a Jaeger restart. It dies on a **Prometheus** restart if the volume is not
persistent — check `--storage.tsdb.path=/prometheus` is backed by a named volume, not the
container filesystem.

#### 📈 Grafana
Widen the time picker past 15 days and panels go empty. **That is retention, not a fault** —
the same trap as INSPECT.md §5.2's time picker.

#### 💰 Langfuse
Retains indefinitely. For a cost ledger that is usually what you want.

**PASS** = you can state, from memory, which of the seven stores expires.

**RESTORE** none — the Jaeger restart discards traces from earlier rounds. Do this one last if
you still need them.

---

## R5-Q6 · Unbounded growth — the table that never stops

R5-Q3 found the checkpoint tables are 30× the `runs` table. **This asks how fast they grow.**

**RUN**
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select relname, pg_size_pretty(pg_total_relation_size(relid)) size, n_live_tup rows
  from pg_stat_user_tables order by pg_total_relation_size(relid) desc"

before=$(docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -tAc \
  "select count(*) from checkpoint_writes")
curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
  -d '{"city":"Marrakesh","interests":["souks","riads"],"days":3}'
sleep 45
after=$(docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -tAc \
  "select count(*) from checkpoint_writes")
echo "checkpoint_writes rows for ONE plan: $((after - before))"
```

**EXPECT** roughly **20+ rows per plan** across the three checkpoint tables — one per graph
step per channel. Multiply by your traffic.

#### 📊 Prometheus
⚠️ **No metric tracks table size.** A database filling up is invisible to this stack until
Postgres refuses a write and `tp_errors_total{type="postgres_error"}` finally moves — which is
**the symptom, arriving far too late.**

#### 📈 Grafana
§4 *Errors by type* is the only panel that would ever react, and only at the very end.
> **The honest conclusion: this stack monitors the application well and the infrastructure
> underneath it barely at all.** Disk, table size, and connection-pool saturation have no
> panels. That is the single largest gap in the observability story, and R5-Q6 is how you
> demonstrate it rather than assert it.

#### 🔍 Jaeger
The individual write spans are there; their *cumulative* effect is not a span-shaped thing.

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select (select count(*) from runs where status in ('succeeded','failed')) terminal_runs,
         (select count(distinct thread_id) from checkpoints) threads"
```
**Checkpoints for a terminal run have no remaining purpose.** Resume only matters while a run
is in flight (R4-Q3). Every checkpoint row for a `succeeded` run is dead weight *and* a copy
of user content — the same rows R5-Q3 found. **One retention job closes both findings.**

**PASS** = you can state the per-plan row cost and that nothing prunes it.

**RESTORE** none.

---

## R5-Q7 · The receipt — is it true?

A deletion receipt is a **claim about the world**. Round 5 ends by testing it like any other
claim.

**RUN**
```bash
curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
  -d '{"city":"Bergen","interests":["fjords"],"days":2}' >/dev/null
sleep 45
curl -s -X DELETE localhost:3004/me/data | python -m json.tool
curl -s -X DELETE localhost:3004/me/data | python -m json.tool
```

**EXPECT** — the first returns `runs_deleted: N`, the second **`runs_deleted: 0`**.

**Three properties, each worth naming:**

1. **Idempotent.** Deleting twice is safe, and the count tells you it was already done.
2. **The count is a real `rowcount`**, not a guess — `cast("CursorResult[Any]", result).rowcount`.
3. **The tenant id in the receipt comes from the token, never the body.** There is no
   parameter through which to delete someone else's data — *"tenant-scoped by construction."*

**And the caveat this round exists to surface:** the receipt is **true and incomplete**. It
accurately reports rows deleted from `runs`. It does not — and does not claim to — account for
`checkpoints`. A user reading `{"runs_deleted": 4}` would reasonably conclude their data is
gone. **After R5-Q3 you know it is not.**

#### 📊 Prometheus
```promql
sum by (endpoint, outcome) (rate(tp_dispatch_total{endpoint="delete_data"}[15m]))
```
`record_dispatch("delete_data", "ok")` **does** fire — so deletions *are* counted, though no
Grafana panel plots that endpoint. **A metric exists that nothing displays**: worth adding a
panel, and worth remembering that "not on the dashboard" is not the same as "not measured".

#### 📈 Grafana
§2 *API dispatch outcomes* filters to `plan` and `trip`. **Add `delete_data` and you have a
GDPR audit panel for free** — the data has been there all along.

#### 🔍 Jaeger
Both `DELETE /me/data` calls, both 200. Compare durations: the second is faster — nothing to
delete.

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select (select count(*) from runs where tenant_id='local') runs_left,
         (select count(*) from checkpoints
           where thread_id not in (select id from runs)) orphan_threads"
```
**`runs_left = 0` and `orphan_threads > 0` is the defect in two numbers.**

**PASS** = idempotent, honest count, and you can articulate what it omits.

**RESTORE** none.

---

## What this round proves

| claim | evidence |
|---|---|
| One plan writes to **seven** stores | R5-Q1 |
| Cross-tenant reads 404, never 403 | R5-Q2 — ownership cannot be probed |
| `tenant_id` never leaves the API | R5-Q2 — `Field(exclude=True)` |
| Langfuse holds **no content** here | R5-Q1 — `input`/`output` are `None` |
| The shared cache is correct **because** values are tenant-independent | R5-Q4 |
| TTLs encode how fast the world changes | R5-Q5 — 6 h weather vs 30 d geocode |
| Jaeger traces die on restart | R5-Q5 — in-memory `all-in-one` |
| 🔴 **Deletion misses the checkpoint tables** | R5-Q3 — 1,471 blob rows with plaintext content |
| 🔴 **Checkpoints grow without bound** | R5-Q6 — 16,215 rows vs 696 runs |

**Both defects share one root cause and one fix.** LangGraph's checkpointer was adopted for
crash recovery in R4-Q3 — a good decision that made the system resilient. It also, silently,
became a **second copy of user content with no owner and no expiry**. Deleting checkpoints for
terminal runs closes the privacy gap and the growth gap in the same statement.

**And note which instrument found it.** Not Prometheus, not Grafana, not Jaeger, not Langfuse —
all four are built to record **events**, and "data that was never deleted" is not an event. It
is a **state**, and only the database holds state.

> Round 4 ended on a run that never started. Round 5 ends on data that never left. **Both are
> absences, and absence is the one thing an event-based observability stack cannot show you.**

```bash
make verify-all      # checks state, not events — which is the point
```
