"""Q.169.E — heartbeat do worker Arq + solve fora do event loop.

Sem heartbeat, um cpo_schedule_job pendurado (deadlock no load, solver
preso) só era detetável quando o wall-clock de 1200s o matava — 20 min de
silêncio total nos logs. Com o solve em `asyncio.to_thread` (scheduler_run)
o event loop fica livre e o heartbeat corre DURANTE o solve.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import pytest

import src.plan.cpo.worker as worker_mod
from tests.conftest import FakeSession, TEST_TENANT_ID


@pytest.mark.asyncio
async def test_heartbeat_emits_during_long_job(monkeypatch, caplog):
    monkeypatch.setattr(worker_mod, "_HEARTBEAT_INTERVAL_S", 0.05)

    async def _slow_run(session, tenant_id, request):
        await asyncio.sleep(0.25)  # ~5 batimentos a 0.05s
        return {"commit_sha256": "a" * 64, "status": "optimal",
                "solve_time_sec": 0.25}

    import src.plan.cpo.scheduler_run as sr
    monkeypatch.setattr(sr, "run_cpo_schedule", _slow_run)

    @asynccontextmanager
    async def _fake_ctx():
        yield FakeSession()

    import src.shared.database as db
    monkeypatch.setattr(db, "get_session_context", _fake_ctx)

    import src.plan.services.manual_reorder as mr

    async def _noop_reapply(session, tenant_id):
        return {}

    monkeypatch.setattr(mr, "reapply_manual_overrides", _noop_reapply)

    with caplog.at_level(logging.INFO, logger="src.plan.cpo.worker"):
        result = await worker_mod.cpo_schedule_job(
            {"job_id": "test-hb"},
            {},  # CPOScheduleRequest com defaults
            str(TEST_TENANT_ID),
            "tester",
        )

    assert result["status"] == "optimal"
    vivos = [r for r in caplog.records if "vivo" in r.getMessage()]
    assert vivos, "heartbeat tem de bater durante um job longo"
    assert any("complete" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_heartbeat_stops_after_job(monkeypatch, caplog):
    """O heartbeat morre com o job — sem tasks órfãs a bater para sempre."""
    monkeypatch.setattr(worker_mod, "_HEARTBEAT_INTERVAL_S", 0.05)

    async def _fast_run(session, tenant_id, request):
        return {"commit_sha256": None, "status": "optimal",
                "solve_time_sec": 0.0}

    import src.plan.cpo.scheduler_run as sr
    monkeypatch.setattr(sr, "run_cpo_schedule", _fast_run)

    @asynccontextmanager
    async def _fake_ctx():
        yield FakeSession()

    import src.shared.database as db
    monkeypatch.setattr(db, "get_session_context", _fake_ctx)

    import src.plan.services.manual_reorder as mr

    async def _noop_reapply(session, tenant_id):
        return {}

    monkeypatch.setattr(mr, "reapply_manual_overrides", _noop_reapply)

    await worker_mod.cpo_schedule_job(
        {"job_id": "test-stop"}, {}, str(TEST_TENANT_ID), "tester",
    )
    n_before = len(caplog.records)
    await asyncio.sleep(0.2)  # 4 intervalos — zero batimentos novos
    assert len(caplog.records) == n_before
