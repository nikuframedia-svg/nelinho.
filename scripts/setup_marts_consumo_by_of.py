"""Q.108.G — view `marts.v_consumo_by_of_dia`.

Consumo de material PRESERVANDO erp_of_id, ao contrário de
marts.v_consumo_material_dia (que agrega por material+dia perdendo a OF).

Source: supply.inventory_ledger_entries com erp_of_id NOT NULL.
Q.173.F adicionou a coluna erp_of_id ao ledger (INTEGER FK para OF_FP.OF_ID).
O campo legacy work_order_id (UUID) foi substituído por erp_of_id (INTEGER)
para alinhar com o ERP canónico.

Granularidade: (data, erp_of_id, sku_id). Permite cross-cube com
comercial_facturacao_disciplina (para margem por OF) e logística.

Custo é qty_out × P_PRECOCUSTO; mas P_PRECOCUSTO vive em factory_raw.produto,
não em supply.inventory_ledger_entries. Cube faz JOIN com produto para
calcular custo via Q.108.G measure `custo_eur` no cube.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_consumo_by_of_dia AS
-- Q.173.AJ: usa erp_of_id (INTEGER) em vez de work_order_id (UUID removido).
SELECT
    DATE_TRUNC('day', ile.date)::date                            AS data,
    ile.erp_of_id                                                AS erp_of_id,
    ile.sku_id                                                   AS sku_id,
    p."P_NOME"                                                   AS material,
    SUM(ile.qty_out)                                             AS consumo_qty,
    SUM(ile.qty_out * COALESCE(p."P_PRECOCUSTO", 0))             AS custo_eur,
    COUNT(*)                                                     AS n_movimentos
FROM supply.inventory_ledger_entries ile
LEFT JOIN factory_raw.produto p
  ON p."P_ID"::text = ile.sku_id
WHERE ile.erp_of_id IS NOT NULL
  AND ile.transaction_type = 'consume'
  AND ile.qty_out > 0
GROUP BY 1, 2, 3, 4
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_consumo_by_of_dia")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_consumo_by_of_dia"
        )
        print(f"  OK view criada — {n_rows:,} linhas (dia × OF × sku).")

        if n_rows == 0:
            print(
                "  AVISO: 0 linhas. Re-correr `inventory_ledger` mirror após "
                "Q.108.G para popular work_order_id."
            )
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT erp_of_id)        AS n_ofs,
                COUNT(DISTINCT sku_id)           AS n_materiais,
                SUM(consumo_qty)                 AS total_qty,
                SUM(custo_eur)                   AS total_eur,
                MIN(data) AS min_dia,
                MAX(data) AS max_dia
            FROM marts.v_consumo_by_of_dia
            """
        )
        print(
            f"  OFs com consumo = {edge['n_ofs']:,}  "
            f"materiais = {edge['n_materiais']:,}  "
            f"qty total = {edge['total_qty']:,.2f}  "
            f"custo total = €{edge['total_eur']:,.2f}  "
            f"({edge['min_dia']} → {edge['max_dia']})"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
