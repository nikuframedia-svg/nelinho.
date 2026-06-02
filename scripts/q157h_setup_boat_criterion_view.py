"""Q.157.H — Criar/substituir view factory_raw.v_of_is_boat.

Implementa o critério REAL de barco NELO validado contra producao.nelo.eu
(811/811 barcos da fábrica):

  is_boat = (raiz de PRODUTO.P_TP_ID na hierarquia PRODUTO_TIPO é Kayak,
             TP_ID=1) AND (ORDEMFABRICO.OF_ID < 10_000_000)

O critério antigo (P_QTDDECK>0 AND P_QTDCASCO>0) perdia C1/Nacra/Prepreg
e incluía pagaias/fila — ERRADO.

Nota sobre pagaias (TP_ID=331 "Parcerias/DD Pagaias"): estão debaixo da
raiz Kayak na hierarquia, MAS têm OF_ID >= 10M. A cláusula OF_ID < 10M
exclui-as correctamente (count=0 na validação de 2026-06-02).

Uso::

    $env:PYTHONPATH = "C:\\\\Users\\\\User\\\\nelinho"
    .venv\\Scripts\\python.exe scripts/q157h_setup_boat_criterion_view.py

Não requer SQL Server — opera só no Postgres local sobre factory_raw
que já está espelhado (q75 + q102.A).
"""

from __future__ import annotations

import asyncio
import sys

import asyncpg

sys.path.insert(0, "C:/Users/User/nelinho")
from src.shared.config import settings  # noqa: E402

# ── DDL da view ──────────────────────────────────────────────────────────────
#
# Usa CREATE OR REPLACE VIEW → idempotente, sem DROP, sem quebrar dependências.
# A CTE tp_root percorre PRODUTO_TIPO de forma recursiva:
#   base case: nós raiz (TP_TP_ID IS NULL)
#   recursive: filhos herdam root_id do pai
# O JOIN final marca is_boat para cada OF aberta (OF_DATAFIM vazio/NULL).
#
# Colunas da view:
#   of_id       – chave da OF
#   of_p_id     – produto da OF
#   p_tp_id     – tipo directo do produto
#   root_tp_id  – raiz na hierarquia PRODUTO_TIPO
#   is_boat     – true se root=1 (Kayak) e OF_ID < 10M
#
_VIEW_DDL = """\
CREATE OR REPLACE VIEW factory_raw.v_of_is_boat AS
WITH RECURSIVE tp_root AS (
    -- base: nós raiz (sem pai)
    SELECT
        "TP_ID",
        "TP_TP_ID",
        "TP_ID" AS root_id
    FROM factory_raw.produto_tipo
    WHERE "TP_TP_ID" IS NULL

    UNION ALL

    -- recursivo: filhos herdam root_id
    SELECT
        pt."TP_ID",
        pt."TP_TP_ID",
        r.root_id
    FROM factory_raw.produto_tipo pt
    JOIN tp_root r ON pt."TP_TP_ID" = r."TP_ID"
)
SELECT
    of_."OF_ID"                                        AS of_id,
    of_."OF_P_ID"                                      AS of_p_id,
    p."P_TP_ID"                                        AS p_tp_id,
    r.root_id                                          AS root_tp_id,
    (r.root_id = 1 AND of_."OF_ID" < 10000000)        AS is_boat
FROM factory_raw.ordemfabrico of_
JOIN factory_raw.produto       p ON p."P_ID"   = of_."OF_P_ID"
JOIN tp_root                   r ON r."TP_ID"  = p."P_TP_ID"
"""

# Snippet compacto para uso directo pelo CPO (sem a view, inline):
BOAT_CRITERION_INLINE = """\
-- Critério barco NELO (Q.157.H) — inclui K1/C1/Nacra/Prepreg, exclui pagaias
WITH RECURSIVE tp_root AS (
    SELECT "TP_ID", "TP_TP_ID", "TP_ID" AS root_id
    FROM factory_raw.produto_tipo
    WHERE "TP_TP_ID" IS NULL
    UNION ALL
    SELECT pt."TP_ID", pt."TP_TP_ID", r.root_id
    FROM factory_raw.produto_tipo pt
    JOIN tp_root r ON pt."TP_TP_ID" = r."TP_ID"
)
SELECT of_."OF_ID"
FROM factory_raw.ordemfabrico of_
JOIN factory_raw.produto p ON p."P_ID" = of_."OF_P_ID"
JOIN tp_root r             ON r."TP_ID" = p."P_TP_ID"
WHERE r.root_id = 1
  AND of_."OF_ID" < 10000000
  AND (of_."OF_DATAFIM" IS NULL OR of_."OF_DATAFIM" = '')
"""


async def setup() -> dict:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute(_VIEW_DDL)
        # sanity rápida
        boats = await conn.fetchval(
            "SELECT COUNT(*) FROM factory_raw.v_of_is_boat WHERE is_boat"
        )
        non_boats = await conn.fetchval(
            "SELECT COUNT(*) FROM factory_raw.v_of_is_boat WHERE NOT is_boat"
        )
        # pagaias devem ser 0 barcos
        pagaia_boats = await conn.fetchval(
            "SELECT COUNT(*) FROM factory_raw.v_of_is_boat "
            "WHERE p_tp_id = 331 AND is_boat"
        )
        return {
            "status": "ok",
            "view": "factory_raw.v_of_is_boat",
            "boats_all_ofs": int(boats),
            "non_boats_all_ofs": int(non_boats),
            "pagaia_boats_must_be_zero": int(pagaia_boats),
        }
    finally:
        await conn.close()


def main() -> int:
    result = asyncio.run(setup())
    print(f"[q157h] {result}")
    if result["pagaia_boats_must_be_zero"] != 0:
        print("ERRO: pagaias classificadas como barco!", file=sys.stderr)
        return 1
    print(
        f"  is_boat=True : {result['boats_all_ofs']:,} OFs"
    )
    print(
        f"  is_boat=False: {result['non_boats_all_ofs']:,} OFs"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
