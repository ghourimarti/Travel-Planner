# Deployment & Scaling Plan — Voyantra (P3 · AI Travel Planner)

> Written 2026-09-09. Grounded in this repo's actual artifacts, not generic advice:
> `infra/helm/voyantra/` (11 templates + 5 values files), `infra/terraform/` (11 `.tf`, AWS-only),
> `infra/kind/`, `infra/argocd/`, `docker-compose.{app,data,gpu,observability}.yml`.
>
> **Prices are early-2026 list bands and drift.** Verify at the vendor before committing. Where a
> number drives a decision it is marked *(verify)*.

---

## A1 · Is `kind` a real production cluster?

**No. It is a real Kubernetes *API*, on a fake *substrate*.**

`kind` = Kubernetes IN Docker. Every "node" is a container on **one host, one kernel, one
machine, one power cord**. The control plane is genuine upstream Kubernetes, so the API surface
is real — which is exactly why it is useful, and exactly why it misleads people.

### What kind genuinely proves (and it is a lot)
- Manifests and Helm templates render and apply correctly — the same API objects as any cluster.
- Controller behaviour: Deployments, rollouts, readiness/liveness gating, restarts, backoff.
- RBAC, ServiceAccounts, ConfigMap/Secret wiring, init containers, resource requests/limits.
- Image pull + startup ordering, service discovery by DNS name, PVC binding *mechanics*.
- CI: a throwaway cluster per pipeline run, free and fast.

### What kind structurally **cannot** prove
| Cannot prove | Why |
|---|---|
| Multi-AZ / HA | One host. There is no second availability zone to fail into. |
| Real LoadBalancer | No cloud LB controller; `type: LoadBalancer` stays `<pending>` without MetalLB. |
| Real StorageClass / CSI | kind uses `local-path` on the host disk. No snapshots, no IOPS classes, no volume expansion, no cross-node reattach. |
| Node autoscaling | Node count is fixed at cluster-create. Cluster-autoscaler has nothing to scale. |
| NetworkPolicy enforcement | Default `kindnet` does not enforce NetworkPolicy — policies apply silently and block nothing. |
| Node upgrade / drain | No real cordon-drain-replace across machines; no surge capacity. |
| Blast radius / failure domains | Killing the host kills everything. You cannot lose "a node" independently. |
| Cloud IAM integration | No IRSA / workload identity. The IRSA annotation in `serviceaccount.yaml` is inert. |
| Realistic performance | Loopback networking, shared page cache, no real inter-AZ latency, no noisy neighbours. |
| Cost behaviour | Everything is free, so nothing teaches you what is expensive. |

**Verdict:** kind is a *rehearsal stage*, not a venue. It de-risks roughly the top two-thirds of a
deployment (everything above the substrate) for $0 — and then stops, hard, at exactly the line
where "I deployed to Minikube" stops being a credible claim.

---

## A2 · Correct architecture per scale tier

### The workload model (state the assumptions before quoting numbers)
This app is **concurrency-bound, not RPS-bound**: a plan is a long agent run (tool fan-out plus
multiple LLM calls), not a 50 ms request. The binding constraint is *concurrent in-flight runs*.

```
concurrent_runs ≈ (DAU × plans_per_user_per_day × avg_run_seconds × peak_factor) / 86,400
```

Assumptions used below: DAU ≈ 8% of MAU · 1 plan/active user/day · avg run 60 s · peak factor 6.

| MAU | DAU | plans/day | **peak concurrent runs** |
|---|---|---|---|
| 10k | ~800 | 800 | **~3** |
| 100k | ~8k | 8k | **~33** |
| 1M | ~80k | 80k | **~333** |
| 10M+ | ~800k | 800k | **~3,300+** |

That table is the whole argument. A 10k-MAU product needs about **three** concurrent agent
workers. This tier is wildly over-built in practice.

