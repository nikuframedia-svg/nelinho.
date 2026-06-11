# IMPLEMENTATION_PLAN.md — Plano faseado pós-auditoria (Q.173+)

> **Snapshot de dados:** todas as contagens de BD citadas neste documento são o snapshot de
> **2026-06-11** (auditoria multiagente: 44 agentes, BD real `prodplan-pg-wsl/prodplan_one` em
> modo read-only, verificação adversarial). Números podem ter divergido desde então — re-medir
> antes de cada fase.
>
> **Documentos-irmãos:** [AUDIT.md](AUDIT.md) (achados completos) · [DATA_FLOW_MAP.md](DATA_FLOW_MAP.md) ·
> [DOMAIN_RULES.md](DOMAIN_RULES.md) · [STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md) (Fases 4-5) ·
> [CUBE_LLM_KPI_AUDIT.md](CUBE_LLM_KPI_AUDIT.md) (Fase 8) · [TEST_PLAN.md](TEST_PLAN.md) (Fase 9) ·
> [DESIGN_SKILL_PROPOSAL.md](DESIGN_SKILL_PROPOSAL.md) (skill UX, Fase 6).

---

## 0. Decisões do Luis (2026-06-11) — tomadas, NÃO voltar a perguntar

1. **Gate CP-SAT: tolerância própria + baseline justo.** O baseline do gate axioma-7 é
   recalculado sobre o **mesmo op-set** do candidato (sem reparações 14/76/77); guardrails
   **soft** ficam isentos quando o makespan melhora **>50%**; **hard axioms intocáveis**;
   tudo configurável por tenant (`cpo.cpsat_gate.*`).
2. **Reparações (fases 14/76/77): merge-back no MESMO plano /overall.** O CP-SAT planeia
   barcos; as reparações são agendadas a seguir, no mesmo commit, com filtro/badge próprio.
   Não há agenda separada.
3. **"Gama/drop" = tipo/disciplina do produto** (`produto_tipo.TP_ID` /
   `produto.P_TP_ID_DISCIPLINA`). O filtro de gama no planeamento usa estas colunas.
4. **Stock mínimo: importar `P_STOCKMIN` do ERP + override local no nelinho** (o PATCH
   `/v1/supply/materials/{sku}/min-stock` já existe); lead times de `entidade.E_PRAZOENTREGA`.

## 1. Protocolo por fase (exigido pelo Luis)

**ANTES de cada fase:**
- Plano curto (o que vai mudar e porquê), lista de ficheiros prováveis, riscos.
- Fazer ao Luis as perguntas da secção "Perguntas" dessa fase (e só dessa fase).

**DEPOIS de cada fase, entregar:**
- Ficheiros alterados + o que mudou em cada um.
- Comandos de teste corridos + resultado (pytest no âmbito tocado, evidência live:
  queries SQL / chamadas HTTP / logs).
- Screenshots se houver UI (chrome-devtools).
- Riscos restantes + próxima fase recomendada.

**Regras duras:**
- **NÃO avançar para a fase seguinte se a fase atual estiver quebrada.**
- Sem refactors grandes; seguir o estilo do projeto; ambiguidade → ponto configurável ou
  pergunta ao Luis.
- Definições de UI têm de estar ativas no backend (nada de knobs decorativos).
- UI → validação visual; planeamento → testes com cenários reais; stock → testar
  rutura/suficiente/reservado/lead-time; Cube/LLM → validar explicabilidade.

## 2. Convenções de engenharia

| Convenção | Detalhe |
|---|---|
| Commits | `Q.173+.Y` (Q.173.A, Q.173.B, …), título ≤72 chars, body explica WHY, trailer `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` |
| Granularidade | 1 commit = 1 mudança lógica |
| Gate pré-push | `& .\scripts\verify.ps1` (**NÃO** `pwsh` — não existe nesta máquina; Windows PowerShell 5.1) |
| Branch | `feat/decisoes-frescas` (continuar; push já autorizado pelo Luis — campanha Q.168→Q.172) |
| Invariantes CLAUDE.md | ZERO MOCKS no frontend · PT-PT (nunca PT-BR) · 7 axiomas Spelke (property tests em `tests/plan/test_preview_delta_property.py` para qualquer invariant novo) · audit trail (`governance/audit_service.audit_change` na mesma tx) · DADOS HONESTOS (estado-vazio honesto, nunca número inventado) · CoeficienteX NUNCA em `src/plan/cpo/*` · Q.17 `requires_human_approval=True` |
| Backend dev | uvicorn :8001 **sem --reload** — depois de mexer em rotas/serviços, reiniciar backend e worker Arq antes de verificar live |
| O que apagar | registar em `DELETION_LOG.md` |

## 3. Mapa de fases e dependências

| Fase | Nome | Depende de | Decisão Luis | Áreas de origem |
|---|---|---|---|---|
| 0 | 8 documentos da auditoria + skill UX | — | — | todas |
| 1 | Fontes de dados erradas / hardcoded / ETLs | — | #4 (parcial) | bd-real, stock-mrp, profit-euros, vertical-barco, frontend |
| 2 | Regras configuráveis persistidas E usadas | — | — | regras-config |
| 3 | Lógica de planeamento e CP-SAT | F1 (recomendado) | **#1, #2** | cpsat-planeamento, verificacao-cpsat |
| 4 | Vertical por barco: materiais restantes + reparações | F1 | #2 | vertical-barco, stock-mrp, termos-dominio |
| 5 | Previsão de ruturas de stock | F1 + F4 | **#4** | stock-mrp |
| 6 | Gantt operacional com filtros fortes | F3, F4, F5 (filtros) | **#3** | ux-gantt |
| 7 | Subtabs ligadas à lógica real | F6 (parcial) | — | ux-gantt, frontend |
| 8 | KPIs, Cube e LLM corretos | — (paralelizável) | — | kpi-cube-llm |
| 9 | Validação completa | F1-F8 | — | plano-de-testes |
| 10 | Erros restantes (ML, learning loop, limpeza) | F9 | — | camada-ML, backend-api, profit-euros |

Rastreabilidade: cada item abaixo termina com `[origem: <área da auditoria>]` — as áreas são
as 9 da auditoria (frontend, backend-api, bd-real, cpsat-planeamento, regras-config, stock-mrp,
kpi-cube-llm, ux-gantt, termos-dominio) + as 5 lacunas fechadas (plano-de-testes, camada-ML,
verificacao-cpsat, vertical-barco, profit-euros). Detalhe e evidência de cada achado em
[AUDIT.md](AUDIT.md).

---

## Fase 0 — Escrever os 8 documentos da auditoria

**Estado: EM CURSO** (este documento faz parte dela).

**Objetivo:** persistir a matéria-prima da auditoria em documentos versionados antes que o
output efémero do workflow se perca.

**Itens:**
- `AUDIT.md`, `DATA_FLOW_MAP.md`, `DOMAIN_RULES.md`, `DESIGN_SKILL_PROPOSAL.md`,
  `STOCK_AND_REPAIRS_PLAN.md`, `CUBE_LLM_KPI_AUDIT.md`, `IMPLEMENTATION_PLAN.md`,
  `TEST_PLAN.md` na raiz do repo. [origem: todas]
