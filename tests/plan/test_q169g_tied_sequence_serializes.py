"""Q.169.G — sequências EMPATADAS serializam (um barco não está em 2 fases).

2ª descoberta da prova live F2.F: depois de a cura ficar viva (Q.169.F),
o validate_schedule recusou o plano seguinte com "fases 1 e 67 sobrepostas
no tempo" (Laminagem E Infusão ao mesmo tempo no mesmo barco) e "77 e 76"
(2 reparações simultâneas). Causa: a rota real dá a fases alternativas a
MESMA sequência (e às reparações sequence=0) — o decoder tratava empates
como paralelos (`prev.sequence < op.sequence` ignora ties) e o postpass
do CP-SAT podia re-sobrepô-los ao empurrar por recursos.

Política: empate serializa por operation_id (determinístico), SEM gaps de
cura (é o mesmo barco a mudar de mãos, não uma transição química).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.plan.cpo.decoder_resources import _earliest_start, _precedences_met
from src.plan.cpo.state import FactoryState
from src.plan.engines import cpsat_scheduler as cs
from src.plan.engines.cpsat_scheduler import CPSATConfig, CPSATScheduler
from src.plan.engines.scheduling_adapter import SchedulingOperation

_T0 = datetime(2026, 6, 1, 8, 0, 0)


def _op(oid, order, fase, seq, dur=60.0):
    return SchedulingOperation(
        operation_id=oid, order_id=order, product_id="P", sequence=seq,
        operation_code=fase, duration_minutes=dur, machine_id=None,
        phase_id=fase, team_size=1,
    )


class TestDecoderTiedSequence:
    def test_precedences_tie_blocks_until_first_done(self):
        a = _op("OF1::1", "OF1", "1", 5)
        b = _op("OF1::67", "OF1", "67", 5)  # MESMA sequência (rota real)
        order_to_ops = {"OF1": [a, b]}

        # b (id maior) só fica pronto quando a terminar
        assert _precedences_met(a, order_to_ops, {}) is True
        assert _precedences_met(b, order_to_ops, {}) is False
        assert _precedences_met(
            b, order_to_ops, {"OF1::1": _T0 + timedelta(hours=2)},
        ) is True

    def test_earliest_start_tie_floors_at_sibling_end(self):
        a = _op("OF1::1", "OF1", "1", 5)
        b = _op("OF1::67", "OF1", "67", 5)
        order_to_ops = {"OF1": [a, b]}
        end_a = _T0 + timedelta(hours=4)

        earliest = _earliest_start(
            b, order_to_ops, {"OF1::1": end_a}, _T0,
            state=FactoryState(tenant_id=uuid4()),
        )
        assert earliest is not None and earliest >= end_a

    def test_repairs_sequence_zero_serialize(self):
        """Reparações (76/77) entram com sequence=0 — empate típico."""
        r1 = _op("OF2::76", "OF2", "76", 0)
        r2 = _op("OF2::77", "OF2", "77", 0)
        order_to_ops = {"OF2": [r1, r2]}
        assert _precedences_met(r2, order_to_ops, {}) is False
        assert _precedences_met(r1, order_to_ops, {}) is True

    def test_different_sequences_unchanged(self):
        a = _op("OF3::1", "OF3", "1", 1)
        b = _op("OF3::2", "OF3", "2", 2)
        order_to_ops = {"OF3": [a, b]}
        assert _precedences_met(b, order_to_ops, {}) is False
        assert _precedences_met(
            b, order_to_ops, {"OF3::1": _T0},
        ) is True


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_cpsat_tied_sequence_never_overlaps():
    """No CP-SAT, 2 ops do mesmo barco com sequência empatada têm de sair
    serializadas mesmo com estações/operadores de sobra."""
    state = FactoryState(tenant_id=uuid4())
    state.phase_stations = {"1": 2, "67": 2}
    state.skill_matrix = {"1": {"w1", "w2"}, "67": {"w1", "w2"}}

    ops = [
        _op("OF1::1", "OF1", "1", 5, dur=120),
        _op("OF1::67", "OF1", "67", 5, dur=120),
    ]
    res = CPSATScheduler(CPSATConfig(budget_s=10, deterministic=True)).solve_timing(
        ops, state, _T0,
    )
    assert res.available and res.status in ("OPTIMAL", "FEASIBLE")
    s1, e1 = res.starts_min["OF1::1"], res.ends_min["OF1::1"]
    s2, e2 = res.starts_min["OF1::67"], res.ends_min["OF1::67"]
    assert s2 >= e1 or s1 >= e2, "empate de sequência tem de serializar"
