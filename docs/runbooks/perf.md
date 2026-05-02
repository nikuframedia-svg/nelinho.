# Performance Runbook — slow queries + tracing

> **Sprint Q.13.B (B2)** — wired alongside `alembic 040_slow_query_logging`.

## Quando este runbook se aplica

- Endpoint demora >2s a responder em produção
- CEO Dashboard fica "loading" >5s
- `/v1/plan/cpo/schedule` ultrapassa o budget de 60s
- Alarme `HighRequestLatency` no Prometheus

## Onde olhar primeiro

### 1. Postgres slow query log

A migração `040_slow_query_logging` activa `log_min_duration_statement = 1000`,
ou seja, qualquer query >1s aparece no log do Postgres com texto completo.

```bash
# Em produção (NELO torre):
sudo journalctl -u postgresql -n 200 --no-pager | grep "duration:"

# Filtrar por queries específicas:
sudo journalctl -u postgresql --since "1 hour ago" | grep -E "duration: [0-9]{4,}"
```

Padrões típicos a procurar:
- `factory_curated.allocation` sem index → adicionar à `ix_curated_allocation_*`
- `production_schedule` filtrado por `tenant_id + date_range` sem composite index
- N+1 do CopilotMessage join — usar `selectinload` em vez de lazy load

### 2. Prometheus latency histogram

```promql
# p95 latency por endpoint
histogram_quantile(0.95,
  sum by (path_template, le) (
    rate(prodplan_http_request_duration_seconds_bucket[5m])
  )
)

# Endpoints acima de SLO
histogram_quantile(0.95, ...) > 2
```

### 3. CPO budget exhaustion

`CPOConfig.total_budget_s = 60`. Se a engine ultrapassa, é normalmente:
- GA com pop/gen alto sem early-exit (verificar `engine.py:_run_genetic_algorithm`)
- L-RHO sem ortools instalado (`HAS_ORTOOLS=False` graceful, mas log WARN)
- MAP-Elites grid demasiado fino (>200 cells)

## Checklist de mitigação

1. [ ] Identificar query lenta no log
2. [ ] `EXPLAIN ANALYZE` no psql para confirmar plan
3. [ ] Adicionar index se table scan
4. [ ] `VACUUM ANALYZE` na tabela suspeita
5. [ ] Se for endpoint, adicionar pagination (`limit`/`offset`)
6. [ ] Re-medir em staging antes de produção

## Tunables (ConfigStore)

- `cpo.total_budget_s` (default 60.0) — orçamento total CPO
- `cpo.greedy_budget_s` (default 2.0)
- `cpo.ga_budget_s` (default 30.0)
- `cpo.cpsat_budget_s` (default 15.0)

Mexer em ConfigStore (NÃO em código). Cada alteração fica audit-tracked.

## Recuperação se log enche disco

```bash
# Postgres logs em /var/log/postgresql/
sudo du -sh /var/log/postgresql/
# Se >2GB, rotate:
sudo systemctl reload rsyslog  # se usar rsyslog
# Ou desligar temporariamente (NÃO em produção long-term):
psql -c "ALTER SYSTEM SET log_min_duration_statement = -1; SELECT pg_reload_conf();"
```

## Referências

- `alembic/versions/040_slow_query_logging.py` — migração que activa
- `monitoring/prometheus/alerts.yml` — alertas que disparam (HighRequestLatency)
- `src/shared/http_metrics_middleware.py` — onde os histograms são emitidos
- Sprint Q.13.B (B2) — adição original

## Não fazer

- ❌ Reverter `040_slow_query_logging` apenas porque o log "está cheio". O log é o sinal — desligar é cegar-se.
- ❌ Subir o threshold acima de 5000ms sem aprovação CEO. Operações lentas são bug, não feature.
- ❌ Escrever EXPLAIN dentro de transacções de escrita — usa réplica ou session separada.
