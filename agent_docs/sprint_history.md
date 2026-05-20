# Sprint history (Q.X.Y)

Reference cronológica do que cada sprint entregou. Substitui o "Sprints Q.1-Q.6" do CLAUDE_1.md
(stale). Lê para perceber por que é que algum padrão existe ou onde foi fixado um bug.

## Sprint convention (Q.X.Y format)

- **Q.X** = main sprint (Q.13, Q.14, Q.17, Q.18)
- **Q.X.Y** = sub-sprint (Q.17.B, Q.17.C, Q.17.D...)
- **Q.X.Y.Z** = micro-sub (raro, ex: Q.15.D.5 = ChainBuilder + integration tests)

Cada sub-sprint termina com pytest verde + smoke demo + commit message `Q.X.Y: <one-liner>`.

## Macro phases

### Q.1-Q.6 (early sprints, ~Apr 2026 — historical)

- **Q.1** TrustIndex v1→v2 (7+1 components) + frontend tooling (@dnd-kit, papaparse)
- **Q.2** Despacho/Expedição — 7 endpoints transport + 5 detectors + DispatchPage drag-drop
- **Q.3** Colaboradores GC01-GC10 — EmployeeExtras, quality_score Laplace, skill matrix, history
- **Q.4** Drag-drop Planeamento — PreviewDeltaService sub-segundo + DragDropPlanner Layer 1+2
- **Q.5** CEO Dashboard — DashboardMetricsService (OTD, FPY, backlog, expeditions next 7d)
- **Q.6** Polish + Settings — 6 tabs (Cura/Moldes/Quality/Trust/Sistema/Aprendizagem) + ConfigKeysPanel
- Resultado: 927 testes, advisory loop end-to-end

### Q.7-Q.10 (audit + foundation, ~Apr-May 2026)

- **Q.7** Audit pass — 17 modules, 9 bugs, 0 CVEs
- **Q.8** Data lineage — 10/10 sheets curated, CuratedAllocation 423K, CuratedModelo 899
- **Q.9** Fase 2-4 — 8 stubs production-path fechados, robustness, lazy imports
- **Q.10** Sandbox/twin/improve gaps fechados

### Q.11-Q.12 (foundation, ~May 2026)

- **Q.11** 60→92% — Camada 1+2 wired, 8 CPO flags ON, write-gate real, UX components
- **Q.12** Auth + segurança — `shared/auth/headers.py`, JWT, RBAC, kill switch, schema drift

### FASE -1/0 → FASE 6 (audit fixes, ~Apr 2026)

Bugs descobertos por audits que o plano original não previa. Fixed via FASE 1A (CRIT-10/11/12),
FASE 1B (CRIT-13..16, 23), FASE 2 (CRIT-02/17/18 atomicity), FASE 3 (HIGH-41..56), FASE 4
(silent_fallback metric), FASE 5 (regression tests), FASE 6 (tech debt cleanup).

### Q.13 — Causal & ABL pipeline (~May 2026)

- **Q.13.A** ScheduleCommit chain integrity
- **Q.13.B** OpenTelemetry scaffolding (no-op without exporter)
- **Q.13.C** Fitness adaptive weights retrain
- **Q.13.D** Camada 4 ABL infrastructure: `record_causal_audit`, `verify_chain_dict` (5 layers),
  NELO_DAG (23 nodes)
- **Q.13.E** Workforce service tightening, Truck moda=26 seed
- **Q.13.F** RBAC matrix completo (33 routes)
- **Q.13.G** Persistent issues closure: ABL admin endpoint, Sentry/OTel deploy gap, perf_audit
  tests, trust gate test rewrite

### Q.14 — Rule firing log + push reactivo + A/B (~May 2026)

- **Q.14.A** `governance.rule_firing` table + `@record_rule_firing` decorator + 14 sites
  instrumented + `GET /v1/governance/rule-firings` endpoint
- **Q.14.B** Postgres `LISTEN/NOTIFY` + SSE bridge `rule_firing` channel + listener task
  in lifespan
- **Q.14.C** A/B framework: `compute_adoption_stats` (Beta-Bernoulli), `resolve_variant`
  (deterministic hash), variant_id em rule_firing

### Q.15 — Diagnostic handlers (~May 2026)

