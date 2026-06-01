"""Q.138.I — dedup de alertas CPO via INSERT ... ON CONFLICT DO UPDATE.

Cobre o caminho real que escapava ao dedup Q.138.G:
  - A função _upsert_cpo_alert usa pg_insert com on_conflict_do_update.
  - O statement é sempre executado (independente de sessão.new/dirty).
  - session.commit() é chamado explicitamente pelo _upsert_cpo_alert.

Estratégia: AsyncMock para session.execute + session.commit.
Não usamos FakeSession porque ON CONFLICT só existe em Postgres;
testamos que o statement correcto é construído e submetido à sessão.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, call, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.plan.cpo.scheduler_run import _upsert_cpo_alert

_TENANT = UUID("00000000-0000-0000-0000-000000000001")
_CODE = "ORDERS_WITHOUT_ROUTING"


def _make_session() -> AsyncMock:
    """Sessão AsyncMock mínima para _upsert_cpo_alert."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=AsyncMock())
    session.commit = AsyncMock(return_value=None)
    return session


@pytest.mark.asyncio
async def test_upsert_executes_pg_insert_statement():
    """_upsert_cpo_alert chama session.execute com um pg_insert statement."""
    session = _make_session()

    await _upsert_cpo_alert(
        session, _TENANT, _CODE, "Titulo", "Mensagem", {"count": 4}
    )

    assert session.execute.call_count == 1
    stmt = session.execute.call_args[0][0]
    # O statement deve ser um INSERT (pg_insert devolve Insert)
    from sqlalchemy.dialects.postgresql.dml import Insert
    assert isinstance(stmt, Insert), (
        f"Esperado pg_insert Insert, obtido {type(stmt)}"
    )


@pytest.mark.asyncio
async def test_upsert_commits_explicitly():
    """_upsert_cpo_alert faz session.commit() para garantir persistência.

    session.execute de statement raw não marca session.new/dirty;
    sem commit explícito o get_session_context não commita — rollback implícito.
    """
    session = _make_session()

    await _upsert_cpo_alert(
        session, _TENANT, _CODE, "T", "M", {}
    )

    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_called_twice_executes_twice():
    """Duas chamadas com o mesmo code executam 2× o ON CONFLICT (BD deduplica).

    O Python não precisa de fazer SELECT; a constraint parcial BD garante ≤1 activo.
    """
    session = _make_session()

    await _upsert_cpo_alert(session, _TENANT, _CODE, "T1", "M1", {"n": 1})
    await _upsert_cpo_alert(session, _TENANT, _CODE, "T2", "M2", {"n": 2})

    # 2 execute + 2 commit — a BD é quem dedup via ON CONFLICT DO UPDATE
    assert session.execute.call_count == 2
    assert session.commit.call_count == 2


@pytest.mark.asyncio
async def test_upsert_includes_on_conflict_clause():
    """O statement pg_insert tem on_conflict_do_update configurado.

    Compila o statement para Postgres e verifica que contém ON CONFLICT.
    """
    from sqlalchemy.dialects import postgresql as pg_dialect

    session = _make_session()

    await _upsert_cpo_alert(
        session, _TENANT, _CODE,
        title="4 ordens sem rota",
        message_pt="Mensagem de teste",
        context={"unplanned_count": 4, "orders_coverage": 0.98},
        severity="WARN",
    )

    stmt = session.execute.call_args[0][0]
    compiled = stmt.compile(
        dialect=pg_dialect.dialect(),
        compile_kwargs={"literal_binds": False},
    )
    sql = str(compiled)
    assert "ON CONFLICT" in sql.upper(), (
        f"Statement devia ter ON CONFLICT; obtido:\n{sql}"
    )
    assert "DO UPDATE" in sql.upper(), (
        f"Statement devia ter DO UPDATE; obtido:\n{sql}"
    )


@pytest.mark.asyncio
async def test_upsert_uses_correct_code_and_tenant():
    """Os valores tenant_id e code são passados correctamente ao INSERT."""
    from sqlalchemy.dialects import postgresql as pg_dialect

    session = _make_session()
    tenant = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    code = "DURATION_FALLBACK_HIGH"

    await _upsert_cpo_alert(
        session, tenant, code, "T", "M", {"fallback_fraction": 0.42}
    )

    stmt = session.execute.call_args[0][0]
    # Inspecção dos parâmetros do statement (compiled_parameters)
    compiled = stmt.compile(dialect=pg_dialect.dialect())
    params = compiled.params
    assert str(params.get("tenant_id")) == str(tenant)
    assert params.get("code") == code
    assert params.get("status") == "active"
