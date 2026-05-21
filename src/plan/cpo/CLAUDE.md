# src/plan/cpo

**Propósito: CPO solver — greedy + GA + MAP-Elites + FRRMAB + surrogate XGBoost. 7 axiomas Spelke encoded.**

## Invariantes locais (always-true neste módulo)

- 16 curing/secagem gaps vivem em `state.py:33` `NELO_CURING_GAPS_SEED` (química, não filas).
- `CoeficienteX` é **DINHEIRO €**, NUNCA tempo — zero ocorrências em `decoder/fitness/pair_assignment/state`.
- `routing_choices` é persistido em `ScheduleCommit` (auditoria de qual padrão saiu do greedy).
- `safety_net.py` é 9 guardrails — NUNCA `baseline_kpi - 5%` sem write-gate human approval.
- Tempos vêm SEMPRE de histórico real (`FaseOf_Inicio→Fim` limpo: zeros→P95→moda→fallback mediana ≠0).
- 7 axiomas Spelke: capacity ≥ 0, precedence monotónica, mold exclusivo, dual-resource Laminagem 88.5%, skill match, cura 16 transições, safety_net ≥ baseline.

## Quando entrar aqui, lê primeiro

- `engine.py` — orchestration greedy→GA→MAP-Elites→commit.
- `decoder.py` — chromosome → schedule (onde os axiomas são enforced).
- `fitness.py` — 5 componentes (makespan, OTD, FPY, energy, fairness).
- `state.py:33` — `NELO_CURING_GAPS_SEED` (16 transições químicas).
- `safety_net.py` — 9 guardrails antes de qualquer commit.

## Comandos

```powershell
.\.venv\Scripts\python.exe -m pytest tests/plan/ -q
.\.venv\Scripts\python.exe scripts/verify_invariants.py
```

## Anti-padrões deste módulo

- NÃO importar de `src.profit` (boundary import-linter contract 2, Q.66.A.1).
- NÃO usar `CoeficienteX` em `decoder/fitness/pair_assignment/state` (é €, pertence a `src/profit/`).
- NÃO baixar `generations` abaixo do default (regressão Q.59.invariant).
- NÃO mexer em property tests `tests/plan/test_preview_delta_property.py` sem adicionar property test novo (hypothesis, não example tests).
- NÃO usar coeficientes standard de tempo — divergem até 25× do histórico real.
- NÃO trocar MAP-Elites axes para `num_late_orders` (Q.59.invariant regression).

## Referências

- `agent_docs/spelke_axioms.md` — 7 invariants em detalhe.
- `agent_docs/q17_logic_as_data.md` — ACTION_WIRING.
- `.claude/skills/nelinho-invariants/SKILL.md` — 12 invariants automatizados.
