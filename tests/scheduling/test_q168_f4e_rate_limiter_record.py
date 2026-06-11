"""Q.168 F4.E — rate-limiter regista a chave ANTES do propose.

Antes, ``_rate_limiter.record(key)`` só corria DEPOIS de
``propose_decision_row`` ter sucesso. Uma falha transiente (DB timeout,
audit fail) deixava a chave por registar → o tick seguinte re-tentava
agressivamente o mesmo candidato (re-spam dentro da janela de 5 min).

Semântica escolhida (documentada no job): registar ANTES evita o re-spam;
o retry NÃO se perde porque o tick do APScheduler é a +15 min (> janela de
5 min) e o dedup durável (``_blocked_targets``) é quem impede duplicados
na BD.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, List
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.scheduling.jobs import auto_propose_signals_job as job

TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _FakeSession:
    def __init__(self) -> None:
        self.added: List[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if not hasattr(obj, "id") or obj.id is None:
                object.__setattr__(obj, "id", uuid4())

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


@asynccontextmanager
async def _ctx_session():
    yield _FakeSession()


@asynccontextmanager
async def _factory():
    yield _FakeSession()


def _one_candidate():
    return {
        "title": "Adotar novo plano CPO",
        "action_type": "ADOPT_PLAN",
        "target": "draftsha-1",
        "sandbox_result": {"confidence": 80},
        "before_state": {},
        "after_state": {"commit_sha": "draftsha-1"},
        "audit_reason": "x",
        "audit_extra": {},
        "sse_extra": {},
    }


@pytest.mark.asyncio
async def test_transient_propose_failure_still_records_rate_limit_q168_f4e():
    """Propose falha transiente → chave registada na mesma → 2.º tick
    dentro da janela NÃO re-tenta (sem re-spam)."""
    job._rate_limiter._last_seen.clear()
    failing = AsyncMock(side_effect=SQLAlchemyError("DB timeout transiente"))
    ps = (
        patch.object(job, "_resolve_tenants", AsyncMock(return_value=[TENANT])),
        patch("src.shared.database.get_session_context", _ctx_session),
        patch("src.shared.database.async_session_factory", _factory),
        patch.object(job, "_enabled", AsyncMock(return_value=True)),
        patch.object(job, "_decision_ttl_hours", AsyncMock(return_value=24)),
        patch.object(job, "_planning_candidates",
                     AsyncMock(return_value=[_one_candidate()])),
        patch.object(job, "_expedition_candidates", AsyncMock(return_value=[])),
        patch.object(job, "_otd_reschedule_candidates", AsyncMock(return_value=[])),
        patch.object(job, "_supersede_stale_adopt_plans", AsyncMock(return_value=0)),
        patch.object(job, "_revalidate_stale_decisions", AsyncMock(return_value=0)),
        patch.object(job, "_blocked_targets", AsyncMock(return_value=set())),
        patch.object(job, "propose_decision_row", failing),
    )
    for p in ps:
        p.start()
    try:
        await job._auto_propose_signals_job([TENANT])  # propose rebenta
        await job._auto_propose_signals_job([TENANT])  # janela 5 min → skip
    finally:
        for p in ps:
            p.stop()

    # Sem re-spam: o propose só foi tentado 1 vez dentro da janela.
    assert failing.await_count == 1
    # A chave ficou registada apesar da falha.
    key = f"{TENANT}:ADOPT_PLAN:draftsha-1"
    assert key in job._rate_limiter._last_seen
    job._rate_limiter._last_seen.clear()
