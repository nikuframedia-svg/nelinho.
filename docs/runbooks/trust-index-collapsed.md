# Runbook: TrustIndexCollapsed

**Alert:** `min(prodplan_trust_index_score) < 0.60` for 15 min.
**Severity:** warning.

## Blast radius

Schedule commits with the affected entity are blocked from
auto-committing (governance gate). They still go through, but need a
manual approval in `/admin/learned-rules` or the Timeline UI's decide
flow.

## Diagnose

```bash
# Which entity is below 0.60?
curl -s http://localhost:8000/metrics \
  | grep prodplan_trust_index_score | awk '{print $2, $1}' \
  | sort -n | head

# DQA issue history for the tenant:
curl -sf http://localhost:8000/v1/admin/dqa/issues?limit=50 \
  -H "X-Tenant-Id: <tenant>" | jq '.[] | [.issue_type, .entity_type, .entity_id] | @csv'
```

## Mitigate

1. If the issue type is `out_of_range`, run the auto-repair engine
   (`POST /v1/admin/dqa/repair`).
2. If it's `missing_field`, backfill via the ingestion adapter (Nelo
   Excel re-ingest or ERP re-pull).
3. If it's genuine bad data (operator typo), mark as resolved via
   the DQA page and let the score recover over the next refresh
   window.

## Verify

Gauge rises back above 0.60. `/admin/learned-rules` shows "Confiança"
badges green.
