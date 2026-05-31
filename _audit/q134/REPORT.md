# Q.134 — Loop plan-vs-real verdadeiro + fix idle + merge production-safe · REPORT

**Branch:** `feat/q131-cpo-real-data` (continuação de Q.131/Q.132/Q.133). Os 3 itens
deferidos do "Palantir level", a pedido do Luis. Merge **local** (sem push).

## Q.134.A3 — Loop plan-vs-real VERDADEIRO (commit `406f739`)
A calibração Q.133 fechou só a *estrutura* (CPO lê o p50 real). O A3 fecha o loop a sério:
aprende com o **desvio sistemático** PLANEADO vs REALIZADO.

- **A3a** — NOVO `src/scheduling/jobs/capture_plan_execution.py`: por cada `ScheduleCommit`
  LIVE recente, casa cada op planeada (`order_id`=OF_ID, `phase_id`) com `plan.fases_of_history`
  → `deviation_pct=(observed-planned)/planned*100` → UPSERT `plan.plan_execution_observed`.
  Lógica pura `build_observed_records` (unit-testada). Sem realizado → observed/deviation NULL
  (honesto, nunca inventa). `modelo`(=OF_P_ID) resolvido de `ordemfabrico`. Wired 06:35 UTC
  (entre plan_vs_actual 06:30 e calibração 06:40). Índice único parcial `uq_plan_exec_commit_of_phase`
  no modelo → UPSERT idempotente.
- **A3b** — `phase_calibration_job`: `_load_systematic_deviations` (AVG por modelo,fase, ≥3 pares)
  + `_adjust_for_deviation` → p50/p95 escalam pelo MESMO factor `1+clamp(dev,±50%)/100`. Sem dados
  → inalterado (só mediana, como antes). Grava `systematic_deviation_pct`. O `_AGG_SQL` recalcula
  sempre o p50 RAW de of_fp → o ajuste **não compõe** entre corridas.
- **Não verificável ao vivo** (0 commits LIVE + fases_of_history vazio). Buildable + **19 testes
  unitários**. Live (após M1): calibração corre, 3221 pares, desvio NULL (sem execução) → só mediana.

## Q.134.I — Idle do baseline e dos candidatos na MESMA fórmula (commits `c837575`+`5f86315`)
**Causa raiz (provada com probe):** com `use_greedy_pipeline=True` (default), o baseline vem do
`greedy_pipeline` e os candidatos GA do `decode()`. O `_phase8_scoring` **sobrescrevia** o
`total_idle_hours` do decoder (worker-based, `n_workers×horizon−busy` ≈ 200k h) por uma aproximação
avg_util (`makespan×(1−avg_util)` ≈ 1.380 h). O safety_net comparava as **duas fórmulas** → falsa
regressão de idle de ~140× (`192508 > 1.2×1380`) → revertia TODO plano work-center para o baseline,
deitando fora a otimização GA.

**Fix:** o `_phase8_scoring` deixou de recomputar `total_idle_hours`/`idle_ratio`/`idle_pct` — o
decoder (fases 4-7, chamado no `run`) já os põe worker-based. Mesma fórmula nos dois lados →
comparação justa. `num_machines` exposto no dict (observabilidade). **Safety_net e fórmula base
NÃO tocados** (axioma 7 fica mais forte, não mais fraco).

**Live (`probe_idle` + `verify_workcenters`):** violação `[total_idle_hours]` desaparece;
`safety_net_triggered=False` (`status=optimal`, era `safety_net`); makespan work-centers **1.513h
(−94% vs MANUAL 24.602h)**; molde **0 sobreposições**. 104 testes idle/safety_net/decoder verdes +
property test Hypothesis (n_ops/máquinas/horizonte variáveis → idle greedy == idle decode).

## Q.134.M1 — alembic upgrade head production-safe (commit `ca98b51`)
**Teste fresh-DB** (drop + `init-db.sql` + `alembic upgrade head`) provou que o **065 rebentava**:
`ALTER TABLE plan.phase_duration_calibration ENABLE RLS` numa BD fresca (`UndefinedTable`).

**Análise precisa da dívida:** das 7 tabelas da lista RLS do 065, **só 2** eram create_all-only
(sem `create_table` em migração): `plan.phase_duration_calibration` (Q.133.A1) e
`plan.plan_execution_observed` (Q.113/Q.134.A3a). As outras 5 já tinham migração
(`encomendas_cancelled`=q115_x5a, `boat_boost`=q116d, `order_boost`/`work_order_override`=q116c,
`kpi_snapshot`=q117d). *(A análise inicial do plano dizia "3"; o teste fresh-DB corrigiu para 2.)*

**Fix:**
- **065:** cada `ENABLE RLS`/`CREATE POLICY` embrulhado em DO-block com guarda
  `to_regclass(...) IS NOT NULL` → salta tabela inexistente em BD fresca, aplica RLS onde existe
  (backward-compatible). downgrade idem.
- **066 (nova, `down_revision=065`):** cria as 2 tabelas via `Base.metadata`+`checkfirst` (padrão
  055a) + `ALTER ADD COLUMN IF NOT EXISTS systematic_deviation_pct` (A3b) + `CREATE UNIQUE INDEX
  IF NOT EXISTS uq_plan_exec_commit_of_phase` (A3a) + RLS. Idempotente nos dois sentidos.

**Verificação fresh-DB:** `alembic upgrade head` SUCEDE (066 head); as 2 tabelas têm
coluna+índice+RLS. Dev DB migrado p/ 066. Limpou 4 `.pyc` órfãos (066-069 sem fonte). Corrigiu bug
pré-existente do teste RLS (`pg_class.rowsecurity`→`relrowsecurity`).

**Honestidade:** a BD fresca via alembic cria 75 tabelas; a real (create_all) tem ~110. A dívida
create_all/alembic remanescente (~35 tabelas fora da lista RLS do 065) é **pré-existente e maior** —
fora do âmbito deste sprint. O essencial está fechado: o `upgrade head` **já não aborta** (antes
nenhuma tabela depois do 065 era criada) e cobre as tabelas dos features Q.131-133.

## Gate + revisão (Q.134.M2)
- `verify.ps1 -QuickPython`: **ALL GREEN** (ruff src, lint-imports, invariants, audit-coverage,
  drift BLE001, tsc, vitest 173, mocks 0 erros).
- Suite Python completa: só **4 falhas pré-existentes** (test_ask_cube×2 + test_run_sql_live +
  test_percentile_90 — LLM/SQL-live + boat, ambientais; sem relação com Q.134). A RLS pré-existente
  foi **corrigida** (6→5 baseline; 1 SQL-live passou nesta corrida → 4 observadas).
- **nelo-reviewer: APROVADO** (sem violação de invariante crítico). Axioma 7 confirmado mais forte;
  A3 honesto/idempotente (ON CONFLICT casa com o índice da 066); migração production-safe; PT-PT;
  zero mocks. Ressalvas não-bloqueantes: (1) property test idle → **feito** (`5f86315`); (2) audit
  em jobs ML → dívida pré-existente (Q.133.A1 também não usa, tabelas de calibração não são
  estado-de-negócio); (3) 2 títulos de commit >72c (M1=74, I=77) → aceite, local-only.

**Sequência:** A3a → A3b → I (+I2) → M1 → M2. Merge `--no-ff` para `main`, **sem push**.
