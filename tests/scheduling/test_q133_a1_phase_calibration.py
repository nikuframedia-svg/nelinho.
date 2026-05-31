"""Q.133.A1 — job de calibração de durações por (modelo, fase).

Agrega p50/p95 de factory_raw.of_fp → UPSERT plan.phase_duration_calibration.
Mocka a sessão (como test_q115_x6_boat_potential) e testa a orquestração +
params; a idempotência (SQL ON CONFLICT) é verificada ao vivo em _audit/q133.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from src.scheduling.jobs import phase_calibration_job as job

TEST_TENANT = UUID("33333333-3333-3333-3333-333333333333")


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


def _agg(modelo, phase, p50, p95, n):
    return SimpleNamespace(modelo=modelo, phase_id=phase, p50=p50, p95=p95, n=n)


def _patch_session(monkeypatch, agg_rows):
    session = MagicMock()
    calls: list = []

    async def fake_execute(stmt, params=None):
        calls.append((stmt, params))
        return _FakeResult(agg_rows) if len(calls) == 1 else _FakeResult([])

    session.execute = AsyncMock(side_effect=fake_execute)
    session.commit = AsyncMock()

    @asynccontextmanager
    async def fake_ctx():
        yield session

    monkeypatch.setattr(job, "get_session_context", fake_ctx)
    return session, calls


@pytest.mark.asyncio
async def test_calibration_upserts_pairs_keyed_by_of_p_id(monkeypatch):
    agg_rows = [
        _agg("20155", "1", 240.0, 300.0, 12),
        _agg("20155", "2", 1040.0, 1200.0, 8),
    ]
    session, calls = _patch_session(monkeypatch, agg_rows)

    n = await job._phase_calibration_job(TEST_TENANT)

    assert n == 2
    # 1ª chamada = agregação; 2ª = UPSERT executemany com 2 dicts.
    upsert_params = calls[1][1]
    assert isinstance(upsert_params, list) and len(upsert_params) == 2
    first = upsert_params[0]
    assert first["modelo"] == "20155"      # keyspace = OF_P_ID
    assert first["phase"] == "1"
    assert first["p50"] == 240.0 and first["p95"] == 300.0 and first["n"] == 12
    assert first["tid"] == TEST_TENANT
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_calibration_no_data_no_upsert(monkeypatch):
    session, calls = _patch_session(monkeypatch, [])

    n = await job._phase_calibration_job(TEST_TENANT)

    assert n == 0
    session.commit.assert_not_awaited()   # sem dados → não escreve nem comita
    assert len(calls) == 1                # só a agregação correu


def test_cleaning_bounds_match_state_loader():
    """Os limiares de limpeza batem com state.py (_DUR_FLOOR_H=0.05, _CEIL=24*7),
    convertidos para minutos — mesma fonte de verdade, sem inventar."""
    assert job._DUR_FLOOR_MIN == pytest.approx(0.05 * 60.0)
    assert job._DUR_CEIL_MIN == pytest.approx(24.0 * 7 * 60.0)
