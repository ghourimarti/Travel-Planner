# Round 4 — Concurrency, the queue, and crash recovery

**Rounds 1–3 tested a system that was being asked one question at a time by a calm person.**
This round asks:

> **What happens under load, and what happens when the worker dies mid-run?**

Every query is new. The theme is the **asynchronous seam** — the Celery queue between the API
and the worker — which is where this architecture is strongest and where its one open defect
lives.

Read [INSPECT.md §0–§2](INSPECT.md) first.

```bash
make cache-clear && make kill-status      # must print ENABLED + floor true
```

---

## The configuration this round tests

From `packages/core/src/tp_core/celery.py`:

```python
task_acks_late = True              # redeliver if a worker dies MID-TASK
worker_prefetch_multiplier = 1     # fair dispatch for long-running jobs
visibility_timeout = 360           # CELERY_VISIBILITY_TIMEOUT, seconds
```

Worker command: `celery -A tp_worker.celery_app worker -l info`

**Each setting is a deliberate trade, and each is testable:**

| setting | what it buys | what it costs |
|---|---|---|
| `task_acks_late=True` | a task survives a worker crash | a task can run **twice** if the worker dies after finishing but before acking |
| `prefetch_multiplier=1` | no worker hoards a queue while another idles | slightly more broker round-trips |
| `visibility_timeout=360` | how long a task may sit unacked before redelivery | **must exceed the longest real task**, or a slow run is redelivered while still running |

