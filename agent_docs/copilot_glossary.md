# Copilot glossary — PT-PT

Glossário PT-PT para o copilot do nelinho. Termos da fábrica NELO + invariantes
do código. **Single source of truth** — `src/copilot/rag.py:GLOSSARY_TERM_HINTS`
referencia este ficheiro; manter sincronizado.

Usado por:

- Schema docs RAG (Q.67.4.E) — `scripts/copilot_index_schema.py` injecta hints
  destes termos em cada chunk de tabela quando o nome bate.
- LLM system prompt — citações destes termos quando uma resposta envolve domain
  language (futuro: Q.67.4.F).

## Termos de domínio (fábrica)

- **fase** (production phase) — etapa do processo de fabrico (41 fases NELO).
  Ver `agent_docs/domain_glossary.md` para a lista por criticidade.
- **molde** — equipamento usado na laminagem (`pocket_count` = nº de barcos em
  paralelo). 510 moldes no ERP MAR-KAYAKS.
- **OF** (ordem de fabrico) — production order; 14.7/dia média histórica. No
  schema legado da ERP aparece como `OF_*`, `*_of`, `production_order`.
- **FaseOf** — fase específica de uma OF. Tempos vêm SEMPRE de `FaseOf_Inicio`
  → `FaseOf_Fim` (histórico real, limpo), **NUNCA** dos coeficientes standard
  (divergem até 25× do real).
- **cura** — secagem química do laminado; 16 transições com timing rígido
  (`src/plan/cpo/state.py:NELO_CURING_GAPS_SEED`). **Não é fila — é química.**
  Operação seguinte não pode começar antes do gap mínimo (Spelke axiom #6).
- **operário** / **operador** — empregado no chão de fábrica (122 operadores
  activos).
- **rota** (routing) — sequência de fases para um modelo (61 padrões NELO).
- **CoeficienteX** — **DINHEIRO €**; usado em `src/profit/`, **NUNCA** em
  `src/plan/cpo/*`. Invariante #5 do `CLAUDE.md`.
- **retrabalho** (rework) — refazer trabalho devido a defeito. 49.2% nas fases
  Lixagem água, 42.4% em Pintura Acabamento.
- **margem** (margin) — lucro vs custo. Calculada em `src/profit/`.
- **camião** (truck) — moda=26 barcos por viagem. Influencia agrupamento de
  expedições no scheduler.
- **expedição** — saída da fábrica para cliente.

## Termos de plataforma (nelinho)

- **trust_index** — score de confiança 0-1 de um schedule/decisão. Q.61 plan
  indexed-token. Calculado por `src/shared/trust/`.
- **kill switch** — admin-SQL-only emergency stop (governance.yaml_policy,
  `safety.kill_switch = Literal["admin_only"]`). LLM **nunca** pode mexer.
- **tenant_id** — UUID multi-tenant; dev = `00000000-0000-0000-0000-000000000001`.
  Header `X-Tenant-Id` obrigatório em todas as routes API (`require_tenant_header`).
- **schedule_commit** — snapshot autoritativo de um schedule gerado pelo CPO/GA.
  Inclui `rejected_alternatives` (invariante: nunca cair durante refactors).
- **safety_net** — defesas obrigatórias do CPO (cura, capacidade, ordem fases,
  routing_choices). 7 axiomas Spelke.
- **MAP-Elites** — algoritmo de diversidade do GA. Eixos canónicos:
  `num_late_orders` é tabu (Q.66.D invariante).

## Termos de governance

- **YAML policy** — regras logic-as-data (`src/governance/yaml_policy/`). 12
  events × 9 actions × 8 ops × 7 axiomas whitelist fechada.
- **requires_human_approval** — `Literal[True]` em Q.17 rules. LLM **nunca**
  pode opt-out.
- **audit_change** — cada mudança de estado escreve `audit_log` na mesma tx
  (`src/governance/audit_service.py`, Q.61.18).
- **SoD** (Separation of Duties) — proposer ≠ approver (Q.61.09).

## Termos ERP (MAR-KAYAKS)

- **MOVIMENTO** — tabela ERP com 12.4M linhas (operações ALL-TIME). Source
  primário para histórico de fases.
- **OF_FP** — tabela ERP com 2.6M linhas. Histórico de fases por OF.
- **FasesStandardModelos** — coeficientes standard. **Não usar** — divergem
  até 25× do real.
- **produto_stocks_por_armazem** — fonte real de stock no ERP. Espelhado em
  `supply.warehouse_stock` (Q.52.K).

## Tabelas de tempo / duração de fase (Q.68.C)

- **`factory_curated.order_phase`** — fonte canónica de `horas_reais` /
  `horas_previstas` / `horas_standard` por (`of_id`, `fase_id`). Usar para
  responder a "tempo médio fase X" ou "duração real vs prevista". Populada
  pelo mirror ETL `time_mining` (ver [[project_erp_realtime_write]]).
- **`plan.routing_template_phase`** — duração planeada por fase do template
  de routing (não real). Coluna `duration_p50_h` quando o `time_mining`
  conseguiu derivar p50 do histórico ERP.
- **`plan.phase_transition_gap`** — 16 transições de cura/secagem (Q.13).
  Química, não filas — `NELO_CURING_GAPS_SEED` em `state.py`.
- **AVG/p50 por fase em SQL** — `SELECT fase_nome, AVG(horas_reais)
  FROM factory_curated.order_phase WHERE data_inicio >= now() - interval
  '30 days' GROUP BY fase_nome` (com `run_sql` Q.67.4.C).