- Criar `.claude/skills/industrial-ux-design/SKILL.md` (autorizado pelo Luis). [origem: ux-gantt]

**Critério de aceitação:** 8 ficheiros na raiz + skill; commit `DOCS:`; nenhum código tocado.

**Perguntas:** nenhuma.

---

## Fase 1 — Fontes de dados erradas, mocks, hardcoded, queries incorretas

**Objetivo:** tornar a base de dados honesta — eliminar valores fabricados/placeholder no
backend e ETLs que leem fontes erradas ou mortas, para que as fases seguintes assentem em
dados reais. Implementa a parte de importação da **decisão #4**.

**Itens:**
1. `transport_date` fabricada (fallback `OF_DATA` = data de criação → 9.606/9.606 ordens "têm"
   data de expedição): derivação honesta ou NULL — `scripts/q131_setup_production_orders_mirror.py:54-57`
   + o job de sync que a reproduz. [origem: vertical-barco]
2. ETLs mortos `phase_history`/`worker_assignment` (consultam `dbo.FasesOf`/`dbo.WorkerAssignment`,
   nomes do fake-ERP que não existem no ERP real — 9/9 runs em erro; `src/adapters/nelo/services.py:828/863`):
   desligar ou repontar para `OF_FP`/`OFFP_EQ` + **alarme quando `core.etl_run.status='error'`**
   (hoje ninguém lê). [origem: bd-real, plano-de-testes]
3. ETL `src/adapters/nelo/etl/material_master.py:55-56`: importar `P_STOCKMIN` → `min_stock_qty`
   (hoje `min_stock_qty=0` em **14.110/14.110 materiais**; ERP tem **P_STOCKMIN>0 em 1.110**) e
   `E_PRAZOENTREGA` → `lead_time_days` (hoje placeholder **7d em 100%**). Decisão #4: ERP é a
   fonte, override local mantém-se via PATCH min-stock. [origem: stock-mrp]
4. ETL `src/adapters/nelo/etl/purchase_orders.py`: ler do espelho `factory_raw.movimento` tipo 9
   (cobertura 100% vs ~2% atual — 138 POs vs ~5.987 tipo-9/12 meses), sem ETA fictícia
   `ordered_at+30d` (marcar estimativa como estimativa, nunca como facto). [origem: stock-mrp]
5. ETL `src/adapters/nelo/etl/inventory_ledger.py:116`: ler do espelho local (24 meses,
   `factory_raw.movimento` = **2.544.418** linhas) em vez de ERP-live `limit 5000` (hoje o ledger
   só tem 14 dias → StockoutPredictor e ROP sem história). [origem: stock-mrp]
6. ETL rework: preencher `mold_id` a partir de `OF_CHECKLIST` (**5.908 entradas com mold_id NULL**
   → mart `v_rework_por_molde_mes` devolve 0; revive o KPI rework-por-molde). [origem: bd-real]
7. `src/profit/services/margin_preview.py:36`: custo/h hardcoded **€12,00** → ler `core.labor_rates`
   (4.244 taxas reais, média 5,41 €/h). [origem: profit-euros]
8. Números autorais no backend: `src/explain/diagnostics/erro_tree.py:518-526` (€400/4h
   fabricados), `src/profit/explanation_engine.py:221-289` (pesos 55/25/20 e "+5%" inventados),
   `src/plan/cpo/greedy_pipeline.py:169` (timing `core_elapsed/4` fabricado) → remover ou
   tornar honesto. [origem: profit-euros, verificacao-cpsat]
9. `frontend/src/components/simulacoes/crisisScenarios.ts:124-150`: 6 cenários de crise com
   €/dias/cascatas hand-authored → ligar ao twin real ou estado honesto (único bloco de
   números autorais no frontend). [origem: frontend]

**Ficheiros prováveis:** `scripts/q131_setup_production_orders_mirror.py`,
`src/adapters/nelo/services.py`, `src/adapters/nelo/etl/{material_master,purchase_orders,inventory_ledger,sync}.py`,
ETL de rework (quality), `src/profit/services/margin_preview.py`, `src/profit/explanation_engine.py`,
`src/explain/diagnostics/erro_tree.py`, `src/plan/cpo/greedy_pipeline.py`,
`frontend/src/components/simulacoes/crisisScenarios.ts`, testes correspondentes.

**Dependências:** nenhuma. É a fase-fundação — F4/F5 dependem dos itens 3-6.

**Riscos:**
- Mudar `transport_date` para NULL pode esvaziar a /expedicao by-date — verificar consumidores
  antes (a derivação dos camiões Q.143 lê esta coluna).
- O ledger de 24 meses multiplica o volume de `inventory_ledger_entries` (~34k → potencialmente
  centenas de milhares) — medir tempo de sync e índices.
- Lição registada: ao trocar fonte de dados, **enumerar TODOS os leitores** da tabela afetada,
  não só os óbvios (memória `feedback_source_filter_all_readers`).

**Critério de aceitação (verificável):**
- `SELECT count(*) FROM supply.supply_material_master WHERE min_stock_qty>0` ≥ 1.110;
  `lead_time_days` deixa de ser 7 universal (distribuição com ≥2 valores distintos).
- `core.etl_run` sem `status='error'` permanente em phase_history/worker_assignment (desligados
  ou verdes) + alarme provado (forçar 1 erro → alerta visível).
- `SELECT count(*) FROM quality.rework_entry WHERE mold_id IS NOT NULL` > 0 e
  `marts.v_rework_por_molde_mes` devolve linhas.
- 0 ocorrências de `€12`/`12.00` hardcoded em margin_preview; grep aos números autorais
  removidos; pytest verde no âmbito.

**Perguntas ao Luis quando a fase chegar:**
- `E_PRAZOENTREGA` está em dias? É fiável como lead time, ou o real está em
  `MOVIMENTO_FORNECEDOR.MOVFOR_ETA` por encomenda? (ver perguntas abertas)
- Os 6 cenários de crise: remover, ou recalcular com o twin real?
- No tablet do operador, que `error_codes` reais deve cada botão registar? (hoje "Falta
  peça"→COLAGEM_FAIL e "Erro molde"→DIMENSION_OFF parecem trocados —
  `operadorTabletBits.tsx:13-17`) [origem: frontend]

---

## Fase 2 — Regras configuráveis persistidas E usadas

**Objetivo:** fechar o fosso entre "configurável anunciado" e "configurável real": cada knob
da UI tem de chegar ao motor, e os knobs que comandam o planeador têm de voltar a ter UI.

**Itens:**
1. RBAC: acrescentar `/v1/config` à matriz (`src/shared/auth/rbac.py:233` protege
   `/v1/core/config`, prefixo que **nenhum router usa** — o router real é
   `tenant_config.py:34 prefix="/v1/config"` e cai no fall-through do middleware → mutações de
   config sem gate de permissão). [origem: regras-config, plano-de-testes]
