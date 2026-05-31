# Q.136 — Planeamento realista para barcos + working tree limpa · REPORT

**Branch:** `feat/q136-planeamento-barcos` (de `main` pós-Q.135). Merge `--no-ff` local, **SEM push**.

## Verificação EXAUSTIVA dos inputs do CPO (read-only, antes de mexer)
O motor já consome corretamente quase tudo; medido na BD real (prodplan_one):

| Input | Real | Realismo |
|---|---|---|
| WIP | 5315 abertas; **56% acessórios**; barcos (deck/casco)=**777 / 228 modelos** | ❌ gap (planeava acessórios) |
| Fase atual | 359 "Não Laminado"; **~418 a meio** (Colagem/Pintura/QC) | ❌ gap (rota completa p/ barcos a meio) |
| Calendário | 572 dias reais (395 úteis ~8h), carregado + usado (`add_working_hours`) | ✅ |
| Durações | calibradas (356 modelos-barco) + histórico; ~180h/barco | ✅ real |
| Molde | 571 modelos-barco têm molde; exclusividade (axioma 3) | ✅ |
| Skills | 34/41 fases c/ operador; 7 sem = cura/estados/manutenção/3D (sem labor) | ✅ |
| Work-centers, cura, due-dates (739/777), quantidade (1 OF=1 barco) | — | ✅ |
| ERP já planeia | `OF_PLANO_DATA_PREVISTA` em 737 barcos | baseline |

→ **2 gaps reais confirmados** (filtro de produto + fase atual); tudo o resto já estava correto.

## Fase 0 — Working tree limpa (WIP → 3 features)
O WIP uncommitted eram 3 features coerentes (não lixo):
- **Q.133.A** (`84a6f88`): fix REAL de persistência (`ScheduleCommit` não persistia — só flush, sem
  commit) + labels DRAFT/degradado no grid (status + safety_net_triggered via model→API→FE).
- **Q.133.B.1** (`506a2d1`): permissão `ROUTING_EDIT` (editar fases), SoD verificado
  (/v1/plan/routing-templates não está na matriz de prefixos → CEO/Operador editam routing mas
  continuam sem SCHEDULE_WRITE).
- **Q.133.B.2** (`0eae5dd`): switcher Umwelt propaga `user_role` → header → RBAC real em dev.
- Descartada a linha morta de `.claude/settings.local.json`.

## Fase 1 — Planeamento realista (`7446055`)
- **A boats-only (config-driven):** `_load_open_orders_db` + JOIN `produto` + `planning.scope`
  (`boats_only` default | `all`). Filtro `P_QTDDECK>0 AND P_QTDCASCO>0`. Override futuro
  `planning.boat_type_ids` documentado (recupera tipos sem deck/casco, ex. Dragão ~185).
- **B planear-da-fase-atual:** loader devolve `current_fase_id` (=`OF_FP_ID`); `RoutingResolver`
  trunca a rota a `sequence >= fase atual`. Fallback à rota completa quando a fase atual está fora
  da rota (ex. "Não Laminado", 359 barcos não começados) ou ausente. Decoder/loaders intactos (Spelke).

**Verificação AO VIVO** (`_audit/q136/probe_boats.py`):
- `boats_only` → 200 barcos; `all` top-200 = 194 barcos + 6 acessórios → o filtro exclui os 6
  acessórios (o conjunto urgente já é 97% barcos; o grande efeito do filtro é além do cap de 200).
- 200/200 com `current_fase_id`.
- **Truncação real:** of 501171, fase atual 4 → rota completa 10 ops → truncada **7 ops** (poupa 3).
- Schedule (30 barcos): makespan **1.225h**, `status=optimal`, `safety_net=False`, **molde 0
  sobreposições** (axioma 3). Calendário/durações reais alimentam o plano.
- Cobertura do resolver nos 200 barcos = **98% (4 sem rota, honestamente expostos via Q.131.H** —
  modelos sem histórico ≥2 obs nem em `model_routing_assignment`; nunca rota inventada).

**Honestidade:** o "100% routing" via `factory_raw.produto_fase` (existência de template) ≠ cobertura
do resolver (98%), que usa `history_db` + `plan.model_routing_assignment` (4729) /
`routing_template_phase` (1433). Os 4 sem rota ficam `unplanned`, não inventados.

## Fase 2 — Housekeeping CI (`eaa7d73`)
- `conftest.pytest_collection_modifyitems`: socket-check à porta da BD; salta os 8
  `@pytest.mark.integration` quando a BD não está acessível → fecha o vermelho do job `test` do CI
  (corre `pytest tests/` sem postgres). Verificado: BD up → corre; BD morta → "2 passed, 2 skipped".
- `deploy/RUNBOOK.md` §3 corrigido: `init-db.sql` (extensões) ANTES do `alembic upgrade head`;
  remove a afirmação falsa de que `init_db()` faz create_all.

## Gate
`& .\scripts\verify.ps1` (ver Fase 3). `tests/plan` + `tests/scheduling`: **912 passed**, só a falha
pré-existente `test_percentile_90_valores` (boat, percentil — não tocada). nelo-reviewer: ver Fase 3.

## Limitações deixadas (documentadas)
- deck/casco>0 pode falhar tipos-barco sem o campo preenchido (Dragão ~185) → `boat_type_ids` futuro.
- 2% dos barcos sem rota resolvível (honesto). Drift colunas alembic + Stream 2 Q.126 + A3-live
  (operacional) continuam diferidos.
