"""Q.68.2.A — coverage hardening de ``src/shared/api/decisions.py``.

Contexto (auditoria H6 + Q.68.1.E): este modulo e governance critica
(propose/approve/execute/rollback + audit + RBAC) e estava a 56% de
cobertura, com 182 mutmut survivors sem pin. Este ficheiro adiciona
testes dirigidos as 7 areas pouco/nada exercitadas:

* ``list_decisions`` — happy path + filtro de status valido + filtro
  invalido (400) + paginacao.
* ``get_decision`` — 200 com aprovacoes serializadas + 404 (decision
  inexistente) + 404 (tenant cross-talk).
* ``approve_decision`` — 404 (decision inexistente) + 400 (status nao
  PROPOSED).
* ``execute_decision`` — 404 (decision inexistente) + kafka failure nao
  rebenta o request.
* ``rollback_decision`` — 404 + kafka failure absorvida.
* ``get_decision_audit`` — 200 com payload completo + 404 (inexistente)
  + 404 (tenant cross-talk).
* ``propose_decision`` — pin do SOD_POLICIES lookup (action_type custom
  vai por GENERIC_ACTION) + audit_change com os campos certos.

Estilo: DAMP. Cada teste le-se como uma especificacao independente — o
setup repete-se de proposito para servir de referencia.
"""

from __future__ import annotations

from datetime import datetime, timedelta
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


# ─── identidades determinísticas para o ficheiro ────────────────────────

TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PROPOSER = UUID("11111111-1111-1111-1111-111111111111")
APPROVER = UUID("22222222-2222-2222-2222-222222222222")
EXECUTOR = UUID("33333333-3333-3333-3333-333333333333")


# ─── helpers minimos (cada um faz UMA coisa) ────────────────────────────


def _decision_row(
    *,
    status_value: str = DecisionStatus.PROPOSED.value,
    tenant_id: UUID = TENANT,
    executed_at: datetime | None = None,
    rolled_back_at: datetime | None = None,
    proposed_at: datetime | None = None,
    action_type: str = "GENERIC_ACTION",
    title: str = "Test decision",
    target: str = "test-target",
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    sandbox_result: dict[str, Any] | None = None,
) -> SimpleNamespace:
    """Constroi um SimpleNamespace com a shape de ``SharedDecisionRun``.

    Usamos SimpleNamespace (em vez de instanciar o ORM) porque o ORM tem
    columns SQLAlchemy que so se setam via Session.add+flush. Para tests
    de endpoint que so precisam de ler atributos, SimpleNamespace e mais
    leve e nao acende warnings de Mapper.
    """
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant_id,
        title=title,
        action_type=action_type,
        target=target,
        status=status_value,
        sandbox_result=sandbox_result,
        before_state=before_state or {},
        after_state=after_state,
        proposed_by=PROPOSER,
        proposed_at=proposed_at or datetime.utcnow(),
        executed_at=executed_at,
        rolled_back_at=rolled_back_at,
    )


def _build_app_with_session(session: Any) -> FastAPI:
    """Monta FastAPI com o router de decisions e injecta a session dada."""
    app = FastAPI()
    app.include_router(decisions_router, prefix="/v1/shared")

    async def _fake_session():
        yield session

    app.dependency_overrides[get_session] = _fake_session
    return app


def _tenant_headers(*, tenant: UUID = TENANT, user: UUID = APPROVER) -> dict[str, str]:
    return {
        "x-tenant-id": str(tenant),
        "x-user-id": str(user),
    }


@pytest.fixture(autouse=True)
def _kafka_silent(monkeypatch):
    """Stub o publish_event para nao tentar abrir socket real.

    Os endpoints execute/rollback sao "best-effort": apanham qualquer
    Exception do publish e seguem em frente. Mas se o import falha aqui
    o teste apanha tracebacks irrelevantes. Por defeito devolve True.

    Os testes que QUEREM forcar uma kafka-failure fazem-no localmente,
    chamando monkeypatch.setattr de novo dentro do proprio teste.
    """
    async def _ok(_topic, _event):
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", _ok, raising=True,
    )


# ─── 1) list_decisions ───────────────────────────────────────────────────


