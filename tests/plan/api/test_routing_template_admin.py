"""Q.116.B — tests for PATCH endpoints do editor de fases.

Cobertura:
  1. Sequence happy path — fases reordenadas + audit UPDATE com old/new.
  2. Sequence com phase IDs invalidos → 400 (ValueError do service).
  3. set_flexible True com predecessors validos → flip ok + audit.
  4. set_flexible True sem predecessors → 422 (Pydantic min_length=0 ok, mas
     ValueError no service) — esperamos 400.
  5. set_flexible False limpa allowed_predecessors para NULL.
  6. set_flexible em phase row inexistente → 404.

Strategy: FastAPI TestClient + FakeSession. Override require_tenant_header
+ require_user_header + get_session + RBAC dep. Nao toca DB real.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.models.audit import AuditLog
from src.plan.api.routing_template_admin import (
    _require_config_write,
    router as routing_router,
)
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.database import get_session
from tests.conftest import FakeSession, TEST_TENANT_ID

_TENANT = str(TEST_TENANT_ID)
_USER = "admin_routing"
_HEADERS = {"X-Tenant-Id": _TENANT, "X-User-Id": _USER}


# ─── App factory ─────────────────────────────────────────────────────────────


def _minimal_app(session: FakeSession) -> TestClient:
    app = FastAPI()
    app.include_router(routing_router)

    async def _s():
        yield session

    app.dependency_overrides[get_session] = _s
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT_ID
    app.dependency_overrides[require_user_header] = lambda: _USER
    app.dependency_overrides[_require_config_write] = lambda: None
    return TestClient(app, raise_server_exceptions=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _template(template_id: UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=template_id,
        tenant_id=TEST_TENANT_ID,
        code="ROUTING-0001",
        name="Padrao K1",
        description=None,
        phase_count=3,
        active=True,
        model_coverage=219,
    )


def _phase(
    template_id: UUID,
    *,
    row_id: UUID | None = None,
    seq: int = 1,
    phase_id: str = "LAMINAGEM",
    phase_name: str = "Laminagem",
    is_flexible: bool = False,
    allowed_predecessors: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=row_id or uuid4(),
        tenant_id=TEST_TENANT_ID,
        template_id=template_id,
        seq=seq,
        phase_id=phase_id,
        phase_name=phase_name,
        duration_p50_h=None,
        duration_p90_h=None,
        requires_mold=False,
        team_size_default=1,
        can_skip=False,
        alternative_group_id=None,
        is_flexible=is_flexible,
        allowed_predecessors=allowed_predecessors,
    )


def _added_of_type(session: FakeSession, cls: type) -> list:
    return [o for o in session.added if isinstance(o, cls)]


# ─── 1. Sequence happy path ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_sequence_happy_path():
    """3 fases trocadas para a ordem inversa → seq 1..3 + audit UPDATE."""
    session = FakeSession()
    template_id = uuid4()
    template = _template(template_id)

    # 3 fases na ordem [A, B, C] (seq 1, 2, 3).
    pA = _phase(template_id, seq=1, phase_id="LAMINAGEM")
    pB = _phase(template_id, seq=2, phase_id="CURA")
    pC = _phase(template_id, seq=3, phase_id="ACABAMENTO_2")

    # get_template (call 1: scalar=template, scalars=[]) +
    # template_phases (call 2: scalar=None, scalars=[A,B,C]).
    # FakeSession.execute pops UM item de cada queue por chamada, por isso
    # enfileiramos a parte certa em cada slot.
    session.queue_scalar(template)
    session.queue_scalars([])
    session.queue_scalar(None)
    session.queue_scalars([pA, pB, pC])

    client = _minimal_app(session)
    # Inverte: nova ordem [C, B, A].
    resp = client.patch(
        f"/v1/plan/routing-templates/{template_id}/sequence",
        json={"phase_order": [str(pC.id), str(pB.id), str(pA.id)]},
        headers=_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["template_id"] == str(template_id)
    out_ids = [p["id"] for p in body["phases"]]
    assert out_ids == [str(pC.id), str(pB.id), str(pA.id)]
    # seq reescrito 1..3.
    assert [p["seq"] for p in body["phases"]] == [1, 2, 3]
    # In-memory state foi mutado.
    assert pC.seq == 1
    assert pB.seq == 2
    assert pA.seq == 3

    # Audit UPDATE escrito na mesma session.
    audits = _added_of_type(session, AuditLog)
    assert len(audits) == 1
    assert audits[0].action == "UPDATE"
    assert audits[0].entity_type == "routing_template"
    assert audits[0].entity_id == template_id
    assert audits[0].old_values == {
        "phase_order": [str(pA.id), str(pB.id), str(pC.id)]
    }
    assert audits[0].new_values == {
        "phase_order": [str(pC.id), str(pB.id), str(pA.id)]
    }
    assert audits[0].reason == "reorder_phases"


# ─── 2. Sequence com phase IDs invalidos → 400 ───────────────────────────────


@pytest.mark.asyncio
async def test_update_sequence_invalid_phase_ids_returns_400():
    """new_order com ID extra (que nao pertence ao template) → 400."""
    session = FakeSession()
    template_id = uuid4()
    template = _template(template_id)
    pA = _phase(template_id, seq=1, phase_id="LAMINAGEM")
    pB = _phase(template_id, seq=2, phase_id="CURA")

    session.queue_scalar(template)
    session.queue_scalars([])
    session.queue_scalar(None)
    session.queue_scalars([pA, pB])

    intruder = uuid4()  # nao pertence ao template
    client = _minimal_app(session)
    resp = client.patch(
        f"/v1/plan/routing-templates/{template_id}/sequence",
        json={"phase_order": [str(pA.id), str(intruder)]},
        headers=_HEADERS,
    )

    assert resp.status_code == 400, resp.text
    assert "exactamente" in resp.json()["detail"]
    # Nem mutacao nem audit.
    assert _added_of_type(session, AuditLog) == []
    # As fases originais mantiveram o seq.
    assert pA.seq == 1
    assert pB.seq == 2


# ─── 3. set_flexible True happy path ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_flexible_true_with_predecessors_ok():
    """Marca fase como flexible com 2 predecessors validos."""
    session = FakeSession()
    template_id = uuid4()
    phase = _phase(
        template_id,
        seq=2,
        phase_id="ACABAMENTO_2",
        phase_name="Acabamento 2",
        is_flexible=False,
        allowed_predecessors=None,
    )
    session.queue_scalar(phase)

    client = _minimal_app(session)
    resp = client.patch(
        f"/v1/plan/routing-templates/{template_id}/phases/{phase.id}/flexible",
        json={
            "is_flexible": True,
            "allowed_predecessors": ["COLAGEM_PECAS", "LIXAGEM_AGUA"],
        },
        headers=_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(phase.id)
    assert body["is_flexible"] is True
    assert body["allowed_predecessors"] == ["COLAGEM_PECAS", "LIXAGEM_AGUA"]
    # In-memory mutate.
    assert phase.is_flexible is True
    assert phase.allowed_predecessors == ["COLAGEM_PECAS", "LIXAGEM_AGUA"]

    # Audit UPDATE com old/new corretos.
    audits = _added_of_type(session, AuditLog)
    assert len(audits) == 1
    assert audits[0].action == "UPDATE"
    assert audits[0].entity_type == "routing_template_phase"
    assert audits[0].entity_id == phase.id
    assert audits[0].old_values == {
        "is_flexible": False,
        "allowed_predecessors": None,
    }
    assert audits[0].new_values == {
        "is_flexible": True,
        "allowed_predecessors": ["COLAGEM_PECAS", "LIXAGEM_AGUA"],
    }
    assert audits[0].reason == "set_flexible_phase"


# ─── 4. set_flexible True sem predecessors → 400 ─────────────────────────────


@pytest.mark.asyncio
async def test_set_flexible_true_empty_predecessors_returns_400():
    """is_flexible=True com lista vazia → service ValueError → 400.

    NOTA: Pydantic deixa passar (List[str] default vazia); o handler do
    service rejeita. Esperamos 400 com mensagem em PT-PT.
    """
    session = FakeSession()
    template_id = uuid4()
    phase = _phase(template_id, seq=2, phase_id="ACABAMENTO_2")
    # set_flexible faz SELECT antes da validacao... NAO faz — a validacao
    # de combinacao acontece ANTES do SELECT. Mas o handler do FastAPI ja
    # chama o servico; se a validacao for antes nao precisamos sequer da
    # queue.
    # Para defesa-em-profundidade, deixamos um scalar enfileirado caso o
    # service mude a ordem.
    session.queue_scalar(phase)

    client = _minimal_app(session)
    resp = client.patch(
        f"/v1/plan/routing-templates/{template_id}/phases/{phase.id}/flexible",
        json={"is_flexible": True, "allowed_predecessors": []},
        headers=_HEADERS,
    )

    assert resp.status_code == 400, resp.text
    assert "pelo menos 1" in resp.json()["detail"]
    # Nem mutacao nem audit.
    assert _added_of_type(session, AuditLog) == []
    assert phase.is_flexible is False
    assert phase.allowed_predecessors is None


# ─── 5. set_flexible False clears predecessors ───────────────────────────────


@pytest.mark.asyncio
async def test_set_flexible_false_clears_predecessors():
    """is_flexible=False com lista vazia → flip OK + allowed_predecessors=NULL."""
    session = FakeSession()
    template_id = uuid4()
    phase = _phase(
        template_id,
        seq=2,
        phase_id="ACABAMENTO_2",
        is_flexible=True,
        allowed_predecessors=["COLAGEM_PECAS"],
    )
    session.queue_scalar(phase)

    client = _minimal_app(session)
    resp = client.patch(
        f"/v1/plan/routing-templates/{template_id}/phases/{phase.id}/flexible",
        json={"is_flexible": False, "allowed_predecessors": []},
        headers=_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_flexible"] is False
    assert body["allowed_predecessors"] is None
    assert phase.is_flexible is False
    assert phase.allowed_predecessors is None

    audits = _added_of_type(session, AuditLog)
    assert len(audits) == 1
    assert audits[0].old_values == {
        "is_flexible": True,
        "allowed_predecessors": ["COLAGEM_PECAS"],
    }
    assert audits[0].new_values == {
        "is_flexible": False,
        "allowed_predecessors": None,
    }


# ─── 6. set_flexible em phase row inexistente → 404 ──────────────────────────


@pytest.mark.asyncio
async def test_set_flexible_phase_not_found_returns_404():
    """SELECT phase → None → 404."""
    session = FakeSession()
    template_id = uuid4()
    phantom_phase_id = uuid4()
    session.queue_scalar(None)  # SELECT phase → None

    client = _minimal_app(session)
    resp = client.patch(
        f"/v1/plan/routing-templates/{template_id}/phases/{phantom_phase_id}/flexible",
        json={"is_flexible": True, "allowed_predecessors": ["LAMINAGEM"]},
        headers=_HEADERS,
    )

    assert resp.status_code == 404, resp.text
    assert str(phantom_phase_id) in resp.json()["detail"]
    assert _added_of_type(session, AuditLog) == []


# ─── 7. set_flexible com predecessors duplicados → 400 ───────────────────────


@pytest.mark.asyncio
async def test_set_flexible_duplicate_predecessors_returns_400():
    """allowed_predecessors com duplicados → ValueError → 400."""
    session = FakeSession()
    template_id = uuid4()
    phase = _phase(template_id, seq=2, phase_id="ACABAMENTO_2")
    session.queue_scalar(phase)

    client = _minimal_app(session)
    resp = client.patch(
        f"/v1/plan/routing-templates/{template_id}/phases/{phase.id}/flexible",
        json={
            "is_flexible": True,
            "allowed_predecessors": ["COLAGEM_PECAS", "COLAGEM_PECAS"],
        },
        headers=_HEADERS,
    )

    assert resp.status_code == 400, resp.text
    assert "duplicados" in resp.json()["detail"]
    assert _added_of_type(session, AuditLog) == []
