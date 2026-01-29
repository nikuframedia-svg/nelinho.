# Deployment Guide - ProdPlan ONE v3.3

## Pré-requisitos

### Software

- **Python**: 3.11+
- **PostgreSQL**: 14+
- **Kafka**: 2.8+ (com Zookeeper)
- **Docker** & **Docker Compose**: (recomendado)

### Dependências

Ver `requirements.txt` para lista completa.

**Principais**:
- `fastapi>=0.104.0`
- `sqlalchemy>=2.0.0`
- `aiokafka>=0.10.0`
- `prophet>=1.1.5`
- `prometheus-client>=0.19.0`

## Configuração Inicial

### 1. Variáveis de Ambiente

Criar `.env` a partir de `.env.example`:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/prodplan

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CLIENT_ID=prodplan-producer

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### 2. Docker Compose (Desenvolvimento)

```bash
# Iniciar stack completa (PostgreSQL, Kafka, Zookeeper)
docker-compose up -d

# Verificar serviços
docker-compose ps
```

**Serviços**:
- PostgreSQL: `localhost:5432`
- Kafka: `localhost:9092`
- Zookeeper: `localhost:2181`

### 3. Criar Topics Kafka

```bash
# Executar script de inicialização
./scripts/kafka_topics_init.sh

# Verificar topics criados
docker exec -it kafka kafka-topics.sh --list --bootstrap-server localhost:9092
```

**Topics criados**:
- `prodplan.plan.schedule.committed`
- `prodplan.inventory.movement`
- `prodplan.quality.gate.passed`
- `prodplan.copilot.action.executed`
- `prodplan.dlq`

## Database Setup

### 1. Migrations (Alembic)

```bash
# Aplicar todas as migrations
alembic upgrade head

# Verificar migrations aplicadas
alembic current

# Criar nova migration (se necessário)
alembic revision --autogenerate -m "description"
```

**Migrations**:
- `003_create_event_outbox.py` - Event Outbox Pattern
- `004_create_dqa_tables.py` - Data Quality Autopilot
- `005_create_supply_tables.py` - Supply Chain Planning
- `006_create_copilot_action_logs.py` - Copilot Actions

### 2. Verificar Schema

```sql
-- Verificar tabelas criadas
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Verificar índices
SELECT indexname FROM pg_indexes WHERE schemaname = 'public';
```

## Aplicação

### 1. Instalar Dependências

```bash
# Virtual environment (recomendado)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt
```

### 2. Iniciar Aplicação

```bash
# Desenvolvimento
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Produção (com workers)
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. Verificar Health

```bash
# Health check
curl http://localhost:8000/health

# API docs
curl http://localhost:8000/docs
```

## Outbox Dispatcher

### Background Job

O dispatcher deve rodar como job separado.

**Implementação**:
```python
# scripts/run_dispatcher.py
import asyncio
from src.shared.outbox_dispatcher import OutboxDispatcher

async def main():
    dispatcher = OutboxDispatcher(...)
    await dispatcher.run()  # Loop infinito

if __name__ == "__main__":
    asyncio.run(main())
```

**Executar**:
```bash
python scripts/run_dispatcher.py
```

**Ou via systemd** (produção):
```ini
[Unit]
Description=ProdPlan Outbox Dispatcher
After=network.target

[Service]
Type=simple
User=prodplan
WorkingDirectory=/opt/prodplan
ExecStart=/opt/prodplan/venv/bin/python scripts/run_dispatcher.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Prometheus Metrics

### Endpoint

```http
GET /metrics
```

**Métricas expostas**:
- `outbox_dispatcher_latency_seconds` (histogram)
- `kafka_producer_success_total` (counter)
- `kafka_producer_failure_total` (counter)
- `trust_index_score` (gauge)
- `copilot_action_execution_time_seconds` (histogram)

### Configuração Prometheus

`prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'prodplan'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

## Monitoramento

### Grafana Dashboards

**Dashboards recomendados**:
1. **Event Throughput**: Eventos/s por tipo
2. **Dispatcher Latency**: p50, p95, p99
3. **TrustIndex Distribution**: Histograma de TI
4. **Copilot Actions**: Execuções por modo
5. **DLQ Rate**: Eventos em DLQ / Total

### Alertas

**Alerts críticos**:
- Dispatcher p95 latency > 200ms
- DLQ rate > 1%
- TrustIndex < 0.65 (média)
- Circuit breaker aberto

## Troubleshooting

### Kafka não conecta

```bash
# Verificar Kafka está rodando
docker-compose ps kafka

# Verificar conectividade
docker exec -it kafka kafka-broker-api-versions.sh --bootstrap-server localhost:9092

# Verificar logs
docker-compose logs kafka
```

### Database migrations falham

```bash
# Verificar conexão
psql $DATABASE_URL -c "SELECT version();"

# Reverter migration problemática
alembic downgrade -1

# Reaplicar
alembic upgrade head
```

### Outbox dispatcher não publica

1. Verificar `event_outbox` (status='pending')
2. Verificar logs do dispatcher
3. Verificar Kafka connectivity
4. Verificar circuit breaker (não deve estar aberto)

## Production Checklist

- [ ] Variáveis de ambiente configuradas
- [ ] Database migrations aplicadas
- [ ] Kafka topics criados
- [ ] Outbox dispatcher rodando
- [ ] Prometheus scraping `/metrics`
- [ ] Grafana dashboards configurados
- [ ] Alertas configurados
- [ ] Logs centralizados (opcional)
- [ ] Backup database configurado
- [ ] Health checks funcionando

## Referências

- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Alembic Migrations](https://alembic.sqlalchemy.org/en/latest/)
- [Kafka Quickstart](https://kafka.apache.org/quickstart)
- [Prometheus Setup](https://prometheus.io/docs/prometheus/latest/installation/)