def test_list_decisions_returns_serialized_rows_with_pagination():
    """list_decisions devolve dict serializado + total + page/page_size.

    Cobre o happy path do endpoint (linhas 166-206 antes deste pin).
    """
    decisions = [
        _decision_row(title="Decision A"),
        _decision_row(title="Decision B"),
    ]
    session = AsyncMock()

    # Conta total → 2
    count_result = AsyncMock()
    count_result.scalar = lambda: 2
    # scalars().all() → lista de decisions
    page_result = AsyncMock()
    scalars_handle = SimpleNamespace(all=lambda: decisions)
    page_result.scalars = lambda: scalars_handle

    # session.execute e chamada 2x — primeiro count, depois pagina.
    session.execute = AsyncMock(side_effect=[count_result, page_result])

    client = TestClient(_build_app_with_session(session))
    resp = client.get(
        "/v1/shared/decisions/?page=1&page_size=20",
        headers={"x-tenant-id": str(TENANT)},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert len(body["decisions"]) == 2
    # Serialization: IDs viram strings, datetimes viram ISO.
    assert all(isinstance(d["id"], str) for d in body["decisions"])
    assert all("proposed_at" in d for d in body["decisions"])


def test_list_decisions_filters_by_status_when_valid_enum():
    """status_filter valido aplica WHERE status=...; resposta esta ok."""
    session = AsyncMock()

    count_result = AsyncMock()
    count_result.scalar = lambda: 0
    page_result = AsyncMock()
    page_result.scalars = lambda: SimpleNamespace(all=lambda: [])
    session.execute = AsyncMock(side_effect=[count_result, page_result])

    client = TestClient(_build_app_with_session(session))
    resp = client.get(
        "/v1/shared/decisions/?status_filter=PROPOSED",
        headers={"x-tenant-id": str(TENANT)},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 0
    assert body["decisions"] == []


def test_list_decisions_rejects_invalid_status_filter_with_400():
    """status_filter desconhecido (ValueError no enum) devolve 400.

    Pin para o except ValueError no endpoint (linha ~172).
    """
    session = AsyncMock()
    client = TestClient(_build_app_with_session(session))
    resp = client.get(
        "/v1/shared/decisions/?status_filter=NOT_A_REAL_STATUS",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 400
    assert "Invalid status" in resp.json()["detail"]


def test_list_decisions_executed_at_serializes_to_iso_or_none():
    """Cobre o ternario `d.executed_at.isoformat() if d.executed_at else None`.

    Sem este pin, mutar `if d.executed_at` para `if not d.executed_at`
    passa silencioso quando todas as decisions estao PROPOSED.
    """
    decisions = [
        _decision_row(title="exec", status_value=DecisionStatus.EXECUTED.value,
                      executed_at=datetime(2026, 5, 21, 9, 0, 0)),
        _decision_row(title="prop"),  # executed_at=None
    ]
    session = AsyncMock()
    count_result = AsyncMock()
    count_result.scalar = lambda: 2
    page_result = AsyncMock()
    page_result.scalars = lambda: SimpleNamespace(all=lambda: decisions)
    session.execute = AsyncMock(side_effect=[count_result, page_result])

    client = TestClient(_build_app_with_session(session))
    resp = client.get(
        "/v1/shared/decisions/",
        headers={"x-tenant-id": str(TENANT)},
    )
    body = resp.json()
    by_title = {d["title"]: d for d in body["decisions"]}
    assert by_title["exec"]["executed_at"] == "2026-05-21T09:00:00"
    assert by_title["prop"]["executed_at"] is None


# ─── 2) get_decision (detail + 404 paths) ───────────────────────────────


def test_get_decision_returns_detail_with_approvals():
    """Happy path: decision + lista de approvals serializadas."""
    decision = _decision_row()
    approval = SimpleNamespace(
        id=uuid4(),
        approver_id=APPROVER,
        status=ApprovalStatus.APPROVED.value,
        comment="LGTM",
        approved_at=datetime(2026, 5, 20, 10, 0, 0),
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    approvals_result = AsyncMock()
    approvals_result.scalars = lambda: SimpleNamespace(all=lambda: [approval])
    session.execute = AsyncMock(return_value=approvals_result)

    client = TestClient(_build_app_with_session(session))
    resp = client.get(
        f"/v1/shared/decisions/{decision.id}",
        headers={"x-tenant-id": str(TENANT)},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(decision.id)
    assert body["status"] == DecisionStatus.PROPOSED.value
    assert len(body["approvals"]) == 1
    assert body["approvals"][0]["approver_id"] == str(APPROVER)
    assert body["approvals"][0]["approved_at"] == "2026-05-20T10:00:00"
    assert body["approvals"][0]["comment"] == "LGTM"


def test_get_decision_returns_404_when_missing():
    """session.get devolve None → 404."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    client = TestClient(_build_app_with_session(session))
    resp = client.get(
        f"/v1/shared/decisions/{uuid4()}",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 404


def test_get_decision_returns_404_when_tenant_mismatch():
    """Isolamento de tenant: pedir decision de OUTRO tenant → 404 (nao 403)."""
    decision = _decision_row(tenant_id=OTHER_TENANT)
    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    client = TestClient(_build_app_with_session(session))
    resp = client.get(
        f"/v1/shared/decisions/{decision.id}",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 404


def test_get_decision_handles_null_approved_at_in_serialization():
    """Approval com approved_at=None devolve null no JSON, nao crash."""
    decision = _decision_row()
    approval = SimpleNamespace(
        id=uuid4(),
        approver_id=APPROVER,
        status=ApprovalStatus.PENDING.value,
        comment=None,
        approved_at=None,
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    approvals_result = AsyncMock()
    approvals_result.scalars = lambda: SimpleNamespace(all=lambda: [approval])
    session.execute = AsyncMock(return_value=approvals_result)

    client = TestClient(_build_app_with_session(session))
    resp = client.get(
        f"/v1/shared/decisions/{decision.id}",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approvals"][0]["approved_at"] is None
    assert body["approvals"][0]["comment"] is None


# ─── 3) approve_decision (error paths) ──────────────────────────────────


def test_approve_returns_404_when_decision_missing():
    """approve em decision inexistente → 404 (linha ~281)."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    client = TestClient(_build_app_with_session(session))
    resp = client.post(
        f"/v1/shared/decisions/{uuid4()}/approve",
        headers=_tenant_headers(),
        json={"comment": "x"},
    )
    assert resp.status_code == 404


def test_approve_returns_400_when_status_is_not_proposed():
    """approve em decision ja APPROVED → 400 (linha ~288).

    Sem este teste, um mutante que inverta o `!=` para `==` passa
    silencioso em qualquer outro teste que use status=PROPOSED.
    """
    decision = _decision_row(status_value=DecisionStatus.APPROVED.value)
    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    client = TestClient(_build_app_with_session(session))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/approve",
        headers=_tenant_headers(),
        json={"comment": "x"},
    )
    assert resp.status_code == 400
    assert "cannot be approved" in resp.json()["detail"].lower()


def test_approve_returns_404_when_tenant_mismatch():
    """approve em decision de outro tenant → 404 (nao 403)."""
    decision = _decision_row(tenant_id=OTHER_TENANT)
    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    client = TestClient(_build_app_with_session(session))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/approve",
        headers=_tenant_headers(),
        json={"comment": "x"},
    )
    assert resp.status_code == 404


# ─── 4) execute_decision (error + kafka resilience) ─────────────────────


def test_execute_returns_404_when_decision_missing():
    """execute em decision inexistente → 404 (linha ~364)."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    client = TestClient(_build_app_with_session(session))
    resp = client.post(
        f"/v1/shared/decisions/{uuid4()}/execute",
        headers=_tenant_headers(user=EXECUTOR),
    )
    assert resp.status_code == 404


def test_execute_swallows_kafka_publish_failure(monkeypatch):
    """Kafka down NAO falha o request — audit trail e a fonte de verdade.

    Pin para o try/except no execute_decision (linhas 405-406): "best-effort
    event publish — advisory loop should still notify clients."
    """
    async def _boom(_topic, _event):
        raise RuntimeError("kafka offline")
    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", _boom, raising=True,
    )

    decision = _decision_row(status_value=DecisionStatus.APPROVED.value)
    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    session.commit = AsyncMock()
    client = TestClient(_build_app_with_session(session))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/execute",
        headers=_tenant_headers(user=EXECUTOR),
    )

    assert resp.status_code == 200, resp.text
    # status passou a EXECUTED apesar do publish ter falhado.
    assert decision.status == DecisionStatus.EXECUTED.value
    assert resp.json()["advisory_mode"] is True


def test_execute_returns_404_when_tenant_mismatch():
    decision = _decision_row(
        status_value=DecisionStatus.APPROVED.value, tenant_id=OTHER_TENANT,
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    client = TestClient(_build_app_with_session(session))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/execute",
        headers=_tenant_headers(user=EXECUTOR),
    )
    assert resp.status_code == 404


# ─── 5) rollback_decision (error + kafka resilience) ────────────────────


def test_rollback_returns_404_when_decision_missing():
    """rollback em decision inexistente → 404 (linha ~440)."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    client = TestClient(_build_app_with_session(session))
    resp = client.post(
        f"/v1/shared/decisions/{uuid4()}/rollback",
        headers=_tenant_headers(user=EXECUTOR),
    )
    assert resp.status_code == 404


def test_rollback_swallows_kafka_publish_failure(monkeypatch):
    """Kafka down nao impede o rollback de ficar marcado como ROLLED_BACK.

    Pin para o try/except no rollback_decision (linhas 492-493).
    """
    async def _boom(_topic, _event):
        raise RuntimeError("kafka down")
    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", _boom, raising=True,
    )

    decision = _decision_row(
        status_value=DecisionStatus.EXECUTED.value,
        executed_at=datetime.utcnow() - timedelta(hours=1),
        before_state={"snapshot": "ok"},
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    session.commit = AsyncMock()
    client = TestClient(_build_app_with_session(session))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/rollback",
        headers=_tenant_headers(user=EXECUTOR),
    )

    assert resp.status_code == 200, resp.text
    assert decision.status == DecisionStatus.ROLLED_BACK.value
    body = resp.json()
    assert body["before_state"] == {"snapshot": "ok"}


def test_rollback_returns_404_when_tenant_mismatch():
    decision = _decision_row(
        status_value=DecisionStatus.EXECUTED.value,
        tenant_id=OTHER_TENANT,
        executed_at=datetime.utcnow() - timedelta(hours=1),
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    client = TestClient(_build_app_with_session(session))
    resp = client.post(
        f"/v1/shared/decisions/{decision.id}/rollback",
        headers=_tenant_headers(user=EXECUTOR),
    )
    assert resp.status_code == 404


# ─── 6) get_decision_audit ──────────────────────────────────────────────


def test_audit_endpoint_returns_full_decision_state_and_approvals():
    """audit devolve {decision, approvals, state_changes} com tudo
    serializado. Cobre o bloco 521-562.
    """
    decision = _decision_row(
        status_value=DecisionStatus.EXECUTED.value,
        executed_at=datetime(2026, 5, 21, 11, 0, 0),
        rolled_back_at=None,
        before_state={"qty": 100},
        after_state={"qty": 120},
        title="audit-test",
    )
    approval = SimpleNamespace(
        id=uuid4(),
        approver_id=APPROVER,
        status=ApprovalStatus.APPROVED.value,
        comment="reviewed",
        approved_at=datetime(2026, 5, 21, 10, 30, 0),
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    approvals_result = AsyncMock()
    approvals_result.scalars = lambda: SimpleNamespace(all=lambda: [approval])
    session.execute = AsyncMock(return_value=approvals_result)

    client = TestClient(_build_app_with_session(session))
    resp = client.get(
        f"/v1/shared/decisions/{decision.id}/audit",
        headers={"x-tenant-id": str(TENANT)},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Decisao
    assert body["decision"]["id"] == str(decision.id)
    assert body["decision"]["status"] == DecisionStatus.EXECUTED.value
    assert body["decision"]["title"] == "audit-test"
    assert body["decision"]["executed_at"] == "2026-05-21T11:00:00"
    assert body["decision"]["rolled_back_at"] is None
    # Approvals
    assert len(body["approvals"]) == 1
    assert body["approvals"][0]["approver_id"] == str(APPROVER)
    assert body["approvals"][0]["approved_at"] == "2026-05-21T10:30:00"
    # State changes
    assert body["state_changes"]["before_state"] == {"qty": 100}
    assert body["state_changes"]["after_state"] == {"qty": 120}


def test_audit_endpoint_returns_404_when_decision_missing():
    """audit em decision inexistente → 404."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    client = TestClient(_build_app_with_session(session))
    resp = client.get(
        f"/v1/shared/decisions/{uuid4()}/audit",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 404


def test_audit_endpoint_returns_404_when_tenant_mismatch():
    """audit pedido de outro tenant → 404 (mesma logica que get/approve)."""
    decision = _decision_row(tenant_id=OTHER_TENANT)
    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    client = TestClient(_build_app_with_session(session))
    resp = client.get(
        f"/v1/shared/decisions/{decision.id}/audit",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 404


def test_audit_endpoint_serializes_null_dates_correctly():
    """rolled_back_at=None + approved_at=None viram null no JSON."""
    decision = _decision_row(
        status_value=DecisionStatus.PROPOSED.value,
        executed_at=None,
        rolled_back_at=None,
    )
    approval = SimpleNamespace(
        id=uuid4(),
        approver_id=APPROVER,
        status=ApprovalStatus.PENDING.value,
        comment=None,
        approved_at=None,
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=decision)
    approvals_result = AsyncMock()
    approvals_result.scalars = lambda: SimpleNamespace(all=lambda: [approval])
    session.execute = AsyncMock(return_value=approvals_result)

    client = TestClient(_build_app_with_session(session))
    resp = client.get(
        f"/v1/shared/decisions/{decision.id}/audit",
        headers={"x-tenant-id": str(TENANT)},
    )
    body = resp.json()
    assert body["decision"]["executed_at"] is None
    assert body["decision"]["rolled_back_at"] is None
    assert body["approvals"][0]["approved_at"] is None


# ─── 7) propose_decision — SOD policy lookup + audit ─────────────────────


class _ProposeRecordingSession:
    """Stand-in com begin_nested + capture, para inspeccionar audit.

    Equivalente ao _ProposeSession do test_decisions_propose_q61_09 mas
    com flush a setar `id` (mimica o populates-on-flush do SQLAlchemy).
    """

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushes = 0
        self.begin_nested_calls = 0

    def add(self, obj: Any) -> None:
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = uuid4()
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        pass

    def begin_nested(self):
        self.begin_nested_calls += 1

        class _Tx:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, _et, _e, _tb):
                return None

        return _Tx()


def test_propose_uses_custom_sod_policy_when_action_type_known(caplog):
    """SOD_POLICIES["INCREASE_PRICE"] = [FINANCE_CONTROLLER]. O log do
    propose contem o role exigido — pin para o ramo SOD_POLICIES.get(
    action_type, GENERIC_ACTION) com action_type CONHECIDO.
    """
    import logging
    session = _ProposeRecordingSession()
    app = _build_app_with_session(session)

    with caplog.at_level(logging.INFO, logger="src.shared.api.decisions"):
        client = TestClient(app)
        resp = client.post(
            "/v1/shared/decisions/propose",
            headers=_tenant_headers(user=PROPOSER),
            json={
                "title": "raise prices Q3",
                "action_type": "INCREASE_PRICE",
                "target": "sku-9001",
                "sandbox_result": {"delta": 5},
                "before_state": {"price": 100.0},
                "after_state": {"price": 105.0},
            },
        )

    assert resp.status_code == 201, resp.text
    # Logs incluem o role exigido pela politica.
    joined = "\n".join(r.message for r in caplog.records)
    assert "finance_controller" in joined.lower()


def test_propose_falls_back_to_generic_when_action_type_unknown(caplog):
    """Action type fora do dict → entra na GENERIC_ACTION (manager_ops +
    finance_controller). Pin para o segundo SOD_POLICIES.get(...).
    """
    import logging
    session = _ProposeRecordingSession()
    app = _build_app_with_session(session)

    with caplog.at_level(logging.INFO, logger="src.shared.api.decisions"):
        client = TestClient(app)
        resp = client.post(
            "/v1/shared/decisions/propose",
            headers=_tenant_headers(user=PROPOSER),
            json={
                "title": "Mysterious action",
                "action_type": "TOTALLY_NEW_ACTION_TYPE",
                "target": "x",
                "sandbox_result": {},
                "before_state": {},
                "after_state": None,
            },
        )

    assert resp.status_code == 201, resp.text
    joined = "\n".join(r.message for r in caplog.records)
    # GENERIC_ACTION policy → manager_operations + finance_controller
    assert "manager_operations" in joined.lower()


def test_propose_writes_audit_log_with_correct_action_and_actor():
    """Audit log emitido pelo propose: action=INSERT, actor_id=user,
    new_values inclui titulo/action_type/target/status=PROPOSED.
    """
    from src.core.models.audit import AuditLog

    session = _ProposeRecordingSession()
    client = TestClient(_build_app_with_session(session))
    resp = client.post(
        "/v1/shared/decisions/propose",
        headers=_tenant_headers(user=PROPOSER),
        json={
            "title": "audit pin",
            "action_type": "GENERIC_ACTION",
            "target": "sku-1",
            "sandbox_result": {},
            "before_state": {},
            "after_state": None,
        },
    )
    assert resp.status_code == 201, resp.text

    audits = [a for a in session.added if isinstance(a, AuditLog)]
    assert len(audits) == 1
    audit = audits[0]
    assert audit.entity_type == "decision_run"
    assert audit.action == "INSERT"
    assert audit.actor_id == PROPOSER
    assert audit.tenant_id == TENANT
    assert audit.new_values["title"] == "audit pin"
    assert audit.new_values["action_type"] == "GENERIC_ACTION"
    assert audit.new_values["target"] == "sku-1"
    assert audit.new_values["status"] == DecisionStatus.PROPOSED.value
    # Q.61.10: tudo dentro do mesmo savepoint.
    assert session.begin_nested_calls == 1
