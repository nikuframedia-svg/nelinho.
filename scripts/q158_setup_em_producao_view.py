"""Q.158 — Criar/substituir view factory_raw.v_of_em_producao.

Implementa a definição EXATA de "barco em produção" da NELO (query real do
`/OrdemFabrico` do Nuno, verificada na BD MAR-KAYAKS, 2026-06-03). A regra NÃO
usa `OF_DATAFIM` nem staleness — usa o **estado da OPERAÇÃO**: a fase atual
(`OF_FP_ID`) tem de ter uma operação por terminar em `of_fp` (`OFFP_DATAFIM`
NULL). É a mesma regra que o CPO scope (`_load_open_orders_db`) e o watermark do
robô (`auto_cpo_replan_job`) passam a usar — fonte única de verdade.

Classifica cada barco WIP em três tipos mutuamente exclusivos:
  is_fila        – OF_FP_ID = 11 (Não Laminado, por iniciar laminagem) ≈ 379
  is_reparacao   – OF_FP_ID IN (14,76,77) (barco de volta para reparação)
  is_nova_producao – fase atual normal (≠11, ≠14/76/77) — o grosso

Contagens-alvo na origem (2026-06-03):
  total (= o que o CPO planeia)        ≈ 1209
  NOT is_fila (= em produção display)  ≈ 830
  is_fila                              ≈ 379

Uso::

    $env:PYTHONPATH = "C:\\Users\\User\\nelinho"
    .venv\\Scripts\\python.exe scripts/q158_setup_em_producao_view.py

Não requer SQL Server — opera só no Postgres local sobre factory_raw, que já
está espelhado (q75; ORDEMFABRICO precisa do full Q.158.I p/ as reparações em
OFs fechadas, e OF_FP do full Q.158.H p/ as ops não-iniciadas).
"""

from __future__ import annotations

import asyncio
import sys

import asyncpg

sys.path.insert(0, "C:/Users/User/nelinho")
from src.shared.config import settings  # noqa: E402

# ── DDL da view ──────────────────────────────────────────────────────────────
#
# CREATE OR REPLACE VIEW → idempotente, sem DROP, sem quebrar dependências.
#   - JOIN a v_of_is_boat (critério barco Q.157.H: raiz=Kayak AND OF_ID<10M).
#   - JOIN a fases_producao filtrando FP_PRODUCAO=true (exclui Entregue/Armazém/
#     Embalado/...; também exclui a 13 "Para reparar", que é FP_PRODUCAO=false).
#   - INNER JOIN a entidade (a OF tem de ter cliente de encomenda).
#   - EXISTS: operação POR TERMINAR na FASE ATUAL (o CROSS APPLY da NELO).
# Fases de reparação hardcoded {14,76,77} — NÃO LIKE '%epar%' (apanha
# "Pr-epar-ação").
#
_VIEW_DDL = """\
CREATE OR REPLACE VIEW factory_raw.v_of_em_producao AS
SELECT o."OF_ID"                                            AS of_id,
       o."OF_FP_ID"                                         AS fase_atual,
       (o."OF_FP_ID" = 11)                                  AS is_fila,
       (o."OF_FP_ID" IN (14, 76, 77))                       AS is_reparacao,
       (o."OF_FP_ID" <> 11 AND o."OF_FP_ID" NOT IN (14, 76, 77))
                                                            AS is_nova_producao
FROM factory_raw.ordemfabrico o
JOIN factory_raw.v_of_is_boat  vb  ON vb.of_id = o."OF_ID" AND vb.is_boat = true
JOIN factory_raw.fases_producao f  ON f."FP_ID" = o."OF_FP_ID"
JOIN factory_raw.entidade      cli ON cli."E_ID" = o."OF_E_ID_ENC"
WHERE f."FP_PRODUCAO" = true
  AND EXISTS (
        SELECT 1 FROM factory_raw.of_fp op
        WHERE op."OFFP_OF_ID" = o."OF_ID"
          AND op."OFFP_FP_ID" = o."OF_FP_ID"
          AND NULLIF(op."OFFP_DATAFIM", '') IS NULL
      )
"""


async def setup() -> dict:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute(_VIEW_DDL)
        row = await conn.fetchrow(
            """
            SELECT count(*)                                AS total,
                   count(*) FILTER (WHERE NOT is_fila)     AS em_producao,
                   count(*) FILTER (WHERE is_fila)         AS fila,
                   count(*) FILTER (WHERE is_reparacao)    AS reparacao,
                   count(*) FILTER (WHERE is_nova_producao) AS nova_producao
            FROM factory_raw.v_of_em_producao
            """
        )
        return {
            "status": "ok",
            "view": "factory_raw.v_of_em_producao",
            "total": int(row["total"]),
            "em_producao": int(row["em_producao"]),
            "fila": int(row["fila"]),
            "reparacao": int(row["reparacao"]),
            "nova_producao": int(row["nova_producao"]),
        }
    finally:
        await conn.close()


def main() -> int:
    r = asyncio.run(setup())
    print(f"[q158] {r}")
    # Mutuamente exclusivos: fila + reparacao + nova_producao == total.
    parts = r["fila"] + r["reparacao"] + r["nova_producao"]
    if parts != r["total"]:
        print(
            f"ERRO: tipos não-exclusivos — "
            f"{r['fila']}+{r['reparacao']}+{r['nova_producao']}={parts} != {r['total']}",
            file=sys.stderr,
        )
        return 1
    # em_producao == reparacao + nova_producao (== total - fila).
    if r["em_producao"] != r["total"] - r["fila"]:
        print("ERRO: em_producao != total - fila", file=sys.stderr)
        return 1
    print(f"  total (CPO planeia) : {r['total']:,}")
    print(f"  em produção (display): {r['em_producao']:,}  (nova {r['nova_producao']:,} + reparações {r['reparacao']:,})")
    print(f"  fila (Não Laminado) : {r['fila']:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
