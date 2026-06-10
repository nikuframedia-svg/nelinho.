# Matriz de paridade axioma × caminho de execução (Q.169.A, 2026-06-10)

> Gerada por 6 agentes (1 por caminho) + cético a refutar gaps, sobre o código real.
> É o mapa do que cada caminho GARANTE — e o contrato que `validate_schedule()` (Q.169.B)
> passa a verificar de forma universal no caminho de escrita.

## A matriz

| dimensão | greedy+decoder | CP-SAT global | GA+MAP-Elites | reapply (robô) | preview/apply | safety_net |
|---|---|---|---|---|---|---|
| ax1 capacidade | ✅ | ✅ | ✅ | ✅ | ❌ | ✅(KPI) |
| ax2 precedência | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅(KPI) |
| ax3 molde exclusivo | ⚠️¹ | ⚠️² | ⚠️¹ | ❌³ | ⚠️ | n/a⁴ |
| ax4 par Laminagem | ⚠️⁵ | ⚠️ | ⚠️⁵ | ❌⁶ | ⚠️ | n/a⁴ |
| ax5 skill match | ✅ | ✅ | ✅ | ✅ | ⚠️⁷ | n/a⁴ |
| ax6 cura química | ✅ | ✅ | ✅ | ✅ | ⚠️⁷ | n/a⁴ |
| ax7 baseline | (é o baseline) | ✅gate⁸ | ✅ | ⚠️ | ⚠️ | ✅ (9 KPIs) |
| calendário | ✅⁹ | ✅ | ✅ | n/a | ❌ | n/a⁴ |
| due dates | ⚠️¹⁰ | ⚠️¹¹ | ✅ | ⚠️ | ❌ | ✅(KPI) |
| sem double-booking | ✅ | ✅ | ✅ | ✅ | ⚠️⁷ | n/a⁴ |
| work-centers | ✅ | ✅ | ✅ | n/a | ❌ | n/a⁴ |

✅ garantido · ⚠️ parcial · ❌ ausente · n/a⁴ = por design o safety_net é gate de **KPIs**
(axioma 7), não valida estrutura — essa é a função do `validate_schedule()` novo.

## Mecanismos-chave (onde cada garantia vive)

- **greedy+decoder**: `decoder_resources.py` — `machine_free_at`/`worker_free_at`/`mold_free_at`
  (ax1/ax3/double-booking), `_precedences_met`+`_earliest_start` com `min_gap_hours` das 16
  transições (ax2/ax6), `state.workers_for` filtra skill (ax5), `calendar.add_working_hours`
  (decoder_resources.py:676-695, Q.53.B — calendário É consumido, ao contrário do que a
  auditoria alegou), `pair_assignment.prefers_pair` com downgrade soft (ax4, Sprint Q.8).
- **CP-SAT global**: cumulative por fase + molde + calendário no modelo; workers atribuídos
  pelo **postpass** (`cpsat_postpass.py`) que reusa a lógica do decoder.
- **GA**: mutações nunca violam — o decoder re-impõe tudo na descodificação (axiomas hard
  by construction; fitness só pontua).
- **safety_net**: 9 guardrails de KPI (3 hard: late/tardiness/OTD; 6 soft com tolerância:
  makespan 1.5×, throughput −5%, quality_risk +10%, setups +15%, idle +20%,
  lam_utilization −5pp, idle_ratio +5pp). **NOTA: spelke_axioms.md dizia "só 4 KPIs" —
  desatualizado desde Q.54.G; corrigido nesta campanha.**

## GAPS CONFIRMADOS (trabalho Q.169.C/D + Q.170)

1. **(ax3, CP-SAT)** `cpsat_scheduler.py:192-200` — ops com `model_id=''` agrupadas na chave
   vazia; a condição `if mfm is not None and model_id:` salta a constraint → exclusividade
   de molde furada para essas ops. → **Q.169.C**
2. **(due dates, CP-SAT)** o solve minimiza SÓ makespan — sem objetivo/constraint de
   tardiness; due dates só entram nos KPIs a posteriori. → **Q.169.D** (tardiness ponderada
   + makespan, lexicográfico)
3. **(ax7, CP-SAT)** gate de aceitação só compara makespan (`engine.py:246-256`),
   `safety_net_triggered=False` à força — as outras 8 dimensões passam sem gate. → **Q.169.D**
4. **(ax4, reapply)** `manual_reorder.py:282` escreve `workers=[new_operator_id]` (UM) sem
   validar par em fase Laminagem — o apply de operador pode deixar Laminagem solo sem aviso.
   → **Q.169.C** (validação de par no apply) — nota: molde/par ficam garantidos quando o
   robô replaneia, mas entre o drag e o replan o plano LIVE viola.
5. **(due dates, greedy)** `greedy_pipeline.py:214-237` calcula `anchors` (backward
   scheduling) mas NUNCA os passa ao `decode()` (linha 155) — backward fica opt-in via
   `chromosome.schedule_direction` e os anchors da fase 2 são trabalho morto. → **Q.169.D**
6. **(tudo, preview/apply)** `preview_delta_service.apply()` persiste SEM validação nenhuma
   (design Q.153.D2: "o robô revalida no reapply") — mas entre o apply e o replan o LIVE
   pode violar molde/cura/skills/double-booking; e o preview tem o bug start/start_time
   (deteção nunca dispara). → **Q.170.B** (campos certos + validação hard mínima no apply
   via `validate_schedule()` delta-aware)

## Refutações do cético (NÃO mexer)

- "calendário não consumido pelo greedy" — FALSO (`decoder_resources.py:676-695`).
- "Infusão tratada como par obrigatória" — o substring match (state.py:850) torna-a
  par-PREFERIDA (soft); o gap real é de POLÍTICA: histórico diz 58% solo/24h — devia estar
  fora da preferência de par (lista exata, não substring). → **Q.169.C** decide com dados.
- "safety_net sem guardrails estruturais" — por DESIGN (gate de KPIs); a peça estrutural é
  o `validate_schedule()` (Q.169.B), não engordar o safety_net.

## O contrato do `validate_schedule(schedule, state)` (Q.169.B)

Valida ESTRUTURA sobre `schedule["operations"]` (start_time/end_time/mold_id/workers/
phase_id/order_id/sequence), independente de engine e de baseline:

1. ax3: nenhum par de ops com o mesmo `mold_id` sobreposto no tempo (respeitando
   pocket_count>1 como capacidade);
2. double-booking: nenhum worker em 2 ops sobrepostas;
3. ax2/ax6: dentro de cada ordem, sequência monotónica E gap mínimo químico das 16
   transições respeitado entre fases consecutivas;
4. ax5: cada worker atribuído pertence ao pool `state.workers_for(phase_id)`;
5. ax4: fase par-preferida com `team_size>=2` quando o pool permitia (warning, não erro —
   o downgrade soft do Sprint Q.8 é política aceite);
6. ax1/work-centers: nunca mais ops simultâneas numa fase do que estações declaradas.

Ligação: `CommitsService.create_from_schedule` RECUSA schedule inválido (erros hard) e
anexa warnings ao `cpo_meta.validation`; o reapply e o apply-move chamam a variante
delta-aware. Property tests hypothesis por dimensão.
