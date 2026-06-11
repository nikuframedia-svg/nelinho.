# TEST_PLAN.md — Plano de testes do nelinho (cenários reais)

> **Origem:** auditoria multiagente de 2026-06-11 (44 agentes, BD real read-only, verificação
> adversarial). **Todas as contagens da BD são um snapshot de 2026-06-11** — antes de cada
> execução, re-correr os SELECTs de pré-condição.
>
> **Legenda de estados:** `[CÓDIGO]` confirmado-no-código (ficheiro:linha) · `[BD]`
> confirmado-na-BD (SELECT) · `[HIPÓTESE]` plausível mas não provado · `[PERGUNTA]` decisão
> pendente do dono.
>
> **Docs irmãos:** [AUDIT.md](AUDIT.md) · [DATA_FLOW_MAP.md](DATA_FLOW_MAP.md) ·
> [DOMAIN_RULES.md](DOMAIN_RULES.md) · [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md) ·
> [CUBE_LLM_KPI_AUDIT.md](CUBE_LLM_KPI_AUDIT.md) ·
> [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) ·
> [DESIGN_SKILL_PROPOSAL.md](DESIGN_SKILL_PROPOSAL.md)
>
> **Decisões do Luis (2026-06-11), já incorporadas como requisitos de teste:** (1) gate CP-SAT
> com tolerância própria + baseline justo (mesmo op-set, sem reparações; guardrails soft isentos
> quando o makespan melhora >50%; axiomas hard intocáveis; configurável por tenant); (2)
> reparações {14,76,77} merge-back no MESMO plano/commit do /overall, com filtro/badge próprio;
> (3) "gama/drop" = tipo/disciplina do produto (`produto_tipo.TP_ID` / `P_TP_ID_DISCIPLINA`);
> (4) stock mínimo importado de `P_STOCKMIN` + override local; lead times de `E_PRAZOENTREGA`.

---

## 1. Infra de testes atual (inventário)

### 1.1 pytest

- **4.275 funções `def test_` em 449 ficheiros** (`tests/`); `pytest.ini` com
  `asyncio_mode=auto` e markers `slow`/`integration`.
- Distribuição por área: plan **1.236**, copilot **599**, governance **492**, shared 320,
  factory_data_product 256, adapters 180, explain 159, profit 152, twin 112, ml 101, supply 99,
  workforce 85, quality 80, core 78, scheduling 68, dqa 61, hr 36, reports 26, master_data 24,
  diagnostics 19, scripts 15, improve 14, integration 14, api 13, sandbox 10, observability 10,
  search 6, learning 3, raiz 7. **`tests/load` = 0 pytest** (só k6 JS).
- Fakes canónicos em `tests/conftest.py` (427 l): `FakeSession` (:88), `FakeRuleSession` (:247),
  `MockOllamaClient` (:332) — a maioria da suite **não toca a BD real**.
- `tests/integration/` (Postgres vivo): só 4 ficheiros — `test_alembic_table_parity.py`,
  `test_q115_a_migrations.py`, `test_rls_qr_audit.py`, `test_tenant_route_coverage_q168d.py`.
- Property tests Spelke: 24 ficheiros com `hypothesis` em `tests/plan/`
  (ex.: `test_preview_delta_property.py`, 9 testes).

### 1.2 Gates existentes

| Gate | O que corre |
|---|---|
| `scripts/verify.ps1` (Q.61.39, ~70-90 s) | ruff src/ → lint-imports → pytest canary (governance+shared) → `verify_invariants.py` → lint_audit_coverage → drift gate → tsc → vitest → lint:mocks |
| `scripts/verify_invariants.py` | 12 invariantes estáticas (CX/C/F/E/D/ST/WG/CO/ME/H0 + imports + test-floor) + AST scan anti-`def test_*: pass` (Q.61.01) + curing-gaps das fases flexíveis (:184) |
| `scripts/mutation_test.ps1` (Q.61.05) | mutmut sobre `decoder.py`+`fitness.py`, yaml_policy, decisions.py; baseline em `mutmut_baseline.json` |

### 1.3 Harnesses E2E em `scripts/`

| Script | Cobre | Dados |
|---|---|---|
| `e2e_plan_smoke.py` (301 l, Q.172.C) | ciclo de planeamento inteiro: health → robô → validador → SoD 403 → grid → drag válido 200 / inválido 422 → reapply (passo 8) → fila de operador (passo 9) | **LIVE** :8001 + BD real |
| `validate_e2e.py` (824 l) | ingestão+semântica sobre `Folha_IA_extra.xlsx` | **Excel in-memory — não toca o Postgres** (stale: o ML já treina da BD) |
| `test_llm_massive.py` | ~54 cenários × NELO_DAG (23 nós) | Ollama REAL |
| `test_llm_adversarial.py` | linguagem casual/ambígua/fora-do-DAG | Ollama REAL |
| `test_llm_multiturn.py` | 5 conversas × 4 turnos (contexto) | Ollama REAL |
| `test_llm_parametric.py` | 30 cenários × 5 paráfrases (robustez) | Ollama REAL |
| `test_llm_causal.py` | 5 causais + kernel causal_query | Ollama REAL |
| `test_llm_concurrent.py` | 10 perguntas paralelas (breaker/races) | Ollama REAL |
| `test_llm_diretor_q55.py` | 80 prompts, 3 juízes (SCM+verify_chain+DoWhy) | Ollama REAL |
| `q68_copilot_live_smoke.py` | 15 perguntas a `/api/copilot/ask-dev`, gate ≥12/15 | BD VIVA |
| `smoke_q17b.py` / `_route_smoke.py` | rule_schema Q.17 / smoke por rota (500 vs 4xx/503) | sem BD / TestClient |
| `dr-smoke.sh` | pós-restore: curl API+Ollama+psql | **aponta :8000 e `sudo -u postgres`** — falharia num restore real (dev real é :8001 nativo) `[HIPÓTESE]` na topologia de prod |

