# Runbook: High5xxRate

**Alert:** 5xx rate > 5% for 5 min. **Severity:** critical.

## Diagnose

```bash
# Which routes are failing?
curl -s http://localhost:8000/metrics \
  | grep prodplan_http_requests_total | grep '5..' | sort -rnk 2 | head

# Recent app tracebacks
journalctl -u prodplan-api --since "15 min ago" -n 500 \
  | grep -E 'ERROR|Traceback' -A 10
```

Top suspects:

1. **DB connection pool exhausted** → check `PostgresConnectionsNearLimit`.
2. **Kafka producer timing out** → Kafka broker issue (see
   [kafka-down.md](kafka-down.md)).
3. **LLM rate limits / Ollama timeouts** → see [ollama-down.md](ollama-down.md).
4. **Recent deploy** → `git log --oneline -5` on main.

## Mitigate

- Rollback the last deploy if the timing correlates.
- Increase pool size (`DATABASE_POOL_SIZE` env var), restart app.
- Scale Ollama request concurrency down if GPU OOMing.

## Verify

`1 - rate(prodplan_http_requests_total{status=~"5.."}[5m]) /
rate(prodplan_http_requests_total[5m]) > 0.99` for 10 min.
