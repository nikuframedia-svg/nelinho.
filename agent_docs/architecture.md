# Architecture

Reference for module map, deploy topology, scale numbers. Loaded on demand.

## Backend modules (`src/`)

```
src/
├── core/                # Master data (modelos, routing, moldes, fases, tenants, configs)
├── shared/              # DB, auth, outbox, scheduler, kafka client, redis, realtime SSE
├── infrastructure/      # ERP SQL Server adapter (shadow-mode-ready, dormant)
├── factory_data_product/# Excel ingest + curated layer (10 tables, ~423K rows alocações)
├── dqa/                 # Trust Index v2 (7+1 components), quality gates, distribution drift
├── diagnostics/         # Audit board (17 modules), TI live, ScheduleCommit cadence
├── plan/                # CPO scheduler v4 DRCFFS-R + transport + workforce + scheduling
│   ├── cpo/             # chromosome, decoder, engine, fitness v2, frrmab, mapelites,
│   │                    #   surrogate, safety_net, state, workforce, commits, cpsat_lrho
│   ├── api/             # cpo, schedule, schedule_preview, transport, mrp, mold
│   └── services/        # transport_batch_service, transport_suggestions,
│                        #   preview_delta_service (sub-segundo)
├── ml/                  # XGBoost duration, quality_risk, surrogate, model_registry
├── workforce/           # EmployeeExtras, skill_matrix, dependency-graph, SPOF detection
├── hr/                  # Allocations, shifts, payroll, CoeficienteX (€ prémios)
├── supply/              # Materials, ROP, ABC, MR01-MR08 framework
├── quality/             # Rework, error catalog, root_cause_analyzer, mold maintenance
├── profit/              # OEE, COGS, dashboard_metrics_service (OTD/FPY/backlog/expeditions)
├── copilot/             # LLM service, POETIQ, RAG (pgvector), causal/abl, alerts engine
├── explain/             # 4 causas Aristóteles, Mill's diff, ERRO-TREE, Reichenbach (Q.15.D)
├── governance/          # DecisionRun, ScheduleCommit chain, ApprovalRequest, yaml_policy (Q.17),
│                        #   preference_learning detector, ab_framework (Q.14.C)
├── sandbox/             # Scenario CRUD + simulate() chama CPO real
├── twin/                # DigitalTwin counterfactuals via CPO
├── improve/             # Suggestion engine advisory (LLM + seed)
├── legacy/              # Retro-compat (`/api/orders`, `/api/allocations`); escape hatch
└── main.py              # FastAPI app, lifespan (init_db, scheduler start, realtime listener)
```

**Sizes (LOC):** Plataforma 13.3K · Dados 13K · Plano 17.4K · Operações 11.9K · Inteligência 27.3K
· Operador 1.3K · **Total backend ~84.5K LOC** + 1684 tests.

**Frontend (`frontend/src/`):** 47 pages + 108 components (12 Dark) + 52 API clients.

## Deploy topology (production = nelo factory torre)

```
┌─────────────────────────────────────┐
│          TORRE (servidor)           │
│                                     │
│  PostgreSQL 16 ← dados              │
│  FastAPI       ← backend/API        │
│  Ollama        ← LLM (RTX 5060 Ti)  │
│  Caddy         ← serve frontend +   │
│                  reverse proxy +    │
│                  HTTPS              │
│  React build   ← ficheiros estáticos│
│                                     │
│  IP: 192.168.X.X (rede fábrica)     │
│  URL: http://pp1.nelo.local         │
└──────────┬──────────────────────────┘
           │ rede local (Ethernet/Wi-Fi)
     ┌─────┼─────┬──────────┐
     │     │     │          │
  ┌──┴──┐ ┌┴───┐ ┌┴────┐ ┌──┴──────┐
  │ PC  │ │ PC │ │ PC  │ │ Tablet  │
  │escr.│ │prod│ │CEO  │ │operador │
  └─────┘ └────┘ └─────┘ └─────────┘
   browser browser browser  browser
```

Nenhum PC instala nada — tudo via browser. Caddy serve React build estático + proxy ao FastAPI.
RBAC filtra **acções** (write); UI é universal (mesma rota para todos).

## Dev environment (Luis dev box)

- Windows 11 Pro 26200 + scoop postgres 18 + bash (git-bash) + PowerShell 5.1
- Python venv: `c:/Users/User/nelinho/.venv/`
- Set PYTHONPATH antes de pytest: `$env:PYTHONPATH = "c:/Users/User/nelinho"`
- Ollama em `:11434` (Gemma); RAG/copilot dependem
- Kafka NÃO está instalado em dev — `RealtimeBridge` cai a 503 (esperado, frontend faz polling)
- Redis em `:6379` quando disponível; `copilot/rate_limiter` tem fallback memória

## Scale numbers (factuals NELO 2024-2025)

| Métrica | Valor |
|---|---|
| Operações registadas | 529.450 |
| Erros registados | 89.836 (16.97% rate) |
| Operadores activos | 122 |
| Fases | 41 |
| Moldes | 510 |
| Routing patterns | 61 |
| Throughput target | €30K-35K/dia |
| Barcos/dia (média) | 14.7 |
| Truck capacity moda | 26 (real) vs 50 (CEO baseline) |
| Lixagem água retrabalho | 49.2% |
| Pintura Acabamento retrabalho | 42.4% |
| Lixagem polimento retrabalho | 41.3% |
| Laminagem par | 88.5% (axiom 4) |

**Use estes números em prompts/copy** — NUNCA renderizar como dados (são factos do domínio,
não rows). Frontend dev/prod fetcha da API real (ZERO MOCKS).

## Endpoint count

- ~339 backend routes total (`@router.{get,post,put,patch,delete}` enumerados)
- 47 frontend pages
- 52 API clients em `lib/api.ts`

## Test inventory

- **1684 tests** total (alvo current; aumenta a cada sub-sprint)
- Tipo: ~80% small (FakeSession, pure functions) · ~15% medium (aiosqlite/Postgres) · ~5% large
  (FastAPI TestClient + bootstrap_dev_full)
- Property-based: 4 hypothesis props em `tests/plan/test_preview_delta_property.py` (Spelke)
- Canary suite: `pytest tests/governance/ -q` ~53s, 348 tests