**Flower** (<http://localhost:3011>) is this round's fifth instrument — it shows the queue
itself, which no other tool does.

---

## R4-Q1 · Ten plans at once — does the queue hold?

**RUN**
```bash
for i in $(seq 1 10); do
  curl -s -o /dev/null -X POST localhost:3004/plan -H 'content-type: application/json' \
    -d "{\"city\":\"Ljubljana\",\"interests\":[\"castles\"],\"days\":1}" &
done; wait
docker exec p3-ai-travel-planner-redis-1 redis-cli llen celery
```

**EXPECT** all 10 accepted (under the 60/min limit), a queue that grows then **drains to 0**.

#### 📊 Prometheus
```promql
sum(rate(tp_dispatch_total{outcome="queued"}[1m]))       # spikes immediately
sum(rate(tp_runs_total{status="succeeded"}[1m]))         # rises LATER, and more slowly
```
**The gap between those two curves is the queue.** Dispatch is instant; completion is not.
That lag is the whole reason this app is asynchronous.

#### 📈 Grafana
§0 *Runs/sec* rises **after** §2 *API dispatch outcomes*. Watching them together is the
clearest picture of backpressure the dashboard gives.

#### 🔍 Jaeger
Ten `POST /plan` spans under `tp-api`, all short. Ten `run/tp_worker.tasks.plan_task` spans
under `tp-worker`, **spread out over minutes**. Compare the timestamps — the worker is the
bottleneck, by design.

#### 💰 Langfuse
Twenty generations (two per run), arriving gradually.

#### 🌸 Flower — <http://localhost:3011>
**Tasks** tab: watch `plan_task` move `RECEIVED → STARTED → SUCCESS`. **Workers** tab shows
concurrency and how many are active. **This is the only tool that shows the queue as a queue.**

#### 🗄️ Redis
```bash
docker exec p3-ai-travel-planner-redis-1 redis-cli llen celery     # depth, live
```

**PASS** = queue drains to 0, all 10 `succeeded`, no errors.

**RESTORE** none.

---

## R4-Q2 · Does the API stay fast while the worker is saturated?

**PRECONDITION** run R4-Q1 first so work is queued.

**RUN** — while the queue is draining:
```bash
time curl -s -o /dev/null -w "dispatch: %{http_code} in %{time_total}s\n" \
  -X POST localhost:3004/plan -H 'content-type: application/json' \
  -d '{"city":"Bruges","interests":["canals"],"days":1}'
curl -s -o /dev/null -w "health:   %{http_code} in %{time_total}s\n" localhost:3004/health
```

**EXPECT** dispatch still ~250 ms, health instant — **even with a full queue**.

#### 📊 Prometheus
```promql
histogram_quantile(0.95, sum(rate(tp_run_duration_seconds_bucket[5m])) by (le))
```
Run duration climbs (queue wait is included) while **dispatch stays flat**. Two different
numbers that a synchronous app would conflate into one.

#### 📈 Grafana
§0 *Run p95* rises. §2 *API dispatch outcomes* keeps flowing at the same rate. **A saturated
worker must never make the front door slow** — that is the property under test.

#### 🔍 Jaeger
`POST /plan` spans stay short throughout. The `tp-worker` spans lengthen — but that length is
**queue wait plus work**, not API latency.

#### 💰 Langfuse
Unaffected — generations arrive when the worker gets to them.

#### 🌸 Flower
Queue depth high, worker at full concurrency.

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select status, count(*) from runs where created_at > now() - interval '10 minutes' group by 1"
```
**A healthy backlog looks like a growing `queued` count that shrinks again.** A backlog that
never shrinks is R4-Q4.

**PASS** = dispatch latency unchanged under load.

**RESTORE** none.

---

## R4-Q3 · Kill the worker mid-run — does the task survive?

**PRECONDITION** clean. ⚠️ **Restarts the worker. Restore is a restart, so nothing is lost.**

**RUN**
```bash
curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
  -d '{"city":"Salzburg","interests":["music","food"],"days":3}'
sleep 3                                          # let it START, not finish
docker restart p3-ai-travel-planner-worker-1
curl -s --retry 20 --retry-delay 3 --retry-all-errors -o /dev/null localhost:3004/health
sleep 60
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select id, status, created_at::timestamp(0), updated_at::timestamp(0) from runs order by created_at desc limit 1"
```

**EXPECT** — `task_acks_late=True` means the task was **never acked**, so the broker
redelivers it after the visibility timeout and the run **completes**. That is the design.

#### 📊 Prometheus
⚠️ **The worker's counters reset to zero.** Every `tp_*` series on `job="tp-worker"` restarts.
`rate()` handles this correctly; cumulative panels start again. **Do not read the reset as
data loss** — it is what "since restart" means.

#### 📈 Grafana
§1 venue blocks go back to *"not served since restart"*. §4 *Runs by status* has a visible
discontinuity. **This is the clearest illustration in any round of why §1 says "since
restart" rather than pretending to be absolute.**

#### 🔍 Jaeger
Possibly **two** `run/tp_worker.tasks.plan_task` traces for one `run_id` — the abandoned
attempt and the redelivery. **That duplication is `acks_late` working**, not a bug.

#### 💰 Langfuse
May show generations from **both** attempts. The run is billed twice for the interrupted
portion — the price of at-least-once delivery, and worth knowing before you promise a cost
per run.

#### 🌸 Flower
The **Workers** tab shows the worker disappear and return with a new PID.

#### 🗄️ Postgres — **LangGraph checkpoints are why this is cheap**
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select thread_id, count(*) from checkpoints group by 1 order by 2 desc limit 3"
```
`thread_id` **is** the `run_id`. A finished stage is checkpointed, so a redelivered task
resumes from the last checkpoint rather than replaying the whole graph. **A completed city
resumes at END, effectively free; only an unfinished stage replays.**

**PASS** = the run reaches `succeeded` without you touching it.

**RESTORE** the worker is already back. Verify:
```bash
docker exec p3-ai-travel-planner-worker-1 celery -A tp_worker.celery_app status
```

---

## R4-Q4 · 🔴 The orphan — a run that will never finish

**This is an open defect on this deployment, not a hypothetical.**

**RUN**
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select id, created_at::timestamp(0), status, request->>'city' from runs
  where status not in ('succeeded','failed','error') order by created_at"
docker exec p3-ai-travel-planner-redis-1 redis-cli llen celery
```

**MEASURED** — 5 runs stranded at `queued`, oldest over a day old, with **`llen celery = 0`**:
```
c8326894…  2026-09-10 07:02:58  queued  Kyoto
e79b321f…  2026-09-10 06:57:46  queued  Kyoto
79fd92c6…  2026-09-09 13:48:26  queued  Kyoto
...
pending: 0
```

**The mechanism.** The run row is written to Postgres **before** the task is safely
processed. If the broker is then lost — Redis stopped, `appendonly no`, so the queue is gone —
the row survives at `queued` **forever**. Nothing reconciles it. No error, no timeout, no
janitor.

**What the user sees:** a plan stuck "queued" permanently, with no explanation.

#### 📊 Prometheus
⚠️ **Invisible.** `tp_runs_total` only increments on *completion*, so an orphan never
appears. `tp_dispatch_total{outcome="queued"}` counted it once, at accept time, and that
counter has almost certainly reset since.

#### 📈 Grafana
⚠️ **Also invisible.** §4 *Runs by status* shows `succeeded` and `failed` — an orphan is
neither. It is simply **absent**, and absence renders identically to "never happened".

#### 🔍 Jaeger
A `tp-api` trace exists (the request was accepted). **No `tp-worker` trace ever follows.**
The missing half is the signature — but you would have to know to look for it.

#### 💰 Langfuse
Nothing. No model was called.

#### 🗄️ Postgres — the only place it is visible
The query above. Or:
```bash
make verify-all      # reports: "N run(s) queued >15min ago with 0 tasks pending"
```

> **The lesson.** Four observability tools, and **none of them can see a run that never
> started.** Every one is built to record things that happened; an orphan is defined by the
> absence of an event. This is the strongest argument in any round for checking your
> **database** against your dashboards rather than trusting the dashboards alone.
>
> **The fix** would be a reconciler: any run at `queued` older than the visibility timeout,
> with nothing in the broker, is dead and should be marked `failed`. It does not exist yet.

**RESTORE** none — but consider clearing them once you have seen them:
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "update runs set status='failed', error='orphaned: broker lost before dispatch'
  where status='queued' and created_at < now() - interval '1 hour'"
```

---

## R4-Q5 · The visibility timeout — the number that must be bigger than your slowest run

`visibility_timeout=360` (6 minutes) is how long a task may sit unacked before the broker
assumes the worker is dead and **hands it to someone else**.

**RUN** — find your actual slowest run and compare:
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select kind, max(extract(epoch from updated_at - created_at))::int as slowest_seconds
  from runs where status='succeeded' group by kind"
docker exec p3-ai-travel-planner-worker-1 sh -c 'echo "visibility_timeout=${CELERY_VISIBILITY_TIMEOUT:-360}"'
```

**EXPECT** the slowest run comfortably **under** 360s. Measured single-city p95: **14.3s**.
A 5-city trip is the one to watch.

#### 📊 Prometheus
```promql
histogram_quantile(0.99, sum(rate(tp_run_duration_seconds_bucket[1h])) by (le))
```
**Compare p99 against the timeout, not p50.** The timeout is a tail property.

#### 📈 Grafana
§0 *Run p95* against the NFR. If p99 ever approaches 360s, **a slow run gets redelivered
while still running** — and with `acks_late` you then have two workers on one task,
double-billing and racing to write the same row.

#### 🔍 Jaeger
The width of `run/tp_worker.tasks.plan_task` **is** the number being compared.

#### 💰 Langfuse
A redelivered-while-running task shows as **duplicate generations for one run_id** — the
symptom you would actually notice first, on the bill.

#### 🌸 Flower
A task moving back to `RECEIVED` while another instance is `STARTED` is this failure, live.

#### 🗄️ Postgres
The query above is the ground truth for "how slow do runs actually get here".

> **Why this is a genuine trap.** The comment in `celery.py` says it plainly: the timeout
> must exceed the longest real task runtime. Set it too low and you do not get an error —
> you get **silent duplicate work**, which shows up as a doubled bill weeks later.

**RESTORE** none.

---

## R4-Q6 · Fair dispatch — does one big job block everything?

`worker_prefetch_multiplier=1` means a worker takes **one** task at a time instead of
hoarding a batch.

**RUN** — a big trip, then a small plan immediately after:
```bash
curl -s -o /dev/null -X POST localhost:3004/trip -H 'content-type: application/json' \
  -d '{"cities":["Ljubljana","Zagreb","Trieste","Verona","Milan"],"interests":["castles"],"days":10}'
sleep 1
curl -s -X POST localhost:3004/plan -H 'content-type: application/json' \
  -d '{"city":"Ghent","interests":["belfries"],"days":1}'
```

**EXPECT** the small plan is **not** starved behind the big trip any longer than one task.

#### 📊 Prometheus
```promql
histogram_quantile(0.95, sum(rate(tp_run_duration_seconds_bucket[5m])) by (le))
```
Watch whether the small run's duration is dominated by its own work or by waiting.

#### 📈 Grafana
§3 *Stage latency* — the small run's stages should be normal width. **Long stages mean slow
work; a long total with normal stages means queue wait.** Only splitting them apart tells you
which.

#### 🔍 Jaeger
Compare the two `run/…plan_task` spans' **start offsets**. That gap is queueing.

#### 🌸 Flower
The **Tasks** tab shows the ordering directly — this is what Flower is for.

#### 🗄️ Postgres
```bash
docker exec p3-ai-travel-planner-db-1 psql -U tp -d tp -c \
 "select kind, request->>'city', created_at::timestamp(0), updated_at::timestamp(0),
  extract(epoch from updated_at-created_at)::int secs from runs order by created_at desc limit 2"
```

> **With one worker process, `prefetch=1` limits the damage but cannot eliminate it** — a
> 5-city trip still occupies the worker while it runs. The fix at scale is more workers or a
> separate queue for trips, and this query is how you decide you need one.

**RESTORE** none.

---

## What this round proves

| claim | evidence |
|---|---|
| Dispatch stays fast under load | R4-Q2 — ~250 ms with a full queue |
| A worker crash does not lose work | R4-Q3 — `acks_late` + checkpoint resume |
| At-least-once has a real cost | R4-Q3 — duplicate generations are possible |
| Fair dispatch works | R4-Q6 — small jobs are not starved |
| The timeout must exceed p99 | R4-Q5 — or you get silent duplicate work |
| 🔴 **Orphaned runs are real** | R4-Q4 — 5 of them, invisible to all four tools |

**The uncomfortable one is R4-Q4.** Prometheus, Grafana, Jaeger and Langfuse all record
**events that happened**. An orphaned run is defined by an event that *never* happened, and
none of them can represent that. The database can. Any monitoring story built only on the
four tools has a blind spot exactly there — and it is the blind spot a user notices first,
because their plan just sits there.

```bash
make verify-all      # the orphan check, plus every component
```
