"""Q.115.T — testes para o mirror phase_history (FasesOf → plan.fases_of_history).

Seguem o padrao dos outros testes ETL (RecordingSession + monkeypatch de services).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

from src.adapters.nelo.etl import phase_history as ph_mod
from src.adapters.nelo.etl.phase_history import (
    _as_utc,
    _calc_duration_min,
    _map_row,
    _safe_str,
    sync_phase_history,
)
from src.adapters.nelo.schemas import FasesOfHistoryRow
from src.plan.models.fases_of_history import FasesOfHistory

from .conftest import RecordingSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")

_T0 = datetime(2025, 3, 1, 8, 0, 0)
_T1 = datetime(2025, 3, 1, 10, 0, 0)


def _row(**kw) -> FasesOfHistoryRow:
    base = dict(
        of_id="OF-1001",
        phase_id="FP-18",
        fase_inicio=_T0,
        fase_fim=_T1,
        worker_id=42,
        mold_id="M-07",
    )
    base.update(kw)
    return FasesOfHistoryRow(**base)


# ── 1. skip silencioso se SQLSERVER_ENABLED=false ────────────────────────


async def test_sync_phase_history_skip_when_sqlserver_disabled(monkeypatch):
    """Quando sqlserver_enabled=False, devolve status='skipped', sem lancar erro."""
    import src.shared.config as cfg_mod

    original = cfg_mod.settings.sqlserver_enabled
    try:
        cfg_mod.settings.sqlserver_enabled = False
        result = await sync_phase_history(
            session=RecordingSession(), tenant_id=TENANT, since=None,
        )
        assert result.status == "skipped"
        assert result.error == "sqlserver_disabled"
        assert result.rows_read == 0
    finally:
        cfg_mod.settings.sqlserver_enabled = original


# ── 2. fake-ERP 5 rows → 5 upserts em fases_of_history ──────────────────


async def test_sync_phase_history_5_rows_upserted(monkeypatch):
    """Fake-ERP devolve 5 rows → 5 FasesOfHistory inseridos na session."""
    import src.shared.config as cfg_mod

    original = cfg_mod.settings.sqlserver_enabled
    cfg_mod.settings.sqlserver_enabled = True
    try:
        fake_rows = [_row(of_id=f"OF-{i}", phase_id="FP-18") for i in range(5)]
        monkeypatch.setattr(
            ph_mod.services, "list_phase_history",
            AsyncMock(return_value=fake_rows),
        )
        session = RecordingSession()
        result = await sync_phase_history(session=session, tenant_id=TENANT, since=None)

        assert result.status == "ok"
        assert result.rows_read == 5
        inserted = [o for o in session.added if isinstance(o, FasesOfHistory)]
        assert len(inserted) == 5
    finally:
        cfg_mod.settings.sqlserver_enabled = original


# ── 3. watermark incremental ──────────────────────────────────────────────


async def test_sync_phase_history_watermark_incremental(monkeypatch):
    """Segunda execucao com since= passa since para services.list_phase_history."""
    import src.shared.config as cfg_mod

    original = cfg_mod.settings.sqlserver_enabled
    cfg_mod.settings.sqlserver_enabled = True
    try:
        captured: dict = {}

        async def _fake_list(since=None, limit=50_000):
            captured["since"] = since
            return [_row()]

        monkeypatch.setattr(ph_mod.services, "list_phase_history", _fake_list)
        since_date = date(2025, 6, 1)
        await sync_phase_history(
            session=RecordingSession(), tenant_id=TENANT, since=since_date,
        )
        assert captured["since"] == since_date
    finally:
        cfg_mod.settings.sqlserver_enabled = original


# ── 4. duration_min calculado correctamente ───────────────────────────────


def test_duration_min_correct():
    """120 min entre T0 (8h) e T1 (10h)."""
    t0 = datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc)
    t1 = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    result = _calc_duration_min(t0, t1)
    assert result == Decimal("120.00")


# ── 5. fase_fim null → duration_min null ──────────────────────────────────


def test_duration_min_null_when_fase_fim_none():
    """Fase em curso (fase_fim=None) → duration_min None."""
    t0 = datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc)
    assert _calc_duration_min(t0, None) is None


# ── 5b. Q.168 F4.E — duracoes patologicas (dados sujos do ERP) ────────────


def test_duration_min_null_when_negative():
    """fase_fim antes do inicio (dados sujos) → None, nao negativo."""
    t0 = datetime(2025, 1, 2, 8, 0, tzinfo=timezone.utc)
    t1 = datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc)
    assert _calc_duration_min(t0, t1) is None


def test_duration_min_null_when_pathologically_long_q168_f4e():
    """Fase de ~125 anos (OF_FP com 1900-01-01, padrao real do ERP: 37% das
    linhas) → None. Sem o tecto, anos de 'duracao' contaminavam as medianas
    downstream do CPO."""
    t0 = datetime(1900, 1, 1, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc)
    assert _calc_duration_min(t0, t1) is None


def test_duration_min_exactly_30_days_is_kept_q168_f4e():
    """Fronteira: exatamente 30 dias (43 200 min) ainda e aceite — o tecto
    rejeita apenas o que EXCEDE."""
    t0 = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2025, 1, 31, 0, 0, tzinfo=timezone.utc)
    assert _calc_duration_min(t0, t1) == Decimal("43200.00")


# ── 6. encoding UTF-8: acento PT-PT preservado ────────────────────────────


def test_safe_str_preserves_accents():
    """Caracteres acentuados PT-PT (â, ã, ç) preservados pelo _safe_str."""
    assert _safe_str("Lâminação") == "Lâminação"
    assert _safe_str("Montagem/Acabamento") == "Montagem/Acabamento"
    assert _safe_str(None) is None


# ── 7. idempotencia: 2x mesmo input → sem duplicados ─────────────────────


async def test_sync_phase_history_idempotent(monkeypatch):
    """Duas execucoes com os mesmos dados → apenas 1 row inserida, sem duplicados."""
    import src.shared.config as cfg_mod

    original = cfg_mod.settings.sqlserver_enabled
    cfg_mod.settings.sqlserver_enabled = True
    try:
        rows = [_row(of_id="OF-999", phase_id="FP-18")]
        monkeypatch.setattr(
            ph_mod.services, "list_phase_history",
            AsyncMock(return_value=rows),
        )
        session = RecordingSession()
        # primeira execucao
        await sync_phase_history(session=session, tenant_id=TENANT, since=None)
        count_after_first = len([o for o in session.added if isinstance(o, FasesOfHistory)])
        # segunda execucao com mesma session (rows ja presentes no _load_existing)
        await sync_phase_history(session=session, tenant_id=TENANT, since=None)
        inserted = [o for o in session.added if isinstance(o, FasesOfHistory)]
        assert len(inserted) == count_after_first  # sem novos inserts
    finally:
        cfg_mod.settings.sqlserver_enabled = original


# ── pure: _as_utc ─────────────────────────────────────────────────────────


def test_as_utc_naive_gets_utc():
    """Datetime naive do ERP recebe tzinfo=UTC (NELO Vila do Conde)."""
    dt = datetime(2025, 1, 15, 9, 30)
    result = _as_utc(dt)
    assert result is not None
    assert result.tzinfo == timezone.utc


def test_as_utc_none_returns_none():
    assert _as_utc(None) is None


def test_as_utc_aware_unchanged():
    """Datetime ja tz-aware nao e alterado."""
    dt = datetime(2025, 1, 15, 9, 30, tzinfo=timezone.utc)
    result = _as_utc(dt)
    assert result == dt


# ── pure: _map_row ────────────────────────────────────────────────────────


def test_map_row_sets_duration():
    """_map_row calcula duration_min correctamente (T1 - T0 = 120 min)."""
    row = _row(fase_inicio=_T0, fase_fim=_T1)
    mapped = _map_row(row, "test_run")
    assert mapped["duration_min"] == Decimal("120.00")
    assert mapped["source_run_id"] == "test_run"
    assert mapped["of_id"] == "OF-1001"
    assert mapped["phase_id"] == "FP-18"


def test_map_row_null_fase_fim_gives_null_duration():
    """_map_row com fase_fim=None → duration_min None."""
    row = _row(fase_fim=None)
    mapped = _map_row(row, None)
    assert mapped["duration_min"] is None
    assert mapped["fase_fim"] is None
