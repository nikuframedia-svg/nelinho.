"""Q.157.A/F — auto-propose REAL: planeamento (CPO) + expedição + OTD.

Cobre:
  1. propose_decision_row → SharedDecisionRun PROPOSED + audit na mesma sessão
  2. Planeamento (CPO): propõe ADOPT_PLAN quando o DRAFT melhora o LIVE; vazio
     quando o commit mais recente já é LIVE.
  3. Expedição: mapeia TransportSuggestion → decisão (TRUCK_CONSOLIDATE, …).
  4. OTD: confidence = round(p*100); só "alto"; cap; model_unavailable → [].
  5. Job: dedup durável + rate-limit in-memory.

Zero números hardcoded a "fingir" decisões: cada confidence/€ deriva do input.
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


# ───────────────────────── 1 — propose_decision_row ───────────────────────

@pytest.mark.asyncio
async def test_propose_decision_row_creates_proposed_plus_audit():
    from src.core.models.audit import AuditLog
    from src.plan.services.auto_propose import _SYSTEM_ACTOR, propose_decision_row

    sessions: List[FakeSession] = []
    decision = await propose_decision_row(
        _factory(sessions),
        tenant_id=TENANT,
        title="Adotar novo plano CPO",
        action_type="ADOPT_PLAN",
        target="draftsha",
        sandbox_result={"confidence": 80, "source": "CPO Scheduler"},
        after_state={"commit_sha": "draftsha"},
        audit_reason="Q.157.F teste",
        audit_extra={"source": "auto_propose_signals", "signal": "planning"},
    )
    assert decision.status == DecisionStatus.PROPOSED.value
    assert decision.action_type == "ADOPT_PLAN"
    assert decision.proposed_by == _SYSTEM_ACTOR
    added = sessions[0].added
    assert any(isinstance(a, SharedDecisionRun) for a in added)
    assert any(isinstance(a, AuditLog) for a in added), "audit na mesma tx"


# ───────────────────────── 2 — Planeamento (CPO) ──────────────────────────

def _commit(status, sha, makespan, late, ti=0.0, eur=None):
    kpis = {"makespan_hours": makespan, "num_late_orders": late}
    if eur is not None:
        kpis["throughput_eur_day"] = eur
    return SimpleNamespace(status=status, commit_sha256=sha, kpis=kpis, trust_index=ti)


@pytest.mark.asyncio
async def test_planning_proposes_adopt_when_draft_better():
    draft = _commit("DRAFT", "draftsha123456", 40.0, 2)
    live = _commit("LIVE", "livesha", 50.0, 5)

    class _FakeCommits:
        def __init__(self, s, t):
            pass

        async def get_latest(self):
            return draft

        async def latest_live(self):
            return live

    with patch("src.plan.cpo.commits.CommitsService", _FakeCommits), \
         patch("src.plan.services.auto_propose_cpo_runner._cost_delta_for_commit",
               AsyncMock(return_value=120.0)):
        cands = await job._planning_candidates(object(), TENANT)

    assert len(cands) == 1
    c = cands[0]
    assert c["action_type"] == "ADOPT_PLAN"
    assert c["target"] == "draftsha123456"
    assert c["after_state"]["commit_sha"] == "draftsha123456"
    sb = c["sandbox_result"]
    assert sb["commit_sha"] == "draftsha123456"
    assert sb["cost_delta"] == 120.0
    assert sb["delta_makespan_h"] == -10.0  # 40 - 50, melhor (derivado)
    assert sb["delta_late_orders"] == -3     # 2 - 5
    assert "if_accept" in sb  # consequências derivadas dos KPIs reais


@pytest.mark.asyncio
async def test_planning_empty_when_latest_is_live():
    live = _commit("LIVE", "livesha", 50.0, 5)

    class _FakeCommits:
        def __init__(self, s, t):
            pass

        async def get_latest(self):
            return live  # mais recente já é LIVE → nada a adotar

        async def latest_live(self):
            return live

    with patch("src.plan.cpo.commits.CommitsService", _FakeCommits):
        cands = await job._planning_candidates(object(), TENANT)
    assert cands == []


@pytest.mark.asyncio
async def test_planning_proposes_latest_draft_even_if_worse():
    # O DRAFT é a proposta mais recente do CPO por aprovar → é sempre proposto;
    # os deltas mostram que é pior e a confiança fica baixa (humano decide).
    draft = _commit("DRAFT", "draftsha", 55.0, 6)  # pior que o LIVE
    live = _commit("LIVE", "livesha", 50.0, 5)

    class _FakeCommits:
        def __init__(self, s, t):
            pass

        async def get_latest(self):
            return draft

        async def latest_live(self):
            return live

    with patch("src.plan.cpo.commits.CommitsService", _FakeCommits), \
         patch("src.plan.services.auto_propose_cpo_runner._cost_delta_for_commit",
               AsyncMock(return_value=-10.0)):
        cands = await job._planning_candidates(object(), TENANT)
    assert len(cands) == 1
    sb = cands[0]["sandbox_result"]
    assert sb["delta_makespan_h"] == 5.0   # 55 - 50 (pior, mostrado honestamente)
    assert sb["confidence"] == 55          # sem sinais positivos → confiança baixa


# ───────────────────────── 3 — Expedição ──────────────────────────────────

@pytest.mark.asyncio
async def test_expedition_maps_suggestions_to_decisions():
    from src.plan.services.transport_suggestions import TransportSuggestion

    batch = SimpleNamespace(id=uuid4(), code="CAM-1")

    class _Scalars:
        def all(self):
            return [batch]

    class _Result:
        def scalars(self):
            return _Scalars()

    class _Sess:
        async def execute(self, stmt):
            return _Result()

    sug = TransportSuggestion(
        type="complete_truck", what="Completar camião CAM-1",
        why="meio vazio", if_accept="poupa um trip", if_reject="sai a meio",
    )

    class _FakeTSS:
        def __init__(self, s, t):
            pass

        async def for_batch(self, bid):
            return [sug]

    with patch("src.plan.services.transport_suggestions.TransportSuggestionsService",
               _FakeTSS):
        cands = await job._expedition_candidates(_Sess(), TENANT)

    assert len(cands) == 1
    c = cands[0]
    assert c["action_type"] == "TRUCK_CONSOLIDATE"
    assert c["target"] == "CAM-1:complete_truck"
    assert c["sandbox_result"]["why"] == "meio vazio"
    assert c["sandbox_result"]["if_accept"] == ["poupa um trip"]


# ───────────────────────── 4 — OTD ────────────────────────────────────────

@pytest.mark.asyncio
async def test_otd_generator_confidence_band_and_cap():
    orders = [
        {"of_id": f"OF-{i}", "late_probability": 0.80 + i * 0.01,
         "risk_band": "alto", "transport_date": "2026-06-10",
         "features": {"slack_days": -2}, "current_phase_name": "Pintura"}
        for i in range(5)
    ] + [
        {"of_id": "OF-LOW", "late_probability": 0.10, "risk_band": "baixo",
         "transport_date": "2026-07-01", "features": {"slack_days": 30}},
    ]

    class _FakeOTD:
        def __init__(self, s, t):
            pass

        async def otd_risk(self, *, top_n=50):
            return {"model_available": True, "orders": orders}

    with patch("src.plan.services.otd_risk_service.OTDRiskService", _FakeOTD):
        cands = await job._otd_reschedule_candidates(object(), TENANT)

    assert len(cands) == job._OTD_MAX_PER_TICK
    assert all(c["action_type"] == "OTD_RESCHEDULE" for c in cands)
    assert "OF-LOW" not in {c["target"] for c in cands}
    assert cands[0]["sandbox_result"]["confidence"] == round(0.80 * 100)


@pytest.mark.asyncio
async def test_otd_generator_no_model_is_empty_honest():
    class _FakeOTD:
        def __init__(self, s, t):
            pass

        async def otd_risk(self, *, top_n=50):
            return {"model_available": False, "orders": []}

    with patch("src.plan.services.otd_risk_service.OTDRiskService", _FakeOTD):
        cands = await job._otd_reschedule_candidates(object(), TENANT)
    assert cands == []


# ───────────────────────── 5 — Job: dedup + rate-limit ────────────────────

@asynccontextmanager
async def _ctx_session():
    yield FakeSession()


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
async def test_job_blocked_skips_existing_target():
    job._rate_limiter._last_seen.clear()
    persisted = AsyncMock()
    with patch.object(job, "_resolve_tenants", AsyncMock(return_value=[TENANT])), \
         patch("src.shared.database.get_session_context", _ctx_session), \
         patch("src.shared.database.async_session_factory", _factory([])), \
         patch.object(job, "_enabled", AsyncMock(return_value=True)), \
         patch.object(job, "_planning_candidates",
                      AsyncMock(return_value=[_one_candidate()])), \
         patch.object(job, "_expedition_candidates", AsyncMock(return_value=[])), \
         patch.object(job, "_otd_reschedule_candidates", AsyncMock(return_value=[])), \
         patch.object(job, "_supersede_stale_adopt_plans", AsyncMock(return_value=0)), \
         patch.object(job, "_blocked_targets",
                      AsyncMock(return_value={("ADOPT_PLAN", "draftsha-1")})), \
         patch.object(job, "propose_decision_row", persisted):
        await job._auto_propose_signals_job([TENANT])
    persisted.assert_not_called()  # target já existe (qq status) → não re-propõe


@pytest.mark.asyncio
async def test_job_creates_then_rate_limits_second_tick():
    job._rate_limiter._last_seen.clear()
    persisted = AsyncMock()
    ps = (
        patch.object(job, "_resolve_tenants", AsyncMock(return_value=[TENANT])),
        patch("src.shared.database.get_session_context", _ctx_session),
        patch("src.shared.database.async_session_factory", _factory([])),
        patch.object(job, "_enabled", AsyncMock(return_value=True)),
        patch.object(job, "_planning_candidates",
                     AsyncMock(return_value=[_one_candidate()])),
        patch.object(job, "_expedition_candidates", AsyncMock(return_value=[])),
        patch.object(job, "_otd_reschedule_candidates", AsyncMock(return_value=[])),
        patch.object(job, "_supersede_stale_adopt_plans", AsyncMock(return_value=0)),
        patch.object(job, "_blocked_targets", AsyncMock(return_value=set())),
        patch.object(job, "propose_decision_row", persisted),
    )
    for p in ps:
        p.start()
    try:
        await job._auto_propose_signals_job([TENANT])  # cria
        await job._auto_propose_signals_job([TENANT])  # rate-limited
    finally:
        for p in ps:
            p.stop()
    assert persisted.await_count == 1


# ───────────────────────── 6 — Supersede ADOPT_PLAN obsoletos ──────────────

@pytest.mark.asyncio
async def test_supersede_rejects_stale_adopt_plans_keeps_latest():
    from src.core.models.audit import AuditLog

    keep = SimpleNamespace(id=uuid4(), target="shaKEEP",
                           status="PROPOSED", action_type="ADOPT_PLAN")
    stale = SimpleNamespace(id=uuid4(), target="shaOLD",
                            status="PROPOSED", action_type="ADOPT_PLAN")

    class _Scalars:
        def all(self):
            return [keep, stale]

    class _Result:
        def scalars(self):
            return _Scalars()

    class _Sess:
        def __init__(self):
            self.added: List[Any] = []
            self.committed = False

        async def execute(self, stmt):
            return _Result()

        def add(self, o):
            self.added.append(o)

        async def flush(self):
            for o in self.added:
                if getattr(o, "id", None) is None:
                    object.__setattr__(o, "id", uuid4())

        async def commit(self):
            self.committed = True

    sess = _Sess()

    @asynccontextmanager
    async def _factory_one():
        yield sess

    n = await job._supersede_stale_adopt_plans(_factory_one, TENANT, "shaKEEP")
    assert n == 1
    assert keep.status == "PROPOSED"    # o plano mais recente fica
    assert stale.status == "REJECTED"   # o antigo é superseded
    assert sess.committed
    assert any(isinstance(a, AuditLog) for a in sess.added), "audit do supersede"


@pytest.mark.asyncio
async def test_supersede_all_when_keep_sha_none():
    a1 = SimpleNamespace(id=uuid4(), target="sha1", status="PROPOSED",
                         action_type="ADOPT_PLAN")

    class _Sess:
        def __init__(self):
            self.added: List[Any] = []

        async def execute(self, stmt):
            class _R:
                def scalars(self_):
                    class _S:
                        def all(self__):
                            return [a1]
                    return _S()
            return _R()

        def add(self, o):
            self.added.append(o)

        async def flush(self):
            pass

        async def commit(self):
            pass

    @asynccontextmanager
    async def _factory_one():
        yield _Sess()

    # keep_sha=None → não há DRAFT por adotar → supersede TODOS.
    n = await job._supersede_stale_adopt_plans(_factory_one, TENANT, None)
    assert n == 1
    assert a1.status == "REJECTED"
