"""Q.62.B.3 — testes de wiring + isolamento RLS.

Cobre 3 camadas:

1. **ContextVar** (`src/shared/auth/tenant_context.py`) — set/get/reset
   + context manager `tenant_scope`.
2. **Event listener** (`src/shared/database.py`) — confirma que está
   registado no engine.sync_engine para o event "begin", e que emite
   `SET LOCAL app.tenant_id` quando ContextVar tem valor.
3. **Middleware FastAPI** (`src/main.py`) — extrai X-Tenant-Id (ou
   JWT) e poe em ContextVar para a duracao da request.

**NÃO** cobre a aplicação real das policies RLS contra a DB porque o
utilizador postgres é superuser (bypassa RLS por design). Tests de
isolamento real exigem role non-superuser dedicado — fica para
deploy-time integration test em prod.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event

from src.shared.auth.tenant_context import (
    current_tenant_id_var,
    get_tenant_id,
    reset_tenant_id,
    set_tenant_id,
    tenant_scope,
)


TENANT_A = UUID("00000000-0000-0000-0000-000000000001")
TENANT_B = UUID("00000000-0000-0000-0000-000000000002")


# ─── 1. ContextVar layer ──────────────────────────────────────────────


def test_contextvar_default_is_none():
    """Sem set, get_tenant_id devolve None."""
    # Reset por garantia (test ordering pode ter deixado valor).
    token = set_tenant_id(None)
    try:
        assert get_tenant_id() is None
    finally:
        reset_tenant_id(token)


def test_set_get_reset_tenant_id_cycle():
    """set -> get devolve o valor; reset -> get volta ao anterior."""
    initial = get_tenant_id()
    token = set_tenant_id(TENANT_A)
    try:
        assert get_tenant_id() == TENANT_A
    finally:
        reset_tenant_id(token)
    assert get_tenant_id() == initial


def test_tenant_scope_context_manager_set_and_reset():
    """tenant_scope poe e tira."""
    initial = get_tenant_id()
    with tenant_scope(TENANT_B):
        assert get_tenant_id() == TENANT_B
    assert get_tenant_id() == initial


def test_tenant_scope_with_none_resets_to_none_inside_block():
    """tenant_scope(None) e valido — RLS bloqueia tudo no scope."""
    with tenant_scope(TENANT_A):
        assert get_tenant_id() == TENANT_A
        with tenant_scope(None):
            assert get_tenant_id() is None
        # depois do inner exit, volta ao outer.
        assert get_tenant_id() == TENANT_A


def test_tenant_scope_exception_still_resets():
    """Excepcao dentro do scope nao deixa ContextVar contaminado."""
    initial = get_tenant_id()
    try:
        with tenant_scope(TENANT_A):
            assert get_tenant_id() == TENANT_A
            raise RuntimeError("forçado")
    except RuntimeError:
        pass
    assert get_tenant_id() == initial


# ─── 2. Event listener registo ────────────────────────────────────────


def test_event_listener_registered_on_engine_begin():
    """Confirma que `_set_tenant_id_on_transaction_begin` esta listed
    como handler do event 'begin' no engine.sync_engine."""
    from src.shared.database import engine, _set_tenant_id_on_transaction_begin

    assert event.contains(
        engine.sync_engine, "begin", _set_tenant_id_on_transaction_begin,
    ), "_set_tenant_id_on_transaction_begin nao esta registado no 'begin'"


def test_event_listener_emits_set_local_when_tenant_set(monkeypatch):
    """Quando ContextVar tem valor, o listener chama
    `conn.exec_driver_sql("SET LOCAL app.tenant_id = '<uuid>'")`."""
    from src.shared.database import _set_tenant_id_on_transaction_begin

    captured: list[str] = []

    class FakeConn:
        def exec_driver_sql(self, sql: str):
            captured.append(sql)

    token = set_tenant_id(TENANT_A)
    try:
        _set_tenant_id_on_transaction_begin(FakeConn())
    finally:
        reset_tenant_id(token)

    assert len(captured) == 1, f"Esperado 1 SQL, got {captured}"
    assert "SET LOCAL app.tenant_id" in captured[0]
    assert str(TENANT_A) in captured[0]


def test_event_listener_no_op_when_tenant_unset():
    """Sem tenant_id no ContextVar, listener nao emite SQL."""
    from src.shared.database import _set_tenant_id_on_transaction_begin

    captured: list[str] = []

    class FakeConn:
        def exec_driver_sql(self, sql: str):
            captured.append(sql)

    token = set_tenant_id(None)
    try:
        _set_tenant_id_on_transaction_begin(FakeConn())
    finally:
        reset_tenant_id(token)

    assert captured == [], (
        "Listener emitiu SQL com tenant None — RLS deve ficar inerte"
    )


# ─── 3. Middleware FastAPI ───────────────────────────────────────────


def _make_request(headers: dict) -> MagicMock:
    """Mock minimo de starlette Request — só precisa de `.headers.get`."""
    req = MagicMock()
    # Simular o starlette Headers behaviour (case-insensitive via lower).
    norm = {k.lower(): v for k, v in headers.items()}
    req.headers = MagicMock()
    req.headers.get = lambda key, default=None: norm.get(
        key.lower(), default,
    )
    return req


@pytest.mark.asyncio
async def test_middleware_sets_tenant_from_x_tenant_id_header():
    """Middleware extrai X-Tenant-Id e poe em ContextVar."""
    from src.main import TenantContextMiddleware

    middleware = TenantContextMiddleware(app=MagicMock())

    captured: list = []

    async def fake_next(_request):
        captured.append(get_tenant_id())
        return MagicMock()

    req = _make_request({"X-Tenant-Id": str(TENANT_A)})
    await middleware.dispatch(req, fake_next)

    assert captured == [TENANT_A]


@pytest.mark.asyncio
async def test_middleware_zero_uuid_does_not_set():
    """Zero UUID e tratado como ausente (RLS bloqueia)."""
    from src.main import TenantContextMiddleware

    middleware = TenantContextMiddleware(app=MagicMock())

    captured: list = []

    async def fake_next(_request):
        captured.append(get_tenant_id())
        return MagicMock()

    req = _make_request({"X-Tenant-Id": "00000000-0000-0000-0000-000000000000"})
    await middleware.dispatch(req, fake_next)

    assert captured == [None]


@pytest.mark.asyncio
async def test_middleware_invalid_uuid_does_not_set():
    """Header invalido nao parte — fica None."""
    from src.main import TenantContextMiddleware

    middleware = TenantContextMiddleware(app=MagicMock())

    captured: list = []

    async def fake_next(_request):
        captured.append(get_tenant_id())
        return MagicMock()

    req = _make_request({"X-Tenant-Id": "not-a-uuid"})
    await middleware.dispatch(req, fake_next)

    assert captured == [None]


@pytest.mark.asyncio
async def test_middleware_resets_after_request():
    """Depois da request, ContextVar volta ao valor original."""
    from src.main import TenantContextMiddleware

    middleware = TenantContextMiddleware(app=MagicMock())

    async def fake_next(_request):
        return MagicMock()

    initial = get_tenant_id()
    req = _make_request({"X-Tenant-Id": str(TENANT_A)})
    await middleware.dispatch(req, fake_next)

    assert get_tenant_id() == initial


# ─── 4. Migration sanity (pin que 056 existe e tem 87 tabelas) ───────


def test_migration_056_lists_87_tables():
    """Pin: migration 056 deve incluir 87 (tenant, table) tuples."""
    from pathlib import Path

    path = Path("alembic/versions/056_q62_b_rls_enable.py")
    text = path.read_text(encoding="utf-8")

    # Conta tuples no formato ("schema", "table") na lista
    # TABLES_WITH_TENANT_ID.
    import re
    matches = re.findall(r'\("([a-z_]+)",\s*"([a-z_]+)"\)', text)
    assert len(matches) >= 87, (
        f"056 deveria listar >= 87 tabelas; só lista {len(matches)}"
    )


def test_migration_056_creates_tenant_isolation_policy():
    """Pin: migration cria policy chamada `tenant_isolation`."""
    from pathlib import Path

    text = Path("alembic/versions/056_q62_b_rls_enable.py").read_text(
        encoding="utf-8"
    )
    assert "CREATE POLICY tenant_isolation" in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "current_setting('app.tenant_id'" in text
