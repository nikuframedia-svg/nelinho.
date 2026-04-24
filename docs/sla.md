# ProdPlan ONE — Service Level Agreement (Sprint J.5)

> Status: **Internal — Nelo pilot (2026-Q2)**. Revisit after the Sprint G
> connection to the live ERP is complete and we have ≥30 days of
> production telemetry.

## 1. Scope

This SLA covers the ProdPlan ONE deployment running on-prem at Nelo
(Vila Nova de Gaia). The system has six operating modules — Plan /
Profit / HR / Supply / Copilot / Governance — and one realtime
sidecar (Kafka + SSE bridge + Ollama).

Out of scope:

- The Windows tablets on the shop floor (hardware + OS patched by
  Nelo IT).
- The ERP source-of-truth itself (Primavera / SQL Server). Our
  adapter *reads* it; the ERP's availability is its owner's
  concern.
- Internet connectivity between the factory and the Nelo office.

## 2. Service level objectives (SLOs)

| SLO | Target | Measurement window | Telemetry |
|---|---|---|---|
| **Availability (API)** | ≥ 99.0% | 30 days rolling | `up{job="prodplan-api"}` + blackbox probe |
| **Availability (SSE)** | ≥ 99.0% | 30 days rolling | blackbox probe on `/v1/realtime/health` |
| **Latency (P95, read endpoints)** | ≤ 500 ms | 24 h rolling | `prodplan_http_request_duration_seconds{quantile="0.95", method="GET"}` |
| **Latency (P95, CPO schedule)** | ≤ 90 s | 24 h rolling | `prodplan_cpo_solve_duration_seconds{quantile="0.95"}` |
| **SSE freshness** | ≤ 2 s from commit to delivery | 1 h rolling | `prodplan_outbox_dispatcher_latency_seconds{quantile="0.95"}` |
| **Success rate (writes)** | ≥ 99.9% | 7 days rolling | `1 - rate(prodplan_http_requests_total{status=~"5..",method!="GET"})` |
| **TrustIndex floor** | all entities ≥ 0.60 for auto-commit | continuous | `prodplan_trust_index_score` |

A month that breaches *any* availability target triggers an incident
review (see §6). Repeated latency breaches without availability loss
trigger a capacity planning review.

## 3. Recovery targets

| Signal | Target | Notes |
|---|---|---|
| **RTO** (time to restore service from full outage) | ≤ 2 h | Includes DB restore from the latest pgBackRest full + WAL replay. See `docs/disaster-recovery.md`. |
| **RPO** (data lost on catastrophic failure) | ≤ 1 h | Postgres WAL archived every 5 min; Kafka retains 7 days. |
| **Backup success cadence** | 24 h | `BackupStale` alert fires at 26 h. |
| **DR drill** | every 3 months | Dry-run restore on a staging box; timer records the observed RTO. |

## 4. Error budget

A month has ~720 hours. A 99% SLO gives us **7.2 hours of budget** per
month for planned maintenance + unplanned outages. Any burn pattern
crossing 50% before day 15 triggers a freeze on non-essential
deploys.

| Cumulative downtime | Action |
|---|---|
| < 1 h  | Normal ops. |
| 1-3 h  | Bar-raise on deploys: Luis + one reviewer required. |
| > 3 h  | Deploy freeze until the next calendar month unless the fix itself is a P1 regression. |
| > 7.2 h | SLA breach. Incident review within 5 business days. |

## 5. Monitoring & paging

| Channel | Severity | Response target |
|---|---|---|
| Grafana dashboard | info + warning + critical | Visual only. |
| Alertmanager → SMS oncall | **critical** | Acknowledged within 15 min, 24×7. |
| Alertmanager → email | warning | Acknowledged within 1 business day. |
| Alertmanager → e-mail digest | info | Daily 09:00. |

Alert definitions live in `monitoring/prometheus/alerts.yml`. Runbook
links are embedded in every alert.

## 6. Incident handling

1. **Acknowledge** the page within 15 min.
2. **Mitigate** (restore service, not necessarily root-cause the bug).
3. **Communicate** in the #ops channel at the 30-min mark, then every
   60 min until closure.
4. **Post-mortem** within 5 business days for every sev-1 incident.
   Template lives in `docs/runbooks/incident-template.md`.

## 7. Maintenance windows

- **Weekly**: Sunday 04:00-06:00 WET. APScheduler cron-heavy jobs
  (AdaptiveFitnessWeights retrain, preference rule detection) already
  run at 02:00/03:00 so the window is clear for OS patching.
- **Monthly**: First Sunday 03:00-05:00 WET reserved for Postgres
  vacuum analyze + index rebuild.
- **Quarterly**: DR drill (see §3).

## 8. Change management

| Change type | Approval | Rollback window |
|---|---|---|
| **Code deploy** (non-P1) | Luis + one reviewer | within 24 h of deploy |
| **Migration** (Alembic) | Luis + dry-run on staging | 0 — migrations are forward-only once applied |
| **Config change** (TenantConfig) | Luis, in an audit-logged request | unlimited — history is kept |
| **Scheduler knob** (FitnessConfig) | Luis | re-run schedule |
| **Dependency bump** | PR with regression run | revert via git |

## 9. Data retention

| Dataset | Retention | Location |
|---|---|---|
| Postgres operational tables | 7 years (legal minimum for production records) | `pgBackRest` daily full + 7 days WAL |
| Kafka topics | 7 days | On-box disk, rotated by Kafka retention |
| Prometheus metrics | 30 days | TSDB local |
| Grafana dashboards | versioned in `monitoring/grafana/` | git |
| DPO datasets (`datasets/dpo_*.jsonl`) | 12 months | file system, versioned via monthly rotation |
| Logs (JSON via `deploy/logging.yaml`) | 90 days hot + 1 year cold | `/var/log/prodplan/` |

## 10. Review cadence

- **Monthly**: SLO attainment + error budget burn. Luis runs the
  query, pastes the numbers at the bottom of this doc.
- **Quarterly**: this document is revisited. Bump targets as
  confidence builds; don't reduce them without an explicit risk
  note in the commit message.
- **After Sprint G connection**: re-calibrate the latency SLOs once
  real ERP round-trip times are measured.

---

*This SLA lives in git at `docs/sla.md`. Any change is a PR.*