### Tier 1 — 10k MAU (~3 concurrent)
- **Cluster:** 1 managed cluster, 2–3 nodes × 2 vCPU / 4 GB, single region, single AZ acceptable.
- **Autoscaling:** HPA on the API (CPU); worker replicas fixed, or KEDA on Celery queue depth. No cluster-autoscaler needed.
- **Data:** in-cluster Postgres + Redis is *defensible* here (the chart already supports it via `postgres.enabled=true`) — but managed is only ~$30/mo and removes a whole class of 3 a.m. problems.
- **Qdrant:** single pod + PVC. (**Not in the Helm chart today** — see A3.)
- **LLM/GPU:** provider APIs only. No GPU. A GPU at this tier is a hobby, not an optimisation.
- **Cache/CDN:** Redis semantic cache (already built); CDN optional for the Next.js web.
- **Observability:** in-cluster kube-prometheus-stack + Loki; the existing 37-panel dashboard.
- **Cost band:** **$50–150/mo** *(verify)* plus LLM token spend.

### Tier 2 — 100k MAU (~33 concurrent) ← **the tier this project should actually target**
- **Cluster:** 3–6 nodes across **≥2 AZs**; separate node pools for `api` and `worker` (workers are the long-running, memory-hungry ones).
- **Autoscaling:** HPA (api) + **KEDA on Celery queue depth** (worker — the correct signal for concurrency-bound work) + cluster-autoscaler.
- **Data:** **managed Postgres** (HA option) + **managed Redis**, wired through the chart's existing `externalDatabaseUrl` / `externalRedisUrl` seam. PgBouncer if connection count climbs.
- **Qdrant:** StatefulSet with a replica, or Qdrant Cloud.
- **LLM/GPU:** still API-first. A single GPU node pool becomes arguable only if steady QPS justifies it — measure before buying.
- **Cache/CDN:** semantic + tool-result cache doing real work; CDN in front of web.
- **Multi-AZ:** yes. Multi-region: no.
- **Cost band:** **$300–800/mo** *(verify)* plus tokens.

### Tier 3 — 1M MAU (~333 concurrent)
- **Cluster:** 10–30 nodes, 3 AZs, dedicated pools (api / worker / ingest / GPU), PodDisruptionBudgets, topology spread constraints.
- **Autoscaling:** KEDA scaling workers hard; cluster-autoscaler with **warm pools** — agent runs are far too long to tolerate cold-start-on-demand.
- **Data:** managed Postgres + **read replicas** + PgBouncer; Redis cluster mode; per-tenant partitioning of the run tables.
- **Qdrant:** sharded + replicated (or managed). The re-index pipeline becomes a first-class operational concern.
- **LLM/GPU:** now the cost centre. Self-hosted vLLM with continuous batching for the cheap tier plus API for frontier; aggressive model routing. **Token/GPU spend dwarfs infrastructure spend at this tier.**
- **Multi-AZ mandatory**; multi-region only if the user base demands the latency.
- **Observability:** dedicated stack (Mimir/Thanos + Loki) or a vendor; sampling, not full-fidelity tracing.
- **Cost band:** **$3k–15k/mo infra**, plus LLM spend that can be 2–10× that *(verify)*.

### Tier 4 — 10M+ MAU (~3,300+ concurrent)
- **Cell-based architecture**: many independent smaller clusters ("cells"), not one giant cluster. Blast radius becomes the design driver.
- Multi-region active/active, global CDN, data sharded by region + tenant, a dedicated GPU fleet, capacity planning as a standing function, SLO/error-budget process, on-call rotation.
- **Cost band:** $50k–500k+/mo *(verify)*.
- **Honest note:** at this tier the hard part stops being architecture and becomes **operation** — on-call, incident command, capacity economics. That is precisely the part a portfolio cannot manufacture.

### Which tier to actually build
> **Build the Tier-2 (100k MAU) *shape*, run it at Tier-1 *cost*, and document the capacity model up to Tier 3.**

Concretely: a real managed cluster, a multi-AZ node pool, managed Postgres + Redis, KEDA
autoscaling, ingress + TLS, real observability — then prove it with a k6 test that drives
**30–50 concurrent plans** and show the autoscaler reacting. Tier 3 is a written capacity model
using the arithmetic above. **Tier 4 is architecture-on-paper and must be labelled as such** —
claiming otherwise is the exact thing that gets caught in a system-design interview.