### 1.4 Frontend

- vitest: **34 ficheiros `*.test.ts*`, 131 `it()/test()`** — cobertura fina face a ~22 páginas.
- Zero validação visual automatizada (screenshots); o lint:mocks garante apenas ZERO MOCKS.

### 1.5 Gaps confirmados na infra

1. `[CÓDIGO]` Golden traces do copiloto são **shape-only com MockOllama** —
   `tests/copilot/test_golden_traces_q66_e.py:19-34` (docstring admite-o) e `:230`
   `mock_ollama.queue_chat(...)`. **Não existe golden-SQL suite** NL→Cube que compare SQL/números
   contra a BD (`tests/copilot/test_ask_cube.py` só tem guards unit).
2. `[CÓDIGO]` `tests/load` sem nenhum pytest; `validate_e2e.py` corre sobre Excel em memória
   (contradiz "ML treina da BD real"); `dr-smoke.sh` desalinhado do deploy.
3. `[CÓDIGO]` Gate axioma-7 do CP-SAT só tem testes unit
   (`tests/plan/test_q169d_cpsat_gate.py`, 8 testes) — **zero teste de que o commit do robô
   persiste `cpo_meta.cpsat_gate`/`engine`**; `engine.py:293-295` engole a exceção e `:299-305`
   descarta a meta da rejeição. `[BD]` em live só 1 commit em toda a tabela tem `cpsat_gate`.
4. `[CÓDIGO]` Testes que **codificam o defeito**: `tests/factory_data_product/
   test_factory_map_api.py:107` `test_shortage_risks_empty` assert `items==[]` (o vazio-perpétuo
   passa como OK); `tests/api/test_q115_b_config_endpoints.py:135-142` anula o RBAC com
   `dependency_overrides[_require_config_write]=_no_rbac`.
5. Sem teste: `/overall ?commit_sha=` (`OverallPage.tsx:158` fixa `commits[0]`), alerting de ETL
   (`core.etl_run.status='error'` sem leitor), paridade cube↔views (18/51 cubes mortos),
   expedição live com os 20 camiões reais.

---

## 2. Plano por camada

### 2.1 Backend (pytest async)

- **Padrões obrigatórios:** `asyncio_mode=auto`; `FakeSession`/`FakeRuleSession` de
  `tests/conftest.py`; property tests Spelke via `hypothesis` para qualquer invariante novo do
  CPO; DAMP > DRY; zero `skip`/`xfail` sem issue GH.
- **Regra nova (anti-defeito-codificado):** todo o teste `*_empty` de um endpoint de lista tem de
  ter um irmão não-vazio no mesmo ficheiro (semear 1 linha via FakeSession). Aplicar primeiro a
  `test_shortage_risks_empty`.
- **Regra nova (RBAC):** proibido `dependency_overrides` de dependências de permissão em testes
  de endpoints protegidos — testar com a app real e `rbac_strict=true` (ver GATE-7, §4).
- Alvos imediatos: persistência do `cpsat_gate` (R1), reorder no-op (GATE-5), resolução
  employee_code→UUID no `/v1/entity/operador` (R5), ETL health (GATE-4).

### 2.2 Frontend (vitest + validação visual obrigatória)

- vitest component para lógica de render: parsing do plano (`start_time` vs `start`), split de
  group-keys, dedupe realizado→plano, `?commit_sha=` com mock de router.
- **Validação visual obrigatória com screenshots** (Chrome DevTools MCP / manual) para tudo o
  que é grelha/heatmap/badge: badge "Rascunho · não aprovado", heatmap de densidade, filtro
  Reparações (decisão 2), lanes Por Pessoa/Por Barco, /expedicao Prontos-a-sair. Screenshot
  anexado ao PR — um teste de DOM não prova legibilidade.
- Regressões concretas a cobrir (área ux-gantt): OperadorSheet 422 (R5), ModeloSheet com
  `OF_P_ID` numérico vs endpoint por `product_name` (tabs vazias), badge ★afinidade
  (UUID vs employee_code, nunca acende), badge ⚡boost (`effective_boost` nunca mapeado),
  "filtrar por fase" engolido pelo `Clickable` (stopPropagation).

