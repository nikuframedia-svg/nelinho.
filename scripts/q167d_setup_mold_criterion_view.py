"""Q.167.D — Criar/substituir view factory_raw.v_of_is_mold.

Critério de MOLDE NELO (verificado 2026-06-08 vs `getMoldesAReparar()`):

  is_mold = (PRODUTO.P_TP_ID = 82)   -- tipo "molde"

Os moldes vivem em OF_ID 70000-79999 e o seu produto é do tipo 82. A
view é o paralelo de `v_of_is_boat` para desbloquear os moldes no scope do
CPO (decisão do Luís: moldes entram no scope) e a visibilidade "Moldes a
Reparar". Moldes em reparação = fase atual em {13,14} com op aberta — são
route-truncated (single-op), agendados como as reparações de barco; os
operadores de reparação de molde existem na skill-matrix (ENTIDADE_FASE:
fase 14 = 23 operadores activos).

Postgres-only sobre factory_raw já espelhado (q75). Idempotente (CREATE OR
REPLACE, sem DROP).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

sys.path.insert(0, "C:/Users/User/nelinho")
from src.shared.config import settings  # noqa: E402

_VIEW_DDL = """\
CREATE OR REPLACE VIEW factory_raw.v_of_is_mold AS
SELECT
    of_."OF_ID"                  AS of_id,
    of_."OF_P_ID"                AS of_p_id,
    p."P_TP_ID"                  AS p_tp_id,
    (p."P_TP_ID" = 82)           AS is_mold
FROM factory_raw.ordemfabrico of_
JOIN factory_raw.produto       p ON p."P_ID" = of_."OF_P_ID"
"""


async def setup() -> dict:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute(_VIEW_DDL)
        molds = await conn.fetchval(
            "SELECT COUNT(*) FROM factory_raw.v_of_is_mold WHERE is_mold"
        )
        # moldes em reparação (fase 13/14 com op aberta) — bate com getMoldesAReparar
        in_repair = await conn.fetchval(
            """
            SELECT COUNT(*) FROM factory_raw.ordemfabrico ofb
            JOIN factory_raw.v_of_is_mold vm ON vm.of_id = ofb."OF_ID" AND vm.is_mold
            WHERE ofb."OF_FP_ID" IN (13, 14)
              AND EXISTS (
                SELECT 1 FROM factory_raw.of_fp op
                WHERE op."OFFP_OF_ID" = ofb."OF_ID"
                  AND op."OFFP_FP_ID" = ofb."OF_FP_ID"
                  AND NULLIF(op."OFFP_DATAFIM", '') IS NULL
              )
            """
        )
        return {
            "status": "ok",
            "view": "factory_raw.v_of_is_mold",
            "molds_all_ofs": int(molds),
            "molds_in_repair_13_14": int(in_repair),
        }
    finally:
        await conn.close()


def main() -> int:
    result = asyncio.run(setup())
    print(f"[q167d] {result}")
    print(f"  is_mold=True : {result['molds_all_ofs']:,} OFs")
    print(f"  em reparação (fase 13/14, op aberta): {result['molds_in_repair_13_14']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
