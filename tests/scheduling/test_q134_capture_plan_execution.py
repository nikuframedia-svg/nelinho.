"""Q.134.A3a — writer capture_plan_execution (PLANEADO vs REALIZADO).

`build_observed_records` é PURA (casamento + deviation_pct) → testada com dados
planos. A orquestração do job mocka a sessão (como test_q133_a1). O loop ao vivo
(commits LIVE + fases_of_history reais) não corre nesta máquina — provado no REPORT.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.scheduling.jobs import capture_plan_execution as job

TEST_TENANT = UUID("33333333-3333-3333-3333-333333333333")
TS = datetime(2026, 5, 31, 6, 35, 0)


def _op(order_id, phase_id, dur_min, start, end):
    return {
        "operation_id": f"{order_id}:{phase_id}",
        "order_id": order_id,
        "phase_id": phase_id,
        "duration_minutes": dur_min,
        "start_time": start,
        "end_time": end,
    }


def _hist(of_id, phase_id, dur_min, inicio, fim):
    return {
        "of_id": of_id,
        "phase_id": phase_id,
        "duration_min": dur_min,
        "fase_inicio": inicio,
        "fase_fim": fim,
    }


# ---------------------------------------------------------------- pure logic

def test_matched_pair_computes_deviation_pct():
    recs = job.build_observed_records(
        commit_id=uuid4(),
        tenant_id=TEST_TENANT,
        operations=[_op("OF1", "1", 100.0, "2026-05-01T08:00:00", "2026-05-01T09:40:00")],
        history_rows=[_hist("OF1", "1", 120.0,
                            datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
                            datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc))],
        modelo_by_of={"OF1": "42366"},
        ts=TS,
    )
    assert len(recs) == 1
    r = recs[0]
    assert r["of_id"] == "OF1" and r["phase"] == "1"
    assert r["modelo"] == "42366"
    assert r["p_dur"] == 100.0
    assert r["o_dur"] == 120.0
    # (120-100)/100*100 = +20% (realidade demorou mais que o planeado)
    assert r["dev"] == pytest.approx(20.0)
    # colunas são timestamp WITHOUT tz → naive
    assert r["o_start"].tzinfo is None
    assert r["ts"] == TS


def test_no_observed_keeps_null_deviation():
    recs = job.build_observed_records(
        commit_id=uuid4(),
        tenant_id=TEST_TENANT,
        operations=[_op("OF2", "5", 60.0, "2026-05-01T08:00:00", "2026-05-01T09:00:00")],
        history_rows=[],                     # ainda não executado
        modelo_by_of={},
        ts=TS,
    )
    assert len(recs) == 1
    r = recs[0]
    assert r["p_dur"] == 60.0
    assert r["o_dur"] is None
    assert r["dev"] is None                  # honesto: não inventa realizado
    assert r["modelo"] is None


def test_aggregates_multiple_ops_same_of_phase():
    recs = job.build_observed_records(
        commit_id=uuid4(),
        tenant_id=TEST_TENANT,
        operations=[
            _op("OF3", "1", 40.0, "2026-05-01T08:00:00", "2026-05-01T08:40:00"),
            _op("OF3", "1", 60.0, "2026-05-01T09:00:00", "2026-05-01T10:00:00"),
        ],
        history_rows=[
            _hist("OF3", "1", 50.0,
                  datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
                  datetime(2026, 5, 1, 8, 50, tzinfo=timezone.utc)),
            _hist("OF3", "1", 70.0,
                  datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
                  datetime(2026, 5, 1, 10, 10, tzinfo=timezone.utc)),
        ],
        modelo_by_of={"OF3": "20155"},
        ts=TS,
    )
    assert len(recs) == 1                    # 1 par (of, fase) agregado
    r = recs[0]
    assert r["p_dur"] == 100.0               # 40 + 60
    assert r["o_dur"] == 120.0               # 50 + 70
    assert r["dev"] == pytest.approx(20.0)
    # min start / max end
    assert r["p_start"] == datetime(2026, 5, 1, 8, 0)
    assert r["p_end"] == datetime(2026, 5, 1, 10, 0)


def test_zero_planned_duration_avoids_div_by_zero():
    recs = job.build_observed_records(
        commit_id=uuid4(),
        tenant_id=TEST_TENANT,
        operations=[_op("OF4", "1", 0.0, None, None)],
        history_rows=[_hist("OF4", "1", 30.0, None, None)],
        modelo_by_of={"OF4": "1"},
        ts=TS,
    )
    assert recs[0]["dev"] is None            # planned==0 → sem divisão


def test_ops_without_order_or_phase_are_skipped():
    recs = job.build_observed_records(
        commit_id=None,
        tenant_id=TEST_TENANT,
        operations=[
            {"operation_id": "x", "phase_id": "1", "duration_minutes": 10.0},  # sem order_id
            _op("OF5", "", 10.0, None, None),                                  # sem phase
        ],
        history_rows=[],
        modelo_by_of={},
        ts=TS,
    )
    assert recs == []


# ---------------------------------------------------------------- job shell

def _patch_session(monkeypatch, history_rows, modelo_rows):
    session = MagicMock()
    calls: list = []

    class _Mappings:
        def __init__(self, rows):
            self._rows = rows

        def mappings(self):
            return self._rows

    async def fake_execute(stmt, params=None):
        calls.append((str(stmt), params))
        sql = str(stmt)
        if "fases_of_history" in sql:
            return _Mappings(history_rows)
        if "ordemfabrico" in sql:
            return _Mappings(modelo_rows)
        return _Mappings([])               # UPSERT

    session.execute = AsyncMock(side_effect=fake_execute)
    session.commit = AsyncMock()

    @asynccontextmanager
    async def fake_ctx():
        yield session

    monkeypatch.setattr(job, "get_session_context", fake_ctx)
    return session, calls


@pytest.mark.asyncio
async def test_job_no_live_commits_is_noop(monkeypatch):
    session, calls = _patch_session(monkeypatch, [], [])

    async def fake_fetch(_session, _tid):
        return []

    monkeypatch.setattr(job, "_fetch_live_commits", fake_fetch)

    n = await job._capture_plan_execution_job(TEST_TENANT)

    assert n == 0
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_job_upserts_for_live_commit(monkeypatch):
    history = [_hist("OF1", "1", 120.0,
                     datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
                     datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc))]
    modelos = [{"of_id": "OF1", "modelo": "42366"}]
    session, calls = _patch_session(monkeypatch, history, modelos)

    commit = SimpleNamespace(
        id=uuid4(),
        operations=[_op("OF1", "1", 100.0,
                        "2026-05-01T08:00:00", "2026-05-01T09:40:00")],
    )

    async def fake_fetch(_session, _tid):
        return [commit]

    monkeypatch.setattr(job, "_fetch_live_commits", fake_fetch)

    n = await job._capture_plan_execution_job(TEST_TENANT)

    assert n == 1
    session.commit.assert_awaited_once()
    # a última execute = UPSERT executemany com 1 dict
    upsert = [c for c in calls if "plan_execution_observed" in c[0]]
    assert upsert and isinstance(upsert[-1][1], list)
    assert upsert[-1][1][0]["dev"] == pytest.approx(20.0)
    assert upsert[-1][1][0]["modelo"] == "42366"