---

## A3 · Does kind have to come before a real cluster?

**No — it is not a prerequisite. It is a cheap rehearsal, and skipping it does not save work; it
relocates the bugs onto a metered cluster where they cost money and patience to find.**

Roughly two-thirds of a deployment is substrate-independent (templating, config, secrets wiring,
probes, rollout behaviour, RBAC). kind finds those bugs at $0. The remaining third — the rows
below — **only** appear on a real cluster, and no amount of kind proves them.

### kind → managed-Kubernetes delta (grounded in this repo)

| Concern | What exists today | What a real cluster requires | File(s) that change |
|---|---|---|---|
| **Ingress / exposure** | **No `ingress.yaml` in the chart.** Services only; access via port-forward / NodePort | Ingress + real cloud LoadBalancer + DNS record | **NEW** `infra/helm/voyantra/templates/ingress.yaml`; `values-*.yaml` |
| **TLS** | none | cert-manager + Let's Encrypt (or a cloud-managed cert) | new cluster addon; ingress annotations |
| **Storage** | kind `local-path`; `postgres.storage: 1Gi` | Cloud CSI StorageClass, sized volume, snapshots, expansion | `values-*.yaml` (add `storageClassName`); `templates/postgres.yaml` |
| **Postgres / Redis** | in-cluster (`postgres.enabled: true`) | Managed services via `externalDatabaseUrl` / `externalRedisUrl` — **the seam already exists ✅** | `values-prod.yaml`; Terraform |
| **Qdrant** | **only in `docker-compose.data.yml` — absent from the Helm chart** | StatefulSet + PVC (or managed Qdrant) | **NEW** `templates/qdrant.yaml` + values |
| **Registry** | bare tags `tp-api:p61`, side-loaded via `kind load` | Registry-qualified images + imagePullSecret | `values-*.yaml` `image.*.repository`; `.github/workflows/cd.yml` |
| **Secrets** | `secret.yaml` + `externalsecret.yaml` (**ESO template already present ✅**) | External Secrets Operator installed + a real backend | `externalsecret.yaml` values; cluster addon |
| **Autoscaling** | **No `hpa.yaml`.** Fixed `replicas` (prod: api 3 / worker 4) | HPA (api) + **KEDA ScaledObject on Celery queue depth** (worker) + cluster-autoscaler | **NEW** `templates/hpa.yaml`, `templates/keda-scaledobject.yaml` |
| **Identity** | `serviceaccount.yaml` carries an IRSA annotation (inert on kind) | Real workload identity — IRSA on AWS; **no equivalent on most non-AWS** (see A4) | `serviceaccount.yaml`; `infra/terraform/irsa.tf` |
| **Observability** | compose stack (`docker-compose.observability.yml`) | In-cluster kube-prometheus-stack + Loki, or a vendor | `infra/observability/*` → Helm values |
| **Backups / DR** | none | Managed PG automated backups + PVC snapshots + a **restore drill** | Terraform; new runbook |
| **Node lifecycle** | fixed kind nodes | Node pool upgrades, drain, PodDisruptionBudgets | **NEW** `templates/pdb.yaml` |

**Four of those rows are missing chart templates** (ingress, hpa/keda, qdrant, pdb). That is the
real, concrete work hiding inside "deploy to a real cluster" — and it is why Phase 8 is a genuine
phase, not a `terraform apply`.

---

## A4 · The AWS-lock-in problem (the part that matters most)

### Current state
`infra/terraform/` is a **single flat AWS-only root**: `vpc.tf · eks.tf · rds.tf · elasticache.tf ·
ecr.tf · irsa.tf · gpu.tf · providers.tf · versions.tf · variables.tf · outputs.tf`.
There is no provider abstraction and no module boundary between "cloud" and "app".

*(Note: `gpu.tf` **does exist** — the old "6.4.6 GPU node group not written" item is stale. PHASE 10 · R4.2 recorded it as written and validated, never planned.)*

