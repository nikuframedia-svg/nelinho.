"""Q.153.A2 — KPIs separam dívida herdada de atraso novo.

`_compute_tardiness` mede a pontualidade do plano contra
`effective_due = max(due, horizon_start)`:
  - `num_already_overdue`: ordens que já chegam vencidas (due < horizon_start).
  - `num_newly_late` / `tardiness_beyond_today_h`: atraso EVITÁVEL — o que o
    GA deve minimizar — medido para lá de hoje.
O `due_date` real nunca é mutado (legacy `late_orders`/`tardy_hours` ficam).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from src.plan.cpo.decoder_helpers import ScheduledOp
from src.plan.cpo.decoder_kpis import _compute_tardiness
from src.plan.engines.scheduling_adapter import SchedulingOperation

HORIZON_START = datetime(2026, 6, 1, 8, 0, 0)


def _op(op_id, order_id, due):
    return SchedulingOperation(
        operation_id=op_id, order_id=order_id, product_id="P1",
        sequence=1, operation_code="OP", duration_minutes=60,
        machine_id=None, due_date=due,
    )


def _sched(op_id, order_id, end):
    return ScheduledOp(
        operation_id=op_id, order_id=order_id, phase_id="P",
        machine_id="M1", workers=[], mold_id=None,
        start=end - timedelta(hours=1), end=end, duration_minutes=60,
    )


def test_inherited_overdue_excludes_historical_debt():
    """Ordem vencida há 10 dias mas acabada 2h após hoje: a dívida
    histórica (10 dias) NÃO entra; só conta o tempo-para-limpar (2h). Não
    é 'newly late' (já estava vencida à entrada)."""
    due = HORIZON_START - timedelta(days=10)
    ops = [_op("a", "O1", due)]
    scheduled = [_sched("a", "O1", HORIZON_START + timedelta(hours=2))]

    r = _compute_tardiness(scheduled, ops, HORIZON_START)

    assert r["num_already_overdue"] == 1          # herdado
    assert r["num_newly_late"] == 0               # não foi o plano que atrasou
    # Magnitude evitável = 2h (tempo-para-limpar), NÃO os 10 dias herdados.
    assert abs(r["tardiness_beyond_today_h"] - 2.0) < 1e-6
    # Legacy conta vs due real (≈10 dias) — fica para safety_net/OTD.
    assert r["late_orders"] == 1
    assert r["tardy_hours"] > 24 * 9             # ~10 dias, ainda saturável


def test_overdue_clear_time_is_de_saturated():
    """A magnitude evitável de uma ordem vencida = (end - hoje), muito
    menor que (end - due real). É isto que de-satura a fitness."""
    due = HORIZON_START - timedelta(days=200)    # dívida enorme
    ops = [_op("a", "O1", due)]
    scheduled = [_sched("a", "O1", HORIZON_START + timedelta(hours=24))]

    r = _compute_tardiness(scheduled, ops, HORIZON_START)

    assert abs(r["tardiness_beyond_today_h"] - 24.0) < 1e-6   # só 24h
    assert r["tardy_hours"] > 24 * 200                        # ~200 dias (cru)


def test_plan_caused_lateness_on_future_due_is_newly_late():
    """Ordem com due no futuro que o plano atrasa = atraso NOVO (o plano
    estragou uma ordem que tinha folga)."""
    due = HORIZON_START + timedelta(days=10)
    ops = [_op("a", "O1", due)]
    scheduled = [_sched("a", "O1", due + timedelta(hours=24))]

    r = _compute_tardiness(scheduled, ops, HORIZON_START)

    assert r["num_already_overdue"] == 0
    assert r["num_newly_late"] == 1
    assert abs(r["tardiness_beyond_today_h"] - 24.0) < 1e-6


def test_on_time_against_effective_due_is_clean():
    """Plano que acaba antes de effective_due não tem atraso nenhum."""
    due = HORIZON_START + timedelta(days=10)
    ops = [_op("a", "O1", due)]
    scheduled = [_sched("a", "O1", due - timedelta(hours=2))]

    r = _compute_tardiness(scheduled, ops, HORIZON_START)

    assert r["num_newly_late"] == 0
    assert r["tardiness_beyond_today_h"] == 0.0
    assert r["late_orders"] == 0
