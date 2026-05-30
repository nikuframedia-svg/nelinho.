"""Q.R-audit — RLS activo nas 7 tabelas da migração 065 (DB real).

§7 da auditoria 2026-05-30. Verifica, contra Postgres real (após
`alembic upgrade head`), que cada uma das 7 tabelas tem `relrowsecurity` e a
policy `tenant_isolation`. Correr: pytest -m integration tests/integration/test_rls_qr_audit.py
"""
from __future__ import annotations

import pytest


SEVEN_TABLES = [
    ("core", "encomendas_cancelled"),
    ("plan", "boat_boost"),
    ("plan", "order_boost"),
    ("plan", "phase_duration_calibration"),
    ("plan", "plan_execution_observed"),
    ("plan", "work_order_override"),
    ("profit", "kpi_snapshot"),
]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rls_enabled_and_policy_on_065_tables():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.shared.config import settings

    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.connect() as conn:
            for schema, table in SEVEN_TABLES:
                rowsec = (
                    await conn.execute(
                        text(
                            "SELECT c.relrowsecurity FROM pg_class c "
                            "JOIN pg_namespace n ON n.oid = c.relnamespace "
                            "WHERE n.nspname = :s AND c.relname = :t"
                        ),
                        {"s": schema, "t": table},
                    )
                ).scalar_one_or_none()
                assert rowsec is True, f"RLS não habilitado em {schema}.{table}"

                pol = (
                    await conn.execute(
                        text(
                            "SELECT 1 FROM pg_policies "
                            "WHERE schemaname = :s AND tablename = :t "
                            "AND policyname = 'tenant_isolation'"
                        ),
                        {"s": schema, "t": table},
                    )
                ).first()
                assert pol is not None, (
                    f"policy tenant_isolation ausente em {schema}.{table}"
                )
    finally:
        await engine.dispose()
