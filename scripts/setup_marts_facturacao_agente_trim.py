"""Q.108.C — view `marts.v_facturacao_agente_trim`.

Facturação ATRIBUÍDA A AGENTES comerciais (declaração trimestral).
Fonte: factory_raw.agente_faturacao (AF_*, Q.108-A espelhada).

**Fonte é INDEPENDENTE de EPHCF** (comercial_facturacao). São dois
ângulos da mesma facturação:
- `comercial_facturacao.total` (EPHCF): facturação OFICIAL PHC, todas
  as vendas (€125.4M acumulado, €9.5M em 2024).
- `comercial_facturacao_agente.total` (AGENTE_FATURACAO): declaração
  trimestral de agentes (€65.8M acumulado, €3.1M em 2024 — só vendas
  com agente; resto = vendas directas).

NUNCA somar entre si (dupla contagem).

Granularidade view: 1 row por (data_trim, ano, trimestre, agente_id, agente).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_facturacao_agente_trim AS
SELECT
    MAKE_DATE(af."AF_ANO", (af."AF_TRIMESTRE"-1)*3+1, 1) AS data,
    af."AF_ANO"                                          AS ano,
    af."AF_TRIMESTRE"                                    AS trimestre,
    af."AF_E_ID"                                         AS agente_id,
    COALESCE(e."E_NOME", 'Sem agente registado')         AS agente,
    SUM(af."AF_VALOR"::numeric)                          AS facturado_eur,
    COUNT(*)                                             AS n_declaracoes
FROM factory_raw.agente_faturacao af
LEFT JOIN factory_raw.entidade e ON e."E_ID" = af."AF_E_ID"
WHERE af."AF_ANO" IS NOT NULL
GROUP BY 1, 2, 3, 4, 5
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='factory_raw' AND table_name='agente_faturacao')"
        )
        if not exists:
            raise SystemExit(
                "factory_raw.agente_faturacao nao existe — corre primeiro "
                "`python scripts/q108_a_setup_extra_mirror.py`."
            )

        await conn.execute("DROP VIEW IF EXISTS marts.v_facturacao_agente_trim")
        await conn.execute(VIEW_SQL)

        n = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_facturacao_agente_trim"
        )
        totals = await conn.fetchrow(
            "SELECT ROUND(SUM(facturado_eur)::numeric, 0)::bigint AS total, "
            "COUNT(DISTINCT agente_id) AS agentes "
            "FROM marts.v_facturacao_agente_trim"
        )
        a2024 = await conn.fetchval(
            "SELECT ROUND(SUM(facturado_eur)::numeric, 0)::bigint "
            "FROM marts.v_facturacao_agente_trim WHERE ano = 2024"
        )
        gusser = await conn.fetchval(
            "SELECT ROUND(SUM(facturado_eur)::numeric, 0)::bigint "
            "FROM marts.v_facturacao_agente_trim "
            "WHERE ano = 2024 AND agente_id = 19826"
        )

        print(f"  OK view -- {n:,} rows.")
        print(f"  Total acumulado: {totals['total']:,} EUR "
              f"({totals['agentes']} agentes distintos)")
        print(f"  ANCHOR 2024: {a2024:,} EUR (esperado ~3 102 232)")
        print(f"  ANCHOR Gusser 2024: {gusser:,} EUR (esperado ~395 698)")

        # Sanity (régua-mãe, abortar se anchor falhar > 0.1%)
        assert 3_100_000 <= a2024 <= 3_105_000, (
            f"Anchor 2024 falhou: {a2024} (esperado 3 102 232 ±0.1%)"
        )
        assert 395_690 <= gusser <= 395_710, (
            f"Anchor Gusser 2024 falhou: {gusser}"
        )
        print("  Anchors OK.")

        # Top 5 agentes 2024
        print("\n  Top 5 agentes 2024:")
        rows = await conn.fetch(
            "SELECT agente, "
            "ROUND(SUM(facturado_eur)::numeric, 0)::bigint AS eur "
            "FROM marts.v_facturacao_agente_trim WHERE ano = 2024 "
            "GROUP BY agente ORDER BY 2 DESC LIMIT 5"
        )
        for r in rows:
            print(f"    {r['agente'][:40]:<40}  {r['eur']:>10,} EUR")

        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