**Deploying to DigitalOcean is not a variable change. It is a second infrastructure root.**

### What must be rewritten per provider
| AWS resource | DO equivalent | Rewrite? |
|---|---|---|
| `eks.tf` (+ VPC, node groups, OIDC) | `digitalocean_kubernetes_cluster` (+ node pool) | **Full rewrite** — ~80% smaller; DO folds VPC/CP/OIDC into one resource |
| `vpc.tf` | `digitalocean_vpc` (far simpler) | **Full rewrite**, mostly deletion |
| `rds.tf` | `digitalocean_database_cluster` (pg) | **Full rewrite** |
| `elasticache.tf` | `digitalocean_database_cluster` (valkey/redis) | **Full rewrite** |
| `ecr.tf` | `digitalocean_container_registry` | **Full rewrite** |
| `irsa.tf` | **no equivalent** | **Delete + compensate** (see below) |
| `gpu.tf` | DO GPU droplets (limited availability) | Rewrite or drop |

### Recommendation: two thin roots, one chart — and **no abstraction layer**

```
infra/terraform/
├── aws/    ← move the existing 11 .tf here, unchanged
└── do/     ← new, ~120 lines total
infra/helm/voyantra/   ← unchanged, shared by both
```

**Do not build a provider-neutral Terraform module.** It is a trap: provider resources are not
polymorphic, the abstraction costs more than it saves at this size, and — critically — it *hides
the cloud-specific detail that is the entire point of the exercise*. An interviewer wants to hear
"IRSA has no DigitalOcean equivalent, so I did X"; an abstraction layer erases that conversation.

**The portable layer already exists and is the correct one: the Helm chart + values files.**

**Contract between the two roots.** Each must emit the same five outputs so that
`values-<env>.yaml` consumes them identically:
`kubeconfig` · `database_url` · `redis_url` · `registry_endpoint` · `workload_identity_annotation` (may be empty).

### Identity: the honest downgrade
AWS IRSA maps a Kubernetes ServiceAccount to an IAM role via OIDC — per-pod, keyless, rotating.
**DigitalOcean has no equivalent.** On DO you fall back to static credentials in a Secret,
delivered by External Secrets from a real backend (DO's secret storage, or self-hosted Vault /
sealed-secrets). That is a **genuine reduction in security posture**, and the right move is to
*document it as a known trade-off*, not to pretend the two are equivalent. That comparison is
itself portfolio material.

### Lowest-effort path that still counts as real practice
**DOKS + DO Managed Postgres + DO Managed Valkey + DOCR + ingress-nginx + cert-manager + in-cluster Qdrant.**
That exercises real LoadBalancers, real CSI storage, real DNS/TLS, real managed data, a real
registry, real node pools and real autoscaling — roughly **90% of the EKS learning at ~10% of the
cost** — and it forces the four missing chart templates to be written (which AWS would have forced
anyway).

---

## A5 · Vendor landscape

