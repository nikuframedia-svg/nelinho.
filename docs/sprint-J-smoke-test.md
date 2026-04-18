# Sprint J — Smoke Test Manual

Este documento descreve como validar end-to-end a ingestão do ficheiro
`Folha_IA_extra.xlsx` após as mudanças da Sprint J (dev).

O CI corre apenas testes unitários (mock-heavy), por isso este smoke é um
passo **manual** depois de instalar o `requirements.txt` completo num dev
env com acesso ao ficheiro real (57 MB).

---

## 1. Pré-requisitos

- Python 3.11 venv com o **requirements.txt completo instalado**
  (pandas + numpy + openpyxl + prophet + scikit-learn; o
  `requirements-test.txt` lean do CI não chega)
- `PostgreSQL` a correr (a ingestão precisa de DB para persistir
  `IngestionRun`; as tabelas curadas são in-memory no engine, mas o
  `CopilotAlert` da drift bridge persiste)
- `Redis` (opcional — só afecta copilot)
- Ficheiro em `c:/Users/User/nelinho/Folha_IA_extra.xlsx` (já presente)

```powershell
cd c:\Users\User\nelinho
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 2. Arranque

```powershell
# Opcional: activa o watcher para re-ingestão automática
$env:PRODPLAN_FACTORY_FILE = "c:\Users\User\nelinho\Folha_IA_extra.xlsx"
$env:PRODPLAN_FACTORY_AUTO_ACTIVATE = "true"

.venv\Scripts\python.exe -m uvicorn src.main:app --reload
```

Nos logs deves ver:

```
Scheduler started: alerts every 15m for 0 tenant(s); daily_feedback='30 0 * * *' UTC
Factory watcher registered (every 60 min)
```

Se `PRODPLAN_FACTORY_FILE` não estiver setada aparece em vez disso:
`Factory watcher disabled: PRODPLAN_FACTORY_FILE not set`.

---

## 3. Ingestão manual (ingest-by-path)

Mais rápido que o upload multipart (o ficheiro é 57 MB):

```bash
curl -X POST http://localhost:8000/v1/factory/ingest-by-path \
  -H "Content-Type: application/json" \
  -d '{
    "path": "c:/Users/User/nelinho/Folha_IA_extra.xlsx",
    "auto_activate": true,
    "user": "luis"
  }'
```

Resposta esperada (~3–5 min para 1.1M linhas):

```json
{
  "success": true,
  "ingestion_id": "<UUID>",
  "status": "succeeded",
  "is_duplicate": false,
  "total_rows_raw": 1108123,
  "total_rows_curated": 990000,
  "quality_gate_status": "passed",
  "errors": [],
  "warnings": [...]
}
```

Se correres uma segunda vez sem mudar o ficheiro deves obter
`is_duplicate: true, status: "skipped"` (idempotência por hash).

---

## 4. Verificação das tabelas curadas

```bash
curl http://localhost:8000/v1/factory/meta/active-run
# -> has_active: true, active_ingestion_id: <UUID>

curl http://localhost:8000/v1/factory/meta/ingestions
# -> 1 entry with status=succeeded, quality_gate_status=passed

curl http://localhost:8000/v1/factory/meta/quality-report/<UUID>
# -> total_checks, passed_checks
```

---

## 5. Queries semânticas (devem agora devolver dados reais)

```bash
# WIP real
curl http://localhost:8000/v1/factory/semantic/queries/wip

# Bottlenecks
curl http://localhost:8000/v1/factory/semantic/queries/bottlenecks?top_n=10

# Skills risk (SPOF detection)
curl http://localhost:8000/v1/factory/semantic/queries/skills-risk?min_capable=2

# Quality analysis (89k erros)
curl http://localhost:8000/v1/factory/semantic/queries/quality?top_errors=10
```

Cada resposta tem `data_confidence`, `trust_status`, `semantic_label`.
Valores esperados (aproximados do dataset NELO):

- `wip.open_orders`: ~740 barcos
- `bottlenecks.critical_count`: 3-5 fases (Laminagem, Pintura, Acabamento)
- `skills_risk.spof_count`: 2-3 fases com 1 trabalhador
- `quality.total_errors`: 89 836

---

## 6. CPO v4 com dados reais

```bash
curl -X POST http://localhost:8000/v1/plan/cpo/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "horizon_days": 14,
    "time_limit_sec": 20,
    "population_size": 50,
    "generations": 20
  }'
```

Agora que a `FactoryState.load()` encontra skill_matrix, molds, durações
históricas, o scheduler devolve um schedule real (não mais `INSUFFICIENT_DATA`).

Verificar em `cpo_meta`:

- `baseline_fitness`: valor inicial (identity chromosome)
- `best_fitness`: após GA
- `improvement_pct`: >= 0 (safety net garante nunca pior)
- `safety_net_triggered`: `false` no caso geral

---

## 7. Drift bridge — teste forçado

Para ver a bridge drift→alert disparar, ativa duas ingestões diferentes
em sequência (edita uma célula do Excel para mudar o hash):

```bash
# 1. Ingere v1
curl -X POST http://localhost:8000/v1/factory/ingest-by-path ...

# 2. Edita o Excel manualmente (adiciona/remove uma coluna)

# 3. Ingere v2
curl -X POST http://localhost:8000/v1/factory/ingest-by-path ...

# 4. Activar v2
curl -X POST http://localhost:8000/v1/factory/activate/<v2-id> \
  -H "Content-Type: application/json" \
  -d '{"user":"luis"}'
# -> drift_alert_id: <UUID>  (não null se schema mudou)

# 5. Confirmar alerta criado
curl http://localhost:8000/v1/copilot/alerts?status=active
# -> alert com code=FACTORY_SCHEMA_DRIFT, severity=WARN|CRITICAL
```

---

## 8. Watcher

```bash
curl http://localhost:8000/v1/factory/watcher/status
# -> {
#   "enabled": true,
#   "watch_path": "c:/Users/User/nelinho/Folha_IA_extra.xlsx",
#   "last_hash": "<sha256>",
#   "last_ingestion_id": "<UUID>",
#   "last_error": null
# }
```

O job corre a cada 60 min (config default). Para baixar ao vivo:

```python
from src.factory_data_product.watcher import register_with_scheduler
from src.shared.scheduler import get_scheduler
register_with_scheduler(get_scheduler(), interval_minutes=5)
```

---

## Troubleshooting

| Sintoma | Causa provável | Fix |
|---|---|---|
| `openpyxl` not installed | venv leve (requirements-test) | `pip install -r requirements.txt` |
| Ingestão demora >10 min | Disk I/O saturated | Expected; monitora `total_rows_raw` incremental em logs |
| `quality_gate_status: failed_blocking` | Colunas novas/faltam | Ver `meta/quality-report/<id>` para detalhes |
| CPO `INSUFFICIENT_DATA` mesmo após ingest | Ingestão não ativada | `POST /activate/<id>` ou `auto_activate=true` |
| `Factory watcher disabled` no boot | env var não setada | Define `PRODPLAN_FACTORY_FILE` |
