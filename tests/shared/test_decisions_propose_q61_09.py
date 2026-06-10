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


class _NestedTx:
    """Async context manager que mimica savepoint (Q.61.10)."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _ProposeSession:
    """AsyncSession stand-in que captura adds e flushes.

    Q.61.10: suporta `async with session.begin_nested():` — devolve
    um nested tx sem efeito real (testes nao precisam de rollback
    real, so de confirmar o que foi adicionado).
    """

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushes = 0
        self.commits = 0
        self.begin_nested_calls = 0

    def add(self, obj: Any) -> None:
        # decision.id e atribuido aqui (no real, pelo flush).
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = uuid4()
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    def begin_nested(self) -> _NestedTx:
        self.begin_nested_calls += 1
        return _NestedTx()


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
    # Apenas DecisionRun + AuditLog (Q.61.10 UoW) — NUNCA DecisionApproval.
    type_counts: dict[str, int] = {}
    for obj in session.added:
        type_counts[type(obj).__name__] = type_counts.get(type(obj).__name__, 0) + 1
    assert "DecisionApproval" not in type_counts, (
        f"propose adicionou DecisionApproval ({type_counts!r}). "
        f"Regressao do Q.61.09 — voltou a criar placeholder no propose."
    )
    # Sanity Q.61.10: 1 DecisionRun + 1 AuditLog (UoW invariante 7).
    assert type_counts.get("SharedDecisionRun") == 1
    assert type_counts.get("AuditLog") == 1


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


# ─── Q.61.10 — UoW: AuditLog escrito na MESMA transaccao ─────────────────


def test_propose_writes_audit_log_in_same_uow():
    """Invariante 7: cada mudanca de estado escreve AuditLog na mesma tx.

    Q.61.10 envolve INSERT em `async with session.begin_nested():` para
    que decision_run + audit_log committem ou rollback juntos.
    """
    from src.core.models.audit import AuditLog
    from src.shared.models.governance import SharedDecisionRun

    session = _ProposeSession()
    client = TestClient(_propose_app(session))

    resp = client.post(
        "/v1/shared/decisions/propose",
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": str(PROPOSER),
        },
        json={
            "title": "Audit",
            "action_type": "GENERIC_ACTION",
            "target": "t",
            "sandbox_result": {},
            "before_state": {},
            "after_state": {},
        },
    )
    assert resp.status_code == 201, resp.text

    # 1 DecisionRun + 1 AuditLog, na mesma sessao.
    decisions = [o for o in session.added if isinstance(o, SharedDecisionRun)]
    audits = [o for o in session.added if isinstance(o, AuditLog)]
    assert len(decisions) == 1
    assert len(audits) == 1

    # AuditLog aponta para o DecisionRun, com os campos certos.
    audit = audits[0]
    assert audit.entity_type == "decision_run"
    assert audit.entity_id == decisions[0].id
    assert audit.action == "INSERT"
    assert audit.actor_id == PROPOSER
    assert audit.tenant_id == TENANT
    assert audit.new_values is not None
    assert audit.new_values["title"] == "Audit"
    assert audit.new_values["status"] == "PROPOSED"

    # Savepoint aberto exactamente 1x (UoW).
    assert session.begin_nested_calls == 1


def test_propose_rolls_back_when_audit_fails():
    """Forca AuditLog.add a falhar; verifica que o cliente recebe 5xx
    e que o handler entra em begin_nested antes de adicionar audit
    (mesmo que o savepoint nao seja real no FakeSession, o gate e o
    `begin_nested_calls == 1` + a exception bubbling)."""
    from src.core.models.audit import AuditLog

    class _FailingAuditSession(_ProposeSession):
        def add(self, obj):
            if isinstance(obj, AuditLog):
                raise RuntimeError("simulated audit log INSERT failure")
            super().add(obj)

    session = _FailingAuditSession()
    client = TestClient(_propose_app(session), raise_server_exceptions=False)

    resp = client.post(
        "/v1/shared/decisions/propose",
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": str(PROPOSER),
        },
        json={
            "title": "Rollback",
            "action_type": "GENERIC_ACTION",
            "target": "t",
            "sandbox_result": {},
            "before_state": {},
            "after_state": {},
        },
    )
    # FastAPI converte a RuntimeError em 500. O ponto e: nao 201.
    assert resp.status_code == 500
    # begin_nested foi aberto (UoW entrou); a propagacao da excepcao
    # garante rollback do savepoint pelo SQLAlchemy real.
    assert session.begin_nested_calls == 1


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
            # Q.171.B — SoD usa o papel REAL (sem header → viewer → 403).
            "x-user-role": "manager_operations",
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
            # Q.171.B — SoD usa o papel REAL (sem header → viewer → 403).
            "x-user-role": "manager_operations",
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


# ─── Q.153 — list devolve sandbox_result aparado (sem `operations`) ──────


class _ListSession:
    """Stand-in para o list path: 1º execute = count, 2º execute = scalars().

    O endpoint faz `await session.execute(count_query)` e depois
    `await session.execute(query)` — devolvemos objectos com a forma certa
    (`scalar()` e `scalars().all()`) sem precisar de uma BD real.
    """

    def __init__(self, decisions) -> None:
        self._decisions = decisions
        self._calls = 0

    async def execute(self, _stmt):
        self._calls += 1
        decisions = self._decisions
        if self._calls == 1:
            class _Count:
                def scalar(self_inner):
                    return len(decisions)

            return _Count()

        class _Scalars:
            def all(self_inner):
                return list(decisions)

        class _Result:
            def scalars(self_inner):
                return _Scalars()

        return _Result()


def test_list_returns_trimmed_sandbox_result():
    """Q.153 — a lista devolve `sandbox_result` (os cartões e o what-if das
    Simulações leem dele), mas SEM o array pesado `operations` (o plano
    inteiro), para nao inflar o payload de ate 50 decisoes."""
    from datetime import datetime, timezone

    decision = SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT,
        title="Replaneamento automatico",
        action_type="AUTO_PROPOSE_SCHEDULE",
        target="OF-001",
        status=DecisionStatus.PROPOSED.value,
        sandbox_result={
            "commit_sha": "abc123",
            "kpis": {"makespan_hours": 12.5, "num_late_orders": 2},
            "if_accept": ["Novo plano: makespan 12.5 h"],
            "if_reject": ["Mantem o plano atual"],
            "why": "Replaneamento proposto pelo CPO",
            "quality_risk": "medio",
            "cost_delta": 1500.0,
            "operations": [{"order_id": 1, "phase_id": "p1"}] * 500,  # pesado
        },
        before_state={},
        after_state={"commit_sha": "abc123"},
        proposed_by=PROPOSER,
        proposed_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        executed_at=None,
        rolled_back_at=None,
    )
    session = _ListSession([decision])
    client = TestClient(_approve_app(session))  # mesma app helper serve

    resp = client.get(
        "/v1/shared/decisions?status_filter=PROPOSED",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    (row,) = body["decisions"]

    sb = row["sandbox_result"]
    # Campos escalares do cartao presentes …
    assert sb["commit_sha"] == "abc123"
    assert sb["kpis"]["makespan_hours"] == 12.5
    assert sb["if_accept"] and sb["if_reject"]
    assert sb["why"] and sb["quality_risk"] == "medio"
    assert sb["cost_delta"] == 1500.0
    # … mas o array pesado `operations` e aparado.
    assert "operations" not in sb


# ─── Q.153 — approve/reject publicam evento realtime (SSE) ────────────────


def _decision_proposed() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT,
        action_type="GENERIC_ACTION",
        status=DecisionStatus.PROPOSED.value,
        proposed_by=PROPOSER,
    )


def test_approve_publishes_decision_approved_event(monkeypatch):
    """Q.153 — aprovar publica DECISION_APPROVED (antes o ledger shared não
    publicava nada → os listeners SSE da página /decisoes ficavam mudos)."""
    import src.shared.kafka_client as kc

    published: list[tuple[str, str]] = []

    async def _fake_publish(topic, event):
        published.append((topic, event.event_type))
        return True

    monkeypatch.setattr(kc, "publish_event", _fake_publish)

    session = _ApproveSession(_decision_proposed(), existing_approval=None)
    decision = session.decision
    client = TestClient(_approve_app(session))

    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/approve",
        headers={"x-tenant-id": str(TENANT), "x-user-id": str(APPROVER), "x-user-role": "manager_operations"},
        json={"status": "APPROVED"},
    )
    assert resp.status_code == 200, resp.text
    assert published, "approve não publicou nenhum evento realtime"
    assert published[0][1] == "DECISION_APPROVED"
    assert published[0][0] == kc.Topics.DECISION_APPROVED


def test_reject_publishes_decision_rejected_event(monkeypatch):
    """Q.153 — rejeitar publica DECISION_REJECTED (tópico novo; o FE já o
    escutava mas nada o publicava)."""
    import src.shared.kafka_client as kc

    published: list[tuple[str, str]] = []

    async def _fake_publish(topic, event):
        published.append((topic, event.event_type))
        return True

    monkeypatch.setattr(kc, "publish_event", _fake_publish)

    session = _ApproveSession(_decision_proposed(), existing_approval=None)
    decision = session.decision
    client = TestClient(_approve_app(session))

    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/approve",
        headers={"x-tenant-id": str(TENANT), "x-user-id": str(APPROVER), "x-user-role": "manager_operations"},
        json={"status": "REJECTED"},
    )
    assert resp.status_code == 200, resp.text
    assert published, "reject não publicou nenhum evento realtime"
    assert published[0][1] == "DECISION_REJECTED"
    assert published[0][0] == kc.Topics.DECISION_REJECTED
    assert decision.status == DecisionStatus.REJECTED.value


# ─── Q.171.B — SoD com papel REAL (era hardcoded MANAGER_OPERATIONS) ─────────


def _proposed_decision():
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT,
        action_type="GENERIC_ACTION",
        status=DecisionStatus.PROPOSED.value,
        proposed_by=PROPOSER,
    )


def _approve_with_role(role_header: dict) -> int:
    decision = _proposed_decision()
    session = _ApproveSession(decision, existing_approval=None)
    client = TestClient(_approve_app(session))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/approve",
        headers={
            "x-tenant-id": str(TENANT),
            "x-user-id": str(APPROVER),
            **role_header,
        },
        json={"comment": "OK"},
    )
    return resp.status_code


def test_q171b_sem_role_e_viewer_403():
    """Sem X-User-Role o contexto cai em viewer — SEM autorização. Antes o
    papel era hardcoded MANAGER_OPERATIONS: QUALQUER chamada aprovava."""
    assert _approve_with_role({}) == 403


def test_q171b_viewer_explicito_403():
    assert _approve_with_role({"x-user-role": "viewer"}) == 403


def test_q171b_operator_403_para_generic_action():
    """GENERIC_ACTION exige manager_operations/finance_controller."""
    assert _approve_with_role({"x-user-role": "operator"}) == 403


def test_q171b_manager_operations_200():
    assert _approve_with_role({"x-user-role": "manager_operations"}) == 200


def test_q171b_admin_alias_200():
    """'admin' (alias FE) normaliza para admin_platform, que aprova qualquer
    action_type (bypass da regra 2; a regra 1 — não aprovar o próprio —
    continua a valer)."""
    assert _approve_with_role({"x-user-role": "admin"}) == 200


def test_q171b_role_invalido_403():
    assert _approve_with_role({"x-user-role": "hacker"}) == 403
