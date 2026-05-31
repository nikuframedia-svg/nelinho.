"""Q.131.C — Espelha plan.production_orders a partir de factory_raw.ordemfabrico.

A lista de ordens (`/v1/plan/orders`, `/stats`, `/active`, `/v1/work-orders`)
lia 12 ordens DEMO (seed SQLite, `product_id` 4271-6004) — nenhum sync ERP a
alimentava. Este mirror torna-a 0 demo: WIP REAL do ERP.

Conjunto = OFs não-terminadas em fase de PRODUÇÃO (`OF_DATAFIM` NULL +
`fases_producao.FP_PRODUCAO=true`, que exclui Entregue/Armazém/Embalado).
Keyspace alinhado ao routing/durações reais (Q.126): **`product_id = OF_P_ID`**
(catálogo ERP), `legacy_id = OF_ID`. `core.products.product_code` é o mesmo
`OF_P_ID`, por isso o MRP passa a poder resolver o BOM (as 12 demo nunca
casavam).

Lê de `factory_raw.*` (já espelhado de 5/5 min por `_nelo_erp_raw_incremental_job`),
logo NÃO depende do SQL Server estar ligado. Upsert idempotente por `legacy_id`;
remove ordens fora do WIP atual (incl. as 12 demo) que não estejam canceladas.

Uso::

    $env:PYTHONPATH = "."
    .\\.venv\\Scripts\\python.exe scripts/q131_setup_production_orders_mirror.py
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any

import asyncpg

from src.shared.config import settings

DEV_TENANT = "00000000-0000-0000-0000-000000000001"

# WIP real: OF não-terminada cuja fase atual é de produção (FP_PRODUCAO=true).
# Spelke CX1: zero campos monetários (€) — só IDs, nomes, datas e fase.
_WIP_CTE = """
    wip AS (
        SELECT
            ofb."OF_ID"                                   AS of_id,
            ofb."OF_P_ID"                                 AS p_id,
            COALESCE(NULLIF(p."P_NOME", ''),
                     'Modelo ' || ofb."OF_P_ID"::text)    AS product_name,
            CASE
                WHEN split_part(upper(trim(COALESCE(p."P_NOME", ''))), ' ', 1)
                     IN ('K1','K2','K4','C1','C2','C4')
                THEN split_part(upper(trim(p."P_NOME")), ' ', 1)
                ELSE 'Other'
            END                                           AS product_type,
            ofb."OF_FP_ID"                                AS phase_id,
            COALESCE(NULLIF(f."FP_NOME", ''),
                     ofb."OF_FP_ID"::text)                AS phase_name,
            CAST(NULLIF(ofb."OF_DATA", '') AS timestamp)::date            AS created_date,
            COALESCE(
                CAST(NULLIF(ofb."OF_TR_DATA_PREVISTA", '') AS timestamp),
                CAST(NULLIF(ofb."OF_DATA", '')           AS timestamp)
            )::date                                       AS transport_date
        FROM factory_raw.ordemfabrico ofb
        JOIN factory_raw.fases_producao f ON f."FP_ID" = ofb."OF_FP_ID"
        LEFT JOIN factory_raw.produto p   ON p."P_ID"  = ofb."OF_P_ID"
        WHERE NULLIF(ofb."OF_DATAFIM", '') IS NULL
          AND f."FP_PRODUCAO" = true
          AND ofb."OF_P_ID" IS NOT NULL
    )
"""

_UPSERT_SQL = f"""
WITH {_WIP_CTE}
INSERT INTO plan.production_orders
    (id, tenant_id, legacy_id, product_id, product_name, product_type,
     current_phase_id, current_phase_name, created_date, transport_date, status,
     created_at, updated_at)
SELECT
    gen_random_uuid(),
    '{DEV_TENANT}'::uuid,
    wip.of_id,
    wip.p_id,
    LEFT(wip.product_name, 255),
    wip.product_type,
    wip.phase_id,
    LEFT(wip.phase_name, 255),
    wip.created_date,
    wip.transport_date,
    'IN_PROGRESS',
    now(), now()
FROM wip
ON CONFLICT (legacy_id) DO UPDATE SET
    product_id         = EXCLUDED.product_id,
    product_name       = EXCLUDED.product_name,
    product_type       = EXCLUDED.product_type,
    current_phase_id   = EXCLUDED.current_phase_id,
    current_phase_name = EXCLUDED.current_phase_name,
    transport_date     = EXCLUDED.transport_date,
    updated_at         = now(),
    status             = CASE
        WHEN plan.production_orders.status = 'CANCELLED'
        THEN 'CANCELLED' ELSE 'IN_PROGRESS' END
"""

# Remove ordens que já não estão no WIP atual (inclui as 12 demo, OF_ID
# 4271-6004, que nunca aparecem no WIP real). Preserva soft-cancel.
_PRUNE_SQL = f"""
WITH {_WIP_CTE}
DELETE FROM plan.production_orders po
WHERE po.tenant_id = '{DEV_TENANT}'::uuid
  AND po.status <> 'CANCELLED'
  AND NOT EXISTS (SELECT 1 FROM wip WHERE wip.of_id = po.legacy_id)
"""


async def setup() -> dict[str, Any]:
    pg = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        before = await pg.fetchval(
            "SELECT COUNT(*) FROM plan.production_orders "
            "WHERE tenant_id = $1", DEV_TENANT,
        )
        wip_n = await pg.fetchval(
            'SELECT COUNT(*) FROM factory_raw.ordemfabrico ofb '
            'JOIN factory_raw.fases_producao f ON f."FP_ID" = ofb."OF_FP_ID" '
            'WHERE NULLIF(ofb."OF_DATAFIM", \'\') IS NULL '
            'AND f."FP_PRODUCAO" = true AND ofb."OF_P_ID" IS NOT NULL'
        )
        # Guarda: sem WIP real (factory_raw vazio em dev/test) NÃO fazemos
        # prune — senão esvaziávamos production_orders e apagávamos seeds.
        if not wip_n:
            return {
                "wip_real": 0, "orders_before": before, "orders_after": before,
                "pruned": "skipped (factory_raw vazio)", "demo_rows_left": None,
                "skipped": True,
            }
        async with pg.transaction():
            await pg.execute(_UPSERT_SQL)
            pruned = await pg.execute(_PRUNE_SQL)
        after = await pg.fetchval(
            "SELECT COUNT(*) FROM plan.production_orders "
            "WHERE tenant_id = $1", DEV_TENANT,
        )
        demo_left = await pg.fetchval(
            "SELECT COUNT(*) FROM plan.production_orders "
            "WHERE tenant_id = $1 AND product_id BETWEEN 4271 AND 6004", DEV_TENANT,
        )
    finally:
        await pg.close()

    return {
        "wip_real": wip_n,
        "orders_before": before,
        "orders_after": after,
        "pruned": pruned,
        "demo_rows_left": demo_left,
    }


def main() -> int:
    report = asyncio.run(setup())
    print(f"WIP real (factory_raw): {report['wip_real']}")
    print(f"plan.production_orders: {report['orders_before']} -> "
          f"{report['orders_after']} (prune: {report['pruned']})")
    print(f"linhas demo (4271-6004) restantes: {report['demo_rows_left']} "
          f"({'OK' if report['demo_rows_left'] == 0 else 'FALHA'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