### Managed Kubernetes
| Vendor | Control plane | Cheapest real cluster/mo *(verify)* | Managed PG / Redis | GPU | Free credit *(verify)* | Who it's for |
|---|---|---|---|---|---|---|
| **AWS EKS** | ~$73/mo | ~$150+ | ✅ RDS / ElastiCache | ✅ broad | Activate (startup programme) | Enterprise default; the résumé keyword |
| **GCP GKE** | 1 zonal cluster free; else ~$73 | ~$100+ | ✅ Cloud SQL / Memorystore | ✅ best GPU/TPU story | ~$300 trial | Scaleups; best k8s DX (it invented it) |
| **Azure AKS** | Free tier (paid for SLA) | ~$100+ | ✅ | ✅ | ~$200 trial | Microsoft-shop enterprises |
| **DigitalOcean DOKS** | **Free** | **~$50–70** | ✅ PG + Valkey | limited | **$200 / 60 days** | **Indies & startups — best docs-to-cost ratio** |
| **Linode / Akamai LKE** | **Free** | ~$50 | ✅ | limited | ~$100 | Indies, cost-sensitive startups |
| **Vultr VKE** | **Free** | ~$40 | ✅ | ✅ cheap GPU | promos ~$250 | Cost-sensitive; good GPU pricing |
| **Civo** | **Free** | ~$40 | limited | ✅ | ~$250 historically | Fast k3s clusters; dev/test |
| **Scaleway Kapsule** | **Free** | ~$40 | ✅ | ✅ | occasional | EU / data-residency |
| **OVHcloud** | **Free** | ~$40 | ✅ | ✅ | occasional | EU, cost-driven |
| **Oracle OKE** | **Free** | **~$0 (Always Free ARM: 4 OCPU / 24 GB)** | paid | ✅ | Always Free tier | **Cheapest genuinely-real cluster that can stay up** |
| **IBM Cloud K8s** | paid | $$$ | ✅ | ✅ | limited | Regulated / legacy enterprise |
| **Alibaba ACK** | free/paid | $$ | ✅ | ✅ | regional | APAC enterprise |
| **Hetzner** | **no managed k8s** | ~$15 (self-managed k3s/Talos) | ✅ PG only | ❌ | none | Cheapest EU compute; max learning, max effort |

### Non-Kubernetes PaaS worth knowing
| Platform | Model | Who it's for |
|---|---|---|
| **Fly.io** | Containers on a global edge; built-in Postgres | Indies wanting global latency without k8s |
| **Render** | Git-push PaaS + managed PG/Redis | Startups avoiding infra entirely |
| **Railway** | Fastest DX, usage-priced | Prototypes / demos |
| **Porter** | Managed k8s *inside your own* AWS/GCP account | Startups wanting k8s without operating it |
| **Koyeb** | Serverless containers | Edge / async workloads |

### Who actually uses what
- **Startups:** DigitalOcean, Render, Fly, Railway, Vultr, Linode, Hetzner, Civo.
- **Scaleups:** GKE, EKS, AKS, DOKS at upper tiers, Porter.
- **Enterprises:** EKS, GKE, AKS, OpenShift, IBM, Oracle, Alibaba (in-region).

### Recommendation for this project
1. **Phase 8 → DigitalOcean DOKS**, funded by the $200 credit. Best documentation-to-cost ratio, free control plane, real managed PG/Redis, and it forces the four missing chart templates.
2. **Keep a zero-cost long tail → Oracle OKE Always Free**, if you want a cluster that survives after the credit ends.
3. **Phase 9 → AWS EKS**, because `infra/terraform/` already targets it and **"EKS" is the keyword hiring filters actually match on**. Run it briefly, capture evidence, destroy it.
4. **Optional depth → Hetzner + Talos/k3s** self-managed, if you want to prove you understand what a managed control plane is doing for you. High learning, high time cost.

---

## A6 · The $200 DigitalOcean plan (costed and time-boxed)

### Shape A — "Portfolio-credible" (what to actually demo)
| Item | Spec | $/mo *(verify)* |
|---|---|---|
| DOKS control plane | standard (non-HA) | **$0** |
| Node pool | 3 × `s-2vcpu-4gb` | ~$72 |
| Managed Postgres | 1 vCPU / 1 GB, single node | ~$15 |
| Managed Valkey (Redis) | 1 GB | ~$15 |
| Container registry | DOCR Basic | ~$5 |
| Load balancer | 1 × small | ~$12 |
| **Total** | | **≈ $119/mo** |

**$200 ÷ $119 ≈ 50 days** if left running 24/7 — and running it 24/7 is the mistake.

### Shape B — "Cheapest credible" (still proves real k8s)
| Item | Spec | $/mo |
|---|---|---|
| Node pool | 2 × `s-2vcpu-4gb` | ~$48 |
| Postgres + Redis | **in-cluster** (chart already supports `postgres.enabled=true`) | $0 |
| DOCR Basic + Load balancer | | ~$17 |
| **Total** | | **≈ $65/mo → ~92 days** |

