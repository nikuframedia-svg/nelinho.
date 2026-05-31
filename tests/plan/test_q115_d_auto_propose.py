"""Q.115.D — Testes auto_propose listener.

8 cenários:
  1. Happy path orders.created → Decision criada com source=auto_propose
  2. Debounce: 2 eventos <30s mesma chave → 1 só Decision
  3. Rate-limit: 2 eventos dentro de 5min → 2º silenciado
  4. config.updated: replan_hook + auto_propose coexistem; só auto_propose cria Decision
  5. quality.defect_logged: defeito → Decision com payload incluindo defeito
  6. plan.manual_override: override Q.115.C → Decision criada
  7. Audit log: cada Decision tem audit row com action_type=auto_propose
  8. Falha CPO: engine erra → Decision NÃO criada

DAMP: cada teste é auto-suficiente com payload completo.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from src.plan.services.auto_propose import AutoProposeService, _debounce_key
from src.plan.services.debouncer import Debouncer
from src.plan.services.rate_limiter import RateLimiter
from src.plan.services.replan_hook import handle_config_updated, should_trigger_replan
from src.shared.models.governance import DecisionStatus, SharedDecisionRun

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

TENANT = UUID("11111111-1111-1111-1111-111111111111")


class FakeSession:
    """Session mínima para capturar add() + flush()."""

    def __init__(self) -> None:
        self.added: List[Any] = []
        self.flush_calls = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flush_calls += 1
        # Atribui id fictício ao objecto adicionado mais recentemente
        for obj in self.added:
            if not hasattr(obj, "id") or obj.id is None:
                object.__setattr__(obj, "id", uuid4())

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    def begin_nested(self):
        return _FakeNested()


class _FakeNested:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


@asynccontextmanager
async def _fake_session_factory_cm(captured: List[FakeSession]):
    """Session factory que regista a sessão criada para inspecção."""
    session = FakeSession()
    captured.append(session)
    yield session


def _build_service(
    sessions: List[FakeSession],
    *,
    debounce_delay: float = 0.0,
    cpo_runner=None,
) -> AutoProposeService:
    """Constrói AutoProposeService com deps injectadas."""

    @asynccontextmanager
    async def _factory():
        session = FakeSession()
        sessions.append(session)
        yield session

    return AutoProposeService(
        session_factory=_factory,
        rate_limiter=RateLimiter(window=timedelta(minutes=5)),
        debouncer=Debouncer(delay_seconds=debounce_delay),
        cpo_engine_runner=cpo_runner,
    )


async def _fake_cpo_ok(tenant_id: UUID, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"commit_sha": "abc123def456", "kpis": {"throughput_eur_day": 32000.0}, "operations": []}


async def _fake_cpo_fail(tenant_id: UUID, payload: Dict[str, Any]) -> Dict[str, Any]:
    raise RuntimeError("CPO falhou — teste simulado")


def _payload_orders_created(of_id: str = "OF-001") -> Dict[str, Any]:
    return {"tenant_id": str(TENANT), "of_id": of_id, "model_id": "kayak_X"}


def _payload_config_updated(config_key: str = "routing.templates") -> Dict[str, Any]:
    return {
        "tenant_id": str(TENANT),
        "config_key": config_key,
        "config_type": "tenant_configuration.planning",
        "affected_entities": [config_key],
    }


def _payload_defect_logged(boat_id: str = "OF-042") -> Dict[str, Any]:
    return {
        "tenant_id": str(TENANT),
        "boat_id": boat_id,
        "error_code": "BOLHA_PINTURA",
        "severity": "medium",
    }


def _payload_manual_override(commit_sha: str = "deadbeef") -> Dict[str, Any]:
    return {
        "tenant_id": str(TENANT),
        "commit_sha": commit_sha,
        "operation_id": "op-99",
        "from_phase": "PINTURA",
        "to_phase": "ACABAMENTO",
    }


# ---------------------------------------------------------------------------
# Teste 1 — Happy path orders.created
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orders_created_happy_path():
    """orders.created → após debounce (delay=0), Decision criada com source=auto_propose."""
    sessions: List[FakeSession] = []
    svc = _build_service(sessions, debounce_delay=0.0, cpo_runner=_fake_cpo_ok)

    await svc.handle_event("orders.created", _payload_orders_created("OF-001"))
    # delay=0 → callback dispara imediatamente após yield de controlo
    await asyncio.sleep(0.01)

    assert len(sessions) == 1, "deve criar exactamente 1 sessão"
    added = sessions[0].added
    decisions = [a for a in added if isinstance(a, SharedDecisionRun)]
    assert len(decisions) == 1
    d = decisions[0]
    assert d.status == DecisionStatus.PROPOSED.value
    assert d.action_type == "AUTO_PROPOSE_SCHEDULE"
    assert "OF-001" in d.title
    # after_state deve ter o commit_sha do CPO
    assert d.after_state.get("commit_sha") == "abc123def456"


# ---------------------------------------------------------------------------
# Teste 2 — Debounce: 2 eventos seguidos → 1 só Decision
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_debounce_two_events_same_key_one_decision():
    """2 eventos com mesma chave em <delay → timer reseta → só 1 Decision."""
    sessions: List[FakeSession] = []
    svc = _build_service(sessions, debounce_delay=0.05, cpo_runner=_fake_cpo_ok)

    await svc.handle_event("orders.created", _payload_orders_created("OF-002"))
    await asyncio.sleep(0.01)  # ainda dentro do delay
    await svc.handle_event("orders.created", _payload_orders_created("OF-002"))

    # Espera o timer do segundo evento disparar
    await asyncio.sleep(0.1)

    decisions_total = sum(
        1 for s in sessions for a in s.added if isinstance(a, SharedDecisionRun)
    )
    assert decisions_total == 1, f"esperado 1 Decision, obtido {decisions_total}"


# ---------------------------------------------------------------------------
# Teste 3 — Rate-limit: 2 eventos distintos dentro de 5min → 2º silenciado
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limit_second_event_dropped():
    """2 eventos com mesma chave e rate-limiter pré-preenchido → 2º silenciado."""
    sessions: List[FakeSession] = []
    svc = _build_service(sessions, debounce_delay=0.0, cpo_runner=_fake_cpo_ok)

    # Pré-registar chave no rate-limiter (simula Decision já criada há pouco)
    key = _debounce_key("orders.created", _payload_orders_created("OF-003"))
    svc._rate_limiter.record(key)

    await svc.handle_event("orders.created", _payload_orders_created("OF-003"))
    await asyncio.sleep(0.05)

    # Nenhuma sessão deve ter sido criada (rate-limited antes do persist)
    decisions_total = sum(
        1 for s in sessions for a in s.added if isinstance(a, SharedDecisionRun)
    )
    assert decisions_total == 0, "rate-limited: não deve criar Decision"


# ---------------------------------------------------------------------------
# Teste 4 — config.updated: replan_hook + auto_propose coexistem
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_config_updated_replan_hook_and_auto_propose_coexist():
    """replan_hook invoca scheduler_hook; auto_propose cria Decision. Sem duplicação."""
    sessions: List[FakeSession] = []
    svc = _build_service(sessions, debounce_delay=0.0, cpo_runner=_fake_cpo_ok)

    # replan_hook parte pura (predicado)
    payload = _payload_config_updated("machine_capacity_h_day")
    assert should_trigger_replan({"config_type": "machine_rates"}) is True

    scheduler_called = []

    async def _mock_scheduler(**kwargs):
        scheduler_called.append(kwargs)

    await handle_config_updated(
        {"config_type": "machine_rates"},
        tenant_id=TENANT,
        scheduler_hook=_mock_scheduler,
    )
    # replan_hook invocou scheduler
    assert len(scheduler_called) == 1, "replan_hook deve ter chamado scheduler"

    # auto_propose cria Decision separadamente
    await svc.handle_event("config.updated", payload)
    await asyncio.sleep(0.05)

    decisions = [a for s in sessions for a in s.added if isinstance(a, SharedDecisionRun)]
    assert len(decisions) == 1, "auto_propose deve criar 1 Decision independente"
    # replan_hook NÃO criou Decisions (sessions do svc só têm a Decision do auto_propose)
    assert all(d.action_type == "AUTO_PROPOSE_SCHEDULE" for d in decisions)


# ---------------------------------------------------------------------------
# Teste 5 — quality.defect_logged
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_defect_logged_creates_decision_with_payload():
    """quality.defect_logged → Decision com payload de defeito."""
    sessions: List[FakeSession] = []
    svc = _build_service(sessions, debounce_delay=0.0, cpo_runner=_fake_cpo_ok)

    payload = _payload_defect_logged("OF-042")
    await svc.handle_event("quality.defect_logged", payload)
    await asyncio.sleep(0.05)

    decisions = [a for s in sessions for a in s.added if isinstance(a, SharedDecisionRun)]
    assert len(decisions) == 1
    d = decisions[0]
    assert "OF-042" in d.title
    assert d.status == DecisionStatus.PROPOSED.value
    # sandbox_result contém o resultado CPO (inclui commit_sha)
    assert d.sandbox_result is not None
    assert "commit_sha" in d.sandbox_result


# ---------------------------------------------------------------------------
# Teste 6 — plan.manual_override
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manual_override_creates_decision():
    """plan.manual_override (Q.115.C) → Decision criada pelo auto_propose."""
    sessions: List[FakeSession] = []
    svc = _build_service(sessions, debounce_delay=0.0, cpo_runner=_fake_cpo_ok)

    payload = _payload_manual_override("deadbeef1234")
    await svc.handle_event("plan.manual_override", payload)
    await asyncio.sleep(0.05)

    decisions = [a for s in sessions for a in s.added if isinstance(a, SharedDecisionRun)]
    assert len(decisions) == 1
    d = decisions[0]
    assert "deadbeef" in d.title
    assert d.target == "deadbeef1234"


# ---------------------------------------------------------------------------
# Teste 7 — Audit log presente em cada Decision
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_log_present_for_each_decision():
    """Cada Decision tem pelo menos 1 audit row adicionado à mesma sessão."""
    sessions: List[FakeSession] = []
    svc = _build_service(sessions, debounce_delay=0.0, cpo_runner=_fake_cpo_ok)

    await svc.handle_event("orders.created", _payload_orders_created("OF-007"))
    await asyncio.sleep(0.05)

    assert len(sessions) == 1
    session = sessions[0]

    from src.core.models.audit import AuditLog
    audit_rows = [a for a in session.added if isinstance(a, AuditLog)]
    decision_rows = [a for a in session.added if isinstance(a, SharedDecisionRun)]

    assert len(decision_rows) == 1, "1 Decision esperada"
    assert len(audit_rows) >= 1, "pelo menos 1 audit_log esperado"
    # Audit deve mencionar auto_propose
    assert any("auto_propose" in (a.reason or "") for a in audit_rows), (
        "audit row deve mencionar auto_propose na razão"
    )


# ---------------------------------------------------------------------------
# Teste 8 — Falha CPO → Decision NÃO criada
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cpo_failure_no_decision_created():
    """Se CPO engine lança excepção, Decision NÃO é criada."""
    sessions: List[FakeSession] = []
    svc = _build_service(sessions, debounce_delay=0.0, cpo_runner=_fake_cpo_fail)

    await svc.handle_event("orders.created", _payload_orders_created("OF-999"))
    await asyncio.sleep(0.05)

    decisions = [a for s in sessions for a in s.added if isinstance(a, SharedDecisionRun)]
    assert decisions == [], "CPO falhou — Decision não deve ser criada"
