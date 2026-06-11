# DATA_FLOW_MAP.md — Mapa de arquitetura e dados do nelinho

> **Snapshot:** todas as contagens de BD neste documento foram medidas a **2026-06-11 (~10:40–11:00 UTC)**
> na instância Postgres `prodplan-pg-wsl` / base `prodplan_one`, em modo SELECT-only, durante a auditoria
> multiagente de 2026-06-11 (44 agentes, verificação adversarial). Cada afirmação está marcada como
> **confirmado-no-código**, **confirmado-na-BD** ou **HIPÓTESE**.
>
> Documentos irmãos: [AUDIT.md](AUDIT.md) · [DOMAIN_RULES.md](DOMAIN_RULES.md) ·
> [DESIGN_SKILL_PROPOSAL.md](DESIGN_SKILL_PROPOSAL.md) · [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md) ·
> [CUBE_LLM_KPI_AUDIT.md](CUBE_LLM_KPI_AUDIT.md) · [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) ·
> [TEST_PLAN.md](TEST_PLAN.md)

---

## 1. Arquitetura de runtime

```
ERP NELO (SQL Server, fabrica.nelo.eu:1039, SQLSERVER_ENABLED=true)
   │  ETLs 5-min / 15-min / nightly (APScheduler, in-process no backend)
   ▼
Postgres 16 (docker prodplan-pg-wsl, pgvector:pg16, :5432, DSN em .env:16)
   ├── factory_raw (espelho ERP, 24 tabelas + 4 views)──► marts (30 views) ──► Cube :4000 ──► LLM (Ollama)
   ├── plan / supply / governance / shared / quality / core / hr / profit …
   │
   ├──► CPO state loaders (src/plan/cpo/state_loaders.py) ──► Arq worker (cpo_schedule_job)
   │       └──► public.plan_schedule_commits (DRAFT) ──► /overall (frontend)
   │
Backend FastAPI uvicorn :8001 (src/main.py:45) ◄── Frontend Vite :5173 (React 19)
   └── Redis (docker) = fila Arq + breaker/health
```

| Processo | Onde | Detalhe (confirmado-no-código) |
|---|---|---|
| **Backend FastAPI** | uvicorn `:8001`, sem `--reload` | App factory `src/main.py:45`; arranque `src/app/startup.py:42` (structlog → OTel → Sentry → `init_db()` → redis/kafka/tool_registry/yaml_policy em paralelo → `start_scheduler()` → ML retrain + `register_tenant()` → RealtimeBridge → NOTIFY listener). Routers únicos em `src/app/routers_registry.py:45` (~60 routers, 465 endpoints). Middleware por ordem (`src/app/middleware_registry.py:94`): TraceId → TenantContext (JWT/X-Tenant-Id → `SET LOCAL app.tenant_id`, RLS migração 056) → CORS → RBAC (só prod/strict, fail-open fora da matriz `middleware.py:154-158`) → QualityGate → metrics + `pause_writes` (423). |
| **Worker Arq** | processo separado | `cpo_schedule_job` (`src/plan/cpo/worker.py:61`) corre `run_cpo_schedule`, grava ScheduleCommit DRAFT + `reapply_manual_overrides` (`worker.py:147`, Q.142.D). `job_timeout=1200s` >> solver 300s (invariante Q.162.A), `max_jobs=4`, heartbeat 60s, health key `arq:nelinho:cpo:health`. Deploy: `deploy/systemd/nelinho-arq.service` + `serve_demo.ps1`. **Gotcha:** `serve_demo.ps1:97-98` trunca `_arq.err` a cada arranque — logs do worker não sobrevivem a restarts. |
| **APScheduler** | in-process no backend | `src/scheduling/core.py:91-396` (20 jobs globais) + `:399-629` (16 por-tenant). `AsyncIOScheduler(timezone='UTC')`, jobstore **em memória** — sem catch-up: se o processo estiver desligado às 06:35 UTC, os jobs diários desse dia perdem-se (consistente com `plan_execution_observed=0`). Detalhe completo na secção 5. |
| **Postgres** | docker `prodplan-pg-wsl` | pgvector/pgvector:pg16, porta 5432; `postgresql+asyncpg://prodplan:***@localhost:5432/prodplan_one`. 19 schemas (secção 3). |
| **Cube** | docker `:4000` | Camada semântica; `CUBEJS_DB_HOST=host.docker.internal:5432`. **51 cubes / 139 measures, mas 18/51 cubes apontam a views inexistentes → 51/139 measures mortas em query-time** (confirmado live: `/load` → HTTP 400). Marts criadas por 48 scripts manuais `scripts/setup_marts_*.py` — Alembic só cria o schema (`alembic/versions/063_q93_a_marts_schema.py`); bootstrap não os corre. Detalhe em [CUBE_LLM_KPI_AUDIT.md](CUBE_LLM_KPI_AUDIT.md). |
| **Ollama** | local | Modelo qwen3.5:9b para o copiloto (`/api/copilot/ask`, `/ask-cube`: interpret→Cube→narrate). |
| **Frontend** | Vite `:5173` | React 19 + TanStack Query + Tailwind. 9 rotas vivas, 5 no menu (`App.tsx:89-111`, `Sidebar.tsx:52-58`). SSE global `/v1/realtime/events` (`App.tsx:84`). |
| **Sync ERP** | 5-min (jobs APScheduler) | Último sync verificado: **2026-06-11 10:40–10:42 UTC** (of_fp, ordemfabrico, movimento, entidade, of_checklist) + nightly 02:30 (moldes, produto, offp_eq). Mirror janelado a 2 anos + keep-open (`scripts/q75_setup_raw_mirror.py:101-110`). |
| **Demo remota** | Tailscale + Caddy | Single-origin; auto-arranque via `serve_demo.ps1` + tarefa `nelinho-demo`. |

