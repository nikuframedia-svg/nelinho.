# Incident response playbook

> Sprint Q.13.F F.6 — top-level "what to do when X happens" with
> roles, decision tree, and escalation paths. Per-alert runbooks live
> in their own pages (linked below); this file is the cold-open
> reference an SRE reads at 03:00 with a phone in one hand.

## Roles during an incident

| Role            | Who               | Responsibility                                               |
|-----------------|-------------------|--------------------------------------------------------------|
| **IC**          | first responder   | Owns the incident timeline. Calls escalation. Posts updates. |
| **Comms**       | second responder  | Talks to stakeholders (CEO, client). Frees the IC to focus.  |
| **Subject**     | domain owner      | Pulled in by IC for the area in question (DB, ML, frontend). |
| **Scribe**      | anyone available  | Writes up the timeline as it happens for the post-mortem.    |

A single-person on-call MUST take IC + Scribe; if the incident lasts
> 30 min, page a second responder for Comms before fatigue sets in.

## Severity ladder

| SEV | Meaning                                       | Response                |
|-----|-----------------------------------------------|-------------------------|
| 1   | Production down, revenue/quality at risk      | Page on-call immediately, CEO notified within 15 min |
| 2   | Major degradation (CPO failing, dashboard 5xx)| Page on-call within 15 min |
| 3   | Single feature degraded, workaround exists    | Same-day; no page out of hours |
| 4   | Cosmetic / data quality drift                 | Next business day      |

## Top 10 incidents — decision tree

For each, the **first action** column is what to do *before* opening
a runbook. The runbook column is the deep dive.

| # | Symptom                                         | First action                                          | SEV | Runbook                                       |
|---|--------------------------------------------------|-------------------------------------------------------|-----|-----------------------------------------------|
| 1 | API returning 5xx > 5% for 2+ min                | `curl /health/ready`; check `prodplan_http_requests_total{status=~"5.."}` | 1 | [high-5xx-rate.md](high-5xx-rate.md)         |
| 2 | API totally unreachable                          | Check Caddy `systemctl status`; check process running | 1 | [api-down.md](api-down.md)                   |
| 3 | Postgres connections at 80% / queries timing out | `SELECT count(*) FROM pg_stat_activity` per role     | 1 | [postgres-down.md](postgres-down.md)         |
| 4 | Kafka producer failure spike                      | Tail `kafka-producer.log`; check broker status        | 2 | [kafka-down.md](kafka-down.md)               |
| 5 | Ollama down → Copilot returns "model unavailable"| `curl ollama/api/tags`; restart `ollama` service     | 3 | [ollama-down.md](ollama-down.md)             |
| 6 | TrustIndex < 0.75 → write-gate refusing all      | Check `prodplan_trust_index_score{component=*}`       | 1 | [trust-index-collapsed.md](trust-index-collapsed.md) |
| 7 | Disk > 85% on data volume                         | `df -h`; check Postgres WAL archive                   | 2 | [disk-full.md](disk-full.md)                 |
| 8 | Excel ingest stuck > 30 min                       | Check `INGEST_STARTED` event in outbox; tail ingest job log | 3 | (no dedicated runbook; see playbook below)   |
| 9 | CPO scheduling timeout > 60s sustained            | Check `prodplan_http_request_duration_seconds_bucket{path_template=~"/v1/plan/cpo.*"}` p99 | 2 | [perf.md](perf.md)                           |
| 10 | Daily backup > 12h stale                          | Check `pgbackrest info`; check cron last-success      | 2 | [backup-stale.md](backup-stale.md)           |

## Escalation paths

```
SEV 1  ──>  Primary on-call (page)
                │ no ack in 5 min
                ▼
            Secondary on-call (page)
                │ no ack in 5 min
                ▼
            Engineering manager (call)
                │ no ack in 5 min
                ▼
            CTO (call)
```

```
SEV 2  ──>  Primary on-call (page)
SEV 3  ──>  Same-day Slack mention; no page outside hours
SEV 4  ──>  Issue tracker
```

## Communications template

Open a thread in `#prodplan-incidents` Slack at IC declaration.

```
:rotating_light: SEV-{1,2,3,4} — {one-line symptom}
IC: @user
Comms: @user (or "TBD")
Started: HH:MM
Impact: {one sentence — who's affected, what's degraded}
Next update: HH:MM (every 15 min for SEV 1, every 30 for SEV 2)
```

Update the same thread every cadence even if "still investigating".
Silence breeds CEO calls.

## Excel ingest stuck (item 8)

No dedicated runbook yet — the symptom is rare. Quick triage:

```bash
# Is the ingest job running?
ps -ef | grep -i ingest

# Last ingestion_run row + status
psql $DB -c "SELECT id, status, started_at, finished_at \
  FROM factory_meta.ingestion_run \
  ORDER BY started_at DESC LIMIT 5;"

# Tail the ingest job log
journalctl -u prodplan-ingest -n 200 --no-pager
```

Common fixes:
- Stuck on Excel reader: kill the job, re-trigger via
  `POST /v1/factory-data-product/ingest/trigger`. Idempotent.
- Stuck on quarantine: check `factory_quarantine.*` row counts; if
  one row blocks the whole load, mark it manually.

## Post-incident

Within 24h of resolution:
1. Open a post-mortem doc using
   [`incident-template.md`](incident-template.md) as the skeleton.
2. File at least one follow-up issue per "what should have caught
   this earlier" insight.
3. Schedule the review meeting for the same week.

The point of the post-mortem is **what to change**, not **who to
blame**. The five whys end at a system gap, never at a person.

## Related

- Per-alert runbooks: see [index.md](index.md).
- Performance investigation (slow query / index audit):
  [perf.md](perf.md).
- Deployment procedure: [deploy.md](deploy.md).
