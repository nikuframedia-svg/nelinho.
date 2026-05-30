"""Q.106.2 — view `marts.v_workforce_horas_extra_mes`.

Horas extra dos colaboradores NELO. Fonte: factory_raw.ent_mov com
MOVENT_MET_ID=1 (Horas Extra). Granularidade 1 row por (mês,
colaborador, departamento).

Q.82 documentou: MOVENT_HORAS é SEMPRE 0 — calcular sempre via
DATEDIFF entre MOVENT_DATA_I e MOVENT_DATA_F. Médias ~3h por evento.

Anchor preliminar: 64 784 eventos histórico × ~3h média = ~190K horas
extra acumulado. A confirmar via psql.

Decisão Luís Q.106: transparência total, dim `colaborador` normal.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_workforce_horas_extra_mes AS
SELECT
    DATE_TRUNC('month', CAST(em."MOVENT_DATA_I" AS timestamp))::date AS data,
    em."MOVENT_E_ID"                                                  AS colaborador_id,
    e."E_NOME"                                                        AS colaborador,
    COALESCE(et."ENT_NOME", 'Sem cargo')                              AS departamento,
    ROUND(SUM(EXTRACT(EPOCH FROM (
        CAST(em."MOVENT_DATA_F" AS timestamp) -
        CAST(em."MOVENT_DATA_I" AS timestamp)
    )) / 3600.0)::numeric, 2)                                         AS horas_extra,
    COUNT(*)                                                          AS n_eventos
FROM factory_raw.ent_mov em
JOIN factory_raw.entidade e ON e."E_ID" = em."MOVENT_E_ID"
LEFT JOIN factory_raw.entidade_tipo et ON et."ENT_ID" = e."E_ENT_ID"
WHERE em."MOVENT_MET_ID" = 1
  AND em."MOVENT_DATA_I" IS NOT NULL
  AND em."MOVENT_DATA_F" IS NOT NULL
  AND NULLIF(em."MOVENT_DATA_I", '') IS NOT NULL
  AND NULLIF(em."MOVENT_DATA_F", '') IS NOT NULL
GROUP BY 1, 2, 3, 4
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS marts")
        await conn.execute("DROP VIEW IF EXISTS marts.v_workforce_horas_extra_mes")
        await conn.execute(VIEW_SQL)

        n = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_workforce_horas_extra_mes"
        )
        totais = await conn.fetchrow(
            "SELECT SUM(horas_extra)::float AS h_total, "
            "SUM(n_eventos)::bigint AS ev_total, "
            "COUNT(DISTINCT colaborador_id) AS n_cols "
            "FROM marts.v_workforce_horas_extra_mes"
        )
        h_2024 = await conn.fetchrow(
            "SELECT ROUND(SUM(horas_extra)::numeric, 0)::bigint AS h, "
            "SUM(n_eventos)::bigint AS ev, "
            "COUNT(DISTINCT colaborador_id) AS n_cols "
            "FROM marts.v_workforce_horas_extra_mes "
            "WHERE EXTRACT(YEAR FROM data) = 2024"
        )
        print(f"  OK -- {n:,} rows (mes x colaborador x departamento).")
        print(f"  Histórico: {totais['h_total']:,.0f}h em {totais['ev_total']:,} "
              f"eventos por {totais['n_cols']} colaboradores")
        print(f"  2024: {h_2024['h']:,}h em {h_2024['ev']:,} eventos "
              f"por {h_2024['n_cols']} colaboradores")

        # Top 5 colaboradores 2024
        print("\n  Top 5 colaboradores por horas extra 2024:")
        rows = await conn.fetch(
            "SELECT colaborador, "
            "ROUND(SUM(horas_extra)::numeric, 0)::bigint AS h "
            "FROM marts.v_workforce_horas_extra_mes "
            "WHERE EXTRACT(YEAR FROM data) = 2024 "
            "GROUP BY colaborador ORDER BY 2 DESC LIMIT 5"
        )
        for r in rows:
            print(f"    {(r['colaborador'] or '?')[:35]:<35}  {r['h']:>6}h")

        # Sanity
        assert totais['ev_total'] >= 60_000, (
            f"Anchor falhou: {totais['ev_total']} eventos (esperado ~64k)"
        )
        print("\n  Anchor OK (≥60k eventos MET=1).")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
