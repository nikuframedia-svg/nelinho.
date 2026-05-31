"""Q.130.I (FE-5) — bulk approve/reject + modify-payload em `shared.decision_runs`.

Bug: o Decisões-hub lista decisões de `GET /v1/decisions` (tabela
`shared.decision_runs`) mas o bulk/modify-payload batiam em
`/v1/governance/decisions/...` (tabela DIFERENTE `governance.decision_run`).
Os ids nunca cruzavam → bulk devolvia "0 ok, N falhou" e o modify dava 400.

Fix: endpoints bulk/modify SHARED que operam na MESMA tabela do list.
Estes testes pinam:
  * bulk-approve de 2 decisões PROPOSED → ambas APPROVED + audit na mesma tx;
  * ids inexistentes → reportados como falha por-item (NÃO 500);
  * modify-payload faz merge raso em `after_state` + audit.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.models.audit import AuditLog
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


class _NestedTx:
    """Async ctx manager que mimica o savepoint (begin_nested)."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _BulkSession:
    """AsyncSession stand-in: guarda decisões por id, captura adds.

    `get` devolve a decisão pelo id (ou None se inexistente — sem 500),
    `execute` devolve sempre "sem approval previa", `begin_nested` é um
    savepoint no-op, `add` coleciona DecisionApproval + AuditLog.
    """

    def __init__(self, decisions: dict[UUID, Any]) -> None:
        self._decisions = decisions
        self.added: list[Any] = []
        self.commits = 0
        self.begin_nested_calls = 0

    async def get(self, _model, ident):
        return self._decisions.get(ident)

    async def execute(self, _stmt):
        class _R:
            def scalar_one_or_none(self_inner):
                return None

        return _R()

    def add(self, obj: Any) -> None:
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = uuid4()
        self.added.append(obj)

    def begin_nested(self) -> _NestedTx:
        self.begin_nested_calls += 1
        return _NestedTx()

    async def commit(self) -> None:
        self.commits += 1


def _decision(status_value: str = DecisionStatus.PROPOSED.value, **extra):
    fields = {
        "id": uuid4(),
        "tenant_id": TENANT,
        "title": "Decisão teste",
        "target": "alvo-teste",
        "action_type": "GENERIC_ACTION",
        "status": status_value,
        "proposed_by": PROPOSER,
        "before_state": {},
        "after_state": {},
    }
    fields.update(extra)  # extra (ex. after_state) sobrepõe os defaults
    return SimpleNamespace(**fields)


def _app(session) -> FastAPI:
    app = FastAPI()
    app.include_router(decisions_router, prefix="/v1/shared")

    async def _fake_session():
        yield session

    app.dependency_overrides[get_session] = _fake_session
    return app


_HDRS = {"X-Tenant-Id": str(TENANT), "X-User-Id": str(APPROVER)}


# ── bulk approve ─────────────────────────────────────────────────────────


