"""Q.157.A — auto-propose REAL de sinais (saúde de molde + OTD-risk).

Cobre:
  1. propose_decision_row → SharedDecisionRun PROPOSED + audit na mesma sessão
  2. Gerador molde: confidence = 100 - score; só red/yellow geram (green skip)
  3. Gerador OTD: confidence = round(p*100); só "alto"; cap _OTD_MAX_PER_TICK;
     model_unavailable → [] (vazio honesto, nunca probabilidade inventada)
  4. Job: dedup durável — candidate já PROPOSED não é re-criado
  5. Job: rate-limit in-memory — 2º tick na janela não repete

Zero números hardcoded a "fingir" decisões: cada confidence é asserido
RELATIVO ao input do sinal.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, List
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from src.scheduling.jobs import auto_propose_signals_job as job
from src.shared.models.governance import DecisionStatus, SharedDecisionRun

TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ---------------------------------------------------------------------------
# FakeSession (igual ao padrão Q.115.D) — captura add()/flush()
# ---------------------------------------------------------------------------

class FakeSession:
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


def _factory(captured: List[FakeSession]):
    @asynccontextmanager
    async def _f():
        session = FakeSession()
        captured.append(session)
        yield session

    return _f


# ---------------------------------------------------------------------------
# 1 — propose_decision_row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_propose_decision_row_creates_proposed_plus_audit():
    from src.core.models.audit import AuditLog
    from src.plan.services.auto_propose import propose_decision_row

    sessions: List[FakeSession] = []
    decision = await propose_decision_row(
        _factory(sessions),
        tenant_id=TENANT,
        title="Manutenção preventiva — molde M-K1",
        action_type="MOLD_MAINTENANCE",
        target="M-K1",
        sandbox_result={"confidence": 70, "source": "Saúde de molde (R.6.2)"},
        audit_reason="Q.157.A teste",
        audit_extra={"source": "auto_propose_signals", "signal": "mold_health"},
    )

    assert decision.status == DecisionStatus.PROPOSED.value
    assert decision.action_type == "MOLD_MAINTENANCE"
    assert decision.target == "M-K1"
    # Q.17: proponente é o sistema, não um humano
    from src.plan.services.auto_propose import _SYSTEM_ACTOR
    assert decision.proposed_by == _SYSTEM_ACTOR

    assert len(sessions) == 1
    added = sessions[0].added
    assert any(isinstance(a, SharedDecisionRun) for a in added)
    audits = [a for a in added if isinstance(a, AuditLog)]
    assert audits, "audit_change deve correr na mesma sessão/tx"
    assert any("auto_propose_signals" in str(a.new_values) for a in audits)


# ---------------------------------------------------------------------------
# 2 — Gerador molde
# ---------------------------------------------------------------------------

def _fake_mold(code: str):
    return SimpleNamespace(id=uuid4(), mold_code=code)


def _fake_health(score: int, risk: str):
    return SimpleNamespace(
        score_0_100=score,
        risk_category=risk,
        components={"cycles_pct": 0.5, "maint_age_pct": 0.5,
                    "defect_penalty": 0.2, "rework_rate": 0.1},
    )


@pytest.mark.asyncio
async def test_mold_generator_confidence_and_filter():
    molds = [_fake_mold("M-RED"), _fake_mold("M-YEL"), _fake_mold("M-GRN")]
    health_by_code = {
        "M-RED": _fake_health(25, "red"),
        "M-YEL": _fake_health(60, "yellow"),
        "M-GRN": _fake_health(90, "green"),
    }
    code_by_id = {m.id: m.mold_code for m in molds}

    class _FakeMoldService:
        def __init__(self, session, tenant_id):  # noqa: D401
            pass

        async def list_molds(self):
            return molds

        async def latest_health(self, mold_id):
            return health_by_code[code_by_id[mold_id]]

    with patch("src.plan.services.mold_service.MoldService", _FakeMoldService):
        cands = await job._mold_maintenance_candidates(object(), TENANT)

    by_target = {c["target"]: c for c in cands}
    # green NÃO gera decisão
    assert "M-GRN" not in by_target
    assert set(by_target) == {"M-RED", "M-YEL"}
    # confidence = 100 - score (derivado do sinal, não literal)
    assert by_target["M-RED"]["sandbox_result"]["confidence"] == 100 - 25
    assert by_target["M-YEL"]["sandbox_result"]["confidence"] == 100 - 60
    assert by_target["M-RED"]["action_type"] == "MOLD_MAINTENANCE"


# ---------------------------------------------------------------------------
# 3 — Gerador OTD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_otd_generator_confidence_band_and_cap():
    orders = [
        {"of_id": f"OF-{i}", "late_probability": 0.80 + i * 0.01,
         "risk_band": "alto", "transport_date": "2026-06-10",
         "features": {"slack_days": -2}, "current_phase_name": "Pintura"}
        for i in range(5)  # 5 "alto" → cap deve cortar a _OTD_MAX_PER_TICK
    ] + [
        {"of_id": "OF-LOW", "late_probability": 0.10, "risk_band": "baixo",
         "transport_date": "2026-07-01", "features": {"slack_days": 30}},
    ]

    class _FakeOTD:
        def __init__(self, session, tenant_id):
            pass

        async def otd_risk(self, *, top_n=50):
            return {"model_available": True, "orders": orders}

    with patch("src.plan.services.otd_risk_service.OTDRiskService", _FakeOTD):
        cands = await job._otd_reschedule_candidates(object(), TENANT)

    assert len(cands) == job._OTD_MAX_PER_TICK  # cap aplicado
    assert all(c["action_type"] == "OTD_RESCHEDULE" for c in cands)
    # nenhuma "baixo"
    assert "OF-LOW" not in {c["target"] for c in cands}
    # confidence = round(p*100)
    c0 = cands[0]
    assert c0["sandbox_result"]["confidence"] == round(0.80 * 100)


@pytest.mark.asyncio
async def test_otd_generator_no_model_is_empty_honest():
    class _FakeOTD:
        def __init__(self, session, tenant_id):
            pass

        async def otd_risk(self, *, top_n=50):
            return {"model_available": False, "orders": []}

    with patch("src.plan.services.otd_risk_service.OTDRiskService", _FakeOTD):
        cands = await job._otd_reschedule_candidates(object(), TENANT)

    assert cands == []  # sem modelo → vazio, nunca inventa


# ---------------------------------------------------------------------------
# 4+5 — Job: dedup durável + rate-limit
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _ctx_session():
    yield FakeSession()


def _one_mold_candidate():
    return {
        "title": "Manutenção preventiva — molde M-K1",
        "action_type": "MOLD_MAINTENANCE",
        "target": "M-K1",
        "sandbox_result": {"confidence": 75},
        "before_state": {},
        "after_state": {},
        "audit_reason": "x",
        "audit_extra": {},
        "sse_extra": {},
    }


@pytest.mark.asyncio
async def test_job_dedup_skips_existing_proposed():
    job._rate_limiter._last_seen.clear()
    persisted = AsyncMock()
    with patch.object(job, "_resolve_tenants", AsyncMock(return_value=[TENANT])), \
         patch("src.shared.database.get_session_context", _ctx_session), \
         patch("src.shared.database.async_session_factory", _factory([])), \
         patch.object(job, "_enabled", AsyncMock(return_value=True)), \
         patch.object(job, "_mold_maintenance_candidates",
                      AsyncMock(return_value=[_one_mold_candidate()])), \
         patch.object(job, "_otd_reschedule_candidates", AsyncMock(return_value=[])), \
         patch.object(job, "_existing_proposed_targets",
                      AsyncMock(return_value={("MOLD_MAINTENANCE", "M-K1")})), \
         patch.object(job, "propose_decision_row", persisted):
        await job._auto_propose_signals_job([TENANT])

    persisted.assert_not_called()  # já existe PROPOSED igual → não recria


@pytest.mark.asyncio
async def test_job_creates_then_rate_limits_second_tick():
    job._rate_limiter._last_seen.clear()
    persisted = AsyncMock()
    common = dict(
        _resolve=AsyncMock(return_value=[TENANT]),
    )
    patches = lambda: (  # noqa: E731
        patch.object(job, "_resolve_tenants", common["_resolve"]),
        patch("src.shared.database.get_session_context", _ctx_session),
        patch("src.shared.database.async_session_factory", _factory([])),
        patch.object(job, "_enabled", AsyncMock(return_value=True)),
        patch.object(job, "_mold_maintenance_candidates",
                     AsyncMock(return_value=[_one_mold_candidate()])),
        patch.object(job, "_otd_reschedule_candidates", AsyncMock(return_value=[])),
        patch.object(job, "_existing_proposed_targets", AsyncMock(return_value=set())),
        patch.object(job, "propose_decision_row", persisted),
    )

    ps = patches()
    for p in ps:
        p.start()
    try:
        await job._auto_propose_signals_job([TENANT])  # 1º tick → cria
        await job._auto_propose_signals_job([TENANT])  # 2º tick → rate-limit
    finally:
        for p in ps:
            p.stop()

    assert persisted.await_count == 1, "rate-limit: só 1 decisão na janela de 5 min"
