# Incident Runbook — AI Travel Planner

On-call reference for production incidents. Written from the failure modes the system is
actually built to survive (Decision 21 degradation matrix) and the alerts in
[`infra/observability/alerts.yaml`](../infra/observability/alerts.yaml).

## Severity & response

| Sev | Definition | Response |
|-----|------------|----------|
| **SEV1** | Total outage — no runs succeed, or data-integrity/security breach | Page immediately; consider the kill switch; declare incident |
| **SEV2** | Degraded — SLO burning (error rate / p95 / cost ceiling) | Page; mitigate within the hour |
| **SEV3** | Localized — one tenant, one provider rung, elevated warnings | Investigate next business day |

## The two big levers

```bash
# KILL SWITCH — stop accepting new planning work (fail-open by design; /plan,/trip → 503).
redis-cli set planning:enabled 0      # disable
redis-cli del planning:enabled        # re-enable (absence = enabled)

# Worker scale — drain or add capacity
kubectl scale deploy/tp-worker --replicas=N
```

## Playbooks (alert → diagnose → mitigate)

### `NoSuccessfulRuns` / `HighRunErrorRate` (SEV1/2)
1. Check worker health: `kubectl get pods -l app=tp-worker`; logs for tracebacks (logs carry `trace_id`).
2. Open the trace for a failed `run_id` in Langfuse/Jaeger — find which span failed (`agent.*` / `llm.complete`).
3. If **LLM providers** are the cause: the gateway already falls back Anthropic→Groq→OpenAI; if *all* are down the run raises a typed `ProviderError` and degrades. Confirm provider status pages; nothing to do but wait/communicate.
4. If **worker/broker** is the cause: check Redis (broker) and restart workers. Runs resume from the LangGraph checkpointer — no lost work.

### `RunLatencyP95Breached` (SEV2)
1. Is it provider latency (`llm.complete` span duration) or queue depth (Celery backlog)? 
2. Backlog → scale workers. Provider latency → check tiering; the corrective loop is capped, so look for slow retrieval (Qdrant) timeouts in spans.

### `ItineraryCostP95NearCeiling` / `CeilingHit` / `SpendRateSpike` (SEV2/1)
1. The per-run hard cap (S10b) should contain individual runs; a breach means *volume* or *loop frequency*.
2. Check `tp_critic_revisions_total` rate — runaway corrective loops inflate cost.
3. If spend is genuinely runaway (abuse/bug): **flip the kill switch**, then investigate.

### `RateLimitingSpike` (SEV3)
- A tenant is hammering quotas. Identify via access logs; raise their `RATE_LIMIT_PER_MIN` if legitimate, or leave the 429s if abusive.

### Dependency-down quick reference (degradation is automatic)
| Down | Built-in behavior | Your action |
|------|-------------------|-------------|
| LLM provider | Fallback chain; typed error + degrade if all down | Watch; communicate |
| Redis (cache) | Cache no-ops, runs recompute (best-effort) | Restore Redis; latency normalizes |
| Redis (broker) | New dispatch can't enqueue | Restart Redis; checkpointer preserves in-flight runs |
| Qdrant (corpus) | Warning + fall back to live POI tools (ungrounded) | Restore Qdrant; `grounded` returns to true |
| Geocode/weather tool | Warning + thinner itinerary | Usually transient |

## Data & recovery
- **Backups/restore:** `bash scripts/backup_restore_drill.sh` — run on schedule and before migrations.
- **GDPR right-to-be-forgotten:** `DELETE /me/data` erases all of a tenant's runs (token-scoped).
- **Log retention:** see [production-hardening.md](production-hardening.md#log-retention-policy).
