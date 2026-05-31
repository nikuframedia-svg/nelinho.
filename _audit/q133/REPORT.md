# Q.133 — Loop de aprendizagem + paralelismo real por fase · REPORT

**Branch:** `feat/q131-cpo-real-data` (continuação). Itens deferidos do "Palantir level".

## Q.133.A1 — Job de calibração de durações (commit `dbacf17`)
`src/scheduling/jobs/phase_calibration_job.py`: agrega `factory_raw.of_fp` JOIN `ordemfabrico`
(keyed por **OF_P_ID**, mesma limpeza do `state.py`) → `percentile_cont(0.5/0.95)` por
(modelo, fase) → UPSERT `plan.phase_duration_calibration` (prior/delta, `HAVING count>=5`). Wire
06:40 UTC. **Live: 3221 pares calibrados, idempotente (delta=0 na 2ª corrida), Laminagem
p50 ~241min (~4.0h, bate na realidade 4.32h).** Runner `scripts/q133_calibrate_durations.py`.

## Q.133.A2 — `state.py` prefere o p50 calibrado (commit `8cd9edc`)
Campo `calibrated_durations` + loader `_load_phase_calibration_db` + `median_duration_h` prefere
o p50 calibrado quando `n_obs >= 5` (degrau, não blend; vazio = back-compat). **Live: load()
carrega 3221 calibrações; `median_duration_h('1','42366')` = 4.02h (calibrado, 153 obs).**
Determinismo: a duração calibrada muda o hash do commit (efeito desejado de aprender).

## Q.133.B — Work-centers: N estações paralelas por fase (commit `a43b551`)
Análise da BD real: o ERP **não tem master de máquinas** (`OFFP_ARM_ID` constante,
`core.machines` vazio). MAS a concorrência histórica em `of_fp` prova o paralelismo
(Laminagem ~11, Cura ~13, Pintura ~6). `phase_workcenters.derive_phase_stations` mede o **p95
da concorrência** (sweep-line) → `{fase: N}` (clamp 1..N_MAX). `routing_resolver` atribui cada op
ao work-center da fase (`{fase}::0k`); `scheduler_run` constrói N máquinas/fase (fallback MANUAL).
**Abordagem b1** (N instâncias, decoder INTACTO) → o molde continua a serializar.
**Live: makespan MANUAL 24.121h → work-centers 1.420h (−94%), realista; Laminagem com molde →
0 sobreposições do mesmo molde (axioma 3 intacto).**

## Surrogate XGBoost — DEFERIDO
Treina em ~100-250ms/retrain; persistir poupa ~1-5% de cold-start. Baixo valor face ao custo de
gerir artefactos/versões. Não implementado (decisão Q.133). O padrão `ModelRegistry`
(`src/ml/models/registry.py`) existe se a demanda mudar.

## Gate
`& .\scripts\verify.ps1 -QuickPython` **ALL GREEN** (ruff, invariants, audit-coverage, drift
BLE001=430, tsc, vitest, mocks 0 erros). tests/plan 854 + scheduling verdes.
**nelo-reviewer: APROVADO** (A1/A2/B) — CX1 limpo, A2 degrau/back-compat, B b1 preserva o molde
(decoder intacto), determinismo OK. 1 ressalva (`_N_DEFAULT` dead code) → corrigida em `cac0513`,
que também fechou um cross-assignment (fases sem concorrência agora cobrem TODAS as 41 fases de
produção com N_DEFAULT, em vez de cair na estação de outra fase).

## A3 — Loop plan-vs-real VERDADEIRO (próximo incremento, ainda NÃO feito)
A1/A2 fecham a **estrutura** (calibração do histórico real, lida pelo CPO + cache). O A3 (escrever
`PlanExecutionObserved` casando PLANEADO vs REALIZADO por commit, e calibrar do **desvio
sistemático**) é a 2ª fase do "ambos faseado". **Não verificável ao vivo aqui** — não há planos
committed (`plan_schedule_commits=0`: o endpoint sync não persiste; worker Arq não corre nesta
máquina). Buildable + unit-testável; demonstrável quando o worker correr e houver commits LIVE.

## Follow-ups honestos
- Métrica idle/safety_net conta estações vazias como idle → sobre-penaliza o modelo N-estações
  (o plano work-center foi flagged mas usado; makespan caiu 94%). Afinar idle p/ capacidade usada.
- A3 (loop do desvio); surrogate persistente; merge Q.131+Q.132+Q.133.
