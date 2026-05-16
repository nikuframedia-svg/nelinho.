# ERP → Postgres sync — runbook (Q.20)

Como pôr os dados reais da fábrica NELO a fluir do ERP (SQL Server
`MAR-KAYAKS`) para o Postgres do ProdPlan ONE.

## 1. Pré-requisito (uma vez) — IT NELO aplica as views

O adapter só toca em views `vw_pp1_*`, nunca nas tabelas raw. Entregar
`agent_docs/views_pp1.sql` a IT NELO:

1. IT NELO confirma os nomes raw marcados `-- CONFIRM` contra o schema real.
2. Aplica o script na BD do ERP (`CREATE OR ALTER VIEW`).
3. Dá `GRANT SELECT` nas 10 views ao login read-only do ProdPlan.

Os **nomes das colunas de saída** (`AS xxx`) não podem mudar — o adapter
depende deles.

## 2. Configurar o ProdPlan

Em `/etc/prodplan/env` (ou `.env` em dev):

```
SQLSERVER_ENABLED=true
SQLSERVER_URL=mssql+aioodbc://prodplan_ro:***@mar-kayaks.lan:1433/NELO_ERP?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```

Com `SQLSERVER_ENABLED=false` (default de dev) o sync faz skip limpo.

## 3. Verificar a ligação

```python
from src.shared.config import settings
from src.infrastructure.erp.sqlserver import NeloERPAdapter

adapter = NeloERPAdapter.from_settings(settings)
assert await adapter.health_check()                 # SELECT 1
assert await adapter.view_available("vw_pp1_produto")  # uma view por dados
await adapter.close()
```

## 4. Correr o sync

```bash
# todos os mirrors
python scripts/sync_nelo_to_postgres.py

# um só
python scripts/sync_nelo_to_postgres.py --only master

# incremental (quality / time_mining) a partir de uma data
python scripts/sync_nelo_to_postgres.py --only quality --since 2025-01-01
```

Cada mirror escreve uma linha em `core.etl_run` (`source`, `status`,
`rows_read/inserted/updated/skipped`). Auditar:

```sql
SELECT source, status, started_at, rows_read, rows_inserted, rows_updated
FROM core.etl_run ORDER BY started_at DESC LIMIT 20;
```

## 5. Automático

O scheduler regista, por tenant, o job `nelo_erp_sync` (diário 02:00 UTC,
todos os mirrors excepto `time_mining`). O `time_mining` corre semanalmente
(job próprio — Q.20.F). Ambos gated por `SQLSERVER_ENABLED`.

## Mirrors (rollout incremental Q.20)

| Mirror | Sub-sprint | Origem (view) | Destino |
|---|---|---|---|
| `master` | Q.20.B | produto / produto_fase / fases_producao / entidade / produto_componente | `core.products`, `core.employees`, `core.bom_items`, `plan.routing_template*` |
| `molds` | Q.20.C | (Excel) + `vw_pp1_moldes` reconcile | `plan.mold` |
| `skills` | Q.20.D | fases_producao / entidade_fase | `hr.skills`, `hr.employee_skills` |
| `quality` | Q.20.E | offp_probs / of_checklist | `quality.error_catalog`, `quality.rework_entry` |
| `time_mining` | Q.20.F | of_fp (live, batched) | `plan.routing_template_phase` p50/p90 |

Idempotente: re-correr um mirror nunca duplica linhas (upsert por
business-key).
