# CONTRATO 010 — Factory Data Product

## Status
**EM IMPLEMENTAÇÃO**

## Objectivo
Implementar um *data product* industrial, auditável e idempotente para ingestão de Excel, com:
- Base de dados separada `prodplan_factory`
- Camadas RAW/CURATED/META/SEMANTIC
- Qualidade com gates bloqueantes
- Activação/rollback lógico por `active_ingestion_id`
- API read-only para consumo por backend/frontend/serviços

## Princípios Inegociáveis

| # | Princípio | Implementação |
|---|-----------|---------------|
| 1 | RAW é append-only | Nunca UPDATE/DELETE em `factory_raw.*` |
| 2 | Rollback é lógico | Troca de `active_ingestion_id`, sem apagar dados |
| 3 | Idempotência por hash | Re-upload do mesmo ficheiro = SKIP |
| 4 | Sem SQL livre | Apenas views allow-listed em `factory_semantic` |
| 5 | Auditoria primeiro | Cada registo tem lineage (ingestion_id, sheet, row, hashes) |
| 6 | PII/Custo protegido | Política explícita de acesso; negar por defeito |

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        EXCEL FILE                                │
│              (Folha_IA_extra.xlsx ou similar)                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     INGEST ENGINE                                │
│  1. Calcular file_sha256                                        │
│  2. Verificar duplicado (idempotência)                          │
│  3. Extrair folhas → factory_raw.excel_row                      │
│  4. Quality gates → factory_meta.quality_check_result           │
│  5. Se BLOCKING fail → status=failed, STOP                      │
│  6. Curar → factory_curated.*                                   │
│  7. status=succeeded                                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│factory_meta │   │factory_raw  │   │factory_curated│
│             │   │             │   │               │
│ingestion_run│   │excel_row    │   │order          │
│active_run   │   │(append-only)│   │order_phase    │
│quality_check│   │             │   │phase_capacity │
│             │   │             │   │mold           │
│             │   │             │   │skill_matrix   │
└─────────────┘   └─────────────┘   └───────┬───────┘
                                            │
                                            ▼
                                   ┌─────────────────┐
                                   │factory_semantic │
                                   │                 │
                                   │v_lead_time_hist │
                                   │v_backlog_fase   │
                                   │v_bottlenecks    │
                                   │v_mold_conflicts │
                                   │v_quality_hotspot│
                                   │v_skill_risk     │
                                   └────────┬────────┘
                                            │
                                            ▼
                                   ┌─────────────────┐
                                   │  API READ-ONLY  │
                                   │                 │
                                   │/v1/factory/*    │
                                   │(paginação,      │
                                   │ filtros allow-  │
                                   │ listed, cache)  │
                                   └─────────────────┘
```

## Quality Gates v1

| check_id | Severity | Descrição |
|----------|----------|-----------|
| `required_sheets_present` | BLOCKING | Folhas obrigatórias existem |
| `required_columns_present` | BLOCKING | Colunas obrigatórias existem |
| `no_duplicate_business_keys` | BLOCKING | Sem duplicados em PKs de negócio |
| `valid_numeric_ranges` | BLOCKING | Valores numéricos em ranges válidos |
| `referential_integrity` | BLOCKING | FKs lógicas resolvem |
| `date_parseable` | WARNING | Datas parseáveis onde esperado |
| `pii_policy_enforced` | WARNING | PII detectado e classificado |

## Ficheiros Implementados

```
src/factory_data_product/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── meta.py          # ingestion_run, active_run, quality_check_result
│   ├── raw.py           # excel_row
│   ├── curated.py       # order, order_phase, mold, etc.
│   └── semantic.py      # view definitions
├── ingest/
│   ├── __init__.py
│   ├── engine.py        # main ingest orchestration
│   ├── parser.py        # Excel parsing
│   ├── hasher.py        # SHA256 hashing
│   └── transformer.py   # RAW → CURATED transformation
├── quality/
│   ├── __init__.py
│   ├── gates.py         # Quality gate definitions
│   └── runner.py        # Quality check execution
├── api/
│   ├── __init__.py
│   └── endpoints.py     # /v1/factory/* endpoints
├── cli/
│   ├── __init__.py
│   └── commands.py      # CLI commands
└── tests/
    ├── __init__.py
    ├── test_ingest.py
    ├── test_quality.py
    └── test_api.py
```

## Critérios de Aceitação

- [ ] Repetição do mesmo ficheiro não duplica efeitos (idempotência)
- [ ] RAW append-only e auditável
- [ ] Curated filtrável por `active_ingestion_id`
- [ ] Views semânticas executam com performance aceitável
- [ ] RBAC activo: `factory_api` não lê PII/custos sem autorização

## Testes Obrigatórios

- [ ] Unit: hashing, parser Excel, normalização payload_json
- [ ] Integration: ingest completo + gates + activação
- [ ] Contract: cada view_id responde e respeita filtros/paginação
- [ ] Security: acesso a PII com role read-only falha


