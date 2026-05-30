"""Q.125 — Popular core.customers a partir de factory_raw.entidade (ERP real).

A auditoria revelou `core.customers = 0`: o mirror `master` espelha produtos/
operadores mas NUNCA os clientes. Os clientes reais estão em `factory_raw.entidade`
tipados por `E_ENT_ID` (entidade_tipo): **ENT_ID=2 = "Cliente"** (18=Fornecedor,
restantes = papéis de operador). Este script:

  1. Refresca `factory_raw.entidade` do NELO (atómico, DROP-free) — fica fresco.
  2. Upsert `entidade WHERE E_ENT_ID='2'` → `core.customers` (chave: customer_code
     = E_ID). Enums com defaults sãos (RETAIL/NET30/STANDARD); contacto/morada/país
     do ERP. is_active = E_ACTIVO.

Corre standalone OU via o job de scheduler `_nelo_erp_customers_job` (5/5 min).

Uso::

    $env:PYTHONPATH = "."
    .\\.venv\\Scripts\\python.exe scripts/setup_customers_from_entidade.py
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any

import asyncpg

from scripts.q75_setup_raw_mirror import RawTable, _refresh_table_atomic
from src.adapters.nelo.services import get_engine
from src.shared.config import settings

DEV_TENANT = "00000000-0000-0000-0000-000000000001"
CLIENTE_TIPO = "2"  # entidade_tipo.ENT_ID = 2 ("Cliente")

# Upsert determinístico: clientes = entidade do tipo Cliente. As colunas de
# factory_raw são text; NULLIF('') normaliza vazios para NULL.
_TRANSFORM_SQL = f"""
INSERT INTO core.customers
    (id, tenant_id, customer_code, customer_name,
     segment, payment_terms, price_tier,
     contact_email, contact_phone, address_line1, city, postal_code, country,
     is_active, created_at, updated_at)
SELECT
    gen_random_uuid(),
    '{DEV_TENANT}'::uuid,
    LEFT(e."E_ID"::text, 50),
    LEFT(COALESCE(NULLIF(e."E_NOME"::text, ''), 'Cliente ' || e."E_ID"::text), 255),
    'RETAIL', 'NET30', 'STANDARD',
    LEFT(NULLIF(e."E_EMAIL"::text, ''), 255),
    LEFT(NULLIF(e."E_TELEFONE"::text, ''), 50),
    LEFT(NULLIF(e."E_MORADA"::text, ''), 255),
    LEFT(NULLIF(e."E_CIDADE"::text, ''), 100),
    LEFT(NULLIF(e."E_CODIGOPOSTAL"::text, ''), 20),
    LEFT(NULLIF(e."E_PAIS"::text, ''), 100),
    COALESCE(e."E_ACTIVO"::boolean, true),
    now(), now()
FROM factory_raw.entidade e
WHERE e."E_ENT_ID"::text = '{CLIENTE_TIPO}'
  AND e."E_ID" IS NOT NULL
ON CONFLICT (tenant_id, customer_code) DO UPDATE SET
    customer_name = EXCLUDED.customer_name,
    contact_email = EXCLUDED.contact_email,
    contact_phone = EXCLUDED.contact_phone,
    address_line1 = EXCLUDED.address_line1,
    city          = EXCLUDED.city,
    postal_code   = EXCLUDED.postal_code,
    country       = EXCLUDED.country,
    is_active     = EXCLUDED.is_active,
    updated_at    = now()
"""


async def setup() -> dict[str, Any]:
    if not settings.sqlserver_enabled:
        raise SystemExit("SQLSERVER_ENABLED=False — não posso espelhar.")

    sql_engine = get_engine()
    pg_conn = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        # 1. Refrescar factory_raw.entidade (atómico, DROP-free).
        await pg_conn.execute("CREATE SCHEMA IF NOT EXISTS factory_raw")
        ent = await _refresh_table_atomic(
            sql_engine, pg_conn, RawTable("ENTIDADE", None),
        )

        # 2. Índice único p/ o upsert (idempotente).
        await pg_conn.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS ux_customers_tenant_code '
            'ON core.customers (tenant_id, customer_code)'
        )

        before = await pg_conn.fetchval("SELECT COUNT(*) FROM core.customers")
        await pg_conn.execute(_TRANSFORM_SQL)
        after = await pg_conn.fetchval("SELECT COUNT(*) FROM core.customers")
    finally:
        await pg_conn.close()
        await sql_engine.dispose()

    return {
        "entidade_refresh": ent,
        "customers_before": before,
        "customers_after": after,
        "customers_new": after - before,
    }


def main() -> int:
    report = asyncio.run(setup())
    print(f"entidade espelhada: {report['entidade_refresh'].get('rows')} linhas")
    print(f"core.customers: {report['customers_before']} -> "
          f"{report['customers_after']} ({report['customers_new']:+d} novos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
