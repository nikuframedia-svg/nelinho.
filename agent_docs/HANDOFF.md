# HANDOFF — nelinho / ProdPlan ONE

> Documento de contexto total. Lê isto antes de tocar em qualquer ficheiro.
> **Data:** 2026-05-16 · **Branch:** `feat/q18-ui-A` · **Sprint:** Q.19.A · **Working dir:** `c:\Users\User\nelinho`

---

## 0. TL;DR — o que é isto

**nelinho** (nome técnico *ProdPlan ONE*, marca NIKUFRA.AI) é um ERP de planeamento de
produção (APS — Advanced Planning & Scheduling) + Machine Learning + copilot LLM, on-premise,
para a fábrica de kayaks de competição NELO / Mar Kayaks em Vila do Conde. Substitui o
planeamento manual (Excel + cabeça do gestor, abandonado digitalmente desde 2019) por um
scheduler genético+CP-SAT que respeita 7 invariantes físicas da fábrica, explica cada decisão
em PT-PT, e aprende com as escolhas que o gestor aceita/rejeita.

- **Backend:** monólito Python 3.11 (FastAPI + SQLAlchemy 2.0 async + Postgres 16). ~84.5K LOC, ~1775 funções de teste, ~40 routers, ~339 rotas.
- **Frontend:** SPA React 19 + Vite + TypeScript strict. 47 páginas.
- **Deploy:** nativo (sem Docker), systemd + Caddy, numa torre na rede local da fábrica.
- **Owner:** Luis (luis@nikufra.ai). PT-PT informal, respostas curtas, números concretos.
- **Estado:** ~70% para produto final (código ~90%, dados a fluir ~50%). Detalhe na §10.

---

## 1. DOMÍNIO — a fábrica NELO

### 1.1 O que a NELO faz

