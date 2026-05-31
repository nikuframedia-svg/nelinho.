"""Q.115.T — testes para o mirror worker_assignment (WorkerAssignment → hr.worker_phase_assignment).

Seguem o padrao dos outros testes ETL (RecordingSession + monkeypatch de services).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID

from src.adapters.nelo.etl import worker_assignment as wa_mod
from src.adapters.nelo.etl.worker_assignment import (
    _derive_assignment_type,
    _map_row,
    _safe_str,
    _worker_uuid,
    sync_worker_assignments,
)
from src.adapters.nelo.schemas import WorkerAssignmentRow
from src.hr.models.worker_phase_assignment import WorkerPhaseAssignment

from .conftest import RecordingSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")

_T_ASSIGNED = datetime(2025, 4, 10, 7, 0, 0)
_T_STARTED = datetime(2025, 4, 10, 8, 0, 0)
_T_ENDED = datetime(2025, 4, 10, 12, 0, 0)


def _row(**kw) -> WorkerAssignmentRow:
    base = dict(
        worker_id=42,
        of_id="OF-2001",
        phase_id="FP-05",
        assigned_at=_T_ASSIGNED,
        started_at=None,
        ended_at=None,
        tipo=None,
    )
    base.update(kw)
    return WorkerAssignmentRow(**base)


# ── 1. skip silencioso se SQLSERVER_ENABLED=false ────────────────────────


async def test_sync_worker_assignments_skip_when_sqlserver_disabled(monkeypatch):
    """Quando sqlserver_enabled=False, devolve status='skipped', sem lancar erro."""
    import src.shared.config as cfg_mod

    original = cfg_mod.settings.sqlserver_enabled
    try:
        cfg_mod.settings.sqlserver_enabled = False
        result = await sync_worker_assignments(
            session=RecordingSession(), tenant_id=TENANT, since=None,
        )
        assert result.status == "skipped"
        assert result.error == "sqlserver_disabled"
        assert result.rows_read == 0
    finally:
        cfg_mod.settings.sqlserver_enabled = original


# ── 2. fake-ERP 5 rows → 5 upserts ──────────────────────────────────────


async def test_sync_worker_assignments_5_rows_upserted(monkeypatch):
    """Fake-ERP devolve 5 rows → 5 WorkerPhaseAssignment inseridos."""
    import src.shared.config as cfg_mod

    original = cfg_mod.settings.sqlserver_enabled
    cfg_mod.settings.sqlserver_enabled = True
    try:
        fake_rows = [
            _row(worker_id=i + 1, of_id=f"OF-{i}", phase_id="FP-05")
            for i in range(5)
        ]
        monkeypatch.setattr(
            wa_mod.services, "list_worker_assignments",
            AsyncMock(return_value=fake_rows),
        )
        session = RecordingSession()
        result = await sync_worker_assignments(
            session=session, tenant_id=TENANT, since=None,
        )
        assert result.status == "ok"
        assert result.rows_read == 5
        inserted = [o for o in session.added if isinstance(o, WorkerPhaseAssignment)]
        assert len(inserted) == 5
    finally:
        cfg_mod.settings.sqlserver_enabled = original


# ── 3. assignment_type='planned' quando so Atribuido_Em ───────────────────


def test_derive_assignment_type_planned_when_no_started():
    """So Atribuido_Em preenchido → assignment_type='planned'."""
    row = _row(started_at=None, ended_at=None)
    assert _derive_assignment_type(row) == "planned"


# ── 4. assignment_type='actual' quando Iniciado_Em presente ───────────────


def test_derive_assignment_type_actual_when_started():
    """Iniciado_Em preenchido → assignment_type='actual'."""
    row = _row(started_at=_T_STARTED, ended_at=_T_ENDED)
    assert _derive_assignment_type(row) == "actual"


# ── 5. idempotencia: 2x mesmo input → sem duplicados ─────────────────────


async def test_sync_worker_assignments_idempotent(monkeypatch):
    """Duas execucoes com os mesmos dados → apenas 1 row, sem duplicados."""
    import src.shared.config as cfg_mod

    original = cfg_mod.settings.sqlserver_enabled
    cfg_mod.settings.sqlserver_enabled = True
    try:
        rows = [_row(worker_id=99, of_id="OF-888", phase_id="FP-10")]
        monkeypatch.setattr(
            wa_mod.services, "list_worker_assignments",
            AsyncMock(return_value=rows),
        )
        session = RecordingSession()
        await sync_worker_assignments(session=session, tenant_id=TENANT, since=None)
        count_first = len([o for o in session.added if isinstance(o, WorkerPhaseAssignment)])
        await sync_worker_assignments(session=session, tenant_id=TENANT, since=None)
        inserted = [o for o in session.added if isinstance(o, WorkerPhaseAssignment)]
        assert len(inserted) == count_first  # sem novos inserts
    finally:
        cfg_mod.settings.sqlserver_enabled = original


# ── pure: _worker_uuid ────────────────────────────────────────────────────


def test_worker_uuid_deterministic():
    """Mesmo worker_id int → sempre o mesmo UUID (idempotencia de upsert)."""
    u1 = _worker_uuid(42)
    u2 = _worker_uuid(42)
    assert u1 == u2
    assert u1 != _worker_uuid(43)


def test_worker_uuid_is_uuid():
    """_worker_uuid devolve um UUID valido."""
    u = _worker_uuid(1)
    assert isinstance(u, UUID)


# ── pure: _map_row ────────────────────────────────────────────────────────


def test_map_row_planned_assignment():
    """Row sem started_at → assignment_type='planned', ended_at=None."""
    row = _row(started_at=None, ended_at=None)
    mapped = _map_row(row)
    assert mapped is not None
    assert mapped["assignment_type"] == "planned"
    assert mapped["started_at"] is None
    assert mapped["ended_at"] is None


def test_map_row_actual_assignment():
    """Row com started_at → assignment_type='actual', ended_at preenchido."""
    row = _row(started_at=_T_STARTED, ended_at=_T_ENDED)
    mapped = _map_row(row)
    assert mapped is not None
    assert mapped["assignment_type"] == "actual"
    assert mapped["started_at"] is not None
    assert mapped["ended_at"] is not None


def test_map_row_none_worker_id_returns_none():
    """Row com worker_id=None e ignorada (linha invalida ERP)."""
    row = WorkerAssignmentRow(
        worker_id=None,
        of_id="OF-X",
        phase_id="FP-1",
        assigned_at=_T_ASSIGNED,
    )
    assert _map_row(row) is None


def test_map_row_timestamps_utc():
    """Timestamps naive ficam tz-aware (UTC) apos _map_row."""
    row = _row(assigned_at=datetime(2025, 5, 1, 9, 0, 0))  # naive
    mapped = _map_row(row)
    assert mapped is not None
    assert mapped["assigned_at"].tzinfo == timezone.utc
