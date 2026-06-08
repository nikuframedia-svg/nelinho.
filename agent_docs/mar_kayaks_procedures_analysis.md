# Stored procedures / funções do ERP NELO — análise (v2, VERIFICADA)

> Atualizado 2026-06-08. Substitui a v1 (2026-06-05), cuja premissa ("as SPs são lixo, só funções
> interessam; precisa grant do Nuno") está OBSOLETA. Catálogo cru (1006 corpos):
> [mar_kayaks_procedures.md](mar_kayaks_procedures.md) (~2.8 MB). JSON: `_dbprof/procedures/catalog.json`.
> Plano de ação completo: `.claude/plans/quero-que-tu-analises-shiny-dijkstra.md`.

## TL;DR

1. **Acesso CONCEDIDO.** `nikufra` ganhou `VIEW DEFINITION` (entre 2026-06-05 e 2026-06-08).
   `HAS_PERMS_BY_NAME(...)=1`, **1006 corpos legíveis** (eram 238 NULL). Havia **709 SPs reais**
   escondidas pela regra de metadata-visibility — a tese "6 SPs lixo" era um artefacto da falta de permissão.
2. **O motor da NELO é centrado na LAMINAÇÃO.** Tudo o resto flui daí (lead-time fixo). O nosso CP-SAT
   global contínuo é, na maioria, mais sofisticado — **não há motor a copiar**, só lógica a alinhar.
3. **O trabalho real é estreito.** Duas passagens de análise (larga: 106 deltas; profunda: 17
   confirmados / 8 corrigidos / **7 refutados**). Metade do que parecia mudança ou já está feito, ou é
   melhor manter.

## O motor de planeamento (corpos lidos ao vivo)

- `Planeamento_Previsão(@diasBarco, @barcosTurno)` — greedy dia×2-turnos que enche até `@barcosTurno`
  (~9) barcos/turno, casando barco↔molde por `(np, modelo, tamanho)`, ordenado por **data de transporte
  → barco mais antigo**. Molde = `P_TP_ID=82`, fases {13,14,15}, OF 70000-79999. **K4 = 2 slots; Ocean
  bloqueia o molde ~3 dias**; molde tem cooldown de cura (indisponível no dia seguinte). Exclui Cliente
  Fábrica (`e_id 19747`). Escreve `Z_PrevisaoPlano` (staging p/ revisão humana) +
  `of_plano_data_prevista`/`of_plano_turno_previsto`/`of_tr_data_prevista`. Lead-time lam→transporte = `@diasBarco` (~7 dias úteis).
- `Plano_Planeia(@of_id,@turno,@data)` — callback da UI; grava `OFFP_DATA_PREVISTA`/`OFFP_TURN_ID`/`OFFP_OF_ID_MLD`.
- `Acelerador_Laminagem_Epoxy/Polyester` — **rácios de capacidade** `(barcos-à-espera, K4=2×)/(equipas×dias×barcos)`
  por resina (`p_tp_id IN (7,9)`=Polyester). **NÃO** é química de cura (erro da v1).

## O que está ALINHADO / onde somos SUPERIORES (não mexer)

Timeline contínuo > turnos discretos · queue-time calibrado do histórico > curing-hard · selecção
multi-molde já replicada (`state.molds_for_model`+`mold_free_at`) · workforce automático > sugestão
manual · BOM single-level correcto (`P_PRECOCUSTO` rolado) · `scrap_factor=1.0` correcto · KPI tree =
metadados de UI (não measures) · prémio €/descontos `OFFP_RETURN`/gravidade = pós-execução (só profit,
nunca CPO) · K4/Ocean duração já está nos tempos históricos medidos · `v_of_is_boat` correcto (0-diff
vs `produto_Classes(1)` = 811 barcos).

## Mudanças verificadas que valem a pena (P0)

1. **Fase 14 confla barco↔molde** no `REPAIR_PHASE_IDS` (state.py:113). `of_EmReparacao`(barco)={76,77}+
   colagem(53) aberta; `getMoldesAReparar`(molde)=fase 14. → discriminar por `is_boat`.
2. **`phase_id_causer == phase_id_rework`** na ETL de qualidade (quality.py:130-131). O ERP separa
   `OFCH_FP_ID` (causou) de `OFCH_FP_ID_CHK` (detectou). Colapsá-los invalida o Root-Cause.
3. **Cadeia de culpa não populada** (`causer_employee_id`/`chefe_employee_id`/`original_op_id`) — o ERP
   rastreia via `OFCH_OFFP_ID_CULPA → OFFP_EQ` + `OFFP_OFFP_ID_RETURN`.
4. **Capacidade-disponível inexistente** — `Report_ProducaoCapacidade_V3` = `SUM(E_PRODUTIVIDADE) −
   ausências(ENT_MOV, MET_MET_ID=2)`. Zero measure nossa.

(P1, oportunidades net-new, roadmap, e decisões pendentes do Luis: ver o plano.)

## Princípio

Replicar (views `factory_raw`/`marts`), não chamar ao vivo (excepto `phc_*` externo). As inline-TVF/
views convertem-se quase 1:1 em views Postgres; as SPs de relatório (`Report_*`) servem de espec. As
SPs de escrita (`*_Add/_Upd/_Del`, `Transportes_*`, `Inventario_*`) são write-side da NELO — só
documentação, não replicar.
