"""Q.96.A.0 — view `marts.v_taxa_defeitos_dia` para a medida qualidade.taxa_defeitos.

Granularidade: (data, fase) — `OFCH_LOCAL` (zona física) NÃO está espelhada
em factory_raw (gap Q.98+). Sem "zona" no escopo Q.96.

Numerador: COUNT(OFCH_GRAVIDADE >= 1) — defeitos reais (grav=0 são templates).
Denominador: COUNT(*) — total de checks. (Comparação: taxa por OFs deu 120%
em Laminagem Abril — refutado, denominador OFs distintas inválido.)

Anchor Q.96.A: Laminagem em Abril 2026 = 331 / 5 341 = 6,20% no espelho
factory_raw (vs 5,3% que Q.81 viu em MAR-KAYAKS — o espelho cobre apenas
2025-05-22 → 2026-05-21, ~3% das 3M rows MAR-KAYAKS).

Defesa contra taxa>1 (denominador errado): este é o invariante FRACAO. A
view não calcula a taxa — devolve num + den separados, e o Cube faz
`SUM(defeitos)/NULLIF(SUM(total_checks),0)` na agregação. Cross-row
aggregation usa num/den separately — NUNCA SUM(taxa).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_taxa_defeitos_dia AS
-- Q.96 — defeitos por (data, fase). Numerador e denominador separados;
-- a taxa calcula-se no Cube via SUM(defeitos)/NULLIF(SUM(total_checks),0).
SELECT
    CAST(NULLIF(c."OFCH_DATA_ACTUALIZACAO", '') AS date) AS data,
    c."OFCH_FP_ID"                                       AS fase_id,
    COALESCE(fp."FP_NOME", '(sem fase)')                 AS fase,
    SUM(CASE WHEN c."OFCH_GRAVIDADE" >= 1 THEN 1 ELSE 0 END) AS defeitos,
    SUM(CASE WHEN c."OFCH_GRAVIDADE" = 3 THEN 1 ELSE 0 END) AS defeitos_graves,
    SUM(CASE WHEN c."OFCH_GRAVIDADE" = 2 THEN 1 ELSE 0 END) AS defeitos_intermedios,
    SUM(CASE WHEN c."OFCH_GRAVIDADE" = 1 THEN 1 ELSE 0 END) AS defeitos_leves,
    COUNT(*)                                             AS total_checks
FROM factory_raw.of_checklist c
LEFT JOIN factory_raw.fases_producao fp ON fp."FP_ID" = c."OFCH_FP_ID"
WHERE NULLIF(c."OFCH_DATA_ACTUALIZACAO", '') IS NOT NULL
GROUP BY 1, 2, 3
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_taxa_defeitos_dia")
        await conn.execute(VIEW_SQL)

        # Sanity checks (Fase 0 portão).
        n_rows = await conn.fetchval("SELECT COUNT(*) FROM marts.v_taxa_defeitos_dia")
        print(f"  OK view criada — {n_rows:,} linhas (data, fase).")

        # Verificar 0 <= taxa <= 1 em todas as linhas.
        edge = await conn.fetchrow(
            """
            SELECT
                MIN(defeitos::float / NULLIF(total_checks, 0)) AS min_taxa,
                MAX(defeitos::float / NULLIF(total_checks, 0)) AS max_taxa,
                SUM(defeitos) AS sum_def,
                SUM(total_checks) AS sum_tot
            FROM marts.v_taxa_defeitos_dia
            """
        )
        print(
            f"  Range guard: min_taxa={edge['min_taxa']}  "
            f"max_taxa={edge['max_taxa']}"
        )
        assert edge["max_taxa"] is not None and edge["max_taxa"] <= 1.0, (
            f"FRACAO range violado: max_taxa={edge['max_taxa']} > 1.0"
        )
        print(f"  Totais: defeitos={edge['sum_def']:,}  checks={edge['sum_tot']:,}")
        print(
            f"  Taxa global = {edge['sum_def']/edge['sum_tot']:.4f} "
            f"({100*edge['sum_def']/edge['sum_tot']:.2f}%)"
        )

        # Anchor Laminagem Abril 2026.
        anchor = await conn.fetchrow(
            """
            SELECT
                SUM(defeitos) AS def,
                SUM(total_checks) AS tot
            FROM marts.v_taxa_defeitos_dia
            WHERE fase = 'Laminagem'
              AND data >= '2026-04-01' AND data < '2026-05-01'
            """
        )
        if anchor and anchor["tot"]:
            taxa = anchor["def"] / anchor["tot"]
            print(
                f"\n  ANCHOR Laminagem Abril 2026: "
                f"{anchor['def']}/{anchor['tot']} = {taxa:.4f} "
                f"({100*taxa:.2f}%)"
            )
            # Esperado Fase 0: ~6,20% (factory_raw espelho).
            assert 0.05 < taxa < 0.08, (
                f"Anchor fora do range esperado: {taxa} (esperado ~0.062)"
            )
            print(f"  Anchor BATE ({100*taxa:.2f}% dentro de [5.0, 8.0]%).")

        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