def test_bulk_approve_two_proposed_decisions(monkeypatch):
    """2 decisões PROPOSED → ambas APPROVED + 1 AuditLog cada (mesma tx)."""
    monkeypatch.setattr(
        "src.shared.auth.rbac.check_sod", lambda **kw: (True, None), raising=True,
    )
    d1 = _decision()
    d2 = _decision()
    session = _BulkSession({d1.id: d1, d2.id: d2})
    client = TestClient(_app(session))

    resp = client.post(
        "/v1/shared/decisions/bulk",
        headers=_HDRS,
        json={
            "decision_ids": [str(d1.id), str(d2.id)],
            "action": "approve",
            "reason": "Bulk approve via Timeline",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] == 2
    assert body["failed"] == 0
    assert {r["decision_id"] for r in body["results"]} == {str(d1.id), str(d2.id)}
    assert all(r["status"] == "ok" for r in body["results"])

    # Estado: ambas APPROVED.
    assert d1.status == DecisionStatus.APPROVED.value
    assert d2.status == DecisionStatus.APPROVED.value

    # Audit: 1 AuditLog UPDATE por decisão, na mesma sessão (invariante 7).
    audits = [o for o in session.added if isinstance(o, AuditLog)]
    assert len(audits) == 2
    assert {a.entity_id for a in audits} == {d1.id, d2.id}
    for a in audits:
        assert a.entity_type == "decision_run"
        assert a.action == "UPDATE"
        assert a.actor_id == APPROVER
        assert a.tenant_id == TENANT
        assert a.new_values == {"status": DecisionStatus.APPROVED.value}

    # 1 DecisionApproval por decisão.
    approvals = [o for o in session.added if isinstance(o, DecisionApproval)]
    assert len(approvals) == 2
    assert all(p.status == ApprovalStatus.APPROVED.value for p in approvals)


def test_bulk_reject_marks_rejected(monkeypatch):
    """action=reject → REJECTED (não APPROVED)."""
    monkeypatch.setattr(
        "src.shared.auth.rbac.check_sod", lambda **kw: (True, None), raising=True,
    )
    d = _decision()
    session = _BulkSession({d.id: d})
    client = TestClient(_app(session))

    resp = client.post(
        "/v1/shared/decisions/bulk",
        headers=_HDRS,
        json={"decision_ids": [str(d.id)], "action": "reject", "reason": "no"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] == 1
    assert d.status == DecisionStatus.REJECTED.value


def test_bulk_nonexistent_ids_reported_as_failure_not_500(monkeypatch):
    """Ids inexistentes → falha por-item, NUNCA 500. Os válidos passam."""
    monkeypatch.setattr(
        "src.shared.auth.rbac.check_sod", lambda **kw: (True, None), raising=True,
    )
    d = _decision()
    ghost = uuid4()
    session = _BulkSession({d.id: d})  # ghost não está no mapa → get devolve None
    client = TestClient(_app(session))

    resp = client.post(
        "/v1/shared/decisions/bulk",
        headers=_HDRS,
        json={
            "decision_ids": [str(d.id), str(ghost)],
            "action": "approve",
            "reason": "mix",
        },
    )
    assert resp.status_code == 200, resp.text  # NÃO 500
    body = resp.json()
    assert body["ok"] == 1
    assert body["failed"] == 1

    by_id = {r["decision_id"]: r for r in body["results"]}
    assert by_id[str(d.id)]["status"] == "ok"
    assert by_id[str(ghost)]["status"] == "error"
    assert by_id[str(ghost)]["error"] == "not found"

    # A decisão válida foi mesmo aprovada.
    assert d.status == DecisionStatus.APPROVED.value


def test_bulk_skips_non_proposed_status(monkeypatch):
    """Decisão já APPROVED → reportada como falha, não re-aprovada."""
    monkeypatch.setattr(
        "src.shared.auth.rbac.check_sod", lambda **kw: (True, None), raising=True,
    )
    d = _decision(status_value=DecisionStatus.APPROVED.value)
    session = _BulkSession({d.id: d})
    client = TestClient(_app(session))

    resp = client.post(
        "/v1/shared/decisions/bulk",
        headers=_HDRS,
        json={"decision_ids": [str(d.id)], "action": "approve"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] == 0
    assert body["failed"] == 1
    assert "cannot act on status" in body["results"][0]["error"]


# ── modify payload ───────────────────────────────────────────────────────


def test_modify_payload_merges_after_state_and_audits():
    d = _decision(after_state={"new_start_date": "2026-01-01", "keep": 1})
    session = _BulkSession({d.id: d})
    client = TestClient(_app(session))

    resp = client.patch(
        f"/v1/shared/decisions/{d.id}/payload",
        headers=_HDRS,
        json={
            "patch": {"new_start_date": "2026-05-01"},
            "reason": "corrigir data de inicio errada",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # merge raso: chave editada muda, restantes preservadas.
    assert body["after_state"] == {"new_start_date": "2026-05-01", "keep": 1}
    assert d.after_state == {"new_start_date": "2026-05-01", "keep": 1}

    audits = [o for o in session.added if isinstance(o, AuditLog)]
    assert len(audits) == 1
    assert audits[0].entity_type == "decision_run"
    assert audits[0].action == "UPDATE"
    assert audits[0].actor_id == APPROVER


def test_modify_payload_rejects_non_proposed():
    d = _decision(status_value=DecisionStatus.APPROVED.value)
    session = _BulkSession({d.id: d})
    client = TestClient(_app(session))

    resp = client.patch(
        f"/v1/shared/decisions/{d.id}/payload",
        headers=_HDRS,
        json={"patch": {"x": 1}, "reason": "tentativa invalida"},
    )
    assert resp.status_code == 400


def test_modify_payload_404_for_unknown_id():
    session = _BulkSession({})
    client = TestClient(_app(session))

    resp = client.patch(
        f"/v1/shared/decisions/{uuid4()}/payload",
        headers=_HDRS,
        json={"patch": {"x": 1}, "reason": "nao existe esta decisao"},
    )
    assert resp.status_code == 404
