"""Q.115.B — testes dos endpoints config + user_input.

13 cenários conforme DoD. Usa FakeSession (sem DB real).

Padrão de override:
  - get_session → FakeSession
  - require_tenant_header → devolve TEST_TENANT_ID directamente
  - require_user_header → devolve "operador_teste"
  - PermissionDependency.__call__ é overridden via monkeypatch no módulo,
    não via dependency_overrides (instâncias não são hashable como chave).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import AsyncGenerator
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.routers.q115_config import (
    _require_config_write,
    _require_schedule_read,
    router as q115_router,
)
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.database import get_session
from tests.conftest import FakeSession, TEST_TENANT_ID

# ─── Constantes de teste ───────────────────────────────────────────────────

_TENANT = str(TEST_TENANT_ID)
_HEADERS = {"X-Tenant-Id": _TENANT, "X-User-Id": "operador_teste"}


# ─── Helpers ──────────────────────────────────────────────────────────────


def _ns(**kwargs) -> SimpleNamespace:
    """Cria um SimpleNamespace para simular rows SQLAlchemy."""
    ns = SimpleNamespace(**kwargs)
    # Preenche campos comuns omitidos
    for field, default in [
        ("id", uuid4()),
        ("tenant_id", TEST_TENANT_ID),
        ("audit_trace_id", None),
        ("result_pr_url", None),
        ("claude_run_id", None),
    ]:
        if not hasattr(ns, field):
            setattr(ns, field, default)
    return ns


def _revenue_row(**kwargs) -> SimpleNamespace:
    defaults = {
        "id": uuid4(),
        "tenant_id": TEST_TENANT_ID,
        "effective_from": date(2026, 6, 1),
        "target_eur": 30000.0,
        "created_by": "operador_teste",
        "created_at": datetime.now(timezone.utc),
        "audit_trace_id": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _cp_row(**kwargs) -> SimpleNamespace:
    cid = kwargs.pop("client_id", uuid4())
    defaults = {
        "client_id": cid,
        "tenant_id": TEST_TENANT_ID,
        "priority": 2,
        "reason": None,
        "updated_at": datetime.now(timezone.utc),
        "updated_by": "operador_teste",
    }
    defaults.update(kwargs)
    ns = SimpleNamespace(**defaults)
    return ns


def _ui_row(**kwargs) -> SimpleNamespace:
    defaults = {
        "id": uuid4(),
        "tenant_id": TEST_TENANT_ID,
        "created_at": datetime.now(timezone.utc),
        "author": "operador_teste",
        "what": "Muda o revenue target de 30000 para 35000 na tab Custos",
        "where_page": "configuracoes",
        "economic_reason": "A faturação subiu 15% e o target está desactualizado desde Janeiro.",
        "status": "pending",
        "result_pr_url": None,
        "claude_run_id": None,
        "audit_trace_id": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)




# ─── 1. POST /v1/config/revenue-target — happy path → 201 ─────────────────


def test_create_revenue_target_happy_path():
    session = FakeSession()
    client = _minimal_app(session)

    resp = client.post(
        "/v1/config/revenue-target",
        json={"effective_from": "2026-06-01", "target_eur": "30000.00"},
        headers=_HEADERS,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["effective_from"] == "2026-06-01"
    assert float(body["target_eur"]) == 30000.0
    # audit row adicionado à session
    audit_rows = [o for o in session.added if o.__class__.__name__ == "AuditLog"]
    assert len(audit_rows) == 1


def _minimal_app(session: FakeSession) -> TestClient:
    app = FastAPI()
    app.include_router(q115_router)

    async def _s():
        yield session

    async def _no_rbac():
        return None

    app.dependency_overrides[get_session] = _s
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT_ID
    app.dependency_overrides[require_user_header] = lambda: "operador_teste"
    app.dependency_overrides[_require_config_write] = _no_rbac
    app.dependency_overrides[_require_schedule_read] = _no_rbac
    return TestClient(app, raise_server_exceptions=True)


# ─── 2. POST com target_eur=0 → 422 ───────────────────────────────────────


def test_create_revenue_target_zero_amount():
    client = _minimal_app(FakeSession())
    resp = client.post(
        "/v1/config/revenue-target",
        json={"effective_from": "2026-06-01", "target_eur": "0"},
        headers=_HEADERS,
    )
    assert resp.status_code == 422


# ─── 3. POST duplicado mesma data → 409 ───────────────────────────────────


def test_create_revenue_target_duplicate_date(monkeypatch):
    """Simula IntegrityError do Postgres no flush."""
    from sqlalchemy.exc import IntegrityError

    session = FakeSession()

    async def _flush_raises():
        raise IntegrityError(None, None, Exception("duplicate key"))

    session.flush = _flush_raises  # type: ignore[method-assign]
    client = _minimal_app(session)

    resp = client.post(
        "/v1/config/revenue-target",
        json={"effective_from": "2026-06-01", "target_eur": "30000.00"},
        headers=_HEADERS,
    )
    assert resp.status_code == 409
    assert "Já existe" in resp.json()["detail"]


# ─── 4. GET revenue-target devolve lista ──────────────────────────────────


def test_list_revenue_targets_ordered():
    rows = [
        _revenue_row(effective_from=date(2026, 6, 1)),
        _revenue_row(effective_from=date(2026, 5, 1)),
    ]
    session = FakeSession()
    session.queue_scalars(rows)
    client = _minimal_app(session)

    resp = client.get("/v1/config/revenue-target", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    # primeiro deve ser mais recente (desc — depende da query real, aqui fake devolve na ordem dada)
    assert body[0]["effective_from"] == "2026-06-01"


# ─── 5. PUT /v1/config/client-priority/{id} — happy path (INSERT) ─────────


def test_upsert_client_priority_happy_path():
    cid = uuid4()
    session = FakeSession()
    # scalar_one_or_none devolve None → INSERT
    session.queue_scalar(None)
    client = _minimal_app(session)

    resp = client.put(
        f"/v1/config/client-priority/{cid}",
        json={"priority": 2, "reason": "cliente VIP"},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["priority"] == 2
    assert body["reason"] == "cliente VIP"
    # audit row adicionado
    audit_rows = [o for o in session.added if o.__class__.__name__ == "AuditLog"]
    assert len(audit_rows) == 1


# ─── 6. PUT com priority=6 → 422 ─────────────────────────────────────────


def test_upsert_client_priority_out_of_range():
    client = _minimal_app(FakeSession())
    resp = client.put(
        f"/v1/config/client-priority/{uuid4()}",
        json={"priority": 6},
        headers=_HEADERS,
    )
    assert resp.status_code == 422


# ─── 7. POST /v1/user-input — happy path ─────────────────────────────────


def test_create_user_input_happy_path():
    session = FakeSession()
    client = _minimal_app(session)

    resp = client.post(
        "/v1/user-input",
        json={
            "what": "Muda o revenue target de 30000 para 35000",
            "where_page": "configuracoes",
            "economic_reason": (
                "A faturacao do trimestre subiu 15% e o target actual esta desactualizado."
            ),
        },
        headers=_HEADERS,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["where_page"] == "configuracoes"
    # audit row adicionado
    audit_rows = [o for o in session.added if o.__class__.__name__ == "AuditLog"]
    assert len(audit_rows) == 1


# ─── 8. POST user-input com what demasiado curto → 422 ───────────────────


def test_create_user_input_what_too_short():
    client = _minimal_app(FakeSession())
    resp = client.post(
        "/v1/user-input",
        json={
            "what": "X",
            "where_page": "overall",
            "economic_reason": "Razao economica suficientemente longa para passar na validacao minima.",
        },
        headers=_HEADERS,
    )
    assert resp.status_code == 422


# ─── 9. POST user-input com economic_reason curta → 422 ──────────────────


def test_create_user_input_economic_reason_too_short():
    client = _minimal_app(FakeSession())
    resp = client.post(
        "/v1/user-input",
        json={
            "what": "Muda o revenue target de 30000 para 35000",
            "where_page": "configuracoes",
            "economic_reason": "curta",
        },
        headers=_HEADERS,
    )
    assert resp.status_code == 422


# ─── 10. POST user-input com what vago → 422 ─────────────────────────────


def test_create_user_input_vague_what():
    client = _minimal_app(FakeSession())
    resp = client.post(
        "/v1/user-input",
        json={
            "what": "qualquer coisa",
            "where_page": "decisoes",
            "economic_reason": "Razao economica suficientemente longa para passar na validacao minima.",
        },
        headers=_HEADERS,
    )
    assert resp.status_code == 422
    assert "vaga" in resp.text.lower()


# ─── 11. POST user-input com where_page inválido → 422 ───────────────────


def test_create_user_input_invalid_where_page():
    client = _minimal_app(FakeSession())
    resp = client.post(
        "/v1/user-input",
        json={
            "what": "Muda o revenue target de 30000 para 35000",
            "where_page": "random",
            "economic_reason": "Razao economica suficientemente longa para passar na validacao minima.",
        },
        headers=_HEADERS,
    )
    assert resp.status_code == 422


# ─── 12. GET /v1/user-input?status=pending filtra correctamente ──────────


def test_list_user_input_filters_by_status():
    pending = _ui_row(status="pending")
    session = FakeSession()
    session.queue_scalars([pending])
    client = _minimal_app(session)

    resp = client.get("/v1/user-input?status=pending", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "pending"


# ─── 13. PATCH /v1/user-input/{id} — audit row criado ────────────────────


def test_patch_user_input_creates_audit():
    row = _ui_row(status="pending")
    session = FakeSession()
    session.queue_scalar(row)
    client = _minimal_app(session)

    resp = client.patch(
        f"/v1/user-input/{row.id}",
        json={"status": "in_progress", "claude_run_id": "run_abc123"},
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["claude_run_id"] == "run_abc123"
    # audit row obrigatório
    audit_rows = [o for o in session.added if o.__class__.__name__ == "AuditLog"]
    assert len(audit_rows) == 1