**Dois motores de planeamento:** greedy+GA legado (`CPOv4Engine`) e solver global OR-Tools CP-SAT
(Q.166, `src/plan/engines/cpsat_global.py`), gated pelo axioma-7 (`src/plan/cpo/engine.py:160-204` +
`safety_net.py`). Estado live no snapshot: **CP-SAT vetado pelo guardrail idle_ratio desde 2026-06-10 →
o plano servido é greedy puro com makespan 22.297h (~2,5 anos) vs ~690h do CP-SAT** (commit `660752e1`,
2026-06-10 16:37, makespan 689,95h). A decisão do Luis (2026-06-11) — baseline justo sobre o mesmo op-set
+ isenção de guardrails soft quando o makespan melhora >50% — está em [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md);
a análise do gate em [AUDIT.md](AUDIT.md).

---

## 2. Mapa páginas → rotas → endpoints → serviços → tabelas

Menu (5): Decisões `/decisoes` · Planeamento `/overall` · Expedição `/expedicao` · Copiloto `/llm` ·
Configurações `/configuracoes`. Fora do menu: `/login`, `/operador` (standalone), `/pesquisa` (⌘K),
`/` → redirect `/decisoes`, `*` → 404 PT-PT. Globais sempre montados: CopilotFab+Drawer (`Layout.tsx:42`),
CommandPalette, EntitySheets (`App.tsx:113`), SchemaDriftAlert (`Layout.tsx:52`), RealtimeProvider SSE.

