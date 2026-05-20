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