- **Q.15.0** System prompt v2.2 + tool-calling specs + Capabilities marker
- **Q.15.D.0** Repository layer (15 query helpers in `src/explain/diagnostics/repository.py`)
- **Q.15.D.1** ERRO-TREE detector cascade (mold/worker/overload)
- **Q.15.D.2** Reichenbach core (multivariate drift monitor + 3 shared-resource checks)
- **Q.15.D.3** Reichenbach completion + drift scheduler
- **Q.15.D.4** Mill's method-of-difference detector (7 dimensions, Cohen's d ranking)
- **Q.15.D.5** CausalChain emission feeds Camada-4 ABL (chain_builder.py + 3 _emit_chain hooks)

### Q.17 — Logic-as-data (~May 2026, in progress)

- **Q.17.A** Foundation: YAML schema, Pydantic models, loader, hot-reload, `system_defaults.yaml`
  extracted from `default_configs.py`
- **Q.17.B** DSL design: 12 events × 9 actions × 8 ops × 7 axioms whitelist; LLM tools
  function-calling specs
- **Q.17.C** Page `/regras` + diff modal (split-pane composer, ViolationsBanner,
  StubbedActionsBadge, NL→Ollama→Pydantic pipeline with retry self-correct)
- **Q.17.D** Engine: registry indexed by event_type, install_rule, on_event with rate limit +
  dedupe (60s window, sha256 fingerprint), block_results
- **Q.17.E** Safety: AxiomChecker (7 axioms), ConflictResolver (5 patterns), RuleSafetyError
  → 422 with structured violations
- **Q.17.F** Wiring: 4 dispatchers wired (alert/block/modify_fitness/set_config); 5 stubbed
  (reassign_worker/propose_maintenance/notify/create_decision/pause_writes); ACTION_WIRING
  matrix + frontend mirror; CPO hook in `/v1/plan/cpo/schedule`

### Q.18 — Frontend consolidation (in progress)

- **Q.18.AUTH** Dev tenant bootstrap + zero UUID fix (frontend `…000` → `…001`)
- **Q.18.BOOTSTRAP** PostgreSQL via scoop + alembic-or-create_all + pgvector skip + 16 schemas
  + 93 tables + 183 configs seeded
- **Q.18.UX_FIX** Invisible chat input bug (bg-white inputs without text-slate-900)
- Future: Q.18.A→J (10-day plan): tokens migration, atom port, backend gaps, route consolidation
  32→5, drawer infrastructure, operator kiosk endpoints

### Q.61 — Consolidação (em curso, plano em `.claude/plans/trust-index-v1-indexed-token.md`)

