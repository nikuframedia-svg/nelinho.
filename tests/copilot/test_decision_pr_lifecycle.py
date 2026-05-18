"""
Q.37.C — testes do ciclo de vida do Decision PR.

Cobre PENDING → APPROVED → EXECUTED e a barreira SoD (aprovador !=
proponente → 403). Só testes unitários: as funções do router são
chamadas directamente com um FakeSession (sem Postgres).
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from src.copilot.actions import clear_action_handlers, register_action_handler
from src.copilot.api_endpoints import decision_pr_api as pr_api
from src.shared.auth.jwt_handler import UserContext

TENANT = UUID("00000000-0000-0000-0000-000000000001")
PROPOSER = UUID("00000000-0000-0000-0000-0000000000aa")
APPROVER = UUID("00000000-0000-0000-0000-0000000000bb")


# ─────────────────────────────────────────────────────────────────────
# Fakes
# ─────────────────────────────────────────────────────────────────────

class _EmptyResult:
    """Resultado de `execute` vazio — `_capture_state` tolera-o."""

    def scalars(self):
        return self

    def all(self):
        return []

    def scalar(self):
        return 0

    def scalar_one_or_none(self):
        return None


class FakeSession:
    """Sessão mínima: `get` resolve por id, `execute` devolve vazio."""

    def __init__(self, objects=None):
        self._objects = {}
        for obj in objects or []:
            self._objects[obj.id] = obj
        self.committed = False
        self.added = []

    async def get(self, _model, obj_id):
        return self._objects.get(obj_id)

    async def execute(self, _query):
        return _EmptyResult()

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass

    async def flush(self):
        pass

    def add(self, obj):
        self.added.append(obj)


def _make_pr(status="PENDING", action_type="adjust_inventory", payload=None):
    base_payload = {"action_type": action_type, "title": "PR teste"}
    if payload:
        base_payload.update(payload)
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT,
        suggestion_id=uuid4(),
        title="PR teste",
        description="descrição",
        status=status,
        payload=base_payload,
        approved_by=None,
        approved_at=None,
        created_at=datetime.now(timezone.utc),
    )


def _make_suggestion(actor_id, actor_role="manager_operations"):
    return SimpleNamespace(
        id=uuid4(),
        actor_id=actor_id,
        actor_role=actor_role,
        tenant_id=TENANT,
    )


def _user(user_id, role="manager_operations"):
    return UserContext(user_id=user_id, tenant_id=TENANT, role=role)


# ─────────────────────────────────────────────────────────────────────
# Listar / obter
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_decision_pr_not_found_devolve_404():
    session = FakeSession()
    with pytest.raises(HTTPException) as exc:
        await pr_api.get_decision_pr(uuid4(), _user(APPROVER), TENANT, session)
    assert exc.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# Approve — SoD
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_approve_pelo_proponente_e_403_sod():
    """O proponente NÃO pode aprovar a sua própria proposta."""
    pr = _make_pr()
    suggestion = _make_suggestion(actor_id=PROPOSER)
    pr.suggestion_id = suggestion.id
    session = FakeSession([pr, suggestion])

    with pytest.raises(HTTPException) as exc:
        # Aprovador == proponente.
        await pr_api.approve_decision_pr(
            pr.id, _user(PROPOSER), TENANT, session
        )
    assert exc.value.status_code == 403
    assert "Segregation of Duties" in exc.value.detail
    assert pr.status == "PENDING"  # não mudou


@pytest.mark.asyncio
async def test_approve_por_outro_user_passa_para_approved():
    pr = _make_pr()
    suggestion = _make_suggestion(actor_id=PROPOSER)
    pr.suggestion_id = suggestion.id
    session = FakeSession([pr, suggestion])

    result = await pr_api.approve_decision_pr(
        pr.id, _user(APPROVER), TENANT, session
    )
    assert result["status"] == "APPROVED"
    assert result["approved_by"] == str(APPROVER)
    assert pr.status == "APPROVED"
    assert session.committed is True


@pytest.mark.asyncio
async def test_approve_pr_nao_pending_devolve_409():
    pr = _make_pr(status="APPROVED")
    suggestion = _make_suggestion(actor_id=PROPOSER)
    pr.suggestion_id = suggestion.id
    session = FakeSession([pr, suggestion])

    with pytest.raises(HTTPException) as exc:
        await pr_api.approve_decision_pr(
            pr.id, _user(APPROVER), TENANT, session
        )
    assert exc.value.status_code == 409


# ─────────────────────────────────────────────────────────────────────
# Reject
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reject_marca_rejected_e_grava_rejected_by():
    pr = _make_pr()
    session = FakeSession([pr])

    result = await pr_api.reject_decision_pr(
        pr.id, _user(APPROVER), TENANT, session
    )
    assert result["status"] == "REJECTED"
    assert result["rejected_by"] == str(APPROVER)
    assert pr.payload["rejected_by"] == str(APPROVER)


# ─────────────────────────────────────────────────────────────────────
# Execute
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_pr_nao_approved_devolve_409():
    pr = _make_pr(status="PENDING")
    session = FakeSession([pr])

    with pytest.raises(HTTPException) as exc:
        await pr_api.execute_decision_pr(
            pr.id, _user(APPROVER), TENANT, session
        )
    assert exc.value.status_code == 409
    assert "APPROVED" in exc.value.detail


@pytest.mark.asyncio
async def test_execute_ciclo_completo_chama_handler_e_marca_executed():
    """Ciclo completo: APPROVED → execute → handler corre → EXECUTED."""
    clear_action_handlers()

    handler_calls = []

    async def _fake_handler(executor, action, plan_id):
        handler_calls.append(action.type)
        return {"products": [], "ok": True}

    register_action_handler("adjust_inventory", _fake_handler, overwrite=True)

    pr = _make_pr(status="APPROVED")
    session = FakeSession([pr])

    result = await pr_api.execute_decision_pr(
        pr.id, _user(APPROVER), TENANT, session
    )

    assert result["status"] == "EXECUTED"
    assert result["executed_by"] == str(APPROVER)
    assert handler_calls == ["adjust_inventory"]
    assert pr.status == "EXECUTED"
    assert pr.payload["execution_result"]["status"] == "executed"

    clear_action_handlers()


@pytest.mark.asyncio
async def test_execute_sem_handler_devolve_501():
    """action_type sem handler registado → 501 (não finge sucesso)."""
    clear_action_handlers()
    pr = _make_pr(status="APPROVED", action_type="nao_existe")
    session = FakeSession([pr])

    with pytest.raises(HTTPException) as exc:
        await pr_api.execute_decision_pr(
            pr.id, _user(APPROVER), TENANT, session
        )
    assert exc.value.status_code == 501


@pytest.mark.asyncio
async def test_execute_handler_rejeita_devolve_422():
    """Handler que levanta ValueError (ex.: axioma 7) → 422."""
    clear_action_handlers()

    async def _rejecting_handler(executor, action, plan_id):
        raise ValueError("safety_stock abaixo do baseline (axioma 7)")

    register_action_handler("adjust_inventory", _rejecting_handler, overwrite=True)

    pr = _make_pr(status="APPROVED")
    session = FakeSession([pr])

    with pytest.raises(HTTPException) as exc:
        await pr_api.execute_decision_pr(
            pr.id, _user(APPROVER), TENANT, session
        )
    assert exc.value.status_code == 422
    assert "axioma 7" in exc.value.detail

    clear_action_handlers()
