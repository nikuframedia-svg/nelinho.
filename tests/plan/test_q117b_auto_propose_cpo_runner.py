"""Q.117.B — runner CPO real do auto_propose: enriquece sandbox_result.

Mocka run_cpo_schedule / compute_margin_preview / DefectRiskService (sem
motor real, sem DB). Verifica enriquecimento, omissão honesta e fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import pytest

from tests.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")


class _FakeSessionCtx:
    """async context manager que devolve uma FakeSession."""

    def __init__(self) -> None:
        self.session = FakeSession()

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, *a) -> bool:
        return False


@dataclass
class _MarginPreview:
    predicted_margin_eur: Optional[Decimal]
    baseline_margin_eur: Optional[Decimal]
    delta_eur: Optional[Decimal]


def _patch_session(monkeypatch):
    import src.shared.database as db_mod
    monkeypatch.setattr(db_mod, "async_session_factory", lambda: _FakeSessionCtx())


def _patch_schedule(monkeypatch, result=None, raises=None):
    import src.plan.cpo.scheduler_run as sr_mod

    async def _fake_run(session, tenant_id, request):
        if raises is not None:
            raise raises
        return result

    monkeypatch.setattr(sr_mod, "run_cpo_schedule", _fake_run)


@pytest.mark.asyncio
async def test_runner_enriquece_commit_cost_delta_quality_risk(monkeypatch):
    from src.plan.services.auto_propose_cpo_runner import real_cpo_propose_runner
    import src.profit.services.margin_preview as mp_mod
    import src.quality.services.defect_risk_service as dr_mod

    _patch_session(monkeypatch)
    _patch_schedule(monkeypatch, result={
        "commit_sha256": "abc123",
        "makespan_hours": 120.0,
        "num_late_orders": 2,
        "avg_utilization": 0.85,
        "total_tardiness_hours": 5.0,
        "engine_used": "cpo_v4",
        "operations": [{"operation_id": "op1"}],
    })

    async def _fake_margin(session, tenant_id, commit, **kw):
        return _MarginPreview(Decimal("1000"), Decimal("800"), Decimal("200.50"))

    monkeypatch.setattr(mp_mod, "compute_margin_preview", _fake_margin)

    class _FakeDR:
        def __init__(self, session, tenant_id):
            pass

        async def defect_risk(self, *, top_n=500):
            return {
                "model_available": True,
                "orders": [{"of_id": "OF-9", "risk_band": "alto"}],
            }

    monkeypatch.setattr(dr_mod, "DefectRiskService", _FakeDR)

    out = await real_cpo_propose_runner(tenant_id=TENANT, payload={"of_id": "OF-9"})

    assert out["commit_sha"] == "abc123"
    assert out["propose_only"] is True
    assert out["kpis"]["num_late_orders"] == 2
    assert out["cost_delta"] == 200.5
    assert out["quality_risk"] == "alto"


@pytest.mark.asyncio
async def test_runner_omite_enriquecimento_quando_indisponivel(monkeypatch):
    from src.plan.services.auto_propose_cpo_runner import real_cpo_propose_runner
    import src.profit.services.margin_preview as mp_mod
    import src.quality.services.defect_risk_service as dr_mod

    _patch_session(monkeypatch)
    _patch_schedule(monkeypatch, result={
        "commit_sha256": "def456",
        "makespan_hours": 100.0,
        "num_late_orders": 0,
        "avg_utilization": 0.9,
        "operations": [],
    })

    async def _fake_margin(session, tenant_id, commit, **kw):
        return _MarginPreview(None, None, None)  # sem dados → delta None

    monkeypatch.setattr(mp_mod, "compute_margin_preview", _fake_margin)

    class _NoModelDR:
        def __init__(self, session, tenant_id):
            pass

        async def defect_risk(self, *, top_n=500):
            return {"model_available": False, "orders": []}

    monkeypatch.setattr(dr_mod, "DefectRiskService", _NoModelDR)

    out = await real_cpo_propose_runner(tenant_id=TENANT, payload={"of_id": "OF-1"})

    assert out["commit_sha"] == "def456"
    # Omissão honesta — nunca um zero/valor falso.
    assert "cost_delta" not in out
    assert "quality_risk" not in out


@pytest.mark.asyncio
async def test_runner_fallback_quando_cpo_falha(monkeypatch):
    from src.plan.services.auto_propose_cpo_runner import real_cpo_propose_runner

    _patch_session(monkeypatch)
    _patch_schedule(monkeypatch, raises=RuntimeError("FactoryState unavailable"))

    out = await real_cpo_propose_runner(tenant_id=TENANT, payload={"order_id": "OF-1"})

    # Forma do noop — listener nunca quebra.
    assert out["commit_sha"] == ""
    assert out["propose_only"] is True
    assert out["operations"] == []
    assert "fallback_reason" in out