- **Q.61.01** Guarda AST `TESTS-no-empty-bodies` em `verify_invariants.py` — apanha `def test_*: pass | ...` antes do CI. Stop-the-bleeding contra falsos positivos (audit overnight tinha-os reportado; AST confirmou zero hoje).
- **Q.61.02** Unificar `FakeRuleSession` no conftest — extraído de `tests/governance/test_yaml_rule_service_q17c.py:59-106` (duplicação face ao queue-based FakeSession). Subclasse `FakeRuleSession(FakeSession)` com typed-stash por SQL inspection; 17/17 testes verdes, canary governance 391/391. Os ~40 `_FakeSession` locais a outros tests ficam (variantes legítimas por service).
- **Q.61.03** Property test write-gate dispatcher — `tests/governance/test_dispatcher_wired_property_q61_03.py` com Hypothesis pin do invariante `_stubbed_or_ok` (status='ok' iff wired AND callback). Cobre toda a matrix `ACTION_WIRING` (9 actions × 4 combinations × 100+ exemplos) + unknown actions + 2 testes end-to-end via real dispatch. Apanha o bug Q.17.F.1 (dispatcher reportar 'ok' com wired=False).
- **Q.61.04** ACTION_WIRING roundtrip — `tests/governance/test_action_wiring_roundtrip_q61_04.py` faz parse do TS `frontend/src/components/regras/ruleHelpers.ts` e compara keys + wired flags com backend `dispatchers.ACTION_WIRING`. Antes só havia teste "backend tem entry por ActionType"; agora drift backend↔frontend falha o CI.
- **Q.61.05** Mutmut baseline script — `scripts/mutation_test.ps1` + `mutmut>=2.5,<3` em requirements-test. Smoke/decisions/yaml_policy/cpo/all targets; saída em `scripts/mutmut_baseline.json`. **Não corrido** nesta sessão (lento); Luis pode kick-off com `pwsh scripts/mutation_test.ps1 -Module smoke`.
- **Q.61.06** Stop-the-bleeding lint: `S110` + `T201` adicionados a `ruff.toml` (11 sites fixados com `# noqa: <rule>  Q.61.06: <razão>`). Para `BLE001` (370 sites, demasiado para mass-fix), novo `scripts/lint_drift_gate.py` com baseline em `scripts/lint_baseline.json` — falha CI se count sobe (Larson De-risk, sem orthogonal damage de massa de `# noqa`).
- **Q.61.07** ESLint anti-direct-fetch — regra `no-restricted-syntax` em `eslint.mocks.config.js` que apanha `fetch(...)` directo em `src/pages/` e `src/components/` (50 sites pré-existentes em warn; Vaga 5 migra-os). Drift gate estendido com `Q61_07_no_direct_fetch` (50 baseline) — count >50 falha CI.
- **Q.61.08** Pre-commit ganha 2 hooks fast (~4.5s combinados): `verify-invariants-static` (invariantes CX/C/F/E/D/ST/WG/CO/ME/H0 + AST testes vazios, sem pytest) + `lint-drift-gate` (BLE001 + Q.61.07 contra baseline). Trava regressão antes do push, sem precisar de canary completo.
- **Q.61.09** Bug SoD em `decisions.py:127` — `propose` deixa de criar `DecisionApproval` placeholder (`approver_id=user_id` era enganador); `approve` passa a `find_or_create` por (decision_id, approver_id). A tabela `decision_approvals` agora contém só aprovações reais. Novo `tests/shared/test_decisions_propose_q61_09.py` com 5 testes; canary shared+governance 628/628.
- **Q.61.10** Unit-of-Work em `propose_decision` — `async with session.begin_nested():` envolve `DecisionRun INSERT` + `AuditLog INSERT` na mesma transacção (cumpre invariante 7: audit na mesma tx que a mudança de estado). 2 testes novos (`test_propose_writes_audit_log_in_same_uow`, `test_propose_rolls_back_when_audit_fails`). Canary 630/630.
- **Q.61.11** Kafka publish via outbox em `governance/service.py:propose_decision` — antes fazia `await publish_event(...)` síncrono (bloqueava ~30s se broker down); agora escreve `EventOutbox` row na mesma tx. Dispatcher background (já existe em `outbox_dispatcher.py`) drena com retry + DLQ. Teste novo `test_propose_writes_event_outbox_not_sync_publish_q61_11`. Canary 631/631.
- **Q.61.12** trace_id end-to-end — novo `src/shared/observability.py` com ContextVar + `TraceIdMiddleware` + `TraceIdLogFilter`. Frontend `client.ts` injecta `X-Request-Id` (crypto.randomUUID). Backend extrai, propaga via ContextVar, ecoa no response, injecta em `payload.trace_id` no EventOutbox. 5 testes novos. Canary 636/636; frontend tsc verde.
- **Q.61.13** CLAUDE.md attribution fix — a quote "every line in CLAUDE.md affects 1000 future prompts — Boris (Anthropic)" não foi encontrada verbatim em fonte primária pelo agente de pesquisa. Substituída por paráfrase + link para `code.claude.com/docs/en/best-practices`. Karpathy + HumanLayer quotes ficam (têm fontes).
- **Q.61.14** Single source of truth para imports SQLA — novo `src/shared/model_registry.py`. Substitui as listas divergentes em `alembic/env.py` (22 imports → 1) e `scripts/bootstrap_dev_full.py` (28 → 1). **21 tabelas órfãs** apanhadas: o env.py original cobria 84 tabelas; registry cobre **105** — tudo o que produção via `alembic upgrade head` deixava por criar. Test pin: 3 testes em `test_model_registry_q61_14.py` (floor + smoke + orfas explicitas). Canary 639/639.
- **Q.61.16** `init_db()` deixa de fazer `create_all` em produção — passa a verificar via `MigrationContext.get_current_revision()` que há revision aplicada; crash early se não há. Helper `init_db_create_all()` exposto para tests/fixtures/bootstrap. 4 testes via AST inspection apanham regressão. Canary 643/643. **Q.61.15 (mega-consolidate migration) ficou pendente** — DB dev está em estado misto (Alembic 046 vs HEAD 055, mas create_all do bootstrap criou tabelas 047-055); requer drop+recreate do dev DB (decisão do Luis).
- **Q.61.17** CI job `alembic` (novo) — sobe Postgres como service, aplica `alembic upgrade head`, depois `alembic check` que compara `Base.metadata` vs HEAD migration. Falha o build se alguém adicionar coluna ao modelo sem migration. 4 testes pinam que o job existe + Postgres service + ordem upgrade→check. Canary 1170/1170 (governance+shared+plan).
- **Q.61.18** Audit pipeline único — novo `src/governance/audit_service.py:audit_change(...)`. Substitui o `session.add(AuditLog(...))` inline do Q.61.10; usado primeiro em `decisions.py:propose_decision`. Auto-injecta `trace_id` (Q.61.12) no `reason` como `[trace_id=...] <razão>` até Q.61.18.1 adicionar coluna dedicada. Contrato: nunca chama `commit` (caller controla, preservando invariante 7). 4 testes novos. Canary 651/651.
- **Q.61.19** `GET /v1/governance/audit-logs` (paginado) + adapter frontend — novo `src/governance/audit_log_api.py` com filtros (entity_type/_id, actor_id, action, since/until, trace_id substring), paginação, tenant scope. `frontend/src/pages/admin/auditTrailTypes.ts` passa de `fetch` directo para `apiFetch` + mapeamento backend→frontend. **Lint drift gate baixou** (BLE001 370→369, Q.61.07 50→49 — `fetch` directo eliminado neste sítio). 5 testes novos. Canary 656/656.
- **Q.61.20** KPI factory honesta — novo `src/profit/kpi_factory.py`. `throughput_*` delega para `ThroughputService` (canónico); `defect_rate`/`oee`/`otd` lançam `NotImplementedError("Q.62...")` com mensagem explícita sobre as 3 semânticas divergentes (worker Laplace / factory ratio / plan adherence). Em vez de fachada theater (Karpathy failure #2), força decisão de produto antes de consolidar. 5 testes pinam delegate + NIE. Canary 661/661.
- **Q.61.22** Lifespan `asyncio.gather` — `init_db` mantém primeiro (deps de schema), depois Redis + Kafka + tool registry pre-warm + YAML policy refresh paralelizam com `return_exceptions=True`. Cada falha é logada e adiciona o subsystem a `app.state.degraded_subsystems` (visível para health endpoint). Modo "degraded" explícito em vez de retry-and-die. 4 testes via AST. Canary 775/775. Q.61.21 (RLS) deferido para sessão supervisionada.
- **Q.61.23** Apagar pastas órfãs: `components/alpha/` (10 ficheiros) + `components/showcase/` (1) — 0 importadores confirmados via `rg`. **`ceo/` ficou** (audit overnight errado — usado por `DirecaoPage` + `direcaoComponents`). 11 ficheiros removidos; tsc verde; vitest 78/78.
- **Q.61.24** (no-fix) — audit chamou `dashboard/LiveBadge` "duplicado" de `dark/LiveBadge`. Inspecção mostra que são **conceitos diferentes**: `dashboard/LiveBadge` é status indicator com `RealtimeProvider` (connected/stale/disconnected); `dark/LiveBadge` é visual pill estático com label. Renomear é Q.62 (decisão de design system). `ui/` (18 ficheiros) tem 15 importadores — refactor maior, fica para Q.62.
- **Q.61.25** (parcial) Causal panels via `lib/api/causalApi.ts` — novo helper com `causalGet`/`causalPost` que usa `request()` central (tenant + trace_id automáticos). Migrados 9 panels (Attribution/ErroTree/Investigate/Mill/NeloDag/Poetiq/Reichenbach/WhyKpi/...). `causalShared.ts` perdeu `BASE` e `TENANT` (deixaram de ser usados). **Drift gate baixou**: BLE001 369→365, Q.61.07 49→39. Frontend tsc + 78/78 vitest. **Restantes ~39 fetch directos** ficam para sub-sprints futuros (touched-file pays).

## Test count progression

| Sprint | Total tests |
|---|---:|
| End of Q.6 | 927 |
| End of Q.13 | ~1.2K |
| End of Q.14 | ~1.4K |
| End of Q.15 | 1684 |
| Current | 1684+ (post-Q.17.F) |

## Where to find canonical references

- **Active plan:** `.claude/plans/plano-diz-c-digo-scalable-minsky.md` — vivo, audits + roadmap
  Q.13→Q.18, includes the macro 73% → 100% phase plan
- **Original product vision:** `PP1_NELO_PLANO_v4.md` (1078 linhas, frozen, historical reference
  only — não actualizado desde Q.6)
- **Frontend design vision:** `FRONTEND_DESIGN_PROMPT.md` (1066 linhas, v1; v2 patches in
  active plan §"FRONTEND_DESIGN_PROMPT v2 — Lista de revisões propostas")
- **Audit baseline:** `scripts/AUDIT_BASELINE.md` — diagnostic snapshot

## When to read this file

- Before asking "why is this code structured this way?"
- When a property test name references `_q14a` ou `_q15d2` (sprint suffix indicates origin)
- When `git log -- <file>` mostra um commit `Q.X.Y` e queres contexto
- Quando Luis menciona "o sprint Q.17.E" e queres saber o que entregou
