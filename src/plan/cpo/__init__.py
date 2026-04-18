"""
ProdPlan ONE — CPO v4 (Cascading Pipeline Optimizer)
====================================================

DRCFFS-R scheduler for NELO: Dual-Resource Constrained Flexible Flow Shop
with Re-entrance. Hyper-heuristic approach — the GA manipulates decision
parameters, the greedy decoder guarantees feasibility (OTD, crew mutex,
shift bounds, mold constraints).

Safety net: never returns worse than baseline greedy.

See `C:/Users/User/.claude/plans/sim-analisa-tudo-muito-atomic-pearl.md`
Part 2, Sprint E for the design.
"""