### 2.3 Dados reais (asserts de contagens/frescura por SELECT)

Suite `@integration` nova `tests/integration/test_data_freshness.py` — cada assert é um SELECT
com limiar, não um número fixo (os valores abaixo são o snapshot 2026-06-11):

| Assert | SELECT | Snapshot |
|---|---|---|
| espelho of_fp vivo | `SELECT count(*) FROM factory_raw.of_fp` | 972.519 |
| movimento vivo | `SELECT count(*) FROM factory_raw.movimento` (tipo 11 = consumo) | 2.544.418 (tipo 11 = 1.468.924) |
| BOM ativa | `SELECT count(*) FROM factory_raw.produto_componente WHERE "COMP_ELIMINADO" IS NULL` | 111.339 |
| scope de produção | `SELECT count(*) FROM factory_raw.v_of_em_producao` | 1.145 (das quais 76 em reparação) |
| operadores ativos | `SELECT count(*) FROM v_active_operators` | 106 |
| mirror de ordens | `SELECT count(*) FROM production_orders` | 9.607 |
| ETL saudável | nenhum source com ≥3 `status='error'` consecutivos em `core.etl_run` | **FALHA hoje**: phase_history 9/9 + worker_assignment 9/9 (`dbo.FasesOf` / `dbo.WorkerAssignment` inexistentes) |
| frescura | `max(finished_at)` por source < 2× cadência do sync | — |

### 2.4 CP-SAT / planeamento

Requisitos de teste derivados da **decisão 1** do Luis + achados (ver [AUDIT.md](AUDIT.md) e
lacuna verificação-CP-SAT — veto PROVADO em `_arq.err:2326`:
`idle_ratio=0.6805 > baseline=0.6280 + 0.05`):

1. **Persistência da decisão do gate** — todo o commit do robô com `cpo.use_cpsat_global=true`
   leva `cpo_meta.cpsat_gate` (aceite/rejeitado) OU `cpo_meta.cpsat_error`; o caminho GA nunca
   fica sem marca (`engine.py:558-605` monta `cpo_meta` novo sem `engine`). Unit + passo novo no
   `e2e_plan_smoke.py`.
2. **Comensurabilidade do baseline** — teste que o baseline do gate é recalculado sobre o MESMO
   op-set do candidato (sem reparações): hoje `cpsat_global.py:72` exclui `REPAIR_PHASE_IDS` mas
   `engine.py:347-361` decodifica TODAS as operations → ratios incomparáveis (a rejeição live
   falhou por ~0,25 pp).
3. **Isenção dos guardrails soft** — property test: se `makespan_cand < 0.5 × makespan_base`,
   violações soft (idle_ratio +5 pp, `safety_net.py:230-241`) não vetam; axiomas hard vetam
   SEMPRE (Spelke intocável). Caso âncora: ~690 h vs 22.297 h (melhoria >96 %) tem de passar.
4. **Tolerância por tenant** — gate lê a tolerância de `core.tenant_configuration`; teste de
   roundtrip config→decisão.
5. **Merge-back de reparações** (decisão 2) — ver R2.
6. **Anti-flag-fantasma** — `cpo_meta.flags` só publica flags com leitor funcional
   (`use_backwards_scheduling`/`use_hungarian_pair_assignment`/`use_cpsat_lrho` são despejo de
   defaults nunca lidos, `engine.py:100/102/111` → `:581-590`); idem telemetria fabricada
   `greedy_pipeline.py:169` (`core_elapsed/4`) — invariante #8.

### 2.5 Stock / MRP — os 4 cenários obrigatórios (decisão 4)

Estado de partida `[BD]`: `supply_rop_configs=0`; `min_stock_qty=0` em **14.110/14.110**
materiais (hardcode `material_master.py:56`) vs `P_STOCKMIN>0` em **1.110** produtos do ERP;
`lead_time_days=7` placeholder em 100 %; detalhe em
[STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md).

| # | Cenário obrigatório | Pré-condição (SELECT) | Esperado |
|---|---|---|---|
| S1 | **Rutura** | SKU com `warehouse_stock.qty <` reservas abertas (TPMOV=4, `MOV_SATISFEITO=false`) + `min_stock_qty>0` importado de `P_STOCKMIN` | alerta de rutura criado pelo ShortageDetector, ligado à(s) OF(s); /shortage-risks ≠ [] |
| S2 | **Suficiente** | SKU com `qty > min_stock_qty +` reservas abertas | zero alerta; estado "OK" explícito (não silêncio) |
| S3 | **Reservado** | SKU cujo stock só chega porque há reservas TPMOV=4 de outra OF | stock *disponível* (livre de reservas) é o que alimenta o detector — não o stock bruto |
| S4 | **Lead-time** | fornecedor com `E_PRAZOENTREGA>0` (114/9.031 entidades) importado; consumo projetado esgota o SKU dentro do lead-time | alerta antecipado "encomendar até <data>"; com placeholder 7d o teste FALHA por construção |

