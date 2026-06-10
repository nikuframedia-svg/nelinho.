"""Q.168.D — quarentena REAL: tabelas curadas em vez de mock.

A auditoria 2026-06-10 (achado CRITICAL verificado) apanhou o
`GET /v1/factory/quarantine` a devolver 2 rows HARDCODED sempre e o
`POST /quarantine/{id}/resolve` a devolver um 200 fake sem persistência
nem audit — violação direta dos invariantes #1 (zero mocks), #7 (audit na
mesma tx) e #8 (dados honestos). Estes testes travam o contrato novo.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.factory_data_product.api.endpoints import router as factory_router
from src.factory_data_product.api.routers._deps import get_engine, get_semantic
from src.factory_data_product.models.curated import CuratedOrder
from src.shared.auth.headers import (
    get_current_user_or_dev_header,
    require_tenant_header,
)
from src.shared.auth.jwt_handler import UserContext
from src.shared.database import get_session
from tests.conftest import FakeSession, TEST_TENANT_ID

_USER_ID = UUID("22222222-2222-2222-2222-222222222222")


def _quarantined_order() -> CuratedOrder:
    return CuratedOrder(
        id=uuid4(),
        ingestion_id=uuid4(),
        of_id="OF-778899",
        is_quarantined=True,
        quarantine_code="INVALID_TIMING",
        quarantine_reason="Fim antes de Início, duração=-2.00h",
        quarantined_at=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def fake_db() -> FakeSession:
    return FakeSession()


@pytest.fixture
def client(fake_db: FakeSession) -> TestClient:
    app = FastAPI()
    app.include_router(factory_router)
    app.dependency_overrides[get_engine] = lambda: object()
    app.dependency_overrides[get_semantic] = lambda: None
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT_ID
    app.dependency_overrides[get_current_user_or_dev_header] = lambda: UserContext(
        user_id=_USER_ID, tenant_id=TEST_TENANT_ID, role="ADMIN",
    )

    async def _db():
        yield fake_db

    app.dependency_overrides[get_session] = _db
    return TestClient(app)


def test_list_returns_real_row_from_curated_table(client, fake_db):
    """Uma row real em quarentena na tabela `order` sai com o shape do
    contrato — id/tabela/código/razão vêm da BD, não de exemplos."""
    row = _quarantined_order()
    fake_db.queue_scalars([row])  # 1ª tabela varrida = order; restantes vazias

    resp = client.get("/v1/factory/quarantine?table=order")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    item = body["rows"][0]
    assert item["id"] == str(row.id)
    assert item["table_name"] == "order"
    assert item["quarantine_code"] == "INVALID_TIMING"
    assert item["row_data"]["of_id"] == "OF-778899"
    assert body["by_table"] == {"order": 1}


def test_resolve_accept_risk_persists_and_audits(client, fake_db):
    """resolve accept_risk → is_quarantined=False, audit_log na MESMA tx
    (invariante #7), commit chamado — nada de 200 fake."""
    row = _quarantined_order()
    fake_db.queue_scalar(row)  # lookup na tabela `order`

    resp = client.post(
        f"/v1/factory/quarantine/{row.id}/resolve",
        params={
            "action": "accept_risk",
            "reason": "Risco aceite pela equipa de dados",
            "table": "order",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["table_name"] == "order"
    assert body["resolved_by"] == str(_USER_ID)

    assert row.is_quarantined is False, "tem de PERSISTIR a resolução"
    assert fake_db.commit_calls >= 1
    audit_rows = [a for a in fake_db.added if type(a).__name__ == "AuditLog"]
    assert audit_rows, "audit_log na mesma transacção (invariante #7)"
    assert audit_rows[0].entity_type == "curated_quarantine:order"


def test_resolve_delete_removes_row_and_audits(client, fake_db):
    row = _quarantined_order()
    fake_db.queue_scalar(row)

    resp = client.post(
        f"/v1/factory/quarantine/{row.id}/resolve",
        params={
            "action": "delete",
            "reason": "Linha lixo confirmada no ERP",
            "table": "order",
        },
    )
    assert resp.status_code == 200
    assert row in fake_db.deleted
    audit_rows = [a for a in fake_db.added if type(a).__name__ == "AuditLog"]
    assert audit_rows and audit_rows[0].action == "DELETE"


def test_resolve_missing_row_is_404(client, fake_db):
    rid = uuid4()
    resp = client.post(
        f"/v1/factory/quarantine/{rid}/resolve",
        params={"action": "repair", "reason": "Tentativa sobre row inexistente"},
    )
    assert resp.status_code == 404
    assert "não está em quarentena" in resp.json()["detail"]


def test_resolve_invalid_action_is_422(client):
    resp = client.post(
        f"/v1/factory/quarantine/{uuid4()}/resolve",
        params={"action": "explodir", "reason": "Acção fora do enum permitido"},
    )
    assert resp.status_code == 422


def test_factory_routes_require_tenant_header(fake_db):
    """Q.168.D — o gate require_tenant_header está no router-pai: sem header
    (e sem override) o /v1/factory/* recusa em vez de servir dados."""
    app = FastAPI()
    app.include_router(factory_router)
    app.dependency_overrides[get_engine] = lambda: object()

    async def _db():
        yield fake_db

    app.dependency_overrides[get_session] = _db
    client = TestClient(app)

    resp = client.get("/v1/factory/quarantine")  # sem X-Tenant-Id
    assert resp.status_code in (400, 401, 422), resp.text