2. Recriar UI de configuração do planeador em /configuracoes (binding FE removido em Q.172.E —
   `platformApi.ts:252-255`): `planning.scope`, `cpo.use_cpsat_global`, caps/time-limit do robô
   (`auto_cpo_replan_job.py:34,42` corre em defaults hardcoded), `transporte.truck.capacity`/
   `capacity_moda` (unifica os 50 vs 26 da /expedicao), thresholds de alertas — tudo via o
   `/v1/config` existente. [origem: regras-config, frontend]
3. Ligar `alertas.*` (**84 keys de config mortas** de 184 seeded — `agent_docs/config_keys_audit.md`)
   ao motor `src/copilot/alerts/engine.py:254` — pelo menos os thresholds; decidir
   apagar-vs-ligar para o resto. [origem: regras-config]
4. Cura DB-first real: semear `plan.phase_transition_gap` (hoje **0 rows** — a cura química vive
   só do seed `state.py:NELO_CURING_GAPS_SEED`, 16 transições) + ligar o PATCH
   `/v1/plan/phase-gaps/{from}/{to}` (`phase_gaps.py:161`, já existe) à tab Cura do FaseSheet
   (hoje read-only). Spelke: cura é química, não fila — editar exige cautela. [origem: regras-config]
5. `use_queue_time` (hoje campo de código `engine.py:104`, default True, não configurável) e
   `REPAIR_PHASE_IDS` (hoje frozenset hardcoded `state.py:113`) → config de tenant com defaults
   atuais. [origem: regras-config, cpsat-planeamento]

**Ficheiros prováveis:** `src/shared/auth/rbac.py`, `src/core/api/tenant_config.py`,
`frontend/src/pages/configuracoes/*`, `frontend/src/lib/api/platformApi.ts`,
`src/copilot/alerts/engine.py`, `src/core/services/default_configs.py`,
`src/plan/api/phase_gaps.py`, `frontend/src/components/entitySheets/sheets/FaseSheet.tsx`,
`src/plan/cpo/{engine,state,scheduler_run}.py`, `src/plan/engines/cpsat_global.py`.

**Dependências:** nenhuma dura; o item 5 (REPAIR_PHASE_IDS configurável) deve aterrar **antes
ou junto** do merge-back da Fase 3 para evitar mexer duas vezes no mesmo sítio.

**Riscos:**
- Item 1 pode partir clients que hoje editam config sem permissão — RBACMiddleware é off em
  dev, testar com `rbac_strict`.
- Atenção ao teste que anula o RBAC (`tests/api/test_q115_b_config_endpoints.py:135-142`
  faz `dependency_overrides`) — corrigir o teste, não herdar o buraco.
- Editar gaps de cura por UI pode violar química real — manter audit trail + valores seed
  como default visível.

**Critério de aceitação (verificável):**
- `requirements_for_route('/v1/config/...')` devolve permissão (teste novo); PATCH sem role
  → 403 com `rbac_strict`.
- Mudar `transporte.truck.capacity` na UI muda o valor servido pelo backend (prova live).
- Mudar um threshold `alertas.*` muda o disparo do motor de alertas (teste + prova live).
- `plan.phase_transition_gap` > 0 rows; PATCH de um gap reflete-se no próximo plano
  (`cpo_meta` ou query ao decoder).
- pytest verde + property test Spelke se algum invariant novo for introduzido.

**Perguntas ao Luis quando a fase chegar:**
- Das 84 chaves mortas (alertas.*, dispatch.*, kpi_targets.*, notifications.*): ligar quais e
  apagar quais do seed?
- Calendário de fábrica: precisas de UI para sábados de trabalho/paragens (hoje só GET,
  `etl/calendar.py:145` gera seg-sex+feriados PT), ou o gerado chega? [origem: regras-config]
- /regras (Q.17, 0 regras na BD): qual o primeiro caso de uso real que queres como regra YAML?
  Só 1 dos 12 eventos do DSL é emitido hoje (`scheduler_run.py:597` SCHEDULE_PROPOSE) — ligar
  os outros é trabalho por evento; qual priorizar? [origem: regras-config]

---

## Fase 3 — Lógica de planeamento e CP-SAT (decisões #1 e #2)

**Objetivo:** devolver o plano live ao CP-SAT (makespan live **22.297h ≈ 2,5 anos** vs CP-SAT
**~690h** — o gate axioma-7 veta o candidato por **0,25pp** de idle_ratio desde 2026-06-10) e
tornar a decisão do gate auditável pela BD.

**Itens:**
1. Persistir `cpo_meta.cpsat_gate` **SEMPRE** (accepted=false + reason + engine) no commit final
   — hoje a rejeição morre em `src/plan/cpo/engine.py:293-305` (`return None` descarta a meta;
   só 1 commit em toda a tabela tem `cpsat_gate`); auditoria pela BD é impossível por
   construção. Incluir `cpo_meta.cpsat_error` quando o solver rebenta (fallback silencioso
   confirmado). [origem: verificacao-cpsat, cpsat-planeamento]
2. **Decisão #1 — baseline comensurável:** mesmo op-set nos dois lados do gate (hoje o candidato
   exclui 14/76/77 em `src/plan/engines/cpsat_global.py:72` e o baseline decodifica TODAS as ops
   em `engine.py:347-361` → idle_ratio incomparável). [origem: verificacao-cpsat]
3. **Decisão #1 — isenção de guardrails soft** quando o makespan melhora >50%, hard axioms
   intocáveis, configurável `cpo.cpsat_gate.*` por tenant (tolerância própria do gate CP-SAT,
   separada do +5pp desenhado para ruído da GA em `safety_net.py:83`). [origem: cpsat-planeamento]
4. **Decisão #2 — merge-back das reparações:** agendar as fases 14/76/77 pós-solve **no mesmo
   commit** (hoje, quando o CP-SAT ganha, as **76 OFs em reparação** desaparecem do plano — 0 ops
   vs 190 no greedy; nenhum runner separado existe). Badge/filtro `is_reparacao` fica para a
   Fase 6. [origem: cpsat-planeamento, termos-dominio]
5. Override fantasma: rejeitar reorder no-op (`from==to`) na origem + TTL para overrides sem
   commit LIVE (`src/plan/cpo/commits.py:404` só fecha a janela com um LIVE — último é
   2026-06-02, com **203 DRAFT vs 3 LIVE** o override "op 110532::77 de 77 para 77" do smoke
   Q.172.C re-aplica-se a cada replan e duplica commits de 8k ops) + limpar os DRAFTs-lixo.
   [origem: cpsat-planeamento, verificacao-cpsat]
6. Boosts pré-solve: passar `boost_inputs` ao `decode()` nos call-sites de produção
   (`engine.py:355/440`, `greedy_pipeline.py:155` — hoje recolhidos pós-solve em
   `scheduler_run.py:636-644`, só badge) — prioridade de cliente passa a influenciar a ordem
   do plano. [origem: cpsat-planeamento]
