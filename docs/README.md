# ProdPlan ONE v3.3 - Documentação Técnica

## Visão Geral

Esta documentação cobre a implementação completa das 4 lacunas críticas (P0+P1) do ProdPlan ONE v3.3 - Decision Intelligence Platform para manufacturing industrial.

## Estrutura da Documentação

### Arquitetura

1. **[Event-Driven Architecture](event-driven-architecture.md)**
   - Outbox Pattern para exactly-once delivery
   - Kafka producer com circuit breaker e retry
   - DLQ (Dead Letter Queue) handling
   - SLO compliance e monitoramento

### Módulos de Funcionalidade

2. **[Data Quality Autopilot](data-quality-autopilot.md)**
   - TrustIndex Calculator (4 componentes)
   - Quality Gates Middleware
   - Auto-Repair Engine
   - Drift Detection (Kolmogorov-Smirnov)

3. **[Copilot Actions](copilot-actions.md)**
   - 3 modos de execução (PREVIEW, SANDBOX, EXECUTE)
   - Runbook Engine com branching logic
   - Sandbox isolation (nested transactions)
   - Rollback mechanism (24h window)

4. **[Supply Chain Planning](supply-chain-planning.md)**
   - Inventory Ledger (Event Sourcing)
   - Prophet Forecasting (ARIMA)
   - ROP Calculator (Reorder Point)
   - ABC Analysis (Pareto 80/15/5)

### Operações

5. **[Deployment Guide](deployment-guide.md)**
   - Setup e configuração inicial
   - Database migrations (Alembic)
   - Kafka topics setup
   - Prometheus metrics
   - Troubleshooting

## Quick Start

```bash
# 1. Setup ambiente
docker-compose up -d

# 2. Criar topics Kafka
./scripts/kafka_topics_init.sh

# 3. Aplicar migrations
alembic upgrade head

# 4. Iniciar aplicação
uvicorn src.main:app --reload

# 5. Iniciar dispatcher
python scripts/run_dispatcher.py
```

## Testes

### Estrutura

```
tests/
├── conftest.py                    # Fixtures comuns
├── test_outbox_pattern.py         # Outbox Pattern
├── test_kafka_idempotency.py      # Kafka idempotency
├── test_dlq_handling.py           # DLQ handling
├── test_trust_index_calc.py       # TrustIndex calculation
├── test_auto_repair.py            # Auto-repair strategies
├── test_drift_detection.py        # Drift detection
├── test_action_execution.py       # Copilot actions (3 modos)
├── test_sandbox_isolation.py      # Sandbox isolation
├── test_runbook_engine.py         # Runbook execution
├── test_rop_calculation.py        # ROP calculation
├── test_abc_analysis.py           # ABC classification
├── test_arima_forecast.py         # Prophet forecasting
├── e2e_test_all_lacunae.py        # E2E integration
└── load_test.py                   # Load testing (SLO)
```

### Executar Testes

```bash
# Todos os testes
pytest tests/ -v

# Com cobertura
pytest tests/ --cov=src --cov-report=html

# Testes específicos
pytest tests/test_outbox_pattern.py -v
pytest tests/e2e_test_all_lacunae.py -v
pytest tests/load_test.py -v
```

## SLO Compliance

| Métrica | Target | Status |
|---------|--------|--------|
| Outbox dispatcher p95 | ≤ 200ms (1k/s) | ✅ Testado |
| TrustIndex calculation | < 10ms | ✅ Testado |
| Copilot action p95 | ≤ 2s | ✅ Testado |
| Forecast WMAPE | < 15% | ✅ Testado |
| Replan latency p95 | ≤ 30s (50k orders) | ✅ Testado |

## Métricas Prometheus

Endpoint: `GET /metrics`

**Métricas expostas**:
- `outbox_dispatcher_latency_seconds` (histogram)
- `kafka_producer_success_total` (counter)
- `kafka_producer_failure_total` (counter)
- `trust_index_score` (gauge)
- `copilot_action_execution_time_seconds` (histogram)

## Monitoramento

### Grafana Dashboards

Dashboards recomendados:
1. **Event Throughput**: Eventos/s por tipo
2. **Dispatcher Latency**: p50, p95, p99
3. **TrustIndex Distribution**: Histograma
4. **Copilot Actions**: Execuções por modo
5. **DLQ Rate**: Eventos em DLQ / Total

## Troubleshooting

Ver seção "Troubleshooting" em cada documento:
- [Event-Driven Architecture - Troubleshooting](event-driven-architecture.md#troubleshooting)
- [Data Quality Autopilot - Troubleshooting](data-quality-autopilot.md#troubleshooting)
- [Copilot Actions - Troubleshooting](copilot-actions.md#troubleshooting)
- [Supply Chain Planning - Troubleshooting](supply-chain-planning.md#troubleshooting)
- [Deployment Guide - Troubleshooting](deployment-guide.md#troubleshooting)

## Referências

- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [Prophet Documentation](https://facebook.github.io/prophet/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Prometheus Documentation](https://prometheus.io/docs/)

## Suporte

Para questões ou problemas:
1. Verificar documentação específica do módulo
2. Verificar logs (`docker-compose logs`)
3. Verificar métricas Prometheus (`/metrics`)
4. Consultar seção Troubleshooting

---

**Versão**: 3.3  
**Última Atualização**: 2024  
**Status**: Production Ready ✅










