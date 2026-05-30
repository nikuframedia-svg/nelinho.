"""Q.93.A — criar `marts.v_consumo_material_dia` (Cube Fase 0 view).

Cria a view canónica de consumo de matéria-prima por dia × material × unidade,
fundação para a camada semântica (Cube.dev). Depende de `factory_raw.movimento`
e `factory_raw.produto` existirem — populadas por `q75_setup_raw_mirror.py`.

A view replica os filtros INTOCÁVEIS Q.78 SubB2.3 já provados pela rota
congelada `consumo_materiais.yml` (Q.86):
  - MOV_TPMOV_ID = 11 (Saída como componente, consumo de produção)
  - P_PCONT_ID   = 1  (Matéria-prima estrita; 5.913 produtos)
  - Factor:      MOV_QUANTIDADE * COALESCE(P_UNI_MOV_FACTOR, 1)

Granularidade: uma linha por (data, material, unidade_id). NÃO agrega por
mês — agregar é trabalho do consumidor (Cube, dashboard).

Idempotente. Falha cedo se factory_raw.* não existir.

Uso:
    .\\.venv\\Scripts\\python.exe scripts/setup_marts_cube_fase0.py
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_consumo_material_dia AS
-- KPI: consumo de matéria-prima por dia × material × unidade.
-- Fonte: factory_raw.movimento (espelho 1:1 dbo.MOVIMENTO SQL Server).
-- Filtros canónicos confirmados em Q.78 SubB2.3 / _GLOSSARIO_CENTRAL.md.
--   MOV_TPMOV_ID = 11  -> Saída como componente (consumo de produção)
--   P_PCONT_ID   = 1   -> Matéria-prima estrita (5.913 produtos)
--   Factor:  MOV_QUANTIDADE * COALESCE(P_UNI_MOV_FACTOR, 1)
-- Granularidade: (data, material, unidade_id) — uma linha por dia × produto × unidade.
-- NÃO inclui: Reservas (TPMOV=4), stockagem (TPMOV in 2,12),
-- consumíveis (PCONT=2 — lixas, fitas 3M).
-- Note: MOV_DATA é text (ISO-8601) por causa do mapping do Q.75 — cast para date.
SELECT
    CAST(m."MOV_DATA" AS date)                                AS data,
    p."P_NOME"                                                AS material,
    p."P_UNI_ID_MOVIMENTOS"                                   AS unidade_id,
    SUM(m."MOV_QUANTIDADE"::numeric
        * COALESCE(p."P_UNI_MOV_FACTOR", 1))                  AS quantidade,
    COUNT(*)                                                  AS n_movimentos
FROM factory_raw.movimento m
JOIN factory_raw.produto p ON p."P_ID" = m."MOV_P_ID"
WHERE m."MOV_TPMOV_ID" = 11
  AND p."P_PCONT_ID"   = 1
GROUP BY CAST(m."MOV_DATA" AS date), p."P_NOME", p."P_UNI_ID_MOVIMENTOS"
"""


async def _ensure_prereqs(pg_conn: asyncpg.Connection) -> None:
    """Confirma que factory_raw.movimento e factory_raw.produto existem."""
    for table in ("movimento", "produto"):
        exists = await pg_conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'factory_raw' AND table_name = $1
            )
            """,
            table,
        )
        if not exists:
            raise SystemExit(
                f"factory_raw.{table} não existe — corre primeiro "
                "`python scripts/q75_setup_raw_mirror.py` para espelhar "
                "o ERP, depois volta a correr este script."
            )

    # Schema marts vem da migração 063_q93_a_marts_schema, mas garantir aqui
    # também (idempotente, defensivo).
    await pg_conn.execute("CREATE SCHEMA IF NOT EXISTS marts")


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    pg_conn = await asyncpg.connect(pg_dsn)
    try:
        await _ensure_prereqs(pg_conn)
        await pg_conn.execute(VIEW_SQL)
        print("OK — marts.v_consumo_material_dia criada/actualizada.")

        # Sanity check rápido: a view tem rows?
        n_rows = await pg_conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_consumo_material_dia"
        )
        n_dias = await pg_conn.fetchval(
            "SELECT COUNT(DISTINCT data) FROM marts.v_consumo_material_dia"
        )
        n_materiais = await pg_conn.fetchval(
            "SELECT COUNT(DISTINCT material) FROM marts.v_consumo_material_dia"
        )
        print(
            f"   {n_rows:,} linhas | {n_dias:,} dias distintos "
            f"| {n_materiais:,} materiais distintos"
        )
        if n_rows == 0:
            print(
                "AVISO: view criada mas 0 linhas — verificar se "
                "factory_raw.movimento foi populada e se há movimentos "
                "com TPMOV=11 + PCONT=1 na janela espelhada."
            )
            return 2
    finally:
        await pg_conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