7. Logs do worker com append/rotate (`scripts/serve_demo.ps1:97-98` trunca `_arq.err` a cada
   arranque — a evidência do veto de 2026-06-10 perdeu-se). [origem: verificacao-cpsat]
8. Property tests Spelke para qualquer invariant novo
   (`tests/plan/test_preview_delta_property.py`). [invariante CLAUDE.md]

**Ficheiros prováveis:** `src/plan/cpo/{engine,safety_net,commits,scheduler_run,decoder}.py`,
`src/plan/engines/{cpsat_global,cpsat_scheduler,cpsat_postpass}.py`,
`src/plan/services/manual_reorder.py`, `src/plan/cpo/greedy_pipeline.py`,
`scripts/serve_demo.ps1`, `tests/plan/test_q169d_cpsat_gate.py` (+ teste novo de persistência
do gate no commit), `src/core/services/default_configs.py` (keys `cpo.cpsat_gate.*`).

**Dependências:** F1 recomendada antes (telemetria honesta do greedy_pipeline); item 4 coordena
com F2-item 5 (REPAIR_PHASE_IDS configurável).

**Riscos:**
- O maior da campanha: mexer no gate de segurança do planeador. Mitigação: hard axioms
  intocáveis, tudo por config de tenant com default conservador, e o gate continua a poder
  vetar — só o baseline passa a ser justo e a rejeição a ficar gravada.
- Merge-back das reparações pode reintroduzir contenção de operadores/moldes pós-solve —
  validar axiomas no plano final combinado (gate corre DEPOIS do merge).
- HIPÓTESE da auditoria: a fila inter-fase Q.160 não é modelada no caminho CP-SAT
  (`cpsat_scheduler.py:132-158` só aplica cura) — assimetria que favorece o candidato; com o
  baseline no mesmo op-set fica mensurável; decidir se entra no modelo (pergunta abaixo).
- Reiniciar backend **e worker Arq** depois de cada mudança (processo stale = falso negativo).

**Critério de aceitação (verificável):**
- Após replan do robô: commit mais recente tem `cpo_meta.engine` preenchido e
  `cpo_meta.cpsat_gate` presente (accepted true ou false + reason) —
  `SELECT cpo_meta->'cpsat_gate' FROM plan_schedule_commits ORDER BY created_at DESC LIMIT 1`
  não-NULL.
- Plano live com engine=cpsat_global e makespan na ordem de centenas de horas (não 22.297h),
  **incluindo** ops nas fases 14/76/77 (≈190 ops no scope atual; as 76 OFs em reparação
  presentes).
- Reorder `from==to` → 4xx; zero pares de commits ~1s após limpeza; DRAFTs-lixo removidos
  (registado em DELETION_LOG.md).
- Plano A/B com boost de cliente: ordem muda (teste determinístico com seed).
- `_arq.err` sobrevive a restart do serve_demo (append + rotate provado).
- Suite `tests/plan` verde + e2e_plan_smoke live.

**Perguntas ao Luis quando a fase chegar:**
- Fila inter-fase mediana (Q.160): deve entrar no modelo CP-SAT, ou one-piece-flow
  (fila=desperdício) é a política para o plano otimizado? [origem: cpsat-planeamento]
- Backward scheduling (PL14, `scheduler.direction=backward` morto em produção —
  `decoder.py:132`, nenhum código o ativa): o objetivo tardiness do CP-SAT substitui-o de vez,
  ou é para religar? [origem: cpsat-planeamento]
- Materiais/stock devem condicionar o arranque de fases no plano (hoje não entram de todo no
  modelo — `greedy_pipeline.py:197-201`)? Se sim, em que fase da campanha? [origem: cpsat-planeamento]
- Indisponibilidades individuais (férias/baixas) dos **106 operadores ativos**: modelar?
  Existe fonte no ERP? (ver perguntas abertas) [origem: cpsat-planeamento, regras-config]

---

## Fase 4 — Planeamento por barco: materiais restantes + reparações (decisão #2, lado dos dados)

**Objetivo:** dar ao utilizador a vertical completa de um barco real — que materiais faltam,
quando está planeado, em que camião sai — incluindo barcos em reparação. Detalhe em
[STOCK_AND_REPAIRS_PLAN.md](STOCK_AND_REPAIRS_PLAN.md).

**Itens:**
1. Serviço+endpoint "**materiais restantes por OF**": reservas TPMOV=4 não satisfeitas +
   consumos TPMOV=11 vs BOM (`core.bom_items` / `produto_componente` = **111.339 ativas**, com
   `COMP_FP_ID` = fase de consumo) — OF 902252 como cenário real (**78 reservas em aberto**,
   351,6 unid). Hoje isto **não existe em lado nenhum** do produto. [origem: vertical-barco]
2. Semântica `MOVIMENTO_TIPO` local: espelhar a tabela de tipos do glossário
   (`routes/_GLOSSARIO_BURACOS.md:14-31`: 1=Entrada, 2=Saída, 4=Reserva, 11=Saída como
   componente, 12=Pedidos internos) — hoje queries no espelho não conseguem JOIN ao nome.
   [origem: vertical-barco, stock-mrp]
3. Reparações visíveis na expedição: hoje **74 das 76** OFs em reparação ficam fora de
   `plan.production_orders` (o mirror filtra `WHERE NULLIF(OF_DATAFIM,'') IS NULL` —
   `q131_setup_production_orders_mirror.py:61` — e a reparação reabre uma OF já fechada);
   due honesta (não a da venda original de 2024, ex. OF 900895). [origem: vertical-barco]
4. Camiões: o refresh deve largar assignments obsoletos quando `transport_date` muda
   (`src/plan/services/transport_batch_service.py:256-261` nunca remove stale — camião
   SHP-2026-06-19 tem 50 assignments mas só 5 ainda são desse dia); capacidade via config
   (`transporte.truck.capacity` da F2, não o default 50 hardcoded em
   `transport_batch_service.py:220`). [origem: vertical-barco]
