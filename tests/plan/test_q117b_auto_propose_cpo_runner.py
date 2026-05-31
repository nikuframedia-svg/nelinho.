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

    # Consequências derivadas SÓ de valores reais (Q.131+) — alimenta a card
    # "Consequências" da tab Simulações, que antes ficava sempre vazia.
    assert out["if_accept"], "if_accept devia vir preenchido quando há commit"
    joined_accept = " | ".join(out["if_accept"])
    assert "makespan 120.0 h" in joined_accept
    assert "2 ordens atrasadas" in joined_accept
    assert "+200" in joined_accept and "€" in joined_accept  # margem
    assert "alto" in joined_accept  # risco de qualidade
    assert any("Mantém o plano atual" in line for line in out["if_reject"])
    assert any("OF-9" in line for line in out["if_reject"])
    assert "Replaneamento proposto pelo CPO" in out["why"]


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

    # if_accept ainda vem (há plano), mas SEM linhas de margem/risco.
    assert out["if_accept"]
    joined = " | ".join(out["if_accept"])
    assert "makespan 100.0 h" in joined
    assert "€" not in joined  # sem margem (delta None)
    assert "risco" not in joined.lower()  # sem risco de qualidade (sem modelo)
    assert "why" in out


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
    # Sem schedule → sem consequências falsas.
    assert "if_accept" not in out
    assert "if_reject" not in out
    assert "why" not in out
