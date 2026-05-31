"""Q.94.A.0.3 — estender `marts.v_consumo_material_dia` com coluna `custo`.

Substitui a view existente, mantendo (`data`, `material`, `unidade_id`,
`quantidade`, `n_movimentos`) IDÊNTICOS e acrescentando `custo`.

**Semântica do P_UNI_MOV_FACTOR (validada contra dados reais)**:
- `MOV_QUANTIDADE` está em **unidade-base** (P_UNI_ID — ex.: kg para Resinas).
- `× P_UNI_MOV_FACTOR` (< 1 quando aplicável) **converte para unidade-movs**
  (P_UNI_ID_MOVIMENTOS — ex.: tambor; factor=0.00417=1/240 para tambor 240kg).
- Logo: `quantidade` na view (com factor) está em unidade-movs (tambor);
  custo precisa de `MOV_QUANTIDADE × P_PRECOCUSTO` (em unidade-base × €/kg = €).

**P_PRECOCUSTO em €/unidade-base** (validado contra anchor):
- Resina Lavesan EN 720: P_PRECOCUSTO=7.78, MOV_PRECOUNITARIO=7.78 (idênticos).
- Sanity: 1133.68 kg × 7.78 €/kg = 8.819 € em Abril (industrialmente plausível).

Defesa contra preço inventado: `NULLIF(P_PRECOCUSTO, 0)` força NULL quando
preço é 0 (sentinela "sem preço" da NELO). SUM ignora NULL → custo NULL na
linha quando todos os preços são 0. Não inventa €0.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_consumo_material_dia AS
-- KPI: consumo + custo de matéria-prima por dia × material × unidade.
-- Q.93 (consumo): MOV_TPMOV_ID=11 + P_PCONT_ID=1 + factor.
-- Q.94 (custo):  quantidade × NULLIF(P_PRECOCUSTO, 0) → € em unidade-base.
--                Material sem preço → custo NULL (NÃO inventa 0).
SELECT
    CAST(m."MOV_DATA" AS date)                                AS data,
    p."P_NOME"                                                AS material,
    p."P_UNI_ID_MOVIMENTOS"                                   AS unidade_id,
    SUM(m."MOV_QUANTIDADE"::numeric
        * COALESCE(p."P_UNI_MOV_FACTOR", 1))                  AS quantidade,
    SUM(m."MOV_QUANTIDADE"::numeric
        * NULLIF(p."P_PRECOCUSTO", 0))                        AS custo,
    COUNT(*)                                                  AS n_movimentos
FROM factory_raw.movimento m
JOIN factory_raw.produto p ON p."P_ID" = m."MOV_P_ID"
WHERE m."MOV_TPMOV_ID" = 11
  AND p."P_PCONT_ID"   = 1
GROUP BY CAST(m."MOV_DATA" AS date), p."P_NOME", p."P_UNI_ID_MOVIMENTOS"
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    pg_conn = await asyncpg.connect(pg_dsn)
    try:
        # CREATE OR REPLACE recusa se a ordem das colunas muda (Postgres). DROP + CREATE.
        await pg_conn.execute("DROP VIEW IF EXISTS marts.v_consumo_material_dia")
        await pg_conn.execute(VIEW_SQL)
        # Sanity: row count + linha âncora.
        rows = await pg_conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_consumo_material_dia"
        )
        anchor = await pg_conn.fetchrow(
            """
            SELECT material, unidade_id, quantidade, custo, n_movimentos
            FROM marts.v_consumo_material_dia
            WHERE material = 'Resina Lavesan EN 720'
              AND data >= '2026-04-01' AND data < '2026-05-01'
            ORDER BY data DESC LIMIT 1
            """
        )
        print(f"  OK view criada, total rows={rows:,}")
        if anchor:
            print(
                f"  Âncora Resina Lavesan EN 720 (Abril 2026):\n"
                f"    quantidade={anchor['quantidade']}\n"
                f"    custo     ={anchor['custo']}\n"
                f"    n_movs    ={anchor['n_movimentos']}"
            )
        return 0
    finally:
        await pg_conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
