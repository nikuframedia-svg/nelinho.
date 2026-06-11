"""Q.166.F — integração CP-SAT global: contrato, exclusão de reparações, fallback.

run_cpsat_global emite o MESMO dict do decoder; exclui fases de reparação (fluxo
separado); sem ortools → None (fallback). engine.schedule com use_cpsat_global=True
não crasha e devolve um contrato válido; com False mantém a GA (back-compat).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.plan.cpo.engine import CPOv4Engine, CPOConfig
from src.plan.cpo.state import FactoryState
from src.plan.engines import cpsat_scheduler as cs
from src.plan.engines import cpsat_global as cg
from src.plan.engines.cpsat_global import run_cpsat_global
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation

_H0 = datetime(2026, 6, 1, 0, 0, 0)
_HE = _H0 + timedelta(days=150)

# chaves mínimas do contrato que commits/safety_net/API esperam
_CONTRACT_KEYS = {
    "success", "engine_used", "operations", "makespan_hours",
    "total_tardiness_hours", "num_late_orders", "otd_delivery", "setups",
    "total_idle_hours", "idle_ratio", "num_machines", "lam_utilization",
    "throughput_eur_day", "avg_utilization", "warnings", "infeasible_op_ids",
}


def _state():
    s = FactoryState(tenant_id=uuid4())
    s.phase_stations = {"A": 2, "B": 2}
    s.skill_matrix = {"A": {"w1", "w2"}, "B": {"w3", "w4"}}
    return s


def _ops(n=4, with_repair=False):
    ops = []
    for i in range(n):
        ops.append(SchedulingOperation(
            operation_id=f"O{i}A", order_id=f"OF{i}", product_id="P", sequence=1,
            operation_code="A", duration_minutes=120, machine_id=None, phase_id="A",
            team_size=1))
        ops.append(SchedulingOperation(
            operation_id=f"O{i}B", order_id=f"OF{i}", product_id="P", sequence=2,
            operation_code="B", duration_minutes=60, machine_id=None, phase_id="B",
            team_size=1))
        if with_repair:
            ops.append(SchedulingOperation(
                operation_id=f"O{i}R", order_id=f"OF{i}", product_id="P", sequence=3,
                operation_code="Rep", duration_minutes=300, machine_id=None,
                phase_id="76", team_size=1))  # 76 = Reparação Verniz
    return ops


def _machines():
    return [SchedulingMachine(machine_id=f"M{i}", name=f"M{i}") for i in range(8)]


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_run_cpsat_global_contract_and_merges_repairs_q173q():
    """Q.173.Q (decisão Luis 2026-06-11): as reparações entram no MESMO
    plano via merge-back no assign_concrete — antes desapareciam quando o
    CP-SAT ganhava (76 OFs invisíveis, auditoria 2026-06-11)."""
    state = _state()
    state.skill_matrix["Rep"] = {"w5"}
    ops = _ops(4, with_repair=True)
    res = run_cpsat_global(
        state, ops, _machines(), _H0, _HE,
        config=cs.CPSATConfig(budget_s=10, deterministic=True),
    )
    assert res is not None
    assert _CONTRACT_KEYS.issubset(res.keys())
    assert res["engine_used"] == "cpsat_global"
    # reparações (fase 76) INCLUÍDAS no plano servido
    phases = {op["phase_id"] for op in res["operations"]}
    assert "76" in phases
    assert res["cpo_meta"]["repair_ops_merged"] == 4
    assert len(res["operations"]) == len(ops)
    assert res["makespan_hours"] > 0
    # axioma: nenhum operador em 2 sítios ao mesmo tempo (merge respeitou
    # a ocupação — assign_concrete trata reparações como ops normais)
    busy: dict = {}
    for op in res["operations"]:
        for w in op.get("workers") or []:
            for s, e in busy.get(w, []):
                assert not (op["start_time"] < e and s < op["end_time"]), (
                    f"operador {w} sobreposto"
                )
            busy.setdefault(w, []).append((op["start_time"], op["end_time"]))
    # Q.173.Q.1 — "um barco não está em 2 fases": NENHUMA sobreposição
    # intra-ordem (o gap apanhado pela validação live de 2026-06-11: a
    # reparação com piso 0 atropelava irmãs de sequência inferior — o
    # validador estrutural recusava o commit com 13 violações).
    by_order: dict = {}
    for op in res["operations"]:
        by_order.setdefault(op["order_id"], []).append(op)
    for order_id, order_ops in by_order.items():
        for i, a in enumerate(order_ops):
            for b in order_ops[i + 1:]:
                assert not (
                    a["start_time"] < b["end_time"]
                    and b["start_time"] < a["end_time"]
                ), (
                    f"ordem {order_id}: fases {a['phase_id']} e "
                    f"{b['phase_id']} sobrepostas no tempo"
                )


def test_run_cpsat_global_no_ortools_returns_none(monkeypatch):
    monkeypatch.setattr(cg, "HAS_ORTOOLS", False)
    res = run_cpsat_global(_state(), _ops(2), _machines(), _H0, _HE)
    assert res is None


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_engine_cpsat_global_on_returns_valid_contract():
    state = _state()
    cfg = CPOConfig(
        use_cpsat_global=True, cpsat_budget_s=10, cpsat_deterministic=True,
        generations=2, time_limit_sec=2, population_size=10,
    )
    eng = CPOv4Engine(state, config=cfg)
    res = eng.schedule(_ops(4), _machines(), _H0, _HE)
    assert _CONTRACT_KEYS.issubset(res.keys())
    # cpsat ou greedy (axioma 7) — ambos contratos válidos; engine_used coerente
    assert res["engine_used"] in ("cpsat_global", "cpo_v4")
    assert res["makespan_hours"] >= 0


def test_engine_cpsat_global_off_keeps_ga():
    # back-compat: flag OFF → caminho GA normal (engine_used cpo_v4).
    state = _state()
    cfg = CPOConfig(use_cpsat_global=False, generations=2, time_limit_sec=1, population_size=8)
    eng = CPOv4Engine(state, config=cfg)
    res = eng.schedule(_ops(3), _machines(), _H0, _HE)
    assert res["engine_used"] == "cpo_v4"


def test_engine_persiste_cpsat_gate_em_rejeicao_q173p(monkeypatch):
    """Q.173.P — quando o CP-SAT é rejeitado/indisponível, o veredicto do
    gate viaja no cpo_meta do plano final (greedy/GA) — auditável pela BD.
    Antes morria com o result descartado (só visível em logs truncáveis)."""
    import src.plan.engines.cpsat_global as cg_mod

    monkeypatch.setattr(cg_mod, "run_cpsat_global", lambda *a, **kw: None)

    state = _state()
    cfg = CPOConfig(
        use_cpsat_global=True, generations=1, time_limit_sec=1,
        population_size=6,
    )
    eng = CPOv4Engine(state, config=cfg)
    res = eng.schedule(_ops(2), _machines(), _H0, _HE)

    meta = res["cpo_meta"]
    assert meta["engine"] == "greedy_ga"
    assert meta["cpsat_gate"]["accepted"] is False
    assert "indisponível" in meta["cpsat_gate"]["reason"]


def test_engine_sem_cpsat_nao_inventa_gate(monkeypatch):
    """Flag OFF → sem cpsat_gate no meta (não inventar veredictos)."""
    state = _state()
    cfg = CPOConfig(
        use_cpsat_global=False, generations=1, time_limit_sec=1,
        population_size=6,
    )
    res = CPOv4Engine(state, config=cfg).schedule(_ops(2), _machines(), _H0, _HE)
    assert res["cpo_meta"]["engine"] == "greedy_ga"
    assert "cpsat_gate" not in res["cpo_meta"]
