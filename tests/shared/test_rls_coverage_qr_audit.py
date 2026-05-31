"""Q.R-audit — cobertura RLS (o `test_rls_table_coverage_q62_b` prometido na 056).

§7 da auditoria 2026-05-30: 7 tabelas tenant ficaram sem policy
`tenant_isolation` depois da 056 (modelos criados depois). A migração 065
fecha o buraco. A 056 (docstring, linha 44) prometeu este coverage test mas
nunca foi escrito — fica aqui:

  * pins sem DB sobre a 065 (mesma forma dos pins da 056);
  * o coverage integral (DB real): toda a tabela tenant conhecida pelo ORM que
    existe na BD tem policy `tenant_isolation`, descontando exclusões
    documentadas. Robusto a *qualquer* migração RLS (056, 060, q115_*, 065, …)
    porque inspeciona o catálogo vivo, não o texto das migrações.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


# Tabelas com coluna tenant_id mas SEM RLS direto, por design. Origem: docstring
# da 056_q62_b_rls_enable (tenant_id via JOIN / global / tabela-dos-tenants).
EXCLUDED: set[tuple[str, str]] = {
    ("core", "tenants"),
    ("public", "event_dlq"),
    ("shared", "decision_approvals"),
}


# ─── pins sem DB sobre a migração 065 ────────────────────────────────


def test_migration_065_lists_7_tables():
    text = Path("alembic/versions/065_qr_audit_rls.py").read_text(encoding="utf-8")
    matches = re.findall(r'\("([a-z_]+)",\s*"([a-z_]+)"\)', text)
    assert len(matches) == 7, f"065 devia listar 7 tabelas; lista {len(matches)}"


def test_migration_065_creates_tenant_isolation_policy():
    text = Path("alembic/versions/065_qr_audit_rls.py").read_text(encoding="utf-8")
    assert "CREATE POLICY tenant_isolation" in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "current_setting('app.tenant_id'" in text


# ─── coverage integral (DB real) ─────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rls_table_coverage_q62_b():
    """Toda a tabela tenant (ORM ∩ BD) tem policy `tenant_isolation`."""
    import src.shared.model_registry  # noqa: F401 — popula Base.metadata
    from sqlalchemy import text as sql
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.shared.config import settings
    from src.shared.database import Base

    meta_tenant = {
        (t.schema or "public", t.name)
        for t in Base.metadata.tables.values()
        if "tenant_id" in t.c
    }

    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.connect() as conn:
            existing = {
                (r[0], r[1])
                for r in (
                    await conn.execute(
                        sql(
                            "SELECT n.nspname, c.relname FROM pg_class c "
                            "JOIN pg_namespace n ON n.oid = c.relnamespace "
                            "WHERE c.relkind = 'r'"
                        )
                    )
                ).all()
            }
            policied = {
                (r[0], r[1])
                for r in (
                    await conn.execute(
                        sql(
                            "SELECT schemaname, tablename FROM pg_policies "
                            "WHERE policyname = 'tenant_isolation'"
                        )
                    )
                ).all()
            }
    finally:
        await engine.dispose()

    to_check = (meta_tenant & existing) - EXCLUDED
    missing = sorted(t for t in to_check if t not in policied)
    assert not missing, (
        f"{len(missing)} tabela(s) tenant sem policy tenant_isolation: {missing}. "
        "Adiciona-as a uma migração RLS (padrão 056/065)."
    )