| Página (ficheiro) | Rota | Endpoints principais | Serviço backend (ficheiro) | Tabelas/views (linhas no snapshot) | Estado/problemas |
|---|---|---|---|---|---|
| DecisoesPage (`pages/decisoes/DecisoesPage.tsx`) | `/decisoes?tab=` | GET `/v1/decisions?status_filter=PROPOSED` (poll 5s + SSE 5 tópicos `:74-78`); POST `/v1/decisions/{id}/approve` | `src/shared/api/decisions.py:137-875` | `shared.decision_runs` (105: 102 REJECTED, 2 PROPOSED, 1 APPROVED) + `decision_approvals` (1) | OK; badge da Sidebar engole erro (`Sidebar.tsx:70-72` `catch→0`) |
| · DecisionCard/HubActions (`DecisionHubActions.tsx:78`) | — | GET `/v1/profit/preview?schedule_commit_id=` | `src/profit/services/margin_preview.py` | `core.daily_revenue_target` (**0** → delta € null), `core.labor_rates` (4.244, **não lidas** — €12/h hardcoded, secção 6) | **"Ver plano" passa `?commit_sha=` que o OverallPage ignora** (zero `useSearchParams` no ficheiro) |
| · SimulacoesTab | `?tab=simulacoes` | GET `/v1/twin/scenarios`; POST scenarios/apply-delta/simulate | `src/twin/api.py:118-155` (métricas BLOCKED honestas) | `twin.twin_scenarios` (2) | Crise: 6 cenários com €/dias hand-authored (`crisisScenarios.ts:124-150`, rotulado "referência") |
| · HistoricoTab (`HistoricoTab.tsx:191-199`) | `?tab=historico` | GET `/v1/decisions page_size=100`; `/decisions/{id}/audit`; preference-rules | idem + `core.audit_log` (1.189) | `governance.preference_rule` (**0**) | corta a 100 (BD tem 105), sem paginação |
| OverallPage (`pages/overall/OverallPage.tsx`) | `/overall` | GET `/v1/plan/cpo/commits?limit=1&excludeDegenerate` (30s); `commits/{sha}?include_operations`; `/v1/plan/timeline/actuals`; `/v1/plan/phases/catalog`; `/v1/core/employees` ×2; `/v1/copilot/alerts WARN`; `/v1/factory-map/snapshot`; excluded-boats; POST reorder/preview-delta/schedule async+poll/approve | `cpo_routers/commits.py:79-403` (approve `:519` DRAFT→LIVE SoD); `TimelineActualsService` (`timeline_actuals_service.py:52-151`, SQL cru, ids primeiro + `=ANY()` Q.163) | `public.plan_schedule_commits` (206 = **203 DRAFT + 3 LIVE**; ops em JSONB `operations`, último DRAFT hoje 10:40 com 8.059 ops/985 ordens, payload 2,3 MB); `factory_raw.of_fp` (972.519) + `offp_eq` (1.421.128) + `transp_of` (93.268) + `v_of_is_boat` (76.774 barcos) | `?commit_sha=` não lido; re-fetch 2,3 MB/30s sem GZip/ETag; 985 lanes sem virtualização |
| · RiskStrip (`components/overall/RiskStrip.tsx`) | — | otd-risk ✓ · molds/health-report ✓ · factory-map/shortage-risks ✓ · **`/v1/workforce/risks/spof` ✗ (endpoint APAGADO no saneamento, `src/workforce/__init__.py`)** | `risk_flags.py:77-121` | `supply.supply_rop_configs` (**0** → shortage `items=[]` sempre); `plan.mold_health` (289) | Painel SPOF nunca aparece (404 recorrente); ShortageRiskPanel permanentemente invisível |
| · OpCard→QualityRiskBadge | — | GET `/v1/quality/risk-preview` (lazy, IntersectionObserver Q.144.E) | `defect_risk_service.py:124-143` | `factory_curated.order_phase` (**0**) → `phase_error_rate` sempre 0.0 | Badge praticamente nunca acende (skew treino factory_raw vs serving factory_curated) |
| ExpedicaoPage (`pages/expedicao/ExpedicaoPage.tsx`) | `/expedicao` (`?date=`) | GET `/v1/plan/transport/batches?from_date`; POST `refresh-from-orders`; `/by-date`; `/ready`; `/throughput`; POST `/v1/plan/ctp`; GET `/v1/profit/otd` | `src/plan/api/transport.py` (15 eps); `transport_batch_service.py`; `ctp_service.py:154-194` (gate de materiais = **proxy do stock do produto acabado, não explode BOM**) | `plan.transport_batch` (20, todas OPEN) + `transport_batch_assignment` (589) + `factory_raw.transp_*` | Tabs em useState (sem `?tab=`); capacidade 50 vs `TRUCK_CAP=26` (`ProntosTab.tsx:20`); "meta 95%" hardcoded (`ListaTab.tsx:185`); assignments obsoletos nunca limpos (`transport_batch_service.py:256-261`) |
| LLMPage → CopilotPage | `/llm?tab=chat` | GET/POST `/api/copilot/conversations(+messages)`; POST `/api/copilot/ask` / `/ask-dev-cube` | `src/copilot/api.py:116` (**prefixo `/api/copilot` fora da matriz RBAC /v1/***) | `public.copilot_conversation`/`copilot_message` (**0** — histórico exige JWT, nunca persistiu) | Caminho Cube do chat usa endpoints `*-dev` → 404 em production (`headers.py:313-325`) |
| · KPIsTab (`pages/llm/KPIsTab.tsx`) | `?tab=kpis` | GET `cube/dashboard-dev` (60s); `cube/measures-dev`; POST `cube/measure-cards-dev`; OtdHeatmap `/v1/profit/kpis/otd-heatmap` | `src/copilot/routers/ask_cube.py:289-298` (8 cards curados); `src/profit/api/kpis.py:448-479` | marts (30 views) via Cube; OtdHeatmap lê `plan.production_schedules` (**0** → matriz vazia) | Degradação honesta exemplar nos cards; **18/51 cubes mortos** afetam o picker |
| · AlertasTab | `?tab=alertas` | GET `/v1/copilot/alerts`; POST acknowledge/resolve | `copilot/alerts/engine.py` (thresholds hardcoded, ignora keys `alertas.*`) | `public.copilot_alerts` (17; 2 ativos) | OK |
| · RegrasPage (`pages/admin/RegrasPage.tsx`) | `?tab=regras` (também em `/configuracoes`) | GET/POST `/v1/governance/yaml-policy/rules(+propose/approve/reject/suspend/rollback)` | `src/governance/yaml_policy/api.py` (7 eps); engine arranca "0 active rules" (`startup.py:118-124`) | `governance.yaml_policy_rule` (**0**), `yaml_policy_rule_revision` (**0**) | **Página inteira a zeros**; só 1 dos 12 eventos do DSL é emitido (`scheduler_run.py:597` SCHEDULE_PROPOSE) |
| ConfiguracoesPage (8 tabs) | `/configuracoes?tab=` | master-data, revenue-target, client-priority, user-input, learning, workforce sectors, preferred-operators | `src/master_data/api`; `q115_config.py:127`; `learning/api_*` | `core.daily_revenue_target` (**0**), `client_priority` (1), `user_input` (**0**), `governance.phase_operator_affinity` (266 ✓), `phase_preferred_operator` (2), `quality.runbook` (**0**) | Tab Custos vazia em produção; plan-vs-actual lê `plan.plan_execution_observed` (**0**) |
| OperadorTabletPage | `/operador?worker=` | auth/me; `/v1/core/employees`; workerOperationsApi.today; start/finish; POST rework | `src/quality/api.py:145-214`; `operation_execution_service` | `quality.rework_entry` (5.908); `plan.operation_execution` (**0** — start/complete nunca usados nesta BD) | PROBLEM_KINDS label→error_code desalinhado (`operadorTabletBits.tsx:13-17`) |
| LoginPage | `/login` | POST `/v1/auth/login` | `auth_login.py:74-84` (bcrypt) | `shared.users` (1) | OK |
| SearchResultsPage (`:57-66`) | `/pesquisa?q=` | GET `/v1/search` | `search/api.py:120-166` | production_orders + employees + molds + `quality.error_catalog` (**0** → facet errors sempre vazia) | **barco/molde/erro → `navigate('/overall')` sem contexto**; só operador abre ficha |

**Entity sheets** (`components/entitySheets/`, abertos por Clickable em qualquer página):
ModeloSheet/FaseSheet/ClienteSheet/EncomendaSheet/OperadorSheet → `GET /v1/entity/{tipo}/{id}`
(`src/plan/api/entity_summary.py:624/776/924/1193`) sobre factory_raw + `governance.boat_phase_score`
(68.645) + `phase_operator_affinity` (266). **Wiring partido confirmado-no-código:** OperadorSheet recebe
`employee_code` ("20365") mas o endpoint exige UUID → 422 (`entity_summary.py:1193`); ModeloSheet recebe
`OF_P_ID` numérico mas o endpoint indexa por `product_name` → tabs vazias.

**Cluster órfão no bundle** (construído, inalcançável): 8 componentes `palantir/` (só SchemaDriftAlert é
usado), ~8 hooks sem consumidor (useLiveKPIs, useTrustHeatmap, …), `lib/api/workforceApi.ts`
allocations/skillMatrix → endpoints apagados, `lib/factoryApi.ts` legacy (~750 linhas `Promise<any>`),
`lib/api/supplyApi.ts:13-146` (12 funções, 0 consumidores), `mrpApi` (`planApi.ts:46-69`) chama
`/v1/plan/mrp/runs` que **nem existe** no backend.

---

## 3. Schemas e contagens reais da BD (confirmado-na-BD, 2026-06-11)

### 3.1 Schemas — nº de tabelas base

| Schema | Tabelas | Schema | Tabelas |
|---|---|---|---|
| core | 20 | plan | 26 |
| dqa | 3 | profit | 8 |
| factory_curated | 10 (**todas a 0**) | public | 14 |
| factory_meta | 4 | quality | 4 |
| factory_raw | 24 (+4 views) | reports | 2 |
| governance | 14 | sandbox | 1 |
| hr | 8 (6 a 0) | shared | 3 |
| improve | 1 | supply | 8 (4 a 0) |
| ml | 1 (drift_event=0) | twin | 3 |
| **marts** | **0 tabelas, 30 views** | | |

### 3.2 factory_raw (espelho ERP) e frescura do sync

| Tabela | Linhas | Último `_synced_at` (UTC) |
|---|---|---|
| of_fp | **972.519** (ERP ~2,6M; janela 2 anos + keep-open `OFFP_DATAFIM IS NULL`, `q75_setup_raw_mirror.py:101-106`) | 2026-06-11 10:41:56 |
| movimento | **2.544.418** (janela 2 anos; ERP ~12,4M) | 2026-06-11 10:42:10 |
| offp_eq | 1.421.128 | 2026-06-11 02:30 (nightly) |
| ordemfabrico | 445.435 (OF_DATAFIM NULL 71,5%) | 2026-06-11 10:41:33 |
| of_checklist | 101.360 | 2026-06-11 10:42:02 |
| produto / produto_componente / produto_fase / produto_tipo | 14.110 / 119.910 / 43.510 / 422 | 02:30 (nightly) |
| entidade / entidade_phc / entidade_phc_fact / entidade_tipo | 9.031 / 752 / 100.872 / 36 | 10:41:12 |
| moldes / fases_producao | 91 / 71 | 02:30 |
| transp_of / transporte / transp_datas / transp_tipo / transp_destino | 93.268 / 11.393 / 3.052 / 58 / 4 | 10:40:59 |
| ent_mov / ent_mov_tipo | 167.002 / 15 | — |
| excel_row | 0 | — |

Qualidade do espelho (confirmado-na-BD): **0 datas `1900-01-01`** (o comentário `state_loaders.py:1122`
está desatualizado — min real `1990-01-01`); `OFFP_DATAINICIO` NULL 16,3%, `OFFP_DATAFIM` NULL 58,0%
(keep-open by design); 0 duplicados de `OFFP_ID`; datas em TEXT ISO-8601 (decisão deliberada, q75:132-134).
**Não espelhadas:** `entidade_fase` (gate skills lê o ERP direto, `adapters/nelo/services.py:380` →
`hr.employee_skills`=1.024), `produto_stocks_por_armazem` (→ `supply.warehouse_stock`),
`apontamento_trabalho` (declarada no mirror q75:118 mas **a tabela nunca existiu na BD** — horas de M.O.
reais indisponíveis; ETL time_mining stale 106,8h), `MOVIMENTO_TIPO` (semântica dos tipos só em
`routes/_GLOSSARIO_BURACOS.md:14-31`).

### 3.3 Views críticas e marts

- `factory_raw.v_of_em_producao` → **1.145** · `v_of_is_boat` → 445.435 (is_boat=true em **76.774**) ·
  `v_of_is_mold` → 445.435 · `v_active_operators` → **106** · `marts.v_ofs_fechadas_dia` → 6.353.
- marts (30 views, maiores): v_consumo_material_dia 80.316 · v_facturacao_mes 38.270 · v_arpu_mes 27.642 ·
  v_producao_disciplina_mes 4.374 · v_capacidade_fase_mes 3.360 · v_taxa_defeitos_dia 2.591.
  Suspeitas/mortas: **v_rework_por_molde_mes = 0** (rework_entry.mold_id 100% NULL), v_moldes_idade = 1,
  v_backlog_dia = 1 (HIPÓTESE: view agregada-total ou filtro a excluir quase tudo).
- 18 views referenciadas pelos cubes **não existem** nesta BD (v_workforce_*_mes, v_transportes_mes,
  v_horas_operador_mes, v_ciclos_cura, v_copilot_*, …) — lista completa em [CUBE_LLM_KPI_AUDIT.md](CUBE_LLM_KPI_AUDIT.md).

### 3.4 Restantes schemas — tabelas com dados vs a zero

| Schema | Com dados | A zero (UI/endpoint vivo por cima) |
|---|---|---|
| plan | production_orders **9.607** (todas IN_PROGRESS, completed_date 100% NULL, **sem coluna due_date** — derivado em runtime `state_loaders.py:1138-1140`); model_routing_assignment 4.737; phase_duration_calibration 3.221; routing_template_phase 1.433; factory_calendar_day 583; transport_batch_assignment 589; mold_health 289; routing_template 142; mold 95; transport_batch 20 | production_schedules, phase_config, operation_execution, fases_of_history, material_requirements, purchase_orders, plan_exclusion, order_boost/boat_boost, production_errors, phase_transition_gap, plan_execution_observed, mold_usage_counter/defect_log/maintenance_event |
| supply | warehouse_stock **8.069** (fresco 10:45); inventory_ledger_entries 34.076 (**só 14 dias**); supply_material_master **14.110**; purchase_orders 138 | **supply_rop_configs=0**, supply_forecasts, supply_material_in_transit, supply_stock_reconciliation |
| governance | boat_phase_score 68.645; rule_firing 6.328 (de outro motor, não do yaml_policy); boat_complexity 1.604; phase_operator_affinity 266; phase_preferred_operator 2 | decision_run, decision_policy, approval, **yaml_policy_rule**, yaml_policy_rule_revision, kill_switch_active, preference_rule, boat_potential |
| shared | decision_runs 105; decision_approvals 1; users 1 | — |
| quality | rework_entry **5.908** (5.904 source=erp_of_checklist; **mold_id NULL em 100%**; só 4 com cost_estimate_eur, total 610 €) | error_catalog, runbook, error_type_runbook_link |
| core | employees 362; customers 1.351; products 14.110; bom_items 86.438; labor_rates 4.244 (média 5,41 €/h); tenant_configuration 186; etl_run 11.281; audit_log 1.189 | machines, suppliers, overhead_rates, **daily_revenue_target**, operations, user_input |
| hr | employee_skills 1.024; skills 71 | employee_productivity, hr_allocations, legacy_allocations, monthly_payroll_summary, shift_schedules, worker_phase_assignment (**6/8 a zero**) |
| profit | product_pricing 3.714; kpi_snapshot 60 | cost_calculations, order_revenue, pricing_recommendations, profit_scenarios, shipping_rate, phase_bonus_payout |
| public | plan_schedule_commits 206; copilot_rag_chunk 139; copilot_alerts 17; ml_model_artifact 4 (congelados desde 2026-05-30); event_outbox 2 | copilot_conversation/message/user_feedback/daily_feedback/suggestion/action_logs, decision_pr (`copilot_request_log` **nem existe como tabela**) |
| factory_curated | — | **TODAS as 10 a zero** (allocation, cost_reference, modelo, mold, mold_usage, order, order_phase, phase_capacity, quality_event, skill_matrix) |
| dqa / reports / ml / factory_meta | — / — / — / — | trust_index_snapshots, data_quality_issues, auto_repair_logs, report_run, report_schedule, drift_event, ingestion_run — tudo 0 |
| twin / improve | twin_scenarios 2 / improve 5 | — |

---

## 4. Tabelas reais por domínio (o que o dono pediu)

| Domínio | Fonte de verdade real | Notas |
|---|---|---|
| **Barcos** | `factory_raw.v_of_is_boat` (76.774 barcos de 445.435 OFs; critério = PRODUTO_TIPO raiz Kayak TP_ID=1, **não** P_QTDDECK/CASCO); em produção: `v_of_em_producao` = **1.145** (op aberta na fase atual, sem OF_DATAFIM) | View recursiva — JOIN+ORDER BY dá timeout; padrão correto: buscar ids e `=ANY()` (Q.163) |
| **Modelos** | `factory_raw.produto` (14.110) + `produto_tipo` (422); routing: `plan.model_routing_assignment` (4.737), `routing_template` (142) + `routing_template_phase` (1.433) | `model_id` = `P_ID` numérico; o ModeloSheet parte porque `entity_summary.py:626-646` indexa por `product_name` |
| **Setores** | **Não existe master de setores/máquinas** (`core.machines`=0; `OFFP_ARM_ID` constante no ERP). Proxy: `AREA_GROUPS` 7 sectores em `src/workforce/levels.py:57-65` (só níveis/UI) + estações por fase via p95 da concorrência histórica (`phase_workcenters.py:79`, teto 40, default 4 — auto-referencial) | Não há cap "Laminagem ≤ N barcos/dia" em código nenhum |
| **Operadores** | `core.employees` (362) + view `factory_raw.v_active_operators` = **106 operadores ativos** (E_ACTIVO + atividade nos últimos 2 meses); skills: `hr.employee_skills` (1.024, gate Entidade_Fase lido direto do ERP) + `governance.phase_operator_affinity` (266) | Sem modelo de férias/ausências/turnos individuais — operador de férias continua alocável (calendário GLOBAL 1 turno 8h, `factory_calendar.py:34`). Identidade dupla: plano usa `employee_code`, endpoints entity usam UUID |
| **Expedição** | ERP: `transp_of` (93.268), `transporte` (11.393), `transp_datas` (3.052); nelinho: `plan.transport_batch` (20) + `transport_batch_assignment` (589), derivados de production_orders (Q.143) | "Pessoa de expedição" **não existe como entidade** — só transportadoras-empresa (E_TRANSPORTADOR=84) e TR_OPERADOR_CODIGO c/ 3% cobertura. Plano→camião: **nenhuma ligação** (truck_consolidation weight 0.0, função só chamada em testes) |
| **Fases** | `factory_raw.fases_producao` (71, ordenadas por FP_SEQUENCIA — endpoint `/v1/plan/phases/catalog`); durações reais: `plan.phase_duration_calibration` (3.221); cura: `NELO_CURING_GAPS_SEED` 16 transições (`state.py:33`) — `plan.phase_transition_gap`=0, seed em código é a única fonte | Fases de estado {11,32} duração~0; markers terminais 'entregue/armazem/embalado' (`phase_classification.py:81`) |
| **Gamas** (decisão Luis #3: gama/drop = **tipo/disciplina do produto**) | `factory_raw.produto_tipo.TP_ID` (422 tipos, raiz Kayak=1) + `produto.P_TP_ID_DISCIPLINA` (alimenta marts v_producao_disciplina_mes) | Não existe nenhuma coluna "gama"/"drop" na BD nem no ERP — confirmado por introspecção; a decisão #3 fixa a semântica |
| **Materiais / BOM** | BOM: `factory_raw.produto_componente` **111.339 ativas** (119.910 total; COMP_QUANTIDADE + COMP_FP_ID = fase de consumo) → espelho `core.bom_items` (86.438). Consumos: `factory_raw.movimento` **2.544.418** — tipo 11 (consumo p/ OF) = **1.468.924** (1.243.409 c/ MOV_OF_ID → join `ordemfabrico.OF_P_ID` dá o modelo); tipo 4 = reservas; tipo 9 = pedidos a fornecedor (12.706); mart `v_consumo_material_dia` 80.316 | Semântica TPMOV confirmada em `routes/_GLOSSARIO_BURACOS.md:14-31` (1=Entrada, 2=Saída, 4=Reserva, 11=Saída como componente, 12=Pedidos internos); a tabela lookup **não está espelhada**. "Materiais restantes por OF" não existe no produto (únicos leitores de movimento/BOM em src/ = boat_complexity_job) |
| **Reparações** | `REPAIR_PHASE_IDS` = {14, 76, 77} (`state.py:113`); live: **76 OFs em reparação** (fase 14→32, 77→30, 76→14, via v_of_em_producao) | **74/76 estão FORA de `plan.production_orders`** (mirror filtra `OF_DATAFIM IS NULL`, `q131_setup_production_orders_mirror.py:61`) → invisíveis na expedição; o CP-SAT exclui-as sem merge-back (`cpsat_global.py:72`). Decisão Luis #2: merge-back no MESMO plano /overall, agendadas a seguir no mesmo commit, com filtro/badge — plano em [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md). ERP canónico inclui colagem(53) — divergência por confirmar |
| **Stock** | `supply.warehouse_stock` 8.069 (espelho `produto_stocks_por_armazem`, fresco 10:45); `supply_material_master` 14.110 — **min_stock_qty=0 em 14.110/14.110** (hardcoded `material_master.py:56`) apesar de **P_STOCKMIN>0 em 1.110 produtos** no ERP; **lead_time_days=7 placeholder em 100%** (fonte real: `entidade.E_PRAZOENTREGA` ≠0 em 114 entidades, não importada) | Decisão Luis #4: importar P_STOCKMIN + override local; lead times de E_PRAZOENTREGA — ver [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md). `supply.purchase_orders` 138 = ~2% dos 5.987 pedidos tipo-9/12 meses, ETA fictícia +30d |
| **KPIs** | marts (30 views) → Cube → KPIsTab; `profit.kpi_snapshot` (60, 5 KPIs sem €, sem leitor); faturação: `factory_raw.entidade_phc_fact.EPHCF_FACTURADO` (100.872 linhas — **mesma coluna** no Cube e no ThroughputService, coerente) | Duas definições de "OFs em curso" coexistem: Cube FP_SEQUENCIA<30 (8.510) vs v_of_em_producao (1.145) |
| **Cube** | 51 cubes / 139 measures; **18/51 mortos → 51/139 measures** mortas em query-time; MEASURE_REGISTRY=132 (9 measures YAML fora do registry; 2 workforce com nomes errados) | Detalhe e plano de correção em [CUBE_LLM_KPI_AUDIT.md](CUBE_LLM_KPI_AUDIT.md) |
| **LLM/copiloto** | `copilot_rag_chunk` 139; `copilot_alerts` 17; conversas/feedback **0** (write-only); `copilot_request_log` inexistente | Loop feedback→prompt não existe; endpoints `*-dev` 404 em production |

---

## 5. Jobs de fundo e o que escrevem

### 5.1 APScheduler — globais (`src/scheduling/core.py:91-396`)

| Job | Cadência | Escreve | Estado real (snapshot) |
|---|---|---|---|
| nelo_erp_incremental_sync | 5 min (jitter 25s) | mirrors stock/calendar/quality/checklist | ✓ etl_run HOJE 10:40 |
| nelo_erp_raw_incremental | 5 min | factory_raw pesado (of_fp, movimento, …) | ✓ 10:41-10:42 |
| nelo_erp_comercial / logistica / customers / production_orders | 5 min | entidade_phc_fact / transp_* / core.customers / plan.production_orders | ✓ |
| **nelo_erp_phase_history_incremental** | 15 min | plan.fases_of_history + hr.worker_phase_assignment | ✗ **FALHA PERMANENTE 9/9** — consulta `dbo.FasesOf` / `dbo.WorkerAssignment`, nomes do **fake-ERP de teste** que não existem no ERP real (pyodbc 42S02; `adapters/nelo/services.py:828/863` — o resto do MESMO ficheiro usa OF_FP/OFFP_EQ reais). Destinos a **0**. Nenhum leitor de `etl_run.status='error'` dispara alarme |
| nelo_erp_sync (mirrors leves) | 02:00 | master/molds/skills/quality | ✓ |
| nelo_erp_raw_full_nightly | 02:30 | produto, moldes, offp_eq, … | ✓ 02:30 |
| nelo_erp_time_mining | Dom 01:00 | time mining OF_FP | ✗ stale 106,8h (último ok 2026-06-07; depende de `apontamento_trabalho` que não existe na BD) |
| order_status_reconcile | 15 min | production_orders.status | ✓ |
| auto_cpo_replan | 15 min | enfileira `cpo_schedule_job` (watermark WIP + rate-limit 60 min; `auto_cpo_replan_job.py:34-42`, plan_cap=0, solver 300s) | ✓ DRAFTs de hoje |
| auto_propose_signals | 5 min | `shared.decision_runs` (ADOPT_PLAN PROPOSED; supersede `:113`; Q.161.C auto-rejeita obsoletas `:215`) | ✓ (93 ADOPT_PLAN REJECTED — HIPÓTESE: maioria é o auto-expire, não rejeição humana) |
| plan_vs_actual / **capture_plan_execution** / phase_calibration | 06:30 / 06:35 / 06:40 | — / `plan.plan_execution_observed` / `plan.phase_duration_calibration` | calibration ✓ (3.221); **capture escreve 0** — só lê commits `status='LIVE'` (`capture_plan_execution.py:207-215`) e há **203 DRAFT vs 3 LIVE** (último LIVE 2026-06-02) → loop de aprendizagem plan-vs-actual faminto |
| kpi_snapshot | 00:45 | profit.kpi_snapshot | ✓ (60) |
| daily_feedback / audit_retention_purge / copilot_schema_reindex | 00:30 / 04:30 / 04:00 | copilot_daily_feedback / purge / RAG chunks | feedback **0**; chunks 139 ✓ |

### 5.2 APScheduler — por-tenant (`core.py:399-629`, 16 jobs)

| Job → destino | Estado |
|---|---|
| alerts_scan 15min → copilot_alerts | ✓ 17 |
| shortage_scan 60min → copilot_alerts | **inoperante**: varre 14.110 materiais todos com min_stock_qty=0 → `below_min` nunca true (`material_service.py:221`) → **0 alertas de material alguma vez criados** |
| mold_health_scan diário → mold_health | ✓ 289 |
| quality_risk_scoring 30min / multivariate_drift 30min | corre, sem rasto problemático |
| preference_rule_detector 03:00 → preference_rule | escreve **0** |
| phase_operator_affinity 03:30 / boat_phase_score 03:45 / boat_complexity 04:25 | ✓ 266 / ✓ 68.645 / ✓ 1.604 |
| boat_potential 04:20 → governance.boat_potential | escreve **0** (HIPÓTESE: gate interno ou input em falta — os irmãos funcionam) |
| preference_weights_retrain Dom 02:00 / abl_feedback 04:00 / dpo_finetune Dom 03:00 (opt-in) / causal_discovery Dom 05:00 (opt-in) / improve_adoption_signal 04:15 | sem destino com dados |
| runbook_learning 04:00 → quality.runbook | escreve **0** (gated approved_by=NULL) |

### 5.3 Jobs ML (registados no startup, `src/ml/jobs/scheduling.py:47-59`)

**Estruturalmente avariados** (confirmado-no-código): o dispatcher constrói `SemanticQueriesInMemory()`
sem o argumento `engine` obrigatório → TypeError → EmptyDatasetError em duration/quality_risk/otd_risk
(`scheduling.py:98` vs `semantic/__init__.py:51`); DriftDetectionJob rebenta com TypeError de assinatura
todos os domingos e é scaffold (nunca grava `ml.drift_event`=0); sequence_mining/throughput_forecast
treinam e **deitam fora** o modelo (sem registry.save; Prophet nem instalado). Os 4 artefactos em
`ml_model_artifact` são do seed one-shot de 2026-05-30 (`scripts/train_ml_models.py`) — **nunca houve
retreino**. Detalhe em [AUDIT.md](AUDIT.md).

### 5.4 Worker Arq

`cpo_schedule_job` → ScheduleCommit DRAFT + reapply de overrides manuais. **Override fantasma
confirmado-na-BD:** o delta `manual_drag` "op 110532::77 de 77 para 77" (no-op criado pelo E2E smoke
Q.172.C) é re-aplicado em cada replan porque `commits.py:404` só fecha a janela de coleta com um commit
LIVE — e nunca há LIVE → cada replan cria **2 commits DRAFT de ~8k ops (~2,3 MB cada)** com ~1s de
intervalo (pares 10:40:15 + 10:40:16 verificados).

---

## 6. Mocks / hardcoded / fabricados encontrados (com file:line)

O frontend cumpre o invariante ZERO MOCKS (0 ocorrências de `MOCK_`/`?? [{`) e o backend não tem
`_get_mock_*` — mas a auditoria encontrou números autorais/fabricados nos pontos abaixo:

| # | O quê | Onde (file:line) | Evidência / impacto | Estatuto |
|---|---|---|---|---|
| 1 | **transport_date com fallback OF_DATA (data de criação!)** | `scripts/q131_setup_production_orders_mirror.py:54-57` | 9.606/9.606 ordens "têm" data de expedição; OF sem promessa nenhuma fica com transport_date=OF_DATA. Diverge da derivação honesta do due_date (`state_loaders.py:1138-1140`); roça o invariante #8 | confirmado-na-BD |
| 2 | **€12,00/h hardcoded na margem prevista** | `src/profit/services/margin_preview.py:34-36` (`_DEFAULT_COST_RATE_EUR_H`), uso `:91` | `core.labor_rates` tem 4.244 taxas reais (média 5,41 €/h) e não é lida; `:242` inventa 1h por operação como último recurso → predicted_margin = −duração×12€ | confirmado-no-código |
| 3 | **ETA fictícia +30d nas encomendas** | `src/adapters/nelo/etl/purchase_orders.py:68` (`_ETA_PLACEHOLDER_DAYS`), `:109` (supplier_name "Fornecedor {id}"), `:121` (qty_received=0) | eta=ordered_at+30 em 138/138 POs; placeholders documentados (bloqueio MOVFOR_ETA, issue Q.68.A) | confirmado-na-BD |
| 4 | **min_stock_qty=0 + lead_time_days=7 hardcoded no ETL** | `src/adapters/nelo/etl/material_master.py:55-56` | 14.110/14.110 materiais sem mínimo nem lead time real (P_STOCKMIN>0 em 1.110 no ERP; E_PRAZOENTREGA em 114 entidades) → ShortageDetector inoperante | confirmado-na-BD |
| 5 | **6 cenários de crise hand-authored** | `frontend/src/components/simulacoes/crisisScenarios.ts:124-150` | deltaEur:-3200, "penalização €4.500", cascatas com barcos/datas inventados (#4274, 15/06). Rotulado "cenário de referência" (`CrisisSimulator.tsx:388`) — único bloco de números autorais no frontend | confirmado-no-código |
| 6 | **€400 + 4h fabricados na recomendação de manutenção de molde** | `src/explain/diagnostics/erro_tree.py:518-526` | `cost_estimate_eur: 400, downtime_hours: 4` hardcoded para mold_degradation — € inventado em recomendação ao operador | confirmado-no-código |
| 7 | **ExplanationEngine com pesos/impactos inventados** | `src/profit/explanation_engine.py:273-289` (55%/25%/20%), `:221-242` ("+5%", "+8%") | exposto via `/kpis/snapshot-explained` (`api/kpis.py:399-412`); mitigado por `advisory_mode:True` e por ser UI-órfão | confirmado-no-código |
| 8 | **Telemetria fabricada no greedy: fase 6 = core_elapsed/4** | `src/plan/cpo/greedy_pipeline.py:169` | `PhaseTiming(6, "workforce_assignment", core_elapsed/4, True)` — o Hungarian anunciado não corre (0 chamadores); o tempo reportado em cpo_meta é divisão arbitrária | confirmado-no-código |
| 9 | Backlog a 2.350 €/barco (proxy autoral) | `src/profit/services/dashboard_metrics_service.py:40` (`BACKLOG_DEFAULT_VALUE_EUR`), `:238` | preço único em vez de P_PRECOVENDA real (`profit.product_pricing`, 3.714); endpoints UI-órfãos | confirmado-no-código |
| 10 | Capacidade de camião inconsistente 50 vs 26 | `ExpedicaoPage.tsx:67` + `CTPTab.tsx:31` (50) vs `ProntosTab.tsx:20` (`TRUCK_CAP=26`, "moda real") + `transport_batch_service.py:220` (default 50) | recomendação "próximo camião" corta a 26 enquanto a página fala em 50 | confirmado-no-código |
| 11 | Meta OTD "95%" hardcoded | `frontend/src/pages/expedicao/tabs/ListaTab.tsx:185-195` | não vem de config nem da BD — pergunta ao dono | HIPÓTESE (regra de negócio não confirmada) |
| 12 | Botões de problema do tablet desalinhados | `frontend/src/pages/operadores/operadorTabletBits.tsx:13-17` | "Falta peça"→COLAGEM_FAIL, "Erro molde"→DIMENSION_OFF — causas de retrabalho potencialmente erradas a alimentar RCA | HIPÓTESE |
| 13 | Defaults autorais de scrap no COGS e pricing | `src/profit/calculators/cogs_calculator.py:161-162,193` (recovery 0.5, rework 0.1, scrap 0.02); `pricing_engine.py:112-113` (markup 40%, target margin 30%) | parametrizáveis mas sem origem ERP; pricing é órfão | confirmado-no-código |

Contra-exemplos verificados (honestos): `/v1/profit/oee` degrada com `erp_available:false`+razão
(`dashboard.py:102-204`); twin marca OEE/OTD como BLOCKED; `operators_summary_api.py:62` devolve
`{"count":0}`; factor M.O. 1.065 é **legítimo** (lido de `core.erp_variables` VAR_ID=2, fallback 1.0 —
`material_cost_service.py:44-45,150-165`).

---

## 7. Views vs BD — o que cada página mostra vs o que existe

UI viva (ou endpoint montado) por cima de tabelas vazias — o utilizador vê ecrãs estruturalmente prontos
mas permanentemente a zero:

| Superfície visível | Tabela(s) por trás | Linhas | Consequência |
|---|---|---|---|
| RegrasPage (`/llm?tab=regras`, `/configuracoes?tab=regras`) | `governance.yaml_policy_rule` (+revision) | **0** | 4 KPIs a zero, listas vazias; engine arranca "0 active rules"; só 1/12 eventos do DSL é emitido (`scheduler_run.py:597`) |
| Tab Custos & Objectivos | `core.daily_revenue_target` / `client_priority` | **0** / 1 | meta €30-35K/dia nunca semeada → delta € invisível em /decisoes, `revenue_alignment` do CPO neutro (`fitness.py:236-244`) |
| `/v1/factory/*` (Factory Data Product, 10+ GETs) | `factory_curated.*` | **10×0** | camada "Fase B" nunca ingerida desde Q.34 — mundo paralelo ao factory_raw (cheio); contamina o QualityRiskBadge (skew, secção 2) |
| `/v1/hr/productivity|allocations|payroll` | `hr.*` | **6×0** | módulo HR inteiro devolve vazio (só employee_skills/skills têm dados) |
| `POST /v1/plan/mrp/calculate` | `plan.material_requirements` / `plan.purchase_orders` | **0 / 0** | MRP nunca correu; BOM só via payload (`mrp_service.py:102` não lê core.bom_items); frontend `mrpApi` chama rotas inexistentes |
| ShortageRiskPanel (/overall) | `supply.supply_rop_configs` | **0** | `items=[]` sempre → painel invisível por construção (`risk_flags.py:98-121` + `ShortageRiskPanel.tsx:32`) |
| SpofRiskPanel (/overall) | — (endpoint `/v1/workforce/risks/spof` **apagado**) | n/a | RiskStrip anuncia "SPOF" mas o painel nunca aparece; 404 recorrente |
| OtdHeatmap (tab KPIs) | `plan.production_schedules` | **0** | matriz sempre vazia (sistema substituído pelos commits CPO; endpoint zombie `schedule.py:57`) |
| Pesquisa global — facet "erros" | `quality.error_catalog` | **0** | facet sempre vazia (`search/api.py:166`) |
| Copiloto — coluna de histórico | `public.copilot_conversation`/`message` | **0** | histórico exige JWT; nunca persistiu nesta BD |
| Tab Aprendizagem | `governance.preference_rule`, `quality.runbook`, `plan.plan_execution_observed` | **0/0/0** | "O que o sistema aprendeu" vazio; plan-vs-actual faminto (203 DRAFT vs 3 LIVE) |
| Tab KPIs — picker de measures | 18/51 cubes → views inexistentes | n/a | 51/139 measures dão erro ao adicionar card |
| `/v1/governance/decisions*` (11 eps) | `governance.decision_run`/`approval` | **0/0** | segunda casa de decisões vazia; a casa viva é `shared.decision_runs` (105) |
| FaseSheet — tab Configuração | `plan.phase_config` | **0** | feature Q.135 existe e o CPO respeita-a; nunca usada (defaults) |
| Tab Cura (FaseSheet) | `plan.phase_transition_gap` | **0** | só leitura do seed em código; PATCH existe sem UI |
| `/v1/dqa`, `/v1/reports` | `dqa.*`, `reports.*` | **0** | nunca produziram registos |

**O inverso também existe — dados vivos sem UI:**

- **Página Materiais foi APAGADA** (commit `2def464`, lean A1, 2026-06-02): os endpoints
  `/v1/supply/materials/from-bom` (com predicted_stockout_date), `/purchase-orders` e
  `PATCH /materials/{sku}/min-stock` continuam vivos no backend **sem nenhum consumidor** —
  mínimos/entregas/stockout não têm UI nenhuma. Plano de reposição em [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md).
- **~18 das 20 rotas `/v1/profit/*` são UI-órfãs** (cogs, pricing, scenarios, margins, cost-ledger… —
  `profitApi.ts` define-as, nenhuma página importa); os € visíveis vêm do Cube.
- **Configuração de tenant sem UI** (binding removido Q.172.E, `platformApi.ts:252-255`): as keys que
  comandam o planeador (`planning.scope=boats_and_molds`, `cpo.use_cpsat_global=true`) só são editáveis
  via API/SQL; agravante RBAC: o router real é `/v1/config` mas a matriz protege `/v1/core/config`
  (`rbac.py:233-234` vs `tenant_config.py:34`) → mutações de config caem no fall-through.
- `factory_raw.produto_fase` tem 22.002 linhas com `PRODF_COEFICIENTE_X>0` mas `profit.phase_bonus_payout`=0
  — não há ETL, só endpoint REST nunca chamado (`api/bonus_payouts.py:55-63`).

---

*Gerado pela auditoria multiagente de 2026-06-11. Para os achados priorizados e plano de ação ver
[AUDIT.md](AUDIT.md) e [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).*