5. Gate de materiais do CTP real: explodir BOM nível-1 em vez do proxy do stock do produto
   acabado (`src/plan/services/ctp_service.py:176-194` admite "we check the finished product's
   own stock figure"). [origem: stock-mrp]

**Ficheiros prováveis:** novo serviço em `src/supply/` ou `src/plan/services/` (materiais por
OF), `scripts/q131_setup_production_orders_mirror.py` + mirror de MOVIMENTO_TIPO,
`src/plan/services/{transport_batch_service,ctp_service}.py`, `src/plan/api/transport.py`,
`frontend/src/pages/expedicao/*` (badge reparação, materiais), migração Alembic se houver
tabela nova.

**Dependências:** F1 (itens 1, 3-6 — transport_date honesta, ledger com história, mold_id).
O item 3 alimenta o badge/filtro de reparações da F6.

**Riscos:**
- Incluir OFs de reparação em `production_orders` mexe com TODOS os leitores da tabela
  (CPO scope, expedição, decisões, OTD) — enumerar leitores primeiro.
- `v_of_is_boat` é view recursiva: JOIN+ORDER BY DESC LIMIT dá timeout — buscar boat-ids e
  `= ANY()` (gotcha Q.163).
- Reservas vs BOM divergem (BOM nível-1 inclui pseudo-componentes "Mão de Obra") — pergunta
  abaixo decide a fonte.

**Critério de aceitação (verificável):**
- GET materiais-restantes da OF 902252 devolve as 78 reservas em aberto com quantidades;
  OF sem falta devolve lista vazia honesta.
- As 76 OFs de reparação de `factory_raw.v_of_em_producao` (snapshot: **1.145** OFs em
  produção) aparecem na /expedicao com badge próprio e due honesta (nunca 2024).
- Refresh de camiões: ordem cuja `transport_date` mudou sai do camião antigo (cenário
  SHP-2026-06-19 do [TEST_PLAN.md](TEST_PLAN.md) passa de 50→5+novas).
- CTP de produto com componente em falta → bloqueado com razão; com BOM satisfeita → OK.
- pytest verde no âmbito + prova live com as 3 OFs reais (902252, 900895, 8970144).

**Perguntas ao Luis quando a fase chegar:**
- Materiais restantes: a fonte certa são as **Reservas abertas** (TPMOV=4, com fase de consumo)
  ou a **explosão BOM × consumos TPMOV=11**? Divergem. [origem: vertical-barco]
- Qual é o prazo de entrega real de uma reparação? Existe promessa nova no ERP
  (ENCOMENDA/transp_datas) que devamos usar? [origem: vertical-barco]
- Barcos sem prazo nenhum (ex. projeto ENALEIA): FIFO como hoje, ou há data contratual em
  ENCOMENDA (nunca espelhada)? [origem: vertical-barco]
- Existe o conceito de reserva/kitting na fábrica que devamos modelar, ou o consumo só se
  regista no movimento tipo 11? [origem: stock-mrp]

---

## Fase 5 — Previsão de ruturas de stock (decisão #4)

**Objetivo:** com mínimos e lead times reais (F1) e consumo/BOM ligados (F4), construir o motor
de rutura que avisa ANTES de o plano ser confirmado. Hoje a deteção é 100% inoperante:
`supply_rop_configs=0` → `/shortage-risks` devolve `[]` para sempre; ShortageDetector varre
14.110 materiais todos com mínimo 0 → 0 alertas alguma vez criados.

**Itens:**
1. `recompute_rop_configs` agendado (job no scheduler — hoje o serviço
   `src/supply/services/rop_calculator.py:66` + endpoint `rop.py:135` existem mas **nunca
   correram** e não estão agendados), com os mínimos+lead times reais da F1. [origem: stock-mrp]
2. Consumo previsto do plano: commit atual × BOM (timing por fase via `COMP_FP_ID`) → projeção
   por material/dia. Peça central em falta — não há nenhum código que cruze operações
   planeadas com `core.bom_items`. [origem: stock-mrp]
3. Mediana E moda do consumo por modelo (`factory_raw.movimento` tipo 11 = **1.468.924** linhas
   → OF → modelo; mart `v_consumo_material_dia` já existe com 80.316 linhas). [origem: stock-mrp]
4. Motor de rutura: stock atual + encomendas pendentes reais − reservas − consumo previsto →
   material em risco, barcos/modelos afetados, qtd necessária vs disponível, data provável,
   sugestão (compra/transferência/replaneamento) — **antes de o plano ser confirmado**.
   [origem: stock-mrp]
5. UI: página Materiais nova (rota `/materiais` — a antiga foi apagada no commit 2def464,
   lean A1) + `ShortageRiskPanel` do /overall ganha dados reais (hoje
   `risk_flags.py:98-121` itera 0 configs e o painel esconde-se para sempre) + ShortageDetector
   horário passa a alertar (`material_service.py:221`). [origem: stock-mrp, frontend]

**Ficheiros prováveis:** `src/supply/services/rop_calculator.py`, `src/supply/routers/rop.py`,
`src/scheduling/core.py` (job novo), serviço novo de projeção consumo-do-plano,
`src/factory_data_product/services/factory_map/risk_flags.py`,
`frontend/src/pages/materiais/` (nova), `frontend/src/App.tsx` (rota),
`frontend/src/components/overall/ShortageRiskPanel.tsx`, `src/supply/{shortage_detector,material_service}.py`.

**Dependências:** F1 (mínimos/lead times/ledger/POs reais) e F4 (semântica TPMOV, materiais
por OF). Sem elas o motor produziria números falsos — ordem é obrigatória.

**Riscos:**
- Projeção plano×BOM sobre 8k ops × BOM profunda pode ser pesada — agregar por material/dia,
  cache por commit_sha.
- Falsos positivos no arranque (dados de mínimos do ERP podem estar desatualizados) —
  apresentar sempre a evidência (stock, consumo, lead time) com o alerta.
- O teste existente codifica o vazio como OK (`test_factory_map_api.py:107
  test_shortage_risks_empty`) — adicionar o caso não-vazio, não o substituir.

**Critério de aceitação (verificável):**
- `supply.supply_rop_configs` > 0 após o job; re-corrida idempotente.
- Cenários do [TEST_PLAN.md](TEST_PLAN.md): material em rutura → alerta com data provável e
  barcos afetados; stock suficiente → sem alerta; reservado-mas-não-consumido tratado;
  lead time longo antecipa o aviso.
- `/v1/factory-map/shortage-risks` devolve items ≠ [] no cenário de rutura (prova live).
- Página /materiais carrega com dados reais, estados vazio/erro honestos, zero mocks.
- 1 alerta MATERIAL em `copilot_alerts` criado pelo detector (hoje 0 desde sempre).

**Perguntas ao Luis quando a fase chegar:**
- A previsão deve usar o consumo PREVISTO do plano (BOM×ops, mais fiel) e cair para
  mediana/moda histórica quando não há plano — confirmas esta ordem? [origem: stock-mrp]
- Página /materiais: que colunas/ações queres na v1 (mínimo editável, POs, data de rutura,
  sugestão)? Integrar também vista resumida na /expedicao? [origem: stock-mrp]

---

## Fase 6 — Gantt operacional com filtros fortes (decisão #3)

**Objetivo:** transformar a /overall de grelha lane×slot (célula=dia, `spanSlots=1` fixo,
duração nunca desenhada) num Gantt operacional legível e filtrável. Guia visual em
[DESIGN_SKILL_PROPOSAL.md](DESIGN_SKILL_PROPOSAL.md).

**Itens:**
1. Barras de duração reais (start→end; hoje `PorFaseView.tsx:228-233` empurra `spanSlots:1`
   sempre) + dependências visuais básicas; drill-down e edição em **todas** as escalas
   (semana/mês hoje são `CountBadge` cego sem onClick — `CountBadge.tsx:11-28`). [origem: ux-gantt]
2. Virtualização das lanes (985 lanes na Por Barco) + sticky headers + gzip no payload
   (hoje **2,3 MB re-fetched a cada 30s** — `OverallPage.tsx:160-169`; FastAPI sem
   GZip/ETag). [origem: ux-gantt]
3. Filtros (hoje só texto-livre + toggle "Só barcos" + datas): **barco**, **modelo** (nome real,
   não OF_P_ID numérico), **fase**, **operador**, **setor** (AREA_GROUPS/disciplina),
   **expedição** (camião/data), **gama = tipo/disciplina** (decisão #3:
   `TP_ID`/`P_TP_ID_DISCIPLINA`), **materiais-em-risco** (F5), **reparações** (`is_reparacao`,
   decisão #2), **prioridade** (boost/cliente), **datas**, **estado**
   (realizado/planeado/atrasado/em-risco). "Pessoa de expedição" fica **fora** — não existe
   fonte no ERP (transportadoras=84 empresas; `TR_OPERADOR_CODIGO` só 3% cobertura;
   documentado em [DOMAIN_RULES.md](DOMAIN_RULES.md)). [origem: ux-gantt, termos-dominio]

**Ficheiros prováveis:** `frontend/src/pages/overall/OverallPage.tsx`,
`frontend/src/components/overall/views/{PorFaseView,PorBarcoView,PorPessoaView,PorExpedicaoView}.tsx`,
`frontend/src/components/overall/Timeline.tsx`, `frontend/src/components/dark/TimelineLanes.tsx`,
middleware gzip em `src/app/`, endpoint do plano (campos para filtros: disciplina,
is_reparacao, effective_boost), `src/plan/services/cpo_commit_orders.py`.

**Dependências:** F3 (plano CP-SAT decente para mostrar; merge-back dá o `is_reparacao`),
F4 (reparações/camiões), F5 (filtro materiais-em-risco). Os filtros que dependem de F5 podem
aterrar num segundo commit da fase.

**Riscos:**
- Reescrita visual grande — fazer por vista (Por Fase primeiro), screenshots a cada passo,
  skill `industrial-ux-design` + invariantes do frontend (dark theme, inputs acessíveis).
- Virtualização pode partir o drag-drop existente (reorder provado live em Q.146/Q.153) —
  testar o drag após cada mudança estrutural.
- Performance: medir payload antes/depois (alvo: <500 kB gzipped ou paginação por janela).

**Critério de aceitação (verificável):**
- Op de 3 dias ocupa 3 slots; escala semana/mês permite drill-down e edição.
- Scroll fluido com 985 lanes (medição chrome-devtools performance trace).
- Payload de rede <½ do atual (list_network_requests antes/depois).
- Cada filtro reduz a grelha de forma verificável contra uma query SQL equivalente
  (ex. filtro gama=disciplina X ↔ count de OFs dessa disciplina no commit).
- Screenshots das 4 vistas anexados ao relatório da fase.

**Perguntas ao Luis quando a fase chegar:**
- O filtro "prioridade" é o boost 0-100, a prioridade de cliente, ou ambos? [origem: ux-gantt]
- Clicar num barco na grelha abre a ficha da ENCOMENDA (atual) ou do MODELO? [origem: ux-gantt]
- Dependências visuais: chegam setas fase→fase do mesmo barco, ou também molde/operador partilhado?

---

## Fase 7 — Subtabs ligadas à lógica real

**Objetivo:** matar o wiring partido entre grelha, sheets e pesquisa — tudo o que abre vazio,
dá 422 ou ignora parâmetros.

**Itens:**
1. OperadorSheet: aceitar `employee_code` (resolve→UUID; hoje `entity_summary.py:1193` exige
   UUID e os `workers[]` do plano são codes tipo "20365" → **422** garantido). [origem: ux-gantt, plano-de-testes]
2. ModeloSheet: resolver `OF_P_ID`→produto (hoje `entity_summary.py:626-646` procura
   `product_name == model_id` → tabs encomendas/produção vazias + título numérico). [origem: ux-gantt]
3. FaseSheet: aba KPIs (a `fila_mediana_h` já vem do backend — `entity_summary.py:905-917` — e
   é descartada no tipo FE `entityApi.ts:117-124`; juntar durações p50) + inputs
   `bg-white`→dark (`FaseSheet.tsx:488,509,531`). [origem: ux-gantt]
4. /overall lê `?commit_sha=` ("Ver plano" das decisões deixa de ser mentira —
   `DecisionHubActions.tsx:78` gera o link, `OverallPage.tsx:151` ignora-o e fixa
   `commits[0]`); filtro-por-fase no label (fix `stopPropagation` —
   `PorFaseView.tsx:191-200` + `Clickable.tsx:34-37`); badges **★afinidade** (UUID vs code
   nunca casa — `api_affinities.py:111` vs `PorPessoaView.tsx:184`) e **⚡boost**
   (`effective_boost` nunca mapeado — `OpCard.tsx:75`, `OverallPage.tsx:382-416`) ligados.
   [origem: frontend, ux-gantt]
5. Botão ajuda "?" nas 5 páginas (keys do `PAGE_HELP` são rotas antigas —
   `pageHelp.ts:14-34` tem 'planeamento'/'copilot' mas as rotas são overall/llm/…);
   ExpedicaoPage com `?tab=` (única página com tabs fora do URL); pesquisa global abre
   sheets (hoje `SearchResultsPage.tsx:57-66` descarta o id para 3 dos 4 tipos e navega para
   /overall sem contexto); remover `SpofRiskPanel` (chama `/v1/workforce/risks/spof`,
   endpoint **apagado** no saneamento) + cluster órfão palantir (8 componentes + ~8 hooks +
   APIs workforce mortas) → DELETION_LOG. [origem: frontend, ux-gantt]

**Ficheiros prováveis:** `src/plan/api/entity_summary.py`,
`frontend/src/components/entitySheets/sheets/{OperadorSheet,ModeloSheet,FaseSheet}.tsx`,
`frontend/src/pages/overall/OverallPage.tsx`, `frontend/src/components/overall/views/*`,
`frontend/src/data/pageHelp.ts`, `frontend/src/pages/expedicao/ExpedicaoPage.tsx`,
`frontend/src/pages/search/SearchResultsPage.tsx`,
`frontend/src/components/overall/{SpofRiskPanel,RiskStrip}.tsx`,
`frontend/src/components/palantir/`, `frontend/src/lib/api/{workforceApi,entityApi}.ts`.

**Dependências:** F6 parcial (mesmos ficheiros de vista — sequenciar para evitar conflitos);
itens 1-3 são independentes e podem começar cedo.

**Riscos:**
- `entity_summary.py` serve várias páginas — mudança de assinatura precisa de varrer callers
  (decisionEntities.tsx, vistas, pesquisa).
- Apagar o cluster palantir: confirmar 0 consumidores com grep antes (a auditoria do
  saneamento já mostrou que "órfão" às vezes era inflado).

**Critério de aceitação (verificável):**
- Clicar em operador na Por Pessoa abre sheet com dados (0×422, prova live).
- ModeloSheet aberto da grelha mostra nome do modelo + encomendas reais.
- `/overall?commit_sha=<sha do LIVE de 2026-06-02>` mostra ESSE plano.
- Botão "?" visível e com conteúdo nas 5 páginas do menu.
- Pesquisa global: hit de barco/molde abre sheet respetivo.
- Bundle sem palantir órfão (build verde, DELETION_LOG atualizado); vitest+pytest verdes.

**Perguntas ao Luis quando a fase chegar:**
- O histórico de /decisoes corta a 100 sem paginação (105 na BD) — paginar nesta fase ou na 10?
- Os 4 painéis do RiskStrip fazem fetch mesmo colapsados — lazy-mount aqui ou na 10?

---

## Fase 8 — KPIs, Cube e LLM corretos

**Objetivo:** catálogo Cube íntegro, agregações certas e explicabilidade ponta-a-ponta no
copiloto. Detalhe completo em [CUBE_LLM_KPI_AUDIT.md](CUBE_LLM_KPI_AUDIT.md).

**Itens:**
1. **18/51 cubes mortos** (sql_table aponta para views inexistentes → **51/139 measures**
   morrem em query-time, Cube /load 400): marts criadas no bootstrap/deploy (integrar os 49
   `scripts/setup_marts_*.py` no fluxo, hoje só o schema vem do Alembic
   `063_q93_a_marts_schema.py`) ou cubes removidos; decisão view-a-view conforme os dados
   existirem. [origem: kpi-cube-llm]
2. MEASURE_REGISTRY: corrigir nomes workforce (3 segmentos inválidos —
   `measure_contract.py:2291/2318` regista `workforce.colaboradores_activos.total` mas o Cube
   expõe `workforce_colaboradores.total`) + 9 measures do YAML em falta no registry + rebuild
   do `measure_index`. [origem: kpi-cube-llm]
3. Agregações: sum-de-countDistinct (`comercial_arpu.yml:397-401`), avg-de-médias não
   ponderado (família `*_avg/p50`), `moldes_top_uso.moldes_count` sem o filtro `counter>0`
   prometido; "OFs em curso" → 2 nomes distintos com critério explícito (**8.510**
   FP_SEQUENCIA<30 vs **1.145** v_of_em_producao). [origem: kpi-cube-llm]
4. Explicabilidade ponta-a-ponta: FE renderiza a query Cube exata (measures/filtros/período —
   hoje descartada em `copilotApi.ts:36-92`) + catálogo devolve fórmula SQL e tabela de origem
   → cada resposta explica tabela/campo/filtro/fórmula/período. [origem: kpi-cube-llm]
5. Endpoints autenticados para KPIs/chat-Cube (hoje tudo `*-dev` → **404 em production** —
   `headers.py:313-325`; o chat cairia silenciosamente para /ask sem caminho Cube).
   [origem: kpi-cube-llm]
6. Golden-SQL suite NL→Cube (hoje golden traces são shape-only com Ollama mockado —
   regressões semânticas como o caso workforce não são apanhadas pelo CI; lição
   `feedback_mock_vs_real_divergence`). [origem: kpi-cube-llm, plano-de-testes]

**Ficheiros prováveis:** `cube/model/*.yml`, `src/copilot/cube/{measure_contract,interpret,schema_compiler}.py`,
`src/copilot/routers/ask_cube.py`, `src/copilot/prompts/{cube_interpret,cube_narrate}.md`,
`frontend/src/lib/api/copilotApi.ts`, `frontend/src/pages/llm/KPIsTab.tsx`,
`src/shared/auth/headers.py`, `scripts/setup_marts_*.py` / `scripts/bootstrap_dev_full.py`,
`tests/copilot/` (suite golden-SQL nova).

**Dependências:** nenhuma dura — paralelizável com F4-F7. Gotcha: measure nova no Cube +
reindex NÃO chega; o interpret só escolhe cubes descritos em `cube_interpret.md` (memória
`feedback_llm_picker_needs_prompt_block`).

**Riscos:**
- Mexer no registry/index exige rebuild do `measure_index.npz` e restart do backend (processo
  stale = falso negativo).
- Criar 18 marts pode expor dados nunca validados — validar 2-3 âncoras por view contra SQL
  direto antes de ligar.
- Endpoints autenticados: não partir o caminho dev (a demo corre com
  ENVIRONMENT=development).

**Critério de aceitação (verificável):**
- Cube /load em TODAS as measures do catálogo → 0 erros "relation does not exist".
- Pergunta "quantos colaboradores ativos" → resposta com número (não abstain) e card
  workforce sem erro.
- Resposta do chat mostra: measure, tabela de origem, filtros, período (screenshot).
- KPIs/chat-Cube funcionam com `ENVIRONMENT=production` em teste local.
- Golden-SQL suite no CI: ≥15 pares NL→CubeQuery validados contra a BD; falha se a query
  semanticamente regredir.
- `scripts/e2e_llm_smoke.py` live verde.

**Perguntas ao Luis quando a fase chegar:**
- Definição canónica de "OFs em curso" para KPIs visíveis: critério Cube (8.510) ou critério
  NELO (1.145)? Mostrar ambos com nomes distintos? [origem: kpi-cube-llm]
- Faturação €125,8M (base PHC): confirma-se SEM IVA? (HIPÓTESE pendente CFO desde Q.102)
- "Não Laminado" continua a contar em `producao_pecas_laminadas.total`? (pendente decisão de
  negócio)
- Loop feedback→prompt (👍/👎 hoje write-only, 0 rows): reativar nesta campanha ou adiar?

---

## Fase 9 — Validação completa

**Objetivo:** provar a campanha inteira contra cenários reais, antes da fase de limpeza.
Cenários detalhados (com pré-condições SQL) em [TEST_PLAN.md](TEST_PLAN.md).

**Itens:**
1. `& .\scripts\verify.ps1` + pytest total + `scripts/e2e_plan_smoke.py` +
   `scripts/e2e_llm_smoke.py` live. [origem: plano-de-testes]
2. Cenários reais do TEST_PLAN: barco com falta de material (OF 902252), barco em reparação
   (OF 900895 / OF 17226 fase 77), operador indisponível, setor sem capacidade, stock
   insuficiente, conflito de expedição (camião SHP-2026-06-19 com 45/50 assignments stale).
   [origem: plano-de-testes]
3. Visual: screenshots chrome-devtools de todas as páginas alteradas; fluxos entre páginas
   (decisão→plano→expedição). [origem: plano-de-testes]

**Dependências:** F1-F8 (é o gate de saída da campanha).

**Riscos:** débito de testes pré-existente pode poluir o sinal — registar baseline de falhas
ANTES da campanha (no arranque da F1) para distinguir regressão de herança (a campanha Q.167
registou 3 falhas pré-existentes no verify).

**Critério de aceitação (verificável):** verify.ps1 sem regressões vs baseline; os 6+ cenários
do TEST_PLAN com resultado documentado (passa/falha + evidência); matriz cenário→resultado.

**Perguntas ao Luis:** demo guiada no fim (Tailscale), ou chega o relatório com screenshots?

---

## Fase 10 — Erros restantes da auditoria

**Objetivo:** fechar a cauda — ML avariado ou morto-honesto, loop de aprendizagem, € do
CoeficienteX, e limpeza de código.

**Itens:**
1. ML: retrain jobs (TypeError `SemanticQueriesInMemory()` sem engine →
   `src/ml/jobs/scheduling.py:98`, 100% das corridas falham desde 2026-05-30), drift job
   (assinatura errada + scaffold confesso — `drift.py:220/234-251`, `ml.drift_event=0`),
   `quality_risk` com labels reais (OF_CHECKLIST RCA da Q.167) ou desligado honesto
   (ativo tem auc=null/ap=0.0); `otd_risk` re-treina a cada visita ao /overall
   (`otd_risk_service.py:97`, scan de 200k linhas por GET). [origem: camada-ML]
2. plan-vs-actual: alarme "nenhum LIVE há N dias" (**203 DRAFT vs 3 LIVE**, último LIVE
   2026-06-02 → `plan_execution_observed=0`, o loop de calibração nunca aprende —
   `capture_plan_execution.py:207-215`). [origem: backend-api]
3. CoeficienteX: ETL espelho→`profit.phase_bonus_payout` (**22.002 linhas** com
   `PRODF_COEFICIENTE_X>0` prontas no espelho; hoje 0 na tabela — só existe endpoint REST
   nunca chamado, `api/bonus_payouts.py:55-63`). Semântica a confirmar primeiro (perguntas
   abertas). CoeficienteX é DINHEIRO — só `src/profit/`, NUNCA `src/plan/cpo/`. [origem: profit-euros]
4. Limpeza: query keys inline→factories (`keys.ts`), `request<any>` (opsApi/profitApi/factoryApi),
   HistoricoTab paginação (>100 decisões), Sidebar badge engole erro (`Sidebar.tsx:66-72`),
   endpoints zombie (`/v1/plan/schedule/` lê `production_schedules=0`; lifecycle
   governance.decisions sobre tabela vazia), DELETION_LOG para tudo o que for apagado.
   [origem: frontend, backend-api]

**Ficheiros prováveis:** `src/ml/jobs/scheduling.py`, `src/ml/observability/drift.py`,
`src/ml/models_domain/*`, `src/plan/services/otd_risk_service.py`,
`src/scheduling/jobs/capture_plan_execution.py`, ETL novo de bonus_payout,
`frontend/src/lib/api/keys.ts` e páginas com keys inline, `src/plan/api/schedule.py`,
`src/governance/routers/decisions.py`, `DELETION_LOG.md`.

**Dependências:** F9 (só entra com a campanha validada). O item 2 ganha valor real quando o
Luis definir a cadência DRAFT→LIVE (pergunta aberta).

**Riscos:** tentação de "consertar" ML sem valor de negócio — para cada modelo, decidir
primeiro com o Luis: religar a sério, ou declarar morto honesto (invariante #8) e registar
no DELETION_LOG. Não gastar uma campanha em retrain sem essa decisão.

**Critério de aceitação (verificável):**
- Retrain job corre sem TypeError (ou jobs removidos do scheduler + DELETION_LOG).
- Alarme de LIVE-stale dispara em teste com commit LIVE >N dias.
- `profit.phase_bonus_payout` > 0 e `margin_preview` deixa de devolver bónus 0€ universal.
- Greps de limpeza a zero (keys inline nas páginas tocadas, `request<any>`); endpoints zombie
  removidos ou repontados; verify.ps1 verde final.

**Perguntas ao Luis quando a fase chegar:**
- DurationModel (WMAPE 0,85; o CPO vivo usa medianas reais): retreinar com dados recentes,
  manter, ou remover da wiring? [origem: camada-ML]
- `sequence_mining`/`throughput_forecast` (treinam e deitam fora o modelo; Prophet nem está
  instalado): religar a sério ou apagar? [origem: camada-ML]
- Pipeline QLoRA (código morto, unsloth ausente): declarar morto até haver GPU no deployment
  da NELO? [origem: camada-ML]
- `completed_date` (100% NULL em **9.607 production_orders**) deve passar a vir de
  `OF_DATAFIM` no sync, para tornar o OTD-risk treinável? [origem: camada-ML, bd-real]

---

## Perguntas abertas não-bloqueantes (perguntar quando a fase relevante chegar)

| # | Pergunta | Fase onde decide | Origem |
|---|---|---|---|
| 1 | **Meta €/dia exata** para `core.daily_revenue_target` (CLAUDE.md diz €30-35K; tabela tem 0 rows — delta € invisível em /decisoes e `revenue_alignment` do CPO neutro). Valor e `effective_from`? | F2 (UI já existe: Configurações→custos) | profit-euros, frontend |
| 2 | **Meta OTD 95%** no KPI da Expedição (`ListaTab.tsx:185`) é oficial da fábrica ou placeholder a passar para config? | F2 | frontend |
| 3 | **Capacidade real do camião**: 50 lugares (header/CTP) vs 26 ("moda real Vila do Conde", `ProntosTab.tsx:20`) — qual é a verdade por camião/destino? | F2/F4 (config + refresh) | frontend, vertical-barco |
| 4 | **Cadência de aprovação DRAFT→LIVE**: com 203 DRAFT vs 3 LIVE o loop plan-vs-actual nunca aprende — é gap de processo (hábito diário?) ou de produto (fluxo de aprovação a desenhar)? | F3 (TTL overrides) + F10 (alarme) | backend-api, bd-real |
| 5 | **Fase 53 (colagem)**: o canónico ERP `of_EmReparacao` = {76,77}+53; o nosso `REPAIR_PHASE_IDS`={14,76,77} não inclui a 53. Deliberado, ou marcar `is_reparacao` também na 53? | F2/F3 (quando REPAIR_PHASE_IDS virar config) | termos-dominio |
| 6 | **Semântica de `PRODF_COEFICIENTE_X`** (média 1,32; 22.002 linhas >0): é o bónus € pago por unidade de fase×produto, ou precisa de transformação (×quantidade, ×horas) antes de carregar? | F10 (ETL bonus_payout) | profit-euros |
| 7 | **Acesso a `dbo.MOVIMENTO_FORNECEDOR`** no SQL Server da NELO (MOVFOR_ETA real + receções): existe? O placeholder eta=+30d e `qty_received=0` só se resolvem com ela. | F1 (ETL POs) | stock-mrp |
| 8 | **Ausências/férias no ERP**: existe tabela-fonte? Hoje o CPO assume os 106 ativos disponíveis todos os dias; o evento WORKER_ABSENT do DSL nunca é emitido. | F3 (modelo) / F2 (config) | cpsat-planeamento, regras-config |

---

*Gerado na Fase 0 da campanha Q.173+ a partir da auditoria de 2026-06-11 e do plano aprovado
pelo Luis (`s-um-senior-full-stack-declarative-aurora`). Contagens de BD são snapshot — re-medir.*
