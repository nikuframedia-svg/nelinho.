"""
F4.E — BOM API: auditoria na mesma tx + quantity_per gt=0.

Antes deste fix:

* PUT/POST/DELETE em /v1/core/bom não escreviam ``core.audit_log``
  (violação do invariante #7 — toda a escrita audita na mesma transacção);
* ``quantity_per=0`` era aceite (``ge=0``) e corrompia a explosão BOM em
  silêncio (``plan/engines/bom_adapter`` multiplica por ``quantity_per``,
  logo 0 → componente desaparece sem erro).

Monta só o router BOM com FakeSession (canónica de tests/conftest.py) —
não arrasta o main.py nem precisa de Postgres.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.api.bom import router as bom_router
from src.core.models.audit import AuditLog
from src.core.models.bom import BOMItem
from src.shared.database import get_session
from tests.conftest import TEST_TENANT_ID, FakeSession

_HEADERS = {"X-Tenant-Id": str(TEST_TENANT_ID)}


def _bom_item() -> BOMItem:
    now = datetime(2026, 6, 1, 12, 0, 0)
    return BOMItem(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        parent_product_id=uuid4(),
        component_product_id=uuid4(),
        quantity_per=Decimal("2.5"),
        unit_of_measure="UN",
        sequence=0,
        operation_id=None,
        scrap_factor=Decimal("1.0"),
        effective_from=None,
        effective_to=None,
        bom_version=1,
        position_ref=None,
        notes=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def client_and_session():
    session = FakeSession()

    async def _override():
        yield session

    app = FastAPI()
    app.include_router(bom_router)
    app.dependency_overrides[get_session] = _override
    return TestClient(app), session


def test_put_quantity_per_zero_rejected_422(client_and_session):
    client, _ = client_and_session
    resp = client.put(
        f"/bom/{uuid4()}", json={"quantity_per": "0"}, headers=_HEADERS,
    )
    assert resp.status_code == 422


def test_post_quantity_per_zero_rejected_422(client_and_session):
    client, _ = client_and_session
    resp = client.post(
        "/bom",
        json={
            "parent_product_id": str(uuid4()),
            "component_product_id": str(uuid4()),
            "quantity_per": "0",
        },
        headers=_HEADERS,
    )
    assert resp.status_code == 422


def test_put_negative_quantity_per_rejected_422(client_and_session):
    client, _ = client_and_session
    resp = client.put(
        f"/bom/{uuid4()}", json={"quantity_per": "-1.5"}, headers=_HEADERS,
    )
    assert resp.status_code == 422


def test_put_writes_audit_log_in_same_session(client_and_session):
    client, session = client_and_session
    item = _bom_item()
    session.queue_scalar(item)  # MasterDataService.get_bom_item

    resp = client.put(
        f"/bom/{item.id}", json={"quantity_per": "3.0"}, headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert item.quantity_per == Decimal("3.0")

    audits = [a for a in session.added if isinstance(a, AuditLog)]
    assert len(audits) == 1, "PUT tem de escrever exactamente 1 audit_log"
    audit = audits[0]
    assert audit.entity_type == "bom_item"
    assert audit.entity_id == item.id
    assert audit.action == "UPDATE"
    assert audit.old_values == {"quantity_per": "2.5"}
    assert audit.new_values == {"quantity_per": "3.0"}


def test_put_without_changes_writes_no_audit(client_and_session):
    # Payload vazio = nenhum campo alterado → não polui o audit trail.
    client, session = client_and_session
    item = _bom_item()
    session.queue_scalar(item)

    resp = client.put(f"/bom/{item.id}", json={}, headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    assert not [a for a in session.added if isinstance(a, AuditLog)]


def test_delete_writes_audit_log_in_same_session(client_and_session):
    client, session = client_and_session
    item = _bom_item()
    # 1º get_bom_item (endpoint) + 2º get_bom_item (delete_bom_item interno).
    session.queue_scalar(item)
    session.queue_scalar(item)

    resp = client.delete(f"/bom/{item.id}", headers=_HEADERS)
    assert resp.status_code == 204, resp.text
    assert item in session.deleted

    audits = [a for a in session.added if isinstance(a, AuditLog)]
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "DELETE"
    assert audit.entity_id == item.id
    assert audit.new_values is None
    assert audit.old_values["quantity_per"] == "2.5"
    assert audit.old_values["parent_product_id"] == str(item.parent_product_id)
