"""Q.153.A1 — o sentinel de infeasibilidade não pode poluir o plano.

Antes: `_earliest_start` devolvia `default + timedelta(days=365*10)` quando
uma fase flexível não tinha nenhum `allowed_predecessor` completo. Esse start
a +10 anos era agendado à mesma (soft-horizon), poluindo makespan/datas com
operações no futuro distante (e, combinado com outros caminhos, datas
end<start).

Agora devolve `None`: o loop deixa a op pending e retenta; se nunca ficar
pronta, o ramo de deadlock marca-a `infeasible` SEM a agendar.

Invariante (property): nenhuma operação agendada pode ter
`start`/`end` muito para lá do horizonte, e `end > start` sempre.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.decoder_resources import _earliest_start
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation

HORIZON_START = datetime(2026, 4, 20, 8, 0, 0)
HORIZON_END = HORIZON_START + timedelta(days=14)


def _state() -> FactoryState:
    return FactoryState(tenant_id=UUID("11111111-1111-1111-1111-111111111111"))


def _op(op_id, order_id, sequence, *, phase_id=None, duration_min=60, **kw):
    return SchedulingOperation(
        operation_id=op_id,
        order_id=order_id,
        product_id=kw.pop("product_id", "P1"),
        sequence=sequence,
        operation_code=kw.pop("operation_code", "OP"),
        duration_minutes=duration_min,
        machine_id=kw.pop("machine_id", None),
        phase_id=phase_id,
        **kw,
    )


def test_earliest_start_returns_none_when_flexible_pred_not_done():
    """Contrato Q.153.A1: sem allowed_predecessor completo → None
    (não um datetime a +10 anos)."""
    flex = _op("flex", "O1", 2, phase_id="CURA",
               is_flexible=True, allowed_predecessors=["LAMINAGEM"])
    sibling = _op("lam", "O1", 1, phase_id="LAMINAGEM")
    order_to_ops = {"O1": [sibling, flex]}

    # op_end_at vazio → o sibling LAMINAGEM ainda não completou.
    result = _earliest_start(flex, order_to_ops, {}, HORIZON_START)
    assert result is None

    # Quando o predecessor completa, devolve um datetime real (não None,
    # não +10 anos).
    pred_end = HORIZON_START + timedelta(hours=4)
    result2 = _earliest_start(flex, order_to_ops, {"lam": pred_end}, HORIZON_START)
    assert result2 is not None
    assert result2 < HORIZON_START + timedelta(days=365)


def test_unschedulable_flexible_op_is_infeasible_not_scheduled():
    """Uma fase flexível cujo allowed_predecessor nunca existe acaba em
    infeasible_op_ids e NÃO é agendada (sem data a +10 anos)."""
    # Order com uma op normal + uma flexível cujo predecessor alternativo
    # ('FASE_INEXISTENTE') nunca aparece nos siblings.
    normal = _op("a", "O1", 1, phase_id="LAMINAGEM")
    flex = _op("z", "O1", 2, phase_id="CURA",
               is_flexible=True, allowed_predecessors=["FASE_INEXISTENTE"])
    ops = [normal, flex]
    chromo = Chromosome(permutation=[0, 1])

    result = decode(chromo, ops, [SchedulingMachine(machine_id="M1", name="M1")],
                    _state(), HORIZON_START, HORIZON_END)

    scheduled_ids = {o["operation_id"] for o in result["operations"]}
    assert "z" in result["infeasible_op_ids"]
    assert "z" not in scheduled_ids


def test_no_scheduled_op_has_absurd_dates():
    """Property: toda a op agendada tem end > start e nenhuma data salta
    para lá do horizonte + margem (guarda contra o sentinel a +10 anos)."""
    ops = [
        _op("a", "O1", 1, phase_id="LAMINAGEM"),
        _op("b", "O1", 2, phase_id="CURA"),
        _op("c", "O2", 1, phase_id="LAMINAGEM"),
        _op("d", "O2", 2, phase_id="CURA",
            is_flexible=True, allowed_predecessors=["LAMINAGEM"]),
    ]
    chromo = Chromosome(permutation=[0, 1, 2, 3])
    result = decode(chromo, ops,
                    [SchedulingMachine(machine_id=f"M{i}", name=f"M{i}") for i in (1, 2)],
                    _state(), HORIZON_START, HORIZON_END)

    sane_ceiling = HORIZON_END + timedelta(days=60)
    for o in result["operations"]:
        start = datetime.fromisoformat(o["start_time"])
        end = datetime.fromisoformat(o["end_time"])
        assert end > start, f"op {o['operation_id']} tem end<=start"
        assert start < sane_ceiling, f"op {o['operation_id']} start absurdo {start}"
        assert end < sane_ceiling, f"op {o['operation_id']} end absurdo {end}"