Shape B still gives real nodes, a real LB, real CSI, real ingress/TLS and real autoscaling. It
gives up managed-data experience — which is exactly what Shape A is for. **Do Shape B first to get
it working, then upgrade to Shape A for the evidence run.**

### The number that actually matters: **DO bills by the hour**
Working ~6 h/day on Shape A: `$119/mo ÷ 730 h ≈ $0.163/h × 6 h × 30 d ≈ **$29/mo**` → the $200
credit lasts **~6–7 months of real working time**.

> **This is the single highest-leverage discipline in the whole phase.** An idle cluster is the
> only realistic way to waste this credit.

### Teardown discipline (non-negotiable)
1. `make cloud-up` / `make cloud-down` wrappers around `terraform apply` / `destroy` in `infra/terraform/do/`.
2. **Always `pg_dump` before destroy**; restore on the next bring-up. (Managed databases cannot scale to zero — destroy them.)
3. Scale the node pool to 0 if you must keep the control plane and its DNS.
4. **Billing alerts at $50 / $100 / $150** in the DO console — on day one, before the first apply.
5. A `LAST_APPLY` timestamp in the repo; if it is older than a day and the cluster is still up, that is a bug.
6. End every session with the `terraform destroy` output pasted into the todos as proof.

### What to demo on it
Everything in A7 — captured in **one deliberate evidence run**, not spread across weeks of idling.

---

## A7 · Portfolio evidence to capture

The named career gap is *"production Kubernetes, not Minikube."* Evidence is what closes it.
Capture these **during the real-cluster phase**, into `docs/evidence/` and `screenshots/`:

| # | Artifact | Command / source | What it proves |
|---|---|---|---|
| 1 | Real nodes | `kubectl get nodes -o wide` (≥3 nodes, real instance types, zones) | Not Minikube/kind |
| 2 | Pod spread | `kubectl get pods -o wide` across nodes/zones | Scheduling + topology |
| 3 | **Autoscaling under load** | HPA/KEDA replica count before → during → after k6, with the Grafana graph | The single most valuable artifact |
| 4 | **k6 at real concurrency** | 30–50 concurrent plans; p50/p95/p99 + error rate + cost/plan | A capacity claim backed by measurement |
| 5 | **Rollback drill** | `kubectl rollout undo` with timestamps + zero-downtime proof | Progressive delivery is real |
| 6 | **Chaos drill** | Kill a worker mid-run → prove the LangGraph checkpointer resumes / partial results are returned | Resilience, not just configuration |
| 7 | **Restore drill** | Managed-PG restore-from-backup, timed | DR is rehearsed, not assumed |
| 8 | Ingress + TLS | `curl -vI https://…` showing a valid certificate chain | Real exposure, real DNS |
| 9 | Grafana on real traffic | The 37-panel dashboard (PHASE 9 · T3) against cluster load | Observability wired end-to-end |
| 10 | **Cost report** | DO/AWS billing + `$ per 1k plans` | Cost engineering — a named gap |
| 11 | **Teardown record** | `terraform destroy` output + final bill | Operational discipline |
| 12 | Failure honesty | Anything that broke, and how it was fixed | The most credible artifact of the set |

> Artifacts 3, 4, 5, 6, 10 and 11 are what move the claim from *"I wrote Kubernetes manifests"* to
> *"I ran a cluster, scaled it under load, broke it, recovered it, and knew what it cost."*
> That sentence is what this whole phase exists to earn.

---

## Where this lands in the plan

| Phase | Venue | Purpose |
|---|---|---|
| **Phase 7** | Local: Docker → kind → `terraform validate/plan` → ArgoCD / CI-CD | Rehearse everything substrate-independent, at $0 |
| **Phase 8** | **Real non-AWS managed cluster (DOKS)** | Write the 4 missing templates; prove real LB / CSI / TLS / autoscaling / managed data; capture the A7 evidence |
| **Phase 9** | **AWS EKS** (`infra/terraform/aws/`) | The résumé keyword plus IRSA, on the IaC that already exists; short, evidence-focused, destroyed afterwards |
