# Production Hardening (Phase 5)

Status of the build-spec hardening checklist after the Phase 5 pass. Every item is either
**Done** (implemented + verified here) or **Harness-ready** (artifact/automation delivered now;
real-environment *execution* belongs to Phase 6 once the cluster exists — flagged, not faked).

## Checklist status

| # | Item | Status | Where |
|---|------|--------|-------|
| 1 | Secrets audit | ✅ Done | `detect-secrets` + reviewed `.secrets.baseline`; CI gate; `make secrets` |
| 2 | Dependency (CVE) audit | ✅ Done | `pip-audit` (0 CVEs) + `pnpm audit` (PostCSS fixed via override); CI + `make audit-deps` |
| 3 | License audit | ✅ Done | `pip-licenses` gate fails on GPL/AGPL/LGPL/SSPL; policy below; `make licenses` |
| 4 | Security scan (SAST) | ✅ Done | `bandit` (0 findings, 1 justified `# nosec`); S12 injection/PII suite; CI + `make sast` |
| 5 | Data-deletion / RTBF | ✅ Done | `DELETE /me/data` (token-scoped) + `delete_tenant_data`; tests in `test_api.py` |
| 6 | Cost-alert thresholds | ✅ Done | `alerts.yaml` (cost p95, spend-rate spike) on top of the S10b hard caps |
| 7 | Chaos tests | ✅ Done | `test_chaos.py` (`pytest -m chaos`): LLM / Qdrant / geocode outages degrade gracefully |
| 8 | Log-retention policy | ✅ Done | policy below; structured JSON→stdout (S1), no PII in logs (S12 redaction) |
| 9 | Incident runbook | ✅ Done | [`runbook.md`](runbook.md) |
| 10 | On-call alerting rules | 🟡 Harness-ready | `alerts.yaml` defined + version-controlled; **Alertmanager wiring → Phase 6** |
| 11 | Load test | 🟡 Harness-ready | `tests/load/plan_smoke.js` (k6, ramps to 50 VUs); **real run at scale → Phase 6 staging** |
| 12 | Backup/restore drill | 🟡 Harness-ready | `scripts/backup_restore_drill.sh` (restore-verified); **scheduled run on managed DB → Phase 6** |

The three 🟡 items are deferred *honestly*: each needs infrastructure that only exists after Phase 6
deployment (a live Alertmanager, a staging cluster to load, a managed Postgres/Qdrant to drill). The
**automation is committed now** so execution in Phase 6 is `make load` / `make`-driven, not net-new work.

## Audit results (this pass)

- **Python deps:** `pip-audit` → **no known vulnerabilities**.
- **Web deps:** `pnpm audit` found 1 moderate (PostCSS `<8.5.10` XSS via `next`) → fixed with a pnpm `overrides` pin to `>=8.5.10`; re-audit clean.
- **SAST:** `bandit` on first-party source → **0 issues** (one intentional best-effort `try/except/pass` in `tracing.py` carries a justified `# nosec B110`). Tests excluded (their `assert` use is correct).
- **Secrets:** `detect-secrets` flagged only known non-secrets — `.env.example` placeholders, local-dev `docker-compose.yml` passwords, and two test fixtures with fake keys — all captured in the reviewed `.secrets.baseline`. CI fails only on *new* secrets.

## License policy

Allowed: permissive (MIT, BSD-2/3, Apache-2.0, ISC, Python-2.0). **Blocked in CI:** GPL, AGPL, LGPL, SSPL.
- **MPL-2.0** (`certifi`, `orjson`, `pathspec`, `tqdm`) is **accepted** — file-level copyleft, triggered only by modifying those files, which we don't.
- `UNKNOWN` entries are our own 7 workspace packages (first-party, not third-party risk) and `voyageai` (MIT upstream).

## Log-retention policy

- **Format:** one JSON object per line to **stdout** (12-factor); the platform (Loki/CloudWatch in Phase 6) owns shipping + retention.
- **PII:** prompts/responses are **never** logged (S12 redaction); logs carry only `trace_id`/`span_id`/`run_id`/`tenant_id` + bounded metadata. Full prompt/response inspection lives in Langfuse, access-controlled.
- **Retention targets:** app logs **30 days** hot / 1 year cold (audit); traces **14 days**; metrics **15 months** (Prometheus/managed). Right-to-be-forgotten covers the durable run store; logs are PII-free so no per-user deletion is required there.

## How to run the hardening pass locally

```bash
uv sync --group audit
make audit          # pip-audit + pnpm audit + bandit + license gate
make secrets        # detect-secrets against the baseline
make chaos          # resilience tests
# load + backup drill need a running stack (Phase 6 / local compose):
make services && make api & make worker &
make load           # k6 ramp to 50 concurrent
bash scripts/backup_restore_drill.sh
```
CI (`.github/workflows/ci.yml`) runs the green gate + every audit on push/PR.
