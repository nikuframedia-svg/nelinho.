"""Q.61.09 — regressao SoD: propose nao cria self-approval.

Bug historico (decisions.py:127): o `POST /v1/decisions/propose` criava
sempre um `DecisionApproval` com `approver_id = user_id` (o proposer).
O check de SoD no `/approve` impedia que esse mesmo user aprovasse,
mas:
  * `GET /v1/decisions/{id}` listava o placeholder, dando a ilusao
    de que ja havia 1 aprovador pendente.
  * Se alguem retirasse o `check_sod()`, o proposer aprovaria-se a si
    proprio sem mais nada (defesa em depth perdida).

Q.61.09 fixa as duas coisas:
  * Propose deixa de criar `DecisionApproval`. A tabela passa a
    conter so aprovacoes reais.
  * Approve usa `find_or_create` no row do approver autenticado.

Os tests deste ficheiro pinam exactamente isto.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.api.decisions import router as decisions_router
from src.shared.database import get_session
from src.shared.models.governance import (
    ApprovalStatus,
    DecisionApproval,
    DecisionStatus,
)


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROPOSER = UUID("11111111-1111-1111-1111-111111111111")
APPROVER = UUID("22222222-2222-2222-2222-222222222222")


# ─── propose path: nao cria DecisionApproval ─────────────────────────────


class _ProposeSession:
    """AsyncSession stand-in que captura adds e flushes."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushes = 0
        self.commits = 0

    def add(self, obj: Any) -> None:
        # decision.id e atribuido aqui (no real, pelo flush).
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = uuid4()
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1


def _propose_app(session: _ProposeSession) -> FastAPI:
    app = FastAPI()
    app.include_router(decisions_router, prefix="/v1/shared")

    async def _fake_session():
        yield session

    app.dependency_overrides[get_session] = _fake_session
    return app


def test_propose_does_not_create_self_approval():
    """Regression Q.61.09: propose deixa a tabela decision_approvals vazia.

    Bug historico criava aqui um `DecisionApproval(approver_id=user_id, ...)`.
    Esse placeholder e o defeito original."""
    session = _ProposeSession()
    client = TestClient(_propose_app(session))

    resp = client.post(
        "/v1/shared/decisions/propose",
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": str(PROPOSER),
        },
        json={
            "title": "Pin SoD",
            "action_type": "GENERIC_ACTION",
            "target": "test-target",
            "sandbox_result": {},
            "before_state": {},
            "after_state": {},
        },
    )
    assert resp.status_code == 201, resp.text
    # Apenas o DecisionRun foi adicionado — nada de DecisionApproval.
    types_added = [type(obj).__name__ for obj in session.added]
    assert types_added == ["SharedDecisionRun"], (
        f"propose adicionou {types_added!r}; esperado apenas "
        f"['SharedDecisionRun']. Regressao do Q.61.09 — voltou a criar "
        f"DecisionApproval no propose."
    )


def test_propose_response_shape_unchanged():
    """O contrato publico do endpoint nao mudou (frontend continua a ler)."""
    session = _ProposeSession()
    client = TestClient(_propose_app(session))

    resp = client.post(
        "/v1/shared/decisions/propose",
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": str(PROPOSER),
        },
        json={
            "title": "Shape",
            "action_type": "GENERIC_ACTION",
            "target": "t",
            "sandbox_result": {},
            "before_state": {},
            "after_state": {},
        },
    )
    body = resp.json()
    assert set(body) == {"id", "status", "message"}
    assert body["status"] == "proposed"


# ─── approve path: find_or_create + check_sod() ─────────────────────────


class _ApproveSession:
    """Stand-in para approve: tem `get` (decision) e `execute` (select)."""

    def __init__(self, decision, existing_approval=None) -> None:
        self.decision = decision
        self.existing_approval = existing_approval
        self.added: list[Any] = []
        self.commits = 0
        self.flushes = 0

    async def get(self, _model, _id):
        return self.decision

    async def execute(self, _stmt):
        existing = self.existing_approval

        class _R:
            def scalar_one_or_none(self_inner):
                return existing

        return _R()

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1


def _approve_app(session) -> FastAPI:
    app = FastAPI()
    app.include_router(decisions_router, prefix="/v1/shared")

    async def _fake_session():
        yield session

    app.dependency_overrides[get_session] = _fake_session
    return app


def test_approve_creates_one_approval_for_authenticated_user():
    """Approver != proposer + sem approval previa => INSERT 1 DecisionApproval."""
    decision = SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT,
        action_type="GENERIC_ACTION",
        status=DecisionStatus.PROPOSED.value,
        proposed_by=PROPOSER,
    )
    session = _ApproveSession(decision, existing_approval=None)
    client = TestClient(_approve_app(session))

    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/approve",
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": str(APPROVER),
        },
        json={"comment": "OK"},
    )
    assert resp.status_code == 200, resp.text

    approvals = [
        obj for obj in session.added if isinstance(obj, DecisionApproval)
    ]
    assert len(approvals) == 1, (
        f"esperado 1 DecisionApproval, encontrei {len(approvals)}: "
        f"{[(a.approver_id, a.status) for a in approvals]!r}"
    )
    assert approvals[0].approver_id == APPROVER
    assert approvals[0].status == ApprovalStatus.APPROVED.value
    assert decision.status == DecisionStatus.APPROVED.value


def test_approve_updates_existing_row_when_present():
    """Se ja existe approval do mesmo user (raro mas possivel — retry), atualiza."""
    decision = SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT,
        action_type="GENERIC_ACTION",
        status=DecisionStatus.PROPOSED.value,
        proposed_by=PROPOSER,
    )
    existing = DecisionApproval(
        decision_id=decision.id,
        approver_id=APPROVER,
        status=ApprovalStatus.PENDING.value,
        comment=None,
        approved_at=None,
    )
    session = _ApproveSession(decision, existing_approval=existing)
    client = TestClient(_approve_app(session))

    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/approve",
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": str(APPROVER),
        },
        json={"comment": "updated"},
    )
    assert resp.status_code == 200
    # Nenhuma INSERT — apenas update do row existente.
    new_approvals = [
        obj for obj in session.added if isinstance(obj, DecisionApproval)
    ]
    assert new_approvals == [], (
        f"approve com row existente nao devia adicionar novo INSERT; "
        f"foi adicionado: {new_approvals!r}"
    )
    assert existing.status == ApprovalStatus.APPROVED.value
    assert existing.comment == "updated"


def test_approve_rejects_when_approver_is_proposer():
    """SoD continua activo — proposer nao pode aprovar."""
    decision = SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT,
        action_type="GENERIC_ACTION",
        status=DecisionStatus.PROPOSED.value,
        proposed_by=PROPOSER,
    )
    session = _ApproveSession(decision, existing_approval=None)
    client = TestClient(_approve_app(session))

    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/approve",
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": str(PROPOSER),  # mesmo user que propos
        },
        json={"comment": "self"},
    )
    assert resp.status_code == 403
