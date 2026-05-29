"""Q.117.G — o job quality_risk_scoring deixou de ser stub.

Verifica que corre o DefectRiskService real (não apenas loga) e que
degrada sem levantar para dentro do scheduler.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _mock_session_ctx() -> tuple[MagicMock, AsyncMock]:
    fake_session = AsyncMock()
    fake_session.commit = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=fake_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, fake_session


@pytest.mark.asyncio
async def test_job_invoca_defect_risk_service(monkeypatch):
    from src.scheduling.jobs.ml import _quality_risk_scoring_job
    import src.shared.database as db_mod
    import src.quality.services.defect_risk_service as svc_mod

    ctx, fake_session = _mock_session_ctx()
    monkeypatch.setattr(db_mod, "get_session_context", lambda: ctx)

    calls: dict = {}

    class _FakeSvc:
        def __init__(self, session, tenant_id):
            calls["tenant"] = tenant_id

        async def defect_risk(self, *, top_n: int = 50):
            calls["top_n"] = top_n
            return {
                "model_available": True,
                "total_orders": 3,
                "high_risk_count": 1,
                "orders": [],
            }

    monkeypatch.setattr(svc_mod, "DefectRiskService", _FakeSvc)

    await _quality_risk_scoring_job(TENANT)

    assert calls["tenant"] == TENANT
    assert calls["top_n"] == 50
    fake_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_job_degrada_sem_levantar(monkeypatch):
    from src.scheduling.jobs.ml import _quality_risk_scoring_job
    import src.shared.database as db_mod
    import src.quality.services.defect_risk_service as svc_mod

    ctx, _ = _mock_session_ctx()
    monkeypatch.setattr(db_mod, "get_session_context", lambda: ctx)

    class _BoomSvc:
        def __init__(self, session, tenant_id):
            pass

        async def defect_risk(self, *, top_n: int = 50):
            raise RuntimeError("modelo indisponível")

    monkeypatch.setattr(svc_mod, "DefectRiskService", _BoomSvc)

    # Não deve levantar — o scheduler nunca pode morrer por um tenant.
    await _quality_risk_scoring_job(TENANT)