Mais: ROP (`rop_calculator.py:66`) só pode ser recomputado DEPOIS de S1-S4 terem dados reais —
teste de que `recompute_rop_configs` povoa `supply_rop_configs` (>0) e que o /shortage-risks
distingue "sem config" de "sem risco" (estado-vazio honesto, invariante #8).

### 2.6 Gantt /overall

- `?commit_sha=` carrega o commit pedido + badge "histórico" (hoje impossível:
  `OverallPage.tsx:146-166` sem `useSearchParams`; `/actuals` em `timeline.py:45-58` sem
  parâmetro de commit). vitest + browser.
- Filtros novos (12 pedidos pelo dono; só "datas" completo): cada filtro novo = 1 teste de
  contagem (aplicar filtro → nº de lanes/ops esperado por SELECT equivalente) + screenshot.
  "Gama/drop" filtra por `produto_tipo.TP_ID`/`P_TP_ID_DISCIPLINA` (decisão 3).
- Performance: payload do plano LIVE = 2,3 MB (8.059 ops) re-fetched a cada 30 s, 985 lanes sem
  virtualização — teste de budget (payload < limiar, render < limiar) antes/depois.
- Filtro/badge "Reparações" (decisão 2) — visual + contagem (=76 no snapshot).

### 2.7 Regras / config (UI → persistência → leitura pelo backend)

Estado `[BD]`: as 8 cadeias UI→tabela→CPO existem mas estão vazias (`yaml_policy_rule=0`,
`phase_config=0`, `plan_exclusion=0`, `order_boost=0`, `preference_rule=0`,
`phase_transition_gap=0`); só 1 dos 12 eventos do DSL é emitido (`scheduler_run.py:597`,
SCHEDULE_PROPOSE). Regras de teste em [DOMAIN_RULES.md](DOMAIN_RULES.md).

- **Roundtrip por cadeia**: criar via UI/API → SELECT confirma a linha → replan → assert no
  plano (ex.: `phase_config` muda estações paralelas → ops simultâneas na fase mudam).
  1 teste por cadeia × 8 cadeias; hoje 0 rows = nunca exercidas em produção.
- **RBAC de /v1/config**: com `rbac_strict=true`, `PUT /v1/config/{category}` sem CONFIG_WRITE →
  403. Hoje `[HIPÓTESE forte]` devolve 200: matriz só tem `/v1/core/config`
  (`rbac.py:233-234`), router real é `prefix="/v1/config"` (`tenant_config.py:34`) sem
  `PermissionDependency`, e `middleware.py:154-158` deixa passar rotas fora da matriz.
- **Q.17**: `requires_human_approval=Literal[True]` e kill_switch admin-only continuam cobertos
  (`test_action_wiring_roundtrip_q61_04`); acrescentar teste de emissão dos eventos novos quando
  forem ligados.

### 2.8 Cube — golden-SQL suite NL→Cube

Suite nova `scripts/golden_sql_cube.py` (corre live: Ollama + Cube + Postgres; gate ≥10/12).
Cada caso: pergunta PT-PT → resposta do ask-cube → número comparado com o SELECT canónico.
Contexto: 51 cubes / 139 measures no Cube, **18/51 cubes mortos** (views inexistentes),
51/139 measures morrem em query-time — detalhe em [CUBE_LLM_KPI_AUDIT.md](CUBE_LLM_KPI_AUDIT.md).

| # | Pergunta | Fonte canónica | SQL de verificação | Snapshot 2026-06-11 |
|---|---|---|---|---|
| G1 | "Quantas OFs foram fechadas hoje?" | `marts.v_ofs_fechadas_dia` (6.353 linhas) | `SELECT ofs FROM marts.v_ofs_fechadas_dia WHERE dia=current_date` | — (diário) |
| G2 | "Quantos barcos estão em produção?" | `factory_raw.v_of_em_producao` | `SELECT count(*) FROM factory_raw.v_of_em_producao` | 1.145 |
| G3 | "Quantas OFs estão em reparação?" | idem, fases {14,76,77} | `... WHERE` fase atual IN (14,76,77) `[HIPÓTESE]` na coluna exata | 76 |
| G4 | "Quantos operadores ativos temos?" | `v_active_operators` | `SELECT count(*) FROM v_active_operators` | 106 |
| G5 | "Qual foi a faturação do mês passado?" | `marts.v_facturacao_mes` (`EPHCF_FACTURADO`) | sum do mês na view | — |
| G6 | "Quanto material consumimos este mês?" | `marts.v_consumo_material_dia` (TPMOV=11) | sum qty/custo do mês | — |
| G7 | "Produção por disciplina este ano?" | cube disciplina×mês (Q.167 #3) | SELECT equivalente na view de disciplina | 441 combos disciplina×mês |
| G8 | "Quantas entradas de retrabalho?" | rework ETL | `SELECT count(*) FROM` rework_entry | 5.908 (100% com `mold_id` NULL) |
| G9 | "Quantas ordens de produção existem?" | `production_orders` | `SELECT count(*) FROM production_orders` | 9.607 |
| G10 | "Qual é o makespan do último plano?" | `plan_schedule_commits.kpis` | `kpis->>'makespan_hours'` do commit mais recente | 22.297 h |
| G11 | "Quantos camiões abertos?" | `plan.transport_batch` | `SELECT count(*) ... WHERE status='OPEN'` | 20 |
| G12 | "Horas por operador este mês?" | `v_horas_operador_mes` — **cube MORTO** | n/a | esperado HOJE: **abstain honesto** (não número inventado); pós-fix: números |

Gotcha conhecido: measure nova no Cube + reindex NÃO chega — o interpret só escolhe cubes
descritos em `cube_interpret.md` (hoje só 16/51 à mão); cada golden novo exige o bloco no prompt.

### 2.9 LLM (live + explicabilidade)

- Manter os harnesses live de §1.3 (massive/adversarial/multiturn/parametric/causal/concurrent/
  diretor/q68) como bateria noturna; `q68_copilot_live_smoke.py` mantém gate ≥12/15.
- **Explicabilidade (requisito novo):** cada resposta numérica do copiloto tem de citar
  **tabela/view, campo, filtro, fórmula e período**. `[CÓDIGO]` o backend já devolve a query
  Cube exacta (measures/filtros/período) mas o frontend descarta-a — o teste valida (a) o campo
  no JSON do `/ask`, (b) o render no chat (screenshot). Casos G1-G12 reusados.
- Golden traces shape-only (Q.66.E) mantêm-se como teste de contrato do wrapper, mas deixam de
  contar como cobertura E2E (lição: mockar o envelope HTTP do Ollama esconde bugs).
- `validate_e2e.py`: migrar os asserts semânticos para a BD real ou marcar deprecated — hoje
  audita um Excel que já não é fonte de verdade.

---

## 3. Os 10 cenários reais (entidades concretas da BD, snapshot 2026-06-11)

> Preservados do inventário da auditoria (C1-C10) e fundidos com as entidades do vertical-barco.
> Cada cenário: pré-condições verificáveis por SELECT, passos, resultado esperado,
> automatizável-vs-manual.

### R1 — CP-SAT em fallback silencioso + gate justo (sha `660752e1`) — CRÍTICO

- **Pré `[BD]`:** `core.tenant_configuration` tem `cpo.use_cpsat_global={"v":true}`; o ÚNICO
  commit com `cpo_meta.cpsat_gate` é **660752e1** (2026-06-10 16:37, 1.070 ops, makespan
  689,95 h, accepted=true); todos os "Scheduled" de 2026-06-11 SEM `cpsat_gate`/`engine` e
  `kpis.makespan_hours` 20.837-22.297 h. `[CÓDIGO]` `_arq.err:2326`: "CP-SAT global REJEITADO
  pelo gate axioma-7: idle_ratio=0.6805 > baseline=0.6280 + 0.05".
- **Passos:** (unit) candidato com `idle_ratio=baseline+0.06` → `_cpsat_gate_decision`
  (`engine.py:160`) rejeita citando idle_ratio; candidato com makespan −96 % → guardrail soft
  isento (decisão 1), hard axiom vetado na mesma; (live) `POST /v1/plan/cpo/schedule/async` →
  ler commit novo → `ASSERT cpo_meta ? 'cpsat_gate' OR cpo_meta ? 'cpsat_error'`.
- **Esperado:** hoje o passo live FALHA — `engine.py:293-295` devolve `None` sem rasto e a meta
  da rejeição (`:299`) morre com o result (`:305`). Pós-fix: makespan live ≈690 h e veto
  auditável pela BD.
- **Automação:** pytest (estende `tests/plan/test_q169d_cpsat_gate.py`) + passo novo no
  `e2e_plan_smoke.py`.

### R2 — Reparações merge-back no MESMO plano (OFs 17226/77, 900895/76, 15887/14)

- **Pré `[BD]`:** `factory_raw.v_of_em_producao` = 1.145, das quais **76 em reparação**; OF
  **17226** aberta na fase 77, **15887** na 14, **900895** (Surf Ski 54 L AIR) na 76 (única op
  com `OFFP_DATAFIM` NULL; reentrou via Armazém 2025-03-21). `[CÓDIGO]` `cpsat_global.py:72`
  exclui `REPAIR_PHASE_IDS`; bypass de reparação em `routing_resolver.py:183-192`.
- **Passos:** robô com CP-SAT ativo → ler o commit → assert as 3 OFs têm op agendada no MESMO
  commit, marcadas (campo/flag de reparação); /overall com filtro "Reparações" mostra-as
  (badge); baseline do gate exclui-as (comensurável com o candidato, decisão 1).
- **Esperado:** hoje em modo CP-SAT as reparações ficam fora do plano; no DRAFT GA `f6a0c873` a
  900895::76 está planeada (2026-07-06→09, worker 33270, 18,4 h) — o merge-back tem de manter
  isto verdade também no caminho CP-SAT (decisão 2).
- **Automação:** pytest integração + visual browser (badge/filtro, screenshot).

### R3 — Rutura de material na OF 902252 (78 reservas não satisfeitas)

- **Pré `[BD]`:** OF **902252** (Waterman WWR, P 20237, fase atual 33) tem 85 movimentos
  TPMOV=4 (Reserva, criados 2026-05-12, com `MOV_FP_ID`=fase de consumo), **78 não satisfeitos**
  (`MOV_SATISFEITO=false`, 351,58 unid) vs 7 consumos TPMOV=11; `supply_rop_configs=0`;
  `min_stock_qty=0` em 14.110/14.110 (`material_master.py:56`).
- **Passos:** (a) pós-import `P_STOCKMIN` (decisão 4): assert ≥1.110 materiais com
  `min_stock_qty>0`; (b) detector cruza reservas abertas × stock disponível → alerta de rutura
  ligado à OF 902252; (c) `GET /v1/factory-map/shortage-risks` ≠ [] e distingue "sem config" de
  "sem risco".
- **Esperado:** hoje 0 alertas alguma vez criados (`material_service.py:221` com
  `effective_min=0`) e items=[] perpétuo (`risk_flags.py:98-121`); o painel
  `ShortageRiskPanel.tsx:32` esconde-se. Nota: a conta completa de "materiais restantes" exige
  explosão multi-nível da BOM (os consumos da 902252 vêm da BOM do componente laminado 27658) —
  ver [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md).
- **Automação:** pytest unit (FakeSession) + `@integration` com os SELECTs acima.

### R4 — Os 4 casos de stock obrigatórios (S1-S4 de §2.5) com SKUs reais

- **Pré:** derivar por SELECT 1 SKU por classe (rutura / suficiente / reservado / lead-time) do
  cruzamento `supply.warehouse_stock` (8.069) × reservas TPMOV=4 × `P_STOCKMIN` × fornecedores
  com `E_PRAZOENTREGA>0` (114). Se uma classe não existir live, semear em BD de teste.
- **Passos/Esperado:** tabela de §2.5; cada caso com assert do estado do detector E do
  estado-vazio honesto na UI.
- **Automação:** pytest `@integration` parametrizado; UI manual com screenshot.

### R5 — Operador 20348 João da Silva Alvão: fila do dia + ficha de entidade

- **Pré `[BD]`:** 20348 está em `v_active_operators` (last_worked 2026-06-11 08:01); o último
  commit tem 8.059 ops e `operations->0->'workers'` = `["20365"]` (employee_code, não UUID).
- **Passos:** `GET /v1/plan/.../worker/20348/operations-today` → 200 (lista ou [] honesto, com
  overlay `operation_execution`, `schedule.py:309-345`); `GET /v1/entity/operador/20365` →
  hoje **422** (`entity_summary.py:1191-1193` declara `employee_id: UUID`); clique na entidade
  Operador em /decisoes (`decisionEntities.tsx:67`) e na vista Por Pessoa do /overall.
- **Esperado:** resolver código→UUID (reutilizar `_resolve_worker_code`, `schedule.py:309+`) →
  200 OperadorSummary; código inexistente → 404 PT-PT.
- **Automação:** pytest TestClient (regressão do 422) + e2e smoke passo 9 (assert com operador
  REAL ativo) + browser manual para o clique.

### R6 — Operador indisponível não recebe trabalho

- **Pré:** escolher por SELECT um operador de `v_active_operators` (106) com ops no último
  commit; em BD de teste, torná-lo indisponível (`E_ACTIVO=false` ou last_worked >2 meses → sai
  da view, regra Q.159).
- **Passos:** replan → assert zero ops novas atribuídas; ops dele re-atribuídas a qualificados;
  o dropdown do OperationEditSheet (fonte `/v1/core/employees` active_only) não o lista.
- **Esperado:** o filtro CPO já é input-only sobre `v_active_operators` (regressão); **gestão de
  ausências/férias/turnos NÃO existe** (`[CÓDIGO]` área regras-config: "disponibilidade de
  operadores não é configurável") — a parte "marcar ausência na UI" é **teste-alvo** da feature
  futura, não regressão.
- **Automação:** pytest integração (regressão); ausências = manual/alvo.

### R7 — Setor/fase sem capacidade qualificada

- **Pré:** SELECT por fase produtiva do nº de operadores qualificados ativos (gate
  `Entidade_Fase` ∩ `v_active_operators`); identificar uma fase com 0 qualificados — se não
  existir live, semear em BD de teste removendo as qualificações de uma fase.
- **Passos:** replan → ops dessa fase ficam **unplanned honestas** (o DRAFT `f6a0c873` já conta
  184 unplanned) e NUNCA atribuídas a não-qualificado nem a operador-fantasma; /overall mostra a
  lane com aviso em vez de a esconder.
- **Esperado:** zero atribuição fabricada (Spelke + invariante #8). Capacidade agregada por
  SETOR não existe (só estações por fase) — quando a config por setor chegar
  ([DOMAIN_RULES.md](DOMAIN_RULES.md)), acrescentar o teste de saturação do setor.
- **Automação:** pytest unit/property + integração.

### R8 — Camião SHP-2026-06-19 com 45/50 assignments obsoletos

- **Pré `[BD]`:** `plan.transport_batch` tem 20 batches OPEN (capacity 50, 589 assignments).
  O **SHP-2026-06-19** tem 50 assignments mas só **5** ordens ainda têm
  `transport_date=2026-06-19` (42 mudaram para 2026-07-03, 2 para o passado, 1 órfã) — **45
  obsoletos**; a OF 902252 (transport_date 19-06) ficou DE FORA porque o camião está "cheio" de
  stale. `[CÓDIGO]` `transport_batch_service.py:256-261` nunca reatribui nem limpa.
- **Passos:** `POST refresh-from-orders` 2× → assert: stale removidos/reatribuídos, 902252
  entra no camião do seu dia, idempotência (2ª chamada não duplica); `GET by-date` para
  2026-06-19 e validação visual de Prontos-a-sair em /expedicao.
- **Esperado:** hoje FALHA (non-clobber sem limpeza); pós-fix os assignments refletem as
  transport_dates atuais.
- **Automação:** pytest `@integration` + browser manual (visual).

### R9 — Conflito plano × expedição (OF 902252: due 19-06, planeada para novembro)

- **Pré `[BD]`:** 902252 tem due 2026-06-19 (`OF_TR_DATA_PREVISTA`); no DRAFT `f6a0c873` a fase
  33 só começa a **2026-11-02** (fim 2026-11-05) — 4,5 meses depois do camião. `[CÓDIGO]` NÃO
  existe ligação plano→camião: `fitness.py:100` `truck_consolidation_weight=0.0` e
  `compute_truck_consolidation_penalty_h` (`transport_batch_service.py:322`) só é chamada em
  `tests/plan/test_sprint_p.py`; o `/by-date` (`transport.py:591-662`) classifica risco pela
  fase ATUAL, não pelo plano.
- **Passos:** (alvo) endpoint/painel de conflitos lista OFs cujo fim planeado >
  `transport_date` do camião atribuído → assert 902252 listada; verificação independente por
  SELECT que cruza o JSON do commit com `production_orders.transport_date`.
- **Esperado:** hoje o conflito é invisível por construção; o teste só pode existir DEPOIS da
  ligação plano→camião ([IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)). Atenção ao dado
  envenenado: `transport_date` do mirror usa fallback `OF_DATA` (data de criação!)
  (`q131_setup_production_orders_mirror.py:54-57`) — corrigir antes de testar.
- **Automação:** pytest integração (cruzamento) + manual browser.

### R10 — Cubes mortos + golden-SQL + explicabilidade

- **Pré `[BD/CÓDIGO]`:** 49 `sql_table` únicos em `cube/model/*.yml` vs 30 views em marts →
  **18/51 cubes mortos** (v_ciclos_cura, v_consumo_by_of_dia, v_copilot_{feedback,latency,rag}_*,
  v_cura_compliance_mes, v_estufa_{temp,humidade}_mes, v_facturacao_agente_trim,
  v_horas_operador_mes, v_moldes_top_uso, v_reagendamentos_mes, v_throughput_modelo_sem,
  v_transp_docs_mes, v_transportes_mes, v_workforce_*_mes ×2, factory_raw.iot_sensor_alarm) →
  **51/139 measures** morrem em query-time (provado live: Cube `/load` 400).
- **Passos:** (a) paridade: para cada `sql_table`,
  `SELECT to_regclass('<schema.tabela>') IS NOT NULL` (estilo `test_alembic_table_parity`);
  (b) golden-SQL G1-G12 (§2.8) com gate ≥10/12; (c) explicabilidade: cada resposta cita
  tabela/campo/filtro/fórmula/período (§2.9).
- **Esperado:** (a) FALHA hoje em 18 cubes; (b) G12 tem de dar **abstain honesto** enquanto o
  cube estiver morto.
- **Automação:** (a) pytest `@integration` trivial; (b)(c) harness live (extensão do q68).

---

## 4. Gates de regressão a acrescentar ao `verify_invariants.py` / CI

| Gate | Regra | Prova do defeito que previne |
|---|---|---|
| GATE-1 `cpsat-gate-persisted` | com `use_cpsat_global=true`, todo o commit do robô tem `cpo_meta.cpsat_gate` ou `cpo_meta.cpsat_error` (pytest + assert no `e2e_plan_smoke`) | fallback silencioso desde 2026-06-10; makespan 22.297 h sem ninguém ver (`engine.py:293-305`) |
| GATE-2 `cube-view-parity` | `to_regclass` para cada `sql_table` de `cube/model/*.yml` (`@integration`) | 18/51 cubes mortos em query-time |
| GATE-3 `measure-registry-parity` | nomes do `MEASURE_REGISTRY` (132) ⊆ Cube (139) e vice-versa; proibir nomes de 3 segmentos sem cube correspondente | measures workforce com nomes inexistentes → picker sempre em erro; 9 measures invisíveis ao LLM |
| GATE-4 `etl-health` | nenhum source com ≥3 `status='error'` consecutivos em `core.etl_run`; expor em `/health/ready` ou painel sync | phase_history + worker_assignment 9/9 em erro (`dbo.FasesOf`) sem alarme |
| GATE-5 `no-op-reorder` | `manual_reorder.py` rejeita reorder com from==to (não cria commit nem entra na fila de reapply) | "op 110532::77 de 77 para 77" re-aplicado a cada run → pares DRAFT ~1 s, 203 DRAFT vs 3 LIVE |
| GATE-6 `rbac-route-parity` | toda a rota mutante sob `/v1/` casa com `ROUTE_PREFIX_REQUIREMENTS` OU tem `PermissionDependency` própria (estende `test_tenant_route_coverage_q168d`) | `/v1/config` fora da matriz (`rbac.py:233-234` vs `tenant_config.py:34`) |
| GATE-7 `no-rbac-override-in-tests` | AST scan (como o anti-`def test_*: pass` Q.61.01) que proíbe `dependency_overrides` de dependências de permissão em `tests/` | `test_q115_b_config_endpoints.py:135-142` anula o RBAC |
| GATE-8 `golden-sql-floor` | suite §2.8 ≥10/12 no harness noturno (live); falha bloqueia release, não o verify local | zero golden-SQL NL→Cube; erro silencioso do copiloto |
| GATE-9 `paired-empty-state` | convenção de revisão: teste `*_empty` de endpoint de lista exige irmão não-vazio (checklist do nelinho-review; automatizável por AST mais tarde) | `test_shortage_risks_empty` codifica o vazio-perpétuo |
| GATE-10 `harness-freshness` | check estático: `dr-smoke.sh` aponta :8001/topologia canónica; `validate_e2e.py` marcado deprecated ou repontado à BD | DR smoke falharia num restore real; E2E audita Excel morto |

Nota: GATE-1/4/5 têm também a forma "teste live" (passos novos no `e2e_plan_smoke.py`) porque a
lição Q.119/Q.142 é que fakes não apanham estes — verificar no stack vivo.

---

## 5. Mapeamento cenário → fase do [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

A numeração canónica das fases vive no IMPLEMENTATION_PLAN.md; aqui mapeia-se por tema. Regra:
**cada fase só fecha quando os cenários mapeados passam** (verde automatizado + evidência visual
quando aplicável).

| Cenário | Fase temática do plano | Tipo de teste no fecho da fase |
|---|---|---|
| R1 (CP-SAT gate + persistência) | Gate CP-SAT justo + observabilidade (decisão 1) | unit + e2e live + GATE-1 |
| R2 (reparações merge-back) | Reparações no mesmo plano (decisão 2) | integração + visual (badge/filtro) |
| R3 + R4 (stock/ruturas) | Stock mínimo P_STOCKMIN + lead-times E_PRAZOENTREGA + detector (decisão 4) | `@integration` + GATE-9 |
| R5 (operador 20348 / 422) | Correções de wiring UX (sheets/entidades) | TestClient + browser |
| R6 (operador indisponível) | Workforce/disponibilidade (regressão já; ausências quando a feature existir) | integração |
| R7 (fase sem capacidade) | CPO honesto sob escassez (Spelke/#8) | property + integração |
| R8 (camião stale 45/50) | Expedição: limpeza/reatribuição de assignments | `@integration` + visual |
| R9 (conflito plano×camião) | Ligação plano→expedição (depois de corrigir `transport_date` fallback `OF_DATA`) | integração + visual |
| R10 (cubes mortos + golden-SQL) | Cube/LLM: paridade + golden-SQL + explicabilidade | GATE-2/3/8 + harness live |
| §2.7 (roundtrips de regras) | Regras/config + RBAC `/v1/config` | TestClient + GATE-6/7 |

**Prioridade de implementação dos testes** (da auditoria): R1 (crítico, regressão live) →
GATE-2+GATE-4 (gates baratos de paridade/saúde) → R5+GATE-5 (bugs UX/dados) → GATE-6/7 (RBAC) →
R3/R4 (stock) → R8/R9 (expedição) → R2 (merge-back) → R10 (golden-SQL completo).

---

## 6. Perguntas em aberto ao dono `[PERGUNTA]`

1. Os 203 DRAFTs (incl. os pares "op 110532::77 de 77 para 77" criados pelo smoke Q.172.C) podem
   ser limpos da BD quando o GATE-5 entrar?
2. `/overall` com deep-link por `?commit_sha=` (histórico navegável) é desejado, ou o
   comportamento "só o último commit saudável" (Q.162) é intencional e fica?
3. Quando o CP-SAT cai em fallback: além de persistir `cpsat_error` no commit (exigido pelo R1),
   queres alarme ativo no painel sync?
4. Qual é a porta/topologia canónica de produção para o `dr-smoke.sh` (8000 vs 8001; Postgres
   Docker vs nativo)?
5. Confirma a lista canónica das "8 tarefas do dono" para garantir mapeamento 1:1 da cobertura
   (mapeámos shortage-risks, expedição, gate CP-SAT e RBAC /v1/config).
