"""Q.175.C — view `marts.v_mold_ratio`.

Rácio moldes/barcos-WIP por modelo. Usa o mesmo matching canónico do
`_load_molds_db` (assinatura NP,M,TAM + UNION de links históricos):
  - moldes_count: quantos moldes distintos conseguem produzir este modelo
  - ofs_wip:      quantas OFs deste modelo estão no WIP activo
  - racio:        moldes / ofs_wip (fracção de cobertura)
  - em_risco:     rácio < 0.1 (menos de 1 molde por cada 10 barcos = bottleneck)

SP canónica: `PlanoLaminagem_RacioMoldesModelos` — guardrail de capacidade de
laminação. Famílias com rácio baixo são as primeiras a parar quando o CPO
esgota a janela de moldes.

Fonte: factory_raw.ordemfabrico + factory_raw.produto + factory_raw.of_fp
       + factory_raw.fases_producao + factory_raw.v_of_is_boat.
Sem dependências externas — idempotente (CREATE OR REPLACE VIEW).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

sys.path.insert(0, "C:/Users/User/nelinho")
from src.shared.config import settings  # noqa: E402


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_mold_ratio AS
WITH
-- moldes disponíveis por assinatura (NP, M, TAM): mesmo JOIN do _load_molds_db
mold_by_sig AS (
    SELECT DISTINCT
           p."P_NP_ID" AS np,
           p."P_M_ID"  AS m,
           p."P_TAM_ID" AS tam,
           o."OF_ID" AS molde_of_id
    FROM factory_raw.ordemfabrico o
    JOIN factory_raw.produto p ON p."P_ID" = o."OF_P_ID"
    WHERE o."OF_ID" BETWEEN 70000 AND 79999
      AND o."OF_FP_ID" IN (13, 14, 15, 16)
),
-- moldes históricos via link directo OFFP_OF_ID_MLD
mold_by_link AS (
    SELECT DISTINCT
           p."P_NP_ID" AS np,
           p."P_M_ID"  AS m,
           p."P_TAM_ID" AS tam,
           op."OFFP_OF_ID_MLD" AS molde_of_id
    FROM factory_raw.of_fp op
    JOIN factory_raw.ordemfabrico ofb ON ofb."OF_ID" = op."OFFP_OF_ID"
    JOIN factory_raw.produto p ON p."P_ID" = ofb."OF_P_ID"
    WHERE op."OFFP_OF_ID_MLD" IS NOT NULL
      AND op."OFFP_OF_ID_MLD" <> 0
),
-- UNION canónico (mesma lógica do loader)
mold_sig AS (
    SELECT np, m, tam, COUNT(DISTINCT molde_of_id) AS moldes_count
    FROM (SELECT * FROM mold_by_sig UNION SELECT * FROM mold_by_link) u
    GROUP BY 1, 2, 3
),
-- barcos WIP activos por assinatura
wip_by_sig AS (
    SELECT p."P_ID"    AS modelo_id,
           p."P_NOME"  AS modelo_nome,
           p."P_NP_ID" AS np,
           p."P_M_ID"  AS m,
           p."P_TAM_ID" AS tam,
           COUNT(DISTINCT ofb."OF_ID") AS ofs_wip
    FROM factory_raw.ordemfabrico ofb
    JOIN factory_raw.v_of_is_boat vb ON vb.of_id = ofb."OF_ID" AND vb.is_boat = true
    JOIN factory_raw.fases_producao f ON f."FP_ID" = ofb."OF_FP_ID"
    JOIN factory_raw.produto p ON p."P_ID" = ofb."OF_P_ID"
    WHERE f."FP_PRODUCAO" = true
    GROUP BY 1, 2, 3, 4, 5
)
SELECT
    w.modelo_id,
    w.modelo_nome,
    w.np, w.m, w.tam,
    COALESCE(ms.moldes_count, 0)   AS moldes_count,
    w.ofs_wip,
    ROUND(
        COALESCE(ms.moldes_count, 0)::numeric / NULLIF(w.ofs_wip, 0),
        3
    )                              AS racio,
    (COALESCE(ms.moldes_count, 0)::float / NULLIF(w.ofs_wip, 0) < 0.1
     OR ms.moldes_count IS NULL)   AS em_risco
FROM wip_by_sig w
LEFT JOIN mold_sig ms ON ms.np = w.np AND ms.m = w.m AND ms.tam = w.tam
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS marts")
        await conn.execute(VIEW_SQL)

        total = await conn.fetchrow(
            "SELECT COUNT(*) AS modelos, "
            "COUNT(*) FILTER (WHERE em_risco) AS em_risco, "
            "SUM(ofs_wip) AS ofs_total, "
            "SUM(moldes_count) AS moldes_total "
            "FROM marts.v_mold_ratio"
        )
        print(f"  OK -- {total['modelos']} modelos WIP, {total['em_risco']} em risco, "
              f"{total['ofs_total']} OFs, {total['moldes_total']} pares modelo-molde.")

        top = await conn.fetch(
            "SELECT modelo_nome, moldes_count, ofs_wip, racio "
            "FROM marts.v_mold_ratio "
            "WHERE em_risco ORDER BY ofs_wip DESC LIMIT 10"
        )
        if top:
            print("\n  Top modelos em risco (poucos moldes para a fila WIP):")
            for r in top:
                print(f"    {(r['modelo_nome'] or '?')[:35]:<35} "
                      f"moldes={r['moldes_count']} ofs={r['ofs_wip']} "
                      f"racio={r['racio']}")
        else:
            print("  Nenhum modelo em risco com racio < 0.1 (bom sinal).")

        # Anchor: modelos com moldes (racio > 0)
        covered = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_mold_ratio WHERE racio > 0"
        )
        total_m = await conn.fetchval("SELECT COUNT(*) FROM marts.v_mold_ratio")
        print(f"\n  Cobertura: {covered}/{total_m} modelos com pelo menos 1 molde ({100*covered//max(1,total_m)}%).")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
