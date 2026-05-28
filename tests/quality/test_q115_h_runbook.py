"""Q.115.H — testes de runbooks aprendidos + action type EXECUTE_RUNBOOK.

8 testes conforme especificação:
1. Happy path: 100 rework_entries → 1 runbook learned + 1 link, confidence > 0.5
2. Aprovar: approve_runbook → approved_by + approved_at + audit_trace_id
3. Endpoint: GET /v1/quality/runbook?error_code=X → lista correcta
4. Endpoint vazio: error_code sem runbook → []
5. Action EXECUTE_RUNBOOK com runbook não aprovado → DispatchResult failed
6. Action EXECUTE_RUNBOOK com runbook aprovado + confidence >= 0.8 → Decision pendente
7. Sample insuficiente (<10 entradas) → None (silent skip)
8. Dispatcher round-trip: action em rule_schema mirror em ruleHelpers.ts

Padrão FakeSession (Q.61.02) — sem PostgreSQL, sem SQLite.
"""
from __future__ import annotations

import re
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from src.governance.yaml_policy.dispatchers import (
    ACTION_WIRING,
    DispatchContext,
    _dispatch_execute_runbook,
)
from src.governance.yaml_policy.rule_schema import ActionStep, ActionType, Rule, TriggerSpec
from src.quality.services.runbook_service import (
    MIN_SAMPLES,
    approve_runbook,
    learn_runbook_from_history,
)
from tests.conftest import FakeSession

TENANT = uuid4()
ERROR_CODE = "DEF-TEST-001"

FRONTEND_FILE = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "src"
    / "components"
    / "regras"
    / "ruleHelpers.ts"
)


# ---------------------------------------------------------------------------
# Helpers — objectos simples (SimpleNamespace para evitar ORM overhead)
# ---------------------------------------------------------------------------


def _entry(error_code: str = ERROR_CODE, i: int = 0) -> types.SimpleNamespace:
    base = datetime.now(timezone.utc) - timedelta(days=10)
    return types.SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT,
        of_id=f"OF-{i:04d}",
        error_code=error_code,
        detected_at=base - timedelta(hours=i),
        root_cause_category="material_defeituoso",
        rework_op_id=f"OP-{(i % 3) + 1:03d}",
        phase_id_causer="laminagem",
        phase_id_rework="retrabalho_laminagem",
    )


def _make_entries(n: int, error_code: str = ERROR_CODE) -> list:
    return [_entry(error_code, i) for i in range(n)]


def _runbook(
    *,
    approved: bool = False,
    confidence: float = 0.85,
    error_code: str = ERROR_CODE,
) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT,
        error_code=error_code,
        steps_md=f"## Passos para {error_code}\n1. Verificar material.",
        source="learned",
        confidence=confidence,
        approved_by="luis@nikufra.ai" if approved else None,
        approved_at=datetime.now(timezone.utc) if approved else None,
        audit_trace_id=None,
        created_at=datetime.now(timezone.utc),
    )


def _make_rule() -> Rule:
    return Rule(
        id="test-execute-runbook",
        description="Testa dispatch execute_runbook",
        when=TriggerSpec(event="quality_event_logged"),
        then=[
            ActionStep(
                action=ActionType.EXECUTE_RUNBOOK,
                params={"runbook_id": str(uuid4()), "on_event": "quality_event_logged"},
            )
        ],
    )


# ---------------------------------------------------------------------------
# Teste 1 — happy path: 100 entradas → runbook aprendido
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_learn_runbook_happy_path():
    """100 rework_entries com mesmo error_code → 1 runbook + 1 link, confidence > 0.5."""
    entries = _make_entries(100)
    session = FakeSession()

    # execute() #1 — select ReworkEntry → scalars().all() → 100 entradas
    session.queue_scalars(entries)
    # execute() #2 — select Runbook existente → scalar_one_or_none() → None
    session.queue_scalar(None)
    # execute() #3 — delete ErrorTypeRunbookLink → não consumido pelo add(link)
    # O delete usa session.execute(); a FakeSession devolve scalar=None scalars=[]
    session.queue_scalar(None)

    runbook = await learn_runbook_from_history(
        session=session,
        tenant_id=TENANT,
        error_code=ERROR_CODE,
    )

    assert runbook is not None
    assert runbook.error_code == ERROR_CODE
    assert runbook.source == "learned"
    assert runbook.approved_by is None  # requer aprovação humana
    assert runbook.confidence > 0.5
    assert "material_defeituoso" in runbook.steps_md
    assert ERROR_CODE in runbook.steps_md

    # Runbook + link adicionados à sessão
    added_types = [type(o).__name__ for o in session.added]
    assert "Runbook" in added_types
    assert "ErrorTypeRunbookLink" in added_types


# ---------------------------------------------------------------------------
# Teste 2 — aprovação escreve audit_trace_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_runbook_writes_audit():
    """approve_runbook → approved_by + approved_at + audit_trace_id preenchidos."""
    rb = _runbook(approved=False)

    session = FakeSession()
    session.queue_scalar(rb)  # select Runbook por id

    updated = await approve_runbook(
        session=session,
        tenant_id=TENANT,
        runbook_id=rb.id,
        approved_by="luis@nikufra.ai",
        notes="aprovado após revisão",
    )

    assert updated.approved_by == "luis@nikufra.ai"
    assert updated.approved_at is not None
    assert "approve_runbook" in (updated.audit_trace_id or "")
    assert "luis@nikufra.ai" in (updated.audit_trace_id or "")


