"""Q.171.D — caminho manual passa pelo validador universal (delta-aware).

O `apply_manual_reorder` construía o ScheduleCommit DIRETO (sem
`create_from_schedule`), por isso fugia ao `validate_schedule` (Q.169.B) —
e o check de cura local nunca dispara em ops live (`curing_end_ts=None`
em todas as 8079 ops do commit real). Um drag podia pôr o MESMO barco em
2 fases sobrepostas ou violar a química de cura sem ninguém recusar.

Gate novo (monótono): um drag não pode INTRODUZIR violações estruturais;
violações pré-existentes do plano-pai não bloqueiam moves alheios.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.plan.services.manual_reorder import (
    SafetyNetViolation,
    apply_manual_reorder,
)
from tests.conftest import TEST_TENANT_ID

_BASE_TS = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)


def _op(
    op_id: str,
    order_id: str,
    phase_id: str,
    start_offset_h: float,
    duration_h: float = 2.0,
    worker: Optional[str] = None,
) -> Dict[str, Any]:
    start = _BASE_TS + timedelta(hours=start_offset_h)
    return {
        "operation_id": op_id,
        "order_id": order_id,
        "phase_id": phase_id,
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(hours=duration_h)).isoformat(),
        "workers": [worker] if worker else [],
    }


class _FakeCommit:
    def __init__(self, operations: List[Dict[str, Any]]) -> None:
        self.id = uuid4()
        self.commit_sha256 = "a" * 64
        self.operations = operations
        self.kpis: Dict[str, Any] = {}
        self.delta = {}
        self.alternatives = []
        self.rejected_alternatives = []
        self.cpo_meta = {}
        self.trust_index = 0.0
        self.status = "DRAFT"
        self.created_at = _BASE_TS


class _FakeSession:
    def __init__(self, parent: _FakeCommit) -> None:
        self._parent = parent
        self.added: List[Any] = []

    async def execute(self, stmt):
        parent = self._parent

        class _R:
            def scalar_one_or_none(self):
                return parent

            def scalars(self):
                class _S:
                    def all(self):
                        return [parent] if parent else []

                return _S()

        return _R()

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.commit_calls = getattr(self, "commit_calls", 0) + 1


def _patches(gate_state):
    return (
        patch(
            "src.plan.services.manual_reorder.publish_event",
            new_callable=AsyncMock,
        ),
        patch(
            "src.plan.services.manual_reorder.audit_change",
            new_callable=AsyncMock,
        ),
        patch(
            "src.plan.services.manual_reorder._load_validation_state",
            new_callable=AsyncMock,
            return_value=gate_state,
        ),
    )


async def _apply(session, op_id: str, new_start, gate_state=None, phase="31"):
    k, a, s = _patches(gate_state)
    with k, a, s:
        return await apply_manual_reorder(
            session=session,
            tenant_id=TEST_TENANT_ID,
            operation_id=op_id,
            new_phase=phase,
            new_start_ts=new_start,
            new_operator_id=None,
        )


async def test_drag_que_sobrepoe_fases_do_mesmo_barco_e_recusado():
    """ANTES: mover a fase 31 do barco B1 para cima da fase 30 passava
    todos os checks (precedence só olha a depends_on; cura precisa de
    curing_end_ts). AGORA o validador universal recusa."""
    ops = [
        _op("B1::30", "B1", "30", start_offset_h=0),
        _op("B1::31", "B1", "31", start_offset_h=6),
    ]
    session = _FakeSession(_FakeCommit(ops))

    with pytest.raises(SafetyNetViolation) as exc:
        await _apply(session, "B1::31", _BASE_TS + timedelta(hours=1))

    assert exc.value.axiom_name == "validador_universal"
    assert "sobrepostas" in exc.value.reason_pt
    assert session.added == [], "nada pode persistir num move inválido"


async def test_violacoes_pre_existentes_nao_bloqueiam_moves_alheios():
    """Delta-aware: o plano-pai JÁ tem as fases do barco B9 sobrepostas
    (lixo herdado). Mover uma op do barco B1 para um slot livre não pode
    ser bloqueado pelo lixo alheio — só violações NOVAS recusam."""
    ops = [
        _op("B9::30", "B9", "30", start_offset_h=0),
        _op("B9::31", "B9", "31", start_offset_h=1),  # sobrepõe B9::30
        _op("B1::30", "B1", "30", start_offset_h=0),
    ]
    session = _FakeSession(_FakeCommit(ops))

    result = await _apply(
        session, "B1::30", _BASE_TS + timedelta(hours=30), phase="30",
    )

    assert result["commit_sha"]
    assert len(session.added) == 1


async def test_cura_quimica_exata_no_caminho_manual():
    """Química EXATA por transição (não o piso global): com o estado de
    validação a declarar 16h entre as fases 30→31, mover a 31 para 2h
    depois do fim da 30 é recusado — mesmo SEM curing_end_ts nas ops."""
    gate_state = SimpleNamespace(
        phase_transition_gaps={("30", "31"): 16.0},
        phase_catalog=[],
    )
    ops = [
        _op("B1::30", "B1", "30", start_offset_h=0),       # termina às 10h
        _op("B1::31", "B1", "31", start_offset_h=30),      # folga de sobra
    ]
    session = _FakeSession(_FakeCommit(ops))

    with pytest.raises(SafetyNetViolation) as exc:
        await _apply(
            session, "B1::31", _BASE_TS + timedelta(hours=4),  # gap 2h < 16h
            gate_state=gate_state,
        )

    assert exc.value.axiom_name == "validador_universal"
    assert "cura química" in exc.value.reason_pt

    # O mesmo move com folga >= 16h passa.
    result = await _apply(
        session, "B1::31", _BASE_TS + timedelta(hours=27), gate_state=gate_state,
    )
    assert result["commit_sha"]
