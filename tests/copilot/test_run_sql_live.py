"""Q.68.A — Live DB integration tests para `src/copilot/tools/`.

Complementa os unit tests `test_sql_runner.py` (que mockam o engine) com
testes que **correm contra o Postgres dev real**, validando que o pipeline
end-to-end funciona — não só a lógica defensiva.

Marca ``@pytest.mark.integration`` para a CI separar. Cada teste tenta
abrir uma conexão; se a BD não estiver disponível, *skip* com motivo
claro em vez de fail.

Cobertura:
    1. SELECT real contra `information_schema.tables` devolve rows.
    2. statement_timeout real dispara em ``pg_sleep(10)`` com cap 5s.
    3. LIMIT cap real limita rows num SELECT grande.
    4. `list_database_tables` real devolve schemas reais.
    5. `describe_table` real devolve colunas reais.
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.copilot.tools.schema_introspection import (
    describe_table,
    list_database_tables,
)
from src.copilot.tools.sql_runner import SqlRunnerError, run_sql
from src.shared.config import get_settings

# loop_scope="module" — todos os async tests neste ficheiro partilham o
# mesmo event loop. Necessário porque test_real_statement_timeout usa
# pg_sleep(10) cancelado via statement_timeout; o asyncpg emite cancel
# tasks pendentes que ficam presos se o loop fechar entre testes
# (Windows ProactorEventLoop + asyncpg _request_cancel → RuntimeError).
pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="module"),
]


async def _db_available() -> bool:
    """Tenta SELECT 1 — devolve True se a dev DB está acessível."""
    settings = get_settings()
    url = settings.copilot_database_url or settings.database_url
    try:
        engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
    except Exception:
        return False
    return True


@pytest.fixture(autouse=True, scope="module")
async def skip_if_no_db():
    """Marca skip se a BD dev não está de pé. Mensagem clara — sem
    crashes confusos quando o programador esqueceu o Postgres."""
    if not await _db_available():
        pytest.skip(
            "Postgres dev não disponível — esta suite exige DB live. "
            "Corre `pwsh scripts/nitro.ps1` ou inicia Postgres + bootstrap.",
        )


async def test_real_select_information_schema():
    """SELECT contra `information_schema.tables` devolve ≥ 1 row.

    Esta é a baseline mais forte: prova que o engine, o role, a regex e o
    LIMIT funcionam end-to-end sem mocks.
    """
    result = await run_sql(
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_type = 'BASE TABLE' "
        "AND table_schema NOT IN ('pg_catalog', 'information_schema')",
        max_rows=5,
    )
    assert result["status"] == "ok"
    assert result["rows_returned"] >= 1, (
        "BD dev deveria ter ≥ 1 user table. Bootstrap correu?"
    )
    assert result["rows_returned"] <= 5, (
        f"LIMIT 5 não foi aplicado: {result['rows_returned']} rows"
    )
    assert "LIMIT 5" in result["sql"]
    assert result["elapsed_ms"] >= 0


async def test_real_statement_timeout_fires_on_slow_query():
    """`pg_sleep(10)` deve falhar dentro do timeout (5s default).

    Sem o timeout, o teste levava 10s. Com o timeout, deve falhar em
    ≤ 6s (5s timeout + algum slack do driver). Aceitamos qualquer
    SqlRunnerError — Postgres pode reportar como QueryCanceled ou
    asyncpg como TimeoutError; o sql_runner envelopa ambos.
    """
    start = time.monotonic()
    with pytest.raises(SqlRunnerError):
        await run_sql("SELECT pg_sleep(10)")
    elapsed = time.monotonic() - start
    assert elapsed < 8.0, (
        f"Timeout não disparou — query demorou {elapsed:.1f}s "
        "(esperado < 8s com statement_timeout 5s)"
    )


async def test_real_limit_cap_bounds_result_size():
    """SELECT que devolveria muitas linhas é tapado pelo LIMIT cap.

    Usamos `generate_series(1, 1000)` — Postgres devolveria 1000 rows;
    com `max_rows=3` só vêem 3.
    """
    result = await run_sql(
        "SELECT i FROM generate_series(1, 1000) i",
        max_rows=3,
    )
    assert result["status"] == "ok"
    assert result["rows_returned"] == 3
    assert "LIMIT 3" in result["sql"]


async def test_real_list_database_tables_returns_schemas():
    """`list_database_tables` (Q.67.4.B) devolve tabelas reais.

    Em dev, esperamos schemas como `core`, `plan`, `quality` — basta um
    schema-user-defined existir.
    """
    tables = await list_database_tables()
    assert isinstance(tables, list)
    assert len(tables) >= 1, "Deveria haver ≥ 1 tabela user-defined"

    # Cada entry deve ter ao menos schema + name.
    sample = tables[0]
    assert "schema" in sample or "table_schema" in sample, (
        f"Estrutura inesperada: {sample!r}"
    )


async def test_real_describe_table_returns_columns():
    """`describe_table` devolve colunas reais — testamos contra
    `plan.production_orders` (tabela real, sempre presente em dev).

    Nota: `information_schema.columns` é uma VIEW (relkind='v'), não uma
    tabela base — o `describe_table` só cobre relkind='r'. Usamos uma
    tabela do nosso schema que sabemos existir após bootstrap.
    """
    info = await describe_table("plan", "production_orders")
    assert isinstance(info, dict)
    assert info.get("exists") is not False, (
        "plan.production_orders deve existir (bootstrap correu?)"
    )
    # A implementação pode usar `columns` ou `cols` — aceitamos ambos.
    cols_key = next(
        (k for k in ("columns", "cols", "fields") if k in info), None,
    )
    assert cols_key, f"Esperava key columns/cols/fields em {info.keys()}"
    cols = info[cols_key]
    assert isinstance(cols, list) and len(cols) > 0
