"""Q.169.D — gate COMPLETO do axioma 7 no CP-SAT + tardiness no objetivo.

A matriz de paridade (Q.169.A) confirmou: o gate antigo só comparava
makespan e o solve minimizava só makespan — um candidato CP-SAT podia
melhorar makespan, degradar tardiness/qualidade/idle, e substituir o
baseline com `safety_net_triggered=False` à força. E as due dates (79%
das ordens desde Q.168.A) não constrangiam o solver.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.plan.cpo.engine import _cpsat_gate_decision
from src.plan.cpo.state import FactoryState
from src.plan.engines import cpsat_scheduler as cs
from src.plan.engines.cpsat_scheduler import CPSATConfig, CPSATScheduler
from src.plan.engines.scheduling_adapter import SchedulingOperation

_H0 = datetime(2026, 6, 1, 0, 0, 0)


def _kpis(makespan=100.0, tardy_h=10.0, late=2, otd=0.8, **extra):
    base = {
        "makespan_hours": makespan,
        "total_tardiness_hours": tardy_h,
        "num_late_orders": late,
        "otd_delivery": otd,
    }
    base.update(extra)
    return base


class TestCpsatGateDecision:
    def test_better_makespan_no_violations_accepts(self):
        ok, meta = _cpsat_gate_decision(
            _kpis(makespan=80.0), _kpis(makespan=100.0),
        )
        assert ok and meta["reason"] == "ok"

    def test_more_late_orders_rejects_even_with_better_makespan(self):
        """O buraco que o gate antigo deixava: makespan melhor MAS mais
        ordens atrasadas → o baseline tem de vencer (guardrail hard)."""
        ok, meta = _cpsat_gate_decision(
            _kpis(makespan=80.0, late=5), _kpis(makespan=100.0, late=2),
        )
        assert not ok
        assert "num_late_orders" in " ".join(meta["violations"])

    def test_no_strict_improvement_rejects(self):
        ok, meta = _cpsat_gate_decision(
            _kpis(makespan=100.0, tardy_h=10.0),
            _kpis(makespan=100.0, tardy_h=10.0),
        )
        assert not ok
        assert "sem melhoria estrita" in meta["reason"]

    def test_better_tardiness_with_equal_makespan_accepts(self):
        """Com o objetivo tardiness+makespan, um candidato pode trocar
        makespan igual por menos atraso — conta como melhoria."""
        ok, _ = _cpsat_gate_decision(
            _kpis(makespan=100.0, tardy_h=4.0, late=1, otd=0.9),
            _kpis(makespan=100.0, tardy_h=10.0, late=2, otd=0.8),
        )
        assert ok

    def test_quality_risk_regression_rejects(self):
        """Dimensão soft do safety_net (quality_risk +10% tolerado) também
        conta no gate — o CP-SAT não pode degradar qualidade às escondidas."""
        ok, meta = _cpsat_gate_decision(
            _kpis(makespan=80.0, avg_quality_risk=0.50),
            _kpis(makespan=100.0, avg_quality_risk=0.30),
        )
        assert not ok
        assert any("quality" in v for v in meta["violations"])


def _op(oid, order, fase, seq, dur, due=None):
    return SchedulingOperation(
        operation_id=oid, order_id=order, product_id="P", sequence=seq,
        operation_code=fase, duration_minutes=dur, machine_id=None,
        phase_id=fase, team_size=1, due_date=due,
    )


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_tardiness_objective_prioritizes_due_order():
    """1 estação, 1 operador: 2 ordens concorrem; a B tem due date apertada
    — o objetivo tardiness+makespan agenda B PRIMEIRO. (Com makespan-only,
    a ordem entre elas era indiferente para o solver.)"""
    state = FactoryState(tenant_id=uuid4())
    state.phase_stations = {"A": 1}
    state.skill_matrix = {"A": {"w1"}}

    ops = [
        _op("OA", "OF-A", "A", 1, 240),                                   # sem due
        _op("OB", "OF-B", "A", 1, 240, due=_H0 + timedelta(hours=4)),     # due = 4h
    ]
    res = CPSATScheduler(CPSATConfig(budget_s=10, deterministic=True)).solve_timing(
        ops, state, _H0,
    )
    assert res.available and res.status in ("OPTIMAL", "FEASIBLE")
    assert res.ends_min["OB"] <= 240, (
        f"OF-B (due 4h) tinha de ir primeiro — acabou em {res.ends_min['OB']}min"
    )
    assert res.starts_min["OA"] >= 240


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_no_due_dates_keeps_pure_makespan_objective():
    """Sem due dates o objetivo é o makespan puro — back-compat exacto."""
    state = FactoryState(tenant_id=uuid4())
    state.phase_stations = {"A": 2}
    state.skill_matrix = {"A": {"w1", "w2"}}
    ops = [_op(f"O{i}", f"OF-{i}", "A", 1, 120) for i in range(2)]
    res = CPSATScheduler(CPSATConfig(budget_s=10, deterministic=True)).solve_timing(
        ops, state, _H0,
    )
    assert res.available
    assert max(res.ends_min.values()) == 120  # paralelo, makespan mínimo


class TestPhase8AnchorsAlive:
    def test_tardiness_transport_d_reads_end_time(self):
        """Q.169.D — a phase 8 lia op['end'] mas as ops serializadas têm
        'end_time': o KPI tardiness_transport_d ficou 0 desde sempre.
        Com o campo certo, um fim 2 dias depois da âncora dá 2.0d."""
        from src.plan.cpo.greedy_pipeline import GreedyPipeline

        pipeline = GreedyPipeline(FactoryState(tenant_id=uuid4()))
        schedule = {
            "makespan_hours": 48.0,
            "operations": [{
                "order_id": "OF-1",
                "duration_minutes": 60.0,
                "end_time": (_H0 + timedelta(days=3)).isoformat(),
            }],
        }
        anchors = {"OF-1": _H0 + timedelta(days=1)}
        out = pipeline._phase8_scoring(schedule, anchors)
        assert out["tardiness_transport_d"] == pytest.approx(2.0, abs=0.01)


# ─────────────────────────────────────────────────────────────────────────────
# Q.173.P — isenção de guardrails SOFT por ganho de makespan (decisão Luis)
# ─────────────────────────────────────────────────────────────────────────────


class TestQ173PSoftWaiver:
    def test_idle_ratio_soft_isentado_com_ganho_grande(self):
        """O cenário REAL da auditoria 2026-06-11: makespan 22.297h→~690h
        (−97%) vetado por idle_ratio +5,25pp. Com soft_waiver_gain=0.5 o
        guardrail soft é isentado e o plano 6,5× melhor passa."""
        ok, meta = _cpsat_gate_decision(
            _kpis(makespan=690.0, idle_ratio=0.6805),
            _kpis(makespan=22297.0, idle_ratio=0.6280),
            soft_waiver_gain=0.5,
        )
        assert ok
        assert meta["violations"] == []
        assert any("idle_ratio" in w for w in meta["waived_soft"])
        assert meta["makespan_gain"] > 0.9
        assert "isentado" in meta["reason"]

    def test_waiver_desligado_mantem_veto_soft(self):
        """soft_waiver_gain=0 (desligado) → comportamento Q.169.D intacto."""
        ok, meta = _cpsat_gate_decision(
            _kpis(makespan=690.0, idle_ratio=0.6805),
            _kpis(makespan=22297.0, idle_ratio=0.6280),
            soft_waiver_gain=0.0,
        )
        assert not ok
        assert any("idle_ratio" in v for v in meta["violations"])

    def test_ganho_pequeno_nao_isenta(self):
        """Melhoria de makespan abaixo do limiar não compra isenção."""
        ok, meta = _cpsat_gate_decision(
            _kpis(makespan=90.0, idle_ratio=0.70),
            _kpis(makespan=100.0, idle_ratio=0.60),
            soft_waiver_gain=0.5,
        )
        assert not ok
        assert any("idle_ratio" in v for v in meta["violations"])
        assert meta["waived_soft"] == []

    def test_hard_guardrail_nunca_e_isentado(self):
        """Tardiness pior é HARD — nem um makespan −97% compra a isenção
        (axioma 7: nunca pior que o baseline nas dimensões hard)."""
        ok, meta = _cpsat_gate_decision(
            _kpis(makespan=690.0, tardy_h=50.0),
            _kpis(makespan=22297.0, tardy_h=10.0),
            soft_waiver_gain=0.5,
        )
        assert not ok
        assert any("total_tardiness_hours" in v for v in meta["violations"])

    def test_meta_regista_waiver_para_auditoria(self):
        ok, meta = _cpsat_gate_decision(
            _kpis(makespan=100.0, setups=200),
            _kpis(makespan=400.0, setups=100),
            soft_waiver_gain=0.5,
        )
        assert ok
        assert meta["soft_waiver_gain"] == 0.5
        assert any("setups" in w for w in meta["waived_soft"])