# ---------------------------------------------------------------------------
# Testes 3 e 4 — endpoints HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_endpoint_list_runbooks_by_error_code():
    """GET /v1/quality/runbook?error_code=X devolve lista correcta."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.quality.api import get_tenant_id, router
    from src.shared.database import get_session

    rb = _runbook(approved=True, confidence=0.9, error_code="DEF-ENDPOINT-001")

    session = FakeSession()
    # GET com error_code faz join → result.all() retorna lista de tuplos (runbook, priority)
    session.queue_scalars([(rb, 1)])

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_tenant_id] = lambda: TENANT

    with TestClient(app) as client:
        resp = client.get("/v1/quality/runbook?error_code=DEF-ENDPOINT-001")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["error_code"] == "DEF-ENDPOINT-001"
    assert abs(data[0]["confidence"] - 0.9) < 0.001
    assert data[0]["approved_by"] == "luis@nikufra.ai"


@pytest.mark.asyncio
async def test_endpoint_list_runbooks_empty():
    """error_code sem runbook → lista vazia []."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.quality.api import get_tenant_id, router
    from src.shared.database import get_session

    session = FakeSession()
    session.queue_scalars([])

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_tenant_id] = lambda: TENANT

    with TestClient(app) as client:
        resp = client.get("/v1/quality/runbook?error_code=NONEXISTENT-CODE")

    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Testes 5 e 6 — dispatcher execute_runbook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_execute_runbook_not_approved():
    """Runbook não aprovado → DispatchResult status='failed'."""
    rb = _runbook(approved=False, confidence=0.9)

    session = FakeSession()
    session.queue_scalar(rb)  # select Runbook por id

    rule = _make_rule()
    rule.then[0].params["runbook_id"] = str(rb.id)

    ctx = DispatchContext(
        tenant_id=TENANT,
        event_type="quality_event_logged",
        event_payload={},
        session=session,
    )
    result = await _dispatch_execute_runbook(rule, rule.then[0].params, ctx)

    assert result.status == "failed"
    assert "não aprovado" in (result.detail or "")


@pytest.mark.asyncio
async def test_dispatch_execute_runbook_approved_creates_decision():
    """Runbook aprovado + confidence >= 0.8 → DispatchResult ok + decision criado."""
    rb = _runbook(approved=True, confidence=0.85, error_code="DEF-DISPATCH-002")

    session = FakeSession()
    session.queue_scalar(rb)  # select Runbook por id

    rule = _make_rule()
    rule.then[0].params["runbook_id"] = str(rb.id)

    created_decisions: list[dict] = []

    async def _fake_create_decision(data: dict) -> str:
        created_decisions.append(data)
        return str(uuid4())

    ctx = DispatchContext(
        tenant_id=TENANT,
        event_type="quality_event_logged",
        event_payload={},
        session=session,
        create_decision=_fake_create_decision,
    )
    result = await _dispatch_execute_runbook(rule, rule.then[0].params, ctx)

    assert result.status == "ok"
    assert len(created_decisions) == 1
    assert created_decisions[0]["decision_type"] == "execute_runbook"
    assert "runbook_steps" in created_decisions[0]["action_data"]


# ---------------------------------------------------------------------------
# Teste 7 — sample insuficiente
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_learn_runbook_insufficient_samples():
    """Menos de MIN_SAMPLES entradas → devolve None (silent skip)."""
    entries = _make_entries(MIN_SAMPLES - 1, error_code="DEF-SPARSE-001")
    session = FakeSession()
    session.queue_scalars(entries)

    result = await learn_runbook_from_history(
        session=session,
        tenant_id=TENANT,
        error_code="DEF-SPARSE-001",
    )

    assert result is None


# ---------------------------------------------------------------------------
# Teste 8 — round-trip: backend + frontend em sync
# ---------------------------------------------------------------------------


def test_execute_runbook_action_wiring_roundtrip():
    """ACTION_WIRING backend tem execute_runbook E frontend espelha (Q.61.04 pattern)."""
    # Backend
    assert "execute_runbook" in ACTION_WIRING, (
        "execute_runbook em falta no ACTION_WIRING do backend (dispatchers.py)"
    )
    assert ACTION_WIRING["execute_runbook"]["wired"] is True

    # Frontend
    assert FRONTEND_FILE.exists(), f"ruleHelpers.ts não encontrado em {FRONTEND_FILE}"
    source = FRONTEND_FILE.read_text(encoding="utf-8")

    match = re.search(
        r"ACTION_WIRING\s*:\s*Record<string,\s*boolean>\s*=\s*\{(?P<body>[^}]+)\}",
        source,
        re.DOTALL,
    )
    assert match, "Bloco ACTION_WIRING não encontrado no ruleHelpers.ts"

    frontend_wiring: dict[str, bool] = {}
    for line in match.group("body").splitlines():
        line = re.sub(r"//.*$", "", line).strip().rstrip(",").strip()
        if not line:
            continue
        m = re.match(r"['\"]?(?P<key>[\w_]+)['\"]?\s*:\s*(?P<val>true|false)\s*$", line)
        if m:
            frontend_wiring[m.group("key")] = m.group("val") == "true"

    assert "execute_runbook" in frontend_wiring, (
        "execute_runbook em falta no ACTION_WIRING do frontend (ruleHelpers.ts)"
    )
    assert frontend_wiring["execute_runbook"] is True

    # ActionType enum tem a nova entrada
    assert ActionType.EXECUTE_RUNBOOK.value == "execute_runbook"
