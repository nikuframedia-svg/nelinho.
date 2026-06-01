"""Q.153.D2 — uma edição manual em /producao (apply-move / `preview_apply`)
SOBREVIVE ao replan do robô.

Antes do D2, `PreviewDeltaService.apply()` gravava o delta com `kind="preview_apply"`
e SEM `to_phase`/`to_ts`, por isso `active_manual_overrides` (que filtra
`tipo=="manual_drag"`) NUNCA o apanhava → o ajuste desaparecia em silêncio no
próximo replan. O D2 grava o delta no MESMO formato que o `manual_drag` do
/overall, mantendo a UX boat-level.

Cobre:
1. `apply()` (caminho boat / `order_id`) grava `tipo="manual_drag"` + `to_phase`
   + `to_ts` + `operation_id` resolvido (mantendo `kind="preview_apply"` como
   origem).
2. O delta resultante é consumível por `_reduce_overrides` (a base do
   `active_manual_overrides`) — falhava antes do D2.
3. Sobrevivência REAL: `reapply_manual_overrides` re-aplica esse override e a op
   final fica na fase nova (com revalidação dos axiomas Spelke).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from src.plan.cpo.commits import _reduce_overrides
from src.plan.services import manual_reorder as mr
from src.plan.services.manual_reorder import reapply_manual_overrides
from src.plan.services.preview_delta_service import PreviewDeltaService, PreviewMutation

TENANT = UUID("00000000-0000-0000-0000-000000000001")
_BASE_TS = datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc)


def _boat_op(phase: str = "LAMINAGEM") -> Dict[str, Any]:
    return {
        "operation_id": "4272::5",
        "order_id": "4272",
        "phase_id": phase,
        "start_time": _BASE_TS.isoformat(),
        "end_time": (_BASE_TS + timedelta(hours=4)).isoformat(),
        "workers": ["w-1"],
        "operator_id": "w-1",
    }


class _FakeCommit:
    def __init__(self, operations: List[Dict[str, Any]]) -> None:
        self.id = uuid4()
        self.tenant_id = TENANT
        self.commit_sha256 = "a" * 64
        self.operations = operations
        self.kpis = {"throughput_eur_day": 1000}
        self.alternatives = []
        self.rejected_alternatives = []
        self.user_preference_signal = {}
        self.cpo_meta = {}
        self.trust_index = 0.0
        self.status = "DRAFT"
        self.created_at = _BASE_TS


class _ApplySession:
    """Mínima p/ apply(): captura o commit adicionado; commit/flush no-op."""

    def __init__(self) -> None:
        self.added: List[Any] = []
        self.committed = 0

    async def execute(self, stmt):  # pragma: no cover — _load_order é monkeypatched
        class _R:
            def scalar_one_or_none(_self):
                return None
        return _R()

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for o in self.added:
            if getattr(o, "created_at", None) is None:
                object.__setattr__(o, "created_at", _BASE_TS)

    async def commit(self) -> None:
        self.committed += 1


@pytest.mark.asyncio
async def test_apply_writes_manual_drag_compatible_delta(monkeypatch):
    """apply() (boat-move) grava `tipo=manual_drag` + to_phase/to_ts/operation_id,
    mantendo `kind=preview_apply` como origem."""
    parent = _FakeCommit([_boat_op("LAMINAGEM")])

    async def fake_get_latest(self):
        return parent

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_latest", fake_get_latest,
    )
    # boat-move sem ProductionOrder na BD → cai na 1ª op da ordem (order_ops[0]).
    monkeypatch.setattr(PreviewDeltaService, "_load_order", AsyncMock(return_value=None))

    session = _ApplySession()
    with patch("src.plan.services.preview_delta_service.audit_change", new=AsyncMock()):
        svc = PreviewDeltaService(session, TENANT)
        commit = await svc.apply(
            PreviewMutation(order_id="4272", new_phase_id="MONTAGEM"),
            author="op-user",
            reason="antecipar p/ libertar molde K1 7ML",
        )

    d = commit.delta
    assert d["tipo"] == "manual_drag"        # filtro do reapply apanha-o
    assert d["kind"] == "preview_apply"      # origem preservada (telemetria)
    assert d["operation_id"] == "4272::5"    # resolvido do order_id
    assert d["to_phase"] == "MONTAGEM"
    assert d["to_ts"] == _BASE_TS.isoformat()  # herdou o start_time do plano
    assert session.committed == 1


@pytest.mark.asyncio
async def test_apply_delta_is_consumable_by_reduce_overrides(monkeypatch):
    """O delta do apply() (D2) é apanhado por `_reduce_overrides` — a base do
    `active_manual_overrides`. Falhava antes do D2 (sem `to_phase`/`to_ts`)."""
    parent = _FakeCommit([_boat_op("LAMINAGEM")])

    async def fake_get_latest(self):
        return parent

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.get_latest", fake_get_latest,
    )
    monkeypatch.setattr(PreviewDeltaService, "_load_order", AsyncMock(return_value=None))

    session = _ApplySession()
    with patch("src.plan.services.preview_delta_service.audit_change", new=AsyncMock()):
        svc = PreviewDeltaService(session, TENANT)
        commit = await svc.apply(
            PreviewMutation(order_id="4272", new_phase_id="MONTAGEM"),
            author="op-user",
            reason="motivo de auditoria do apply-move",
        )

    overrides = _reduce_overrides([commit])
    assert len(overrides) == 1
    ov = overrides[0]
    assert ov["operation_id"] == "4272::5"
    assert ov["to_phase"] == "MONTAGEM"
    assert ov["to_ts"] == _BASE_TS.isoformat()


# ── Sobrevivência REAL ao replan (reusa o harness do Q.142) ──────────────────

class _RealishSession:
    """get_latest() devolve o último commit adicionado (ou o parent)."""

    def __init__(self, parent: _FakeCommit) -> None:
        self._parent = parent
        self.added: List[Any] = []
        self.committed = 0
        self.rolledback = 0

    async def execute(self, stmt):
        latest = self.added[-1] if self.added else self._parent

        class _R:
            def scalar_one_or_none(_self):
                return latest

            def scalars(_self):
                class _S:
                    def all(_s):
                        return [latest] if latest else []
                return _S()

            def first(_self):
                return None
        return _R()

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for o in self.added:
            if getattr(o, "created_at", None) is None:
                object.__setattr__(o, "created_at", _BASE_TS)

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolledback += 1


@pytest.mark.asyncio
async def test_preview_apply_survives_replan(monkeypatch):
    """O override (no formato D2) é re-aplicado pelo robô: a op final fica na
    fase nova. Sem o D2 o filtro nunca o apanhava → nada re-aplicado."""
    # Override no formato gravado por apply() (D2) — mover 4272::5 p/ MONTAGEM.
    override = {
        "operation_id": "4272::5",
        "to_phase": "MONTAGEM",
        "to_ts": _BASE_TS.isoformat(),
        "new_operator_id": None,
    }

    async def active(self):
        return [override]

    monkeypatch.setattr(
        "src.plan.cpo.commits.CommitsService.active_manual_overrides", active,
    )

    # plano fresco do robô: a op está em LAMINAGEM (o robô re-gerou).
    fresh = _FakeCommit([_boat_op("LAMINAGEM")])
    with patch.object(mr, "publish_event", new=AsyncMock()), \
            patch.object(mr, "audit_change", new=AsyncMock()):
        session = _RealishSession(fresh)
        stats = await reapply_manual_overrides(session, TENANT)

    assert stats["reapplied"] == 1 and stats["rejected"] == 0
    assert len(session.added) == 1
    op = next(o for o in session.added[0].operations if o["operation_id"] == "4272::5")
    assert op["phase_id"] == "MONTAGEM"  # a edição manual sobreviveu ao replan
