"""Q.135 — paridade de TABELAS: alembic cria tudo o que vive em Base.metadata.

Análogo de `tests/shared/test_rls_coverage_qr_audit.py` (cobertura RLS), mas para
a existência das tabelas. Verificado em 2026-05-31: numa BD pura-alembic
(`alembic upgrade head`, sem create_all) existem as 124 tabelas ORM — Q.62.A.3
(055a) + Q.134 (066) fecharam a dívida de tabelas create_all-only.

Este guard impede a REGRESSÃO: se alguém adicionar um modelo ORM novo e esquecer
a migração (ficando create_all-only), o teste falha numa BD pura-alembic (CI).
Inspeciona o catálogo vivo, robusto a qualquer migração.

FORA do âmbito (não estão em `Base.metadata`): `factory_raw.*` mirrors (sync ERP,
`scripts/q75_setup_raw_mirror.py`) e views `marts` (063). Por isso a asserção é
**subset** (`ORM ⊆ BD`), não igualdade — a BD pode ter objectos extra legítimos.

NOTA honesta: existe drift de COLUNAS conhecido (server_default/índices/comments,
~800 ops no `alembic check`) — cosmético (mesmo data), tolerado pelo CI
(`continue-on-error`), fora do âmbito deste guard (que é só de TABELAS).
"""
from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_all_orm_tables_exist_in_db():
    """Toda a tabela em `Base.metadata` existe na BD ao head (subset)."""
    import src.shared.model_registry  # popula Base.metadata (side-effect)
    from sqlalchemy import text as sql
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.shared.config import settings
    from src.shared.database import Base

    meta_tables = {
        (t.schema or "public", t.name) for t in Base.metadata.tables.values()
    }

    engine = create_async_engine(settings.database_url, echo=False)
    try:
        try:
            conn_ctx = engine.connect()
            conn = await conn_ctx.__aenter__()
        except Exception as exc:  # pragma: no cover — sem infra (ex.: job sem BD)
            pytest.skip(f"BD indisponível (integration requer infra viva): {exc}")
        try:
            existing = {
                (r[0], r[1])
                for r in (
                    await conn.execute(
                        sql(
                            "SELECT n.nspname, c.relname FROM pg_class c "
                            "JOIN pg_namespace n ON n.oid = c.relnamespace "
                            "WHERE c.relkind = 'r' "
                            "AND n.nspname NOT IN ('pg_catalog', 'information_schema')"
                        )
                    )
                ).all()
            }
        finally:
            await conn_ctx.__aexit__(None, None, None)
    finally:
        await engine.dispose()

    missing = sorted(t for t in meta_tables if t not in existing)
    assert not missing, (
        f"{len(missing)} tabela(s) ORM em falta na BD (create_all-only?): "
        f"{missing}. Cria-as numa migração (padrão 055a/066: "
        "Base.metadata.tables[key].create(bind, checkfirst=True))."
    )