Fábrica portuguesa líder mundial em kayaks e canoas de competição (fibra carbono/kevlar — os
atletas olímpicos remam barcos NELO). Classes: K1 (1 lugar, ~46% das ordens, dominante), K2
(2 lugares), K4 (4 lugares), C1/C2/C4 (canoas), V1 (va'a), modelos "Viper" e recreio/touring.

### 1.2 Números reais (NUNCA renderizar como mock — são factos 2024-2025)

| Métrica | Valor |
|---|---|
| Barcos/dia | 14.7 starts / 14.9 completions |
| Meta throughput | €30.000-35.000/dia |
| Preço médio/barco | ~€2.350 |
| Operadores activos | 122 |
| Fases de produção | 41 activas |
| Moldes | 510 (397 em produção; até 7 poços/cavidades) |
| Padrões de routing | 61 |
| Operações registadas (6 anos) | 529.450 |
| Erros registados | 89.836 (taxa global 16.97%) |
| Lead time | moda 15 dias, mediana 37 |
| Turnos | 95% turno único → capacidade 8h/dia/operador |

**Discrepância docs vs BD:** a documentação usa 41 fases / 510 moldes / 122 operadores (os
activos, derivados de Excel). A BD live MAR-KAYAKS dá counts brutos diferentes
(FASES_PRODUCAO=71, MOLDES=91, ORDEMFABRICO=441.392) porque inclui histórico/inactivos. Em
copy de UI usa 41/510/122; em queries SQL espera os counts brutos.

### 1.3 As fases (o "routing")

Cada barco passa por uma sequência de fases (= work centers — diz-se "fase", nunca "estação").
61 padrões de routing diferentes. Fases críticas a decorar:

| Fase | Tempo (moda real) | Notas |
|---|---|---|
| Laminagem | 4h | Fase mais crítica. 88.5% feita por 2 operadores em par. |
| Laminagem Infusão | 24h | Processo DIFERENTE — 58% com 1 operador. Tratar separado. |
| Cura | gap 15h | Química (resina). NÃO é fila — é tempo físico inviolável. |
| Desmolde | curto | 96.4% dos erros são detectados aqui (CQ Final só apanha 3.6%). |
| Lixagem água | 0.5h | 49.2% retrabalho. |
| Pintura Acabamento | 6.5h | 42.4% retrabalho. Bottleneck é ALOCAÇÃO, não competência. |
| Lixagem polimento | 0.5h | 41.3% retrabalho. |

### 1.4 Cura/secagem — química (16 transições)

Entre certas fases há um `min_gap_hours` obrigatório que não é fila — é química real (resina/
tinta a curar). A operação seguinte não pode começar antes do gap, mesmo com operador e molde
livres. São 16 transições em `src/plan/cpo/state.py:33` (`NELO_CURING_GAPS_SEED`): ex.
Laminagem→Cura 15h, Laminagem Infusão→Cura 24h, Colagem Peças→Acabamento 2 23.5h. Migration 023.

### 1.5 Retrabalho

"Retrabalho" (nunca "rework") = barco volta atrás numa fase. Taxas reais altíssimas (ver §1.3).
Na BD marca-se com `OFFP_RETURN` (bit) na tabela `OF_FP`; retornos graves em
`OFFP_RETORNO_GRAVE`.

### 1.6 CoeficienteX — É DINHEIRO (€), NUNCA TEMPO

O erro de domínio mais perigoso do projecto. CoeficienteX é um prémio em euros pago ao
operador por operação. "6.1" na Laminagem = €6,10 de prémio, não 6.1 horas. Confirmado pelo CEO.

- NUNCA usar em `src/plan/cpo/` (decoder, fitness, pair_assignment, state, workforce).
- USAR em `src/profit/` (bonus_payout, cogs) e `src/hr/payroll/`.
- Verificação: `grep -ni coeficiente src/plan/cpo/*.py` → zero matches esperado.

### 1.7 Tempos — nunca os standard

Os coeficientes standard (`PRODUTO_FASE.PRODF_TEMPO`) divergem do real até 25×. O CPO usa
SEMPRE tempos históricos: `OFFP_DATAINICIO`→`OFFP_DATAFIM`, limpos (remover zeros → remover
>P95 → moda dos limpos → fallback mediana ≠0).

### 1.8 Hipóteses NÃO confirmadas (cuidado)

H1 CoeficienteX=tempo 2º operador ❌ ERRADO (é €) · H2 threshold manutenção molde 800/850
usos ⚠️ INVENTADO · H3 gravidade 1=warning/2=defeito ⚠️ · H4 Laminagem solo=erro registo ⚠️ ·
H5 data transporte por dia ⚠️. Se o código depender de uma destas, marca `# Hx:` e pergunta
ao Luis.

---

## 2. STACK + ARQUITECTURA

### 2.1 Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0 (async), asyncpg, Pydantic v2, Alembic.
- **Frontend:** React 19.2, Vite 7.2, TypeScript 5.9 strict, TanStack Query v5.90, Tailwind 4.1, react-router v7.12, recharts, framer-motion, @dnd-kit, zod, lucide-react.
- **BD:** PostgreSQL 16 (dev: scoop postgres 18 no Windows).
- **LLM:** Ollama local, modelo Gemma (gemma4:e4b) numa RTX 5060 Ti 16GB. Embeddings nomic-embed-text.
- **Deploy:** nativo, sem Docker, sem cloud. systemd + Caddy. PCs/tablets da fábrica acedem por browser.
- **Mensageria:** Kafka OPCIONAL e NÃO instalado em dev (padrão = outbox `event_outbox` + Postgres LISTEN/NOTIFY). Redis em :6379 com fallback em memória.

### 2.2 Topologia de deploy

Uma torre na fábrica hospeda tudo: PostgreSQL + FastAPI + Ollama + Caddy + React build. URL
`http://pp1.nelo.local`. RBAC filtra acções (writes); a UI é universal, cada role vê o seu
"Umwelt".

### 2.3 Módulos backend (`src/`) — 17 + shared

| Módulo | O que faz |
|---|---|
| `core/` | Master data (tenants, products, machines, employees, BOM, rates, operations, configs) |
| `shared/` | DB, auth, outbox, scheduler, kafka/redis, realtime SSE, capabilities |
| `adapters/nelo/` | Adapter READ-ONLY à BD live MAR-KAYAKS (ver §6) |
| `infrastructure/erp/sqlserver/` | Camada SQL Server mais antiga (DEPRECATED — usar adapters/nelo) |
| `plan/` | Coração — CPO scheduler v4 + MRP + moldes + transporte + capacidade |
| `plan/cpo/` | GA hyper-heuristic: chromosome, decoder, engine, fitness, frrmab, mapelites, surrogate, safety_net, state, workforce, commits |
| `profit/` | OEE, COGS, pricing, cenários, bónus, dashboards CEO |
| `copilot/` | LLM Gemma via Ollama, RAG, runbooks, POETIQ, causal/ABL, alertas |
| `governance/` | DecisionRun, ScheduleCommit, aprovações, Q.17 yaml_policy, preference learning, A/B |
| `workforce/` | Dependency graph, cascade impact, SPOF, training recs, employee extras |
| `hr/` | Alocações, turnos, payroll, produtividade |
| `supply/` | Forecast, inventário, ROP, ABC, shortage detection |
| `quality/` | Retrabalho, FPY, root cause, worker ranking |
| `factory_data_product/` | Ingestão Excel → curated → semantic; factory map; trust heatmap |
| `ml/` | Model registry, retrain jobs, duration model, quality risk model, surrogate, QLora |
| `explain/` | Explainability: metric catalog, causal attribution/discovery, diagnostics |
| `dqa/` | Data Quality Assurance: Trust Index v2, quality gates |
| `twin/` | Digital Twin — cenários what-if |
| `sandbox/` | Ambiente de experimentação isolado |
| `improve/` | Sugestões de melhoria contínua |
| `diagnostics/` | Rollup de saúde por módulo |
| `reports/` | Geração de relatórios PDF/Excel (parcialmente stubbed) |
| `legacy/` | Endpoints de compatibilidade `/api/*` |

---

## 3. BACKEND — detalhe

### 3.1 API completa — routers principais (`src/main.py` regista ~40)

Health (`/health`, `/health/ready`, `/metrics`) sem auth. Tudo o resto exige header
`X-Tenant-Id`.

- **CORE** `/v1/core/*` — CRUD: tenants, customers, suppliers, products, machines, employees, operations, bom, rates (labor/machine/overhead), tenant_config (`/v1/config/*`). Dados reais.
- **PLAN** `/v1/plan/*`:
  - `/cpo` — POST `/schedule` (corre o CPO v4, persiste commit), GET `/commits`, `/commits/{sha}`, `/commits/{from}/diff/{to}`, `/timeline`, `/commits/{sha}/alternatives`, POST `/commits/{sha}/decide` (regista accept/reject do operador — o endpoint central da aprendizagem; exige `rejection_category` + `reason`≥10 chars), `/operations/{id}/worker-pairs`.
  - `/schedule`, `/schedule/preview-delta` + `/apply-move` (drag-drop sub-segundo), `/orders/active`, `/mrp`, `/molds/*` (health-report, calendar, maintenance), `/transport/batches/*`, `/capacity`, `/phase-gaps`.
- **PROFIT** `/v1/profit/*` — `/cogs`, `/pricing`, `/scenarios`, `/bonus-payouts`, `/dashboard`, GET `/oee` (OEE A×P×Q real, Q.19.A), `/otd`, `/backlog-by-client`, `/kpis/snapshot*`.
- **COPILOT** `/api/copilot/*` (~30 endpoints) — `/ask`, `/action`, `/conversations`, `/rag/ingest`, `/recommendations`, `/insights`, POETIQ `/propose`, alerts `/v1/copilot/alerts`, runbooks.
- **GOVERNANCE** `/v1/governance/*` — Decision Ledger (propose/approve/execute/rollback/audit-pack), kill-switch, rule-firings, preference-rules, learning, yaml-policy (`/rules/propose` NL→YAML).
- **WORKFORCE, HR, SUPPLY, QUALITY, EXPLAIN, TWIN, IMPROVE, FACTORY-DATA, ML, DQA, DIAGNOSTICS, SANDBOX, REALTIME** (SSE), **CAPABILITIES** (usado pelo boot do frontend), **AUTH** (`/v1/auth/me`), **REPORTS** (`/generate` ok; `/schedule`+`/email`+`/retention` STUBBED), **LEGACY** (`/api/*`).

### 3.2 CPO Scheduler (`src/plan/cpo/`)

Hyper-heuristic genetic algorithm para DRCFFS-R (Dual-Resource Constrained Flexible Flow Shop
with Rework).

- `chromosome.py` — representação 1D: permutação de índices de operações + escalares (edd_gap, buffer_pct, quality_weight) + routing_choices (selector A/B) + schedule_direction.
- `engine.py` — `CPOv4Engine`: baseline greedy → GA (pop 100, 200 gerações, torneio 5, OX crossover 0.60, mutação 0.30, elitismo 5%) → safety net. Features adaptativas (flags em `CPOConfig`, todas ON em dev): FRRMAB (bandit escolhe operador de mutação), MAP-Elites 3D (eixos: lam_utilization × tardiness_transport × idle_pct), surrogate (prevê fitness, ~80% skip), restart por estagnação, greedy_pipeline, backwards_scheduling, Hungarian pair assignment, queue_time (5.2h), buffer pós-Desmolde (4h), CP-SAT L-RHO. Budget total 60s.
- `decoder.py` — `decode()`: Chromosome → schedule factível, determinístico. Respeita precedências, no-overlap máquina/worker, exclusividade de molde, multi-pocket batching, gaps de cura. Calcula KPIs (makespan, tardiness, OTD, idle, throughput €/dia).
- `fitness.py` — `compute_fitness()`, soma ponderada (menor=melhor). Legacy: w_tardiness=10 (atraso dói 10×). v2 normalizado (soma=1). CoeficienteX nunca aparece aqui.
- `pair_assignment.py` — dual-resource Laminagem. PREFERRED (não REQUIRED — 11.5% solo é real, CEO confirmou). `rank_pairs()` devolve top-N pares com score 0-10.
- `safety_net.py` — CPO nunca devolve pior que baseline. Compara 7 dimensões.
- `state.py` — `FactoryState`: snapshot in-memory + `NELO_CURING_GAPS_SEED` (16 transições).
- `commits.py` — `ScheduleCommit` ("Schedule-as-Code", estilo git: SHA-256, parent, kpis, alternatives, rejected_alternatives, user_preference_signal).

### 3.3 Q.17 — Logic-as-data (`src/governance/yaml_policy/`)

Lógica configurável em YAML. Página `/regras`: admin escreve em PT-PT natural, LLM traduz para
YAML com 10 camadas de segurança. DSL é whitelist fechada (Pydantic `Literal`):

- 12 EventType, 9 ActionType, 8 ConditionOp, 7 AxiomRequirement.
- Invariantes que o LLM NÃO pode contornar: `requires_human_approval: Literal[True]`, `kill_switch: Literal["admin_only"]`.
- ACTION_WIRING matrix (`dispatchers.py:76`) — 4 de 9 wired: ✅ alert, block, modify_fitness, set_config; ⚠️ stubbed: reassign_worker, propose_maintenance, notify, create_decision, pause_writes. Espelhada no frontend `RegrasPage.tsx` `WIRED:` map — flipar um lado obriga a flipar o outro (test `test_action_wiring_matrix_has_entry_per_action_type`).
- Helper `_stubbed_or_ok()` — devolve "ok" só se wired E callback existe. Fecha o bug Q.17.F.1 (dispatcher reportar "ok" quando não wired — o bug mais trust-breaking do projecto).

### 3.4 Profit (`src/profit/`)

- `oee_service.py` — OEE = Availability × Performance × Quality das operações NELO (`adapters.nelo.list_operations`). Endpoint GET `/v1/profit/oee?date_from=&date_to=&group_by=` (group_by: none/phase/shift/product_type/mold). Dados reais do SQL Server (Q.19.A).
- `cost_service` (COGS), `pricing_service`, `margin_calculator`, `throughput_service`, `dashboard_metrics_service`, `bonus_payout_service`.

### 3.5 Copilot (`src/copilot/`)

LLM Gemma via Ollama. `service.py` pipeline: ask → security check → histórico → intent →
context facts → RAG → prompt → Ollama → guardrails/validação → redacção PII. Causal DAG 23 nós,
POETIQ loop copilot↔CPO, runbooks declarativos, alertas proactivos. RAG indisponível em dev
(pgvector).

### 3.6 Adapter NELO (`src/adapters/nelo/`)

READ-ONLY ao SQL Server MAR-KAYAKS. `sqlserver_enabled=False` por default. 12 funções
públicas: `list_open_orders`, `count_open_orders`, `get_routing`, `get_bom`,
`list_recent_movements`, `list_current_schedule`, `list_operations` (fonte do OEE — query
pesada, OF_FP tem 2.6M linhas), `top_products_by_orders`, `count_movements_last_n_days`,
`health_check`. Schemas Pydantic frozen.

### 3.7 Auth / RBAC / Tenant (`src/shared/auth/`)

- `headers.py` — fail-closed. JWT primeiro, header `X-Tenant-Id` fallback só em dev. Zero-UUID (`...000`) rejeitado por design. Dev tenant: `00000000-0000-0000-0000-000000000001`.
- `rbac.py` — 8 roles (admin_platform, manager_operations, planner_supply, finance_controller, hr_manager, operator, ceo read-only, viewer), ~24 permissions, `ROUTE_PREFIX_REQUIREMENTS`, SoD.

### 3.8 Testes

170 ficheiros, ~1775 funções. `pytest.ini` `asyncio_mode=auto`. Fixtures: `FakeSession` (mock
async — governance é Postgres-only, SQLite não serve), `MockOllamaClient`, `fake_redis`.
Canary = `pytest tests/governance/ -q` (348 tests, ~53s). Property tests Spelke usam
`hypothesis`.

### 3.9 Stubs / TODOs conhecidos

- `reports/api.py` — `/schedule`, `/email`, `/retention` STUBBED; templates payroll/cogs/inventario.
- `yaml_policy/dispatchers.py` — 5 dispatchers stubbed (ver §3.3).
- `legacy/api.py:505,550` — `/api/errors*` TODO (falta model `ProductionError`).
- `shared/api/auth_me.py:55` — email placeholder (sem tabela User real).
- `profit/api/kpis.py:375` — KPI explanations só para 1 KPI.
- `shared/scheduler.py:330` — quality_risk_scoring stub.

---

## 4. FRONTEND — detalhe

### 4.1 Estado geral

Coexistem 3 gerações de páginas: (a) páginas antigas em inglês por módulo (`pages/core/`,
etc.), (b) páginas PT-PT intermédias, (c) as 10 páginas standalone "Q.18.ZIP" (actuais). (a) e
(b) só são acessíveis via sufixo `-legacy` na URL. Muitas das 10 páginas do menu são wrappers
triviais que delegam a (b).

### 4.2 Routing (`src/App.tsx`)

Tudo sob `<Route path="/" element={<Layout/>}>`. Quase todas lazy-loaded (`lazy()` +
`<Suspense>`). Providers: QueryClientProvider → CapabilitiesProvider → UmweltProvider →
ErrorBoundary → CommandPaletteProvider → ToastProvider → RealtimeProvider → BrowserRouter.

### 4.3 Páginas do menu (10 itens / 3 grupos no Sidebar)

| Rota | Componente | Estado |
|---|---|---|
| `/direcao` | DirecaoPage | REAL — dashboard CEO, 4 KPIs, expedições, ProfitDashboard |
| `/inbox` | InboxDecisoesPage | REAL — 4 tabs, counts reais. Cards read-only (aprovação real está no DecisionsPage legacy) |
| `/plano-producao` | PlanoProducaoPage | WRAPPER → ProducaoPage |
| `/atribuicao` | AtribuicaoDiariaPage | WRAPPER → EquipaPage?tab=alocacoes |
| `/oee` | OEEPage | WRAPPER → QualidadePage?tab=oee |
| `/operadores` | OperadoresPage | WRAPPER → EquipaPage?tab=lista |
| `/qualidade` | QualidadePage | REAL — 8 tabs |
| `/expedicao` | ExpedicaoPage | REAL — 2 tabs |
| `/aprendizagem` | AprendizagemPage | WRAPPER → ConfiguracaoPage?tab=aprendizagem |
| `/regras` | RegrasPage | REAL — referência de composição (split-pane + diff modal) |
| `/definicoes` | DefinicoesPage | WRAPPER → ConfiguracaoPage?tab=geral |

Páginas-mãe reais por trás dos wrappers: ProducaoPage (4 vistas: Por fase/Gantt/Calendário/CPO),
EquipaPage (7 tabs), QualidadePage (8 tabs), ConfiguracaoPage (7 tabs gigantes).

### 4.4 Componentes

`components/dark/` (37 ficheiros) = design system actual (PageHeader, Panel, Tabs,
SegmentedControl, EmptyState, DarkBadge, DarkButton, DarkTable, Modal, ZipAtoms).
`components/ui/` = design system antigo (coexiste). `components/alpha/` (9 ficheiros) = MORTO
(restos de template). DarkBadge variants permitidos:
`success/warning/danger/info/neutral/accent/primary/teal` (NÃO green/yellow/red/blue/gray).

### 4.5 API layer (`src/lib/`)

- `api.ts` (~2900 linhas) — `request<T>()` wrapper de fetch com circuit breaker, retry, erros PT. Injecta em cada request: `Authorization: Bearer`, `X-Tenant-Id` (fallback `...001`), `X-User-Id`, `X-User-Role`. ~70 API clients (productsApi, schedulingApi, decisionsApi, yamlPolicyApi…).
- `CapabilitiesProvider` — faz GET `/v1/capabilities/` no boot, bloqueante (a app não arranca sem). Expõe `hasModule`, `isMetricBlocked`. `RealtimeProvider` — uma conexão SSE partilhada.

### 4.6 Como correr

```
cd c:\Users\User\nelinho\frontend
npm install        # primeira vez
npm run dev        # Vite na porta 5173
```

SEM proxy — o frontend fala directo com o backend via `VITE_API_URL`. Build: `npm run build`
(`tsc -b && vite build`). Typecheck: `npx tsc -b --noEmit`.

### 4.7 ⚠️ CONFLITO DE PORTA — resolver primeiro

- `frontend/.env`: `VITE_API_URL=http://127.0.0.1:8001`
- `api.ts:25` + `CapabilitiesProvider` fallback: `http://localhost:8000`
- `agent_docs/bootstrap_recovery.md` documenta o backend em 8000
- 47 ficheiros têm `http://127.0.0.1:8001` hardcoded em `fetch()` directos

→ Arranca o backend em 8001 (`--port 8001`) para `.env` + os 47 hardcodes concordarem, OU
alinha tudo. É a primeira coisa a resolver.

### 4.8 Problemas frontend conhecidos

- **Hardcodes (violam ZERO MOCKS):** `QualidadePage.tsx:774` ThroughputChart array hardcoded + `:780-823` "Impacto financeiro" 4 valores € + total €4.780. `ProducaoPage.tsx:45-85` PHASES (11 fases, fábrica tem 41) + HULL_CLIENT + GANTT_DAYS hardcoded. `WorkforceDashboard.tsx:420` admite na UI que nomes/níveis são placeholder.
- **Botões mortos / `alert()`:** ProducaoPage "Re-optimizar" `:228`, EquipaPage "Sugerir atribuição" `:286`, ExpedicaoPage "Nova expedição" `:133` + "Ver barcos"/"Documentos" sem onClick, WorkforceDashboard onExportPDF `:544`, DispatchPage RejectionDialog `:320`, ConfiguracaoPage AprendizagemZipView botões `:576-599`.
- **"Coming Soon":** SettingsPage 3 tabs (api/notifications/integrations), RelatoriosPage tab Exportar.
- 5 wrappers triviais (ver §4.3) — redirects podiam estar em App.tsx.
- `App.tsx:138`+`:195` — rota `/inbox` declarada 2× (a 2ª é código morto).

---

## 5. BD POSTGRES DEV — schema

`prodplan_one` em `postgresql+asyncpg://prodplan:prodplan@localhost:5432`. 16 schemas, ~75
models, 93 tabelas. 47 migrations Alembic (última 046). `bootstrap_dev_full.py` cria tudo.

| Schema | Tabelas |
|---|---|
| `core` | tenants, tenant_configuration, audit_log, bom_items, employees, machines, operations, customers, suppliers, products, labor/machine/overhead_rates |
| `plan` | production_orders, production_schedules, plan_schedule_commits, mold(+health/maintenance/defect/usage), material_requirements, purchase_orders, phase_transition_gap, routing_template(+phase/assignment), transport_batch(+assignment) |
| `profit` | cost_calculations, pricing_recommendations, profit_scenarios, phase_bonus_payout, product_pricing, order_revenue, shipping_rate |
| `hr` | hr_allocations, shift_schedules, skills, employee_skills, legacy_allocations, employee_productivity, monthly_payroll_summary |
| `governance` | decision_policy, decision_run, kill_switch_active, approval, preference_rule, causal_discovery_report, rule_firing, yaml_policy_rule(+revision) |
| `quality` | error_catalog, rework_entry |
| `dqa` | trust_index_snapshots, data_quality_issues, auto_repair_logs |
| `supply` | inventory_ledger_entries, supply_forecasts, supply_rop_configs, supply_material_master/in_transit/stock_reconciliation |
| `factory_raw/meta/curated` | excel_row · ingestion_run/active_run/activation_history/quality_check_result · order/order_phase/phase_capacity/mold/mold_usage/quality_event/skill_matrix/cost_reference/allocation/modelo |
| `twin/sandbox/improve` | twin_scenarios(+deltas/comparisons) · sandbox_scenarios · improvement_suggestions |
| `public` | copilot_* (alerts, suggestion, rag_chunk[excluída em dev], conversation, message…), ml_model_artifact, event_outbox/dlq |

---

## 6. BD LIVE NELO — SQL Server MAR-KAYAKS

### 6.1 Conexão (read-only)

Máquina `fabrica.nelo.eu:1039`, DB `MAR-KAYAKS` (284 tabelas em `dbo`). Credenciais no `.env`:

```
SQLSERVER_URL=mssql+aioodbc://nikufra:arfukin2026@fabrica.nelo.eu:1039/MAR-KAYAKS?driver=SQL+Server&TrustServerCertificate=yes&Encrypt=no
```

`nikufra` é DataReader only (não pode escrever nem CREATE VIEW). NUNCA escrever — é o ERP vivo.

### 6.2 Tabelas-chave (volumes + colunas)

- **ORDEMFABRICO** — 441.392 linhas, 111 colunas, PK `OF_ID`. As ordens de fabrico. `OF_DATA`, `OF_DATAINICIO`, `OF_DATAFIM` (NULL em 71% = aberta), `OF_DATATRANSPORTE`, `OF_P_ID`→PRODUTO, `OF_FP_ID`→fase actual, `OF_E_ID`→cliente, `OF_PRECOCUSTO`, `OF_COEFICIENTE` (€, não tempo).
- **OF_FP** — 2.627.279 linhas, 52 colunas, PK `OFFP_ID`. Execução por fase. `OFFP_DATAINICIO`, `OFFP_DATAFIM` (tempo histórico real), `OFFP_TEMPERATURA`/`OFFP_HUMIDADE`, `OFFP_PROBS_*` (problemas inline — a tabela child `OFFP_PROBLEMA` está vazia), `OFFP_RETURN` (bit, retrabalho), `OFFP_COEFICIENTE` (horas, fallback), `OFFP_COEFICIENTE_X` (€).
- **OFFP_EQ** — 1.410.887 linhas. Liga operação↔operadores. `OFFPEQ_E_ID`→ENTIDADE, `OFFPEQ_CHEFE` (bit). É aqui que se vê o "par de 2 operadores" da Laminagem.
- **PRODUTO** — 14.016 linhas. Catálogo. `P_NOME`, `P_TP_ID`→PRODUTO_TIPO.
- **PRODUTO_FASE** — 42.811 linhas. O routing. `PRODF_P_ID`, `PRODF_FP_ID`, `PRODF_SEQUENCIA`, `PRODF_TEMPO` (standard — diverge 25×).
- **PRODUTO_COMPONENTE** — 117.900 linhas. O BOM.
- **FASES_PRODUCAO** — 71 linhas. Master de fases. `FP_NOME`, `FP_VALOR_REF_K1/K2/K4`.
- **ENTIDADE** — 8.936 linhas. Polimórfica: pessoas, clientes, fornecedores e operadores. `E_NOME`, `E_ACTIVO`, `E_CUSTOHORA`. NÃO há tabela EMPREGADO dedicada.
- **MOVIMENTO** — 12.392.449 linhas. Ledger stock/WIP (~4.880/dia).
- **MOLDES** — só 91 linhas (esperados ~510 — vivem em Excel). Sem colunas de manutenção.
- Outras: `ENCOMENDA` (410), `ENTIDADE_FASE` (1.269 = skill matrix), `OF_CHECKLIST` (3M, QC), `FP_FP` (11, DAG de precedências), `PLANEAMENTO_DIARIO` (64, plano manual abandonado em 2019).

### 6.3 views `vw_pp1_*` — NÃO existem ainda

`agent_docs/views_pp1.sql` define 6 views read-only (vw_pp1_orders/routings/bom/schedule/
operations/movements). O IT da NELO ainda não as aplicou; o adapter contorna inlining o SQL.

### 6.4 Mapeamento ERP → Postgres

O PP1 não substitui o ERP. Lê via adapter read-only, escreve só no seu Postgres. Único ETL
escrito: `scripts/sync_nelo_to_postgres.py` (untracked) — upsert de OFs abertas em
`plan.production_orders`. Falta sincronizar: master data (PRODUTO, PRODUTO_FASE,
ENTIDADE→employees, PRODUTO_COMPONENTE→bom), moldes (Excel), skills, quality.

---

## 7. OS 7 SPELKE AXIOMS

Invariantes invioláveis do scheduler. Property tests em
`tests/plan/test_preview_delta_property.py` (hypothesis). Se um property test falha, NÃO o
modificar — corrigir o decoder/fitness.

1. **Capacity ≥ 0** — nenhum work center com carga negativa. `decoder.py` + safety_net.
2. **Precedence monotónica** — ordem de fases do BOM; Cura depois de Laminagem, sempre. `state.py`.
3. **Mold exclusivity** — molde 1-poço produz 1 barco/vez; multi-pocket usa pocket_count. 🟡 PARCIAL.
4. **Dual-resource Laminagem** — prefere 2 operadores (88.5% histórico). `pair_assignment.py`.
5. **Skill match** — operador só em fase onde é apto (ENTIDADE_FASE). `workforce.py` (INFEASIBLE_COST=1e12).
6. **Cura/secagem min_gap_hours** — 16 transições químicas. `state.py:33`. Migration 023.
7. **Safety net (CPO ≥ baseline)** — CPO nunca pior que baseline. `safety_net.py`. 🟡 7 KPIs.

---

## 8. SKILLS (`.claude/skills/`) — 7 SKILL.md

- **nelinho-discipline** — guardrails: declarar assunções, mudança mínima, cirúrgica, sucesso verificável. Ler ANTES de qualquer task. Diff >400 LOC = sinal de problema.
- **nelinho-incremental** — sub-sprints Q.X.Y: >1 ficheiro = 1 sub-sprint = pytest verde + smoke.
- **nelinho-tdd** — RED-GREEN-REFACTOR, FakeSession, property tests hypothesis, DAMP>DRY.
- **nelinho-debug** — tabela symptom→cause→recovery. Recovery comum = drop+recreate+bootstrap.
- **nelinho-frontend** — ZERO MOCKS, PT-PT, dark theme, inputs acessíveis, RegrasPage pattern.
- **nelinho-review** — gate pré-merge 9 secções (Spelke, testes, ZERO MOCKS, ACTION_WIRING, audit).
- **nelinho-invariants** — 12 invariantes do CPO verificáveis com grep (CoeficienteX≠tempo, etc.).

---

## 9. COMO CORRER TUDO

```powershell
$env:PYTHONPATH = "c:/Users/User/nelinho"

# 1. BD do zero (quando schema desync)
.\.venv\Scripts\python.exe scripts\bootstrap_dev_full.py

# 2. Backend (porta 8001 — alinhar com o frontend, ver §4.7)
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8001 --reload

# 3. Frontend (noutro terminal)
cd frontend; npm run dev      # Vite na 5173

# Verificação
.\.venv\Scripts\python.exe -m pytest tests/governance/ -q   # canary 348 tests ~53s
.\.venv\Scripts\python.exe -m pytest tests/ -q              # suite completa
cd frontend; npx tsc -b --noEmit                            # frontend typecheck
```

Pré-requisitos: Postgres 16 na 5432; Ollama para o copiloto. Redis/Kafka opcionais em dev.
Tenant dev: `00000000-0000-0000-0000-000000000001`.

---

## 10. ESTADO ACTUAL — % e o que falta

**% para produto final: ~70%**

| Dimensão | % | Razão |
|---|---|---|
| Backend código | 92% | falta wire 5 dispatchers Q.17 + 4 reports stubs + 2 legacy |
| Frontend código | 88% | 3 páginas com hardcodes + ~7 botões mortos + porta 8000/8001 |
| Dados a fluir | 50% | ERP tem tudo (2.6M operações, 18 anos histórico); adapter lê live; faltam 3 ETLs |
| Integração IT NELO | 50% | views `vw_pp1_*` por aplicar |

### Plano Q.20→Q.22 (~3-4 semanas)

- **Q.20 — DADOS (1.5-2 sem):** endpoints novos via adapter (sem ETL maciço); pedir a IT NELO para aplicar `views_pp1.sql`; `sync_master_data.py` (mirror diário PRODUTO/FASE/ENTIDADE/BOM); `sync_excel_moldes.py` (510 moldes); `sync_operator_skills.py`; unificar quality.
- **Q.21 — FRONTEND (1 sem):** remover hardcodes QualidadePage; resolver porta 8000/8001 + 47 hardcodes; wire botões mortos; esconder "Coming Soon"; apagar 5 wrappers triviais.
- **Q.22 — BACKEND (1 sem):** wire 5 dispatchers Q.17; reports persistence + SMTP; tabela User real; KPI explanations; decidir destino do `infrastructure/erp/sqlserver` deprecated.

### Critério de "pronto"

- As 10 páginas do menu mostram dados reais (não vazio, não hardcoded).
- `grep "MOCK_|TODO|coming soon" frontend/src/pages/` → zero.
- `pytest tests/ -q` → ≥1841 verdes.
- CEO abre DirecaoPage → €/dia real → drill-down a OF → fase + operador + tempo real do ERP.

---

## 11. PEGADINHAS — não cair nestas

1. **ZERO MOCKS no frontend** — nunca `const MOCK_X`, nunca `data ?? [...]`. Empty/error/loading explícitos. Dev e prod usam a mesma API; só muda o tenant_id.
2. **PT-PT, não PT-BR** — utilizador (não usuário), tu, camião, registo, gerir, fase (não estação), barco, molde, retrabalho. Aplica-se a UI E a mensagens de erro Pydantic.
3. **CoeficienteX é €, nunca tempo.** Grep antes de submeter em `src/plan/cpo/`.
4. **Não correr `alembic upgrade head` em dev** — falha no pgvector. Usar `bootstrap_dev_full.py`. Bug conhecido: migration 026 tem down_revision errada (025a_phase_bonus_payout vs 025a_phase_bonus).
5. **Kafka offline / `/v1/realtime/events` 503 em dev é esperado** — não é bug.
6. **Conexão SQL Server é read-only** — nunca escrever no ERP vivo.
7. **Property tests Spelke não se modificam** — corrigir o código.
8. **Sub-sprint Q.X.Y** — diff >400 LOC (sem testes) = partir em sub-sprints.
9. **ACTION_WIRING matrix espelhada backend+frontend** — mudar um lado obriga o outro.
10. **`init_db()` faz `create_all` só dos modelos importados** — se falta tabela, falta import (ou correr `bootstrap_dev_full.py`).
11. **CLAUDE_1.md está stale** — usar CLAUDE.md + agent_docs/.
12. **Conflito porta backend 8000 vs 8001** — ver §4.7. Resolver antes de testar a UI.

---

## 12. APONTADORES DE FICHEIROS

- **Instruções:** `CLAUDE.md` · **Docs:** `agent_docs/` (architecture, spelke_axioms, q17_logic_as_data, bootstrap_recovery, sprint_history, domain_glossary, mar_kayaks_schema_discovery, nelo_executive_summary, views_pp1.sql)
- **Skills:** `.claude/skills/` (7 SKILL.md)
- **Adapter NELO:** `src/adapters/nelo/` · **Sync ETL:** `scripts/sync_nelo_to_postgres.py`
- **CPO:** `src/plan/cpo/` · **Q.17:** `src/governance/yaml_policy/`
- **Frontend referência:** `frontend/src/pages/admin/RegrasPage.tsx`
- **Config:** `src/shared/config.py` + `.env` · **Bootstrap:** `scripts/bootstrap_dev_full.py`
- **Visão original:** `PP1_NELO_PLANO_v4.md` (histórico, não actualizado)

---

*Handoff gerado por exploração read-only em 2026-05-16. Branch `feat/q18-ui-A`. Owner: Luis
(luis@nikufra.ai) — PT-PT informal, respostas curtas, números concretos.*
