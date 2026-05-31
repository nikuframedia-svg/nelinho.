"""Q.102.A — Espelhar tabelas Comercial NELO para `factory_raw.*` Postgres.

Continuação de Q.75 / Q.98. Foco: domínio Comercial (4 tabelas PHC).
Desbloqueia a primeira medida do domínio Q.102:

  * `comercial_facturacao.total` (DINHEIRO, €): SUM(EPHCF_FACTURADO)
    sobre `ENTIDADE_PHC_FACT`.
  * Anchor histórico Q.82: **€125 372 058 acumulado (2009-2026)**,
    **Canoe Sprint TP_ID=6 = €73 018 963 (58.24%)**.

**Tabelas espelhadas** (todas full copy — pequenas):

| Tabela              | Rows  | Notas                                |
|---------------------|-------|--------------------------------------|
| ENTIDADE_PHC_FACT   | 100 K | Fonte (8 cols: ANO/MES/DIA + IDs)   |
| ENTIDADE_PHC        | 751   | Ponte PHC ↔ NELO                    |
| PRODUTO_TIPO        | lookup| Disciplinas (Canoe Sprint, …)        |
| ENTIDADE_TIPO       | 36    | Hierarquia cliente/fornecedor/etc.  |

Reutiliza Q.75 (`_reflect_columns`, `_coerce_value`, `_TYPE_MAP`) +
padrão Q.98. NÃO altera ETL existente.

NÃO toca em `measure_contract.py` — Q.102.A é ETL puro. A medida é
registada em Q.102.C.

Uso::

    $env:PYTHONPATH = "C:\\Users\\User\\nelinho"
    $env:PYTHONIOENCODING = "utf-8"
    .\\.venv\\Scripts\\python.exe scripts/q102_setup_comercial_mirror.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from typing import Any, Optional

import asyncpg
from sqlalchemy import text

from scripts.q75_setup_raw_mirror import (
    READ_CHUNK,
    RawTable,
    _coerce_value,
    _reflect_columns,
    _refresh_table_atomic,
)
from src.adapters.nelo.services import get_engine
from src.shared.config import settings


# ─── Tabelas Comercial a espelhar ───────────────────────────────────────

COMERCIAL_TABLES: list[RawTable] = [
    RawTable("ENTIDADE_PHC", None),       # ~751 rows — ponte PHC↔NELO
    RawTable("ENTIDADE_TIPO", None),      # 36 rows — hierarquia cliente/etc.
    RawTable("PRODUTO_TIPO", None),       # lookup disciplinas
    RawTable("ENTIDADE_PHC_FACT", None),  # 100K rows fonte principal (sem janela)
]


async def _mirror_table_comercial(
    sql_engine,
    pg_conn: asyncpg.Connection,
    spec: RawTable,
) -> dict[str, Any]:
    """Espelha 1 tabela NELO Comercial → factory_raw (Q.125: refresh atómico
    DROP-free, partilhado com q75 — seguro com as marts que dependem destas
    tabelas; corre de 5/5 min no scheduler sem janela de leitura vazia)."""
    return await _refresh_table_atomic(sql_engine, pg_conn, spec)


# ─── Sanity pós-espelhamento ────────────────────────────────────────────


async def _sanity_checks(pg_conn: asyncpg.Connection) -> dict[str, Any]:
    """Valida que o espelho comercial bate os anchors Q.82.

    Anchors esperados:
      - SUM(EPHCF_FACTURADO) ≈ 125 372 058 EUR (2009-2026)
      - Canoe Sprint (TP_ID=6) ≈ 73 018 963 EUR = 58.24%
      - 100 625 rows; 3 797 negativos; 4 237 zeros
    """
    out: dict[str, Any] = {}

    # 1. Rows totais + range temporal
    out["row_count"] = await pg_conn.fetchval(
        'SELECT COUNT(*) FROM factory_raw.entidade_phc_fact'
    )
    rng = await pg_conn.fetchrow(
        'SELECT MIN("EPHCF_ANO") AS min_a, MAX("EPHCF_ANO") AS max_a '
        'FROM factory_raw.entidade_phc_fact'
    )
    out["ano_min"] = rng["min_a"]
    out["ano_max"] = rng["max_a"]

    # 2. Distribuição valores (anchor positivos/negativos/zeros)
    dist = await pg_conn.fetchrow(
        """
        SELECT
          SUM(CASE WHEN "EPHCF_FACTURADO" > 0 THEN 1 ELSE 0 END) AS pos,
          SUM(CASE WHEN "EPHCF_FACTURADO" < 0 THEN 1 ELSE 0 END) AS neg,
          SUM(CASE WHEN "EPHCF_FACTURADO" = 0 THEN 1 ELSE 0 END) AS zero
        FROM factory_raw.entidade_phc_fact
        """
    )
    out["pos"] = dist["pos"]
    out["neg"] = dist["neg"]
    out["zero"] = dist["zero"]

    # 3. ANCHOR: SUM total
    total = await pg_conn.fetchval(
        'SELECT ROUND(SUM("EPHCF_FACTURADO")::numeric, 0) '
        'FROM factory_raw.entidade_phc_fact'
    )
    out["sum_total_eur"] = float(total) if total else None

    # 4. ANCHOR: Canoe Sprint (TP_ID=6)
    canoe = await pg_conn.fetchrow(
        """
        SELECT COUNT(*)::int AS n,
               ROUND(SUM("EPHCF_FACTURADO")::numeric, 0) AS sum_eur
        FROM factory_raw.entidade_phc_fact
        WHERE "EPHCF_TP_ID" = 6
        """
    )
    out["canoe_n"] = canoe["n"]
    out["canoe_sum_eur"] = float(canoe["sum_eur"]) if canoe["sum_eur"] else None
    if out["sum_total_eur"]:
        out["canoe_pct"] = round(
            100.0 * out["canoe_sum_eur"] / out["sum_total_eur"], 2
        )

    # 5. JOIN cliente — top 5 clientes 2024
    out["entidade_phc_rows"] = await pg_conn.fetchval(
        'SELECT COUNT(*) FROM factory_raw.entidade_phc'
    )
    out["produto_tipo_rows"] = await pg_conn.fetchval(
        'SELECT COUNT(*) FROM factory_raw.produto_tipo'
    )
    out["entidade_tipo_rows"] = await pg_conn.fetchval(
        'SELECT COUNT(*) FROM factory_raw.entidade_tipo'
    )

    top_clientes = await pg_conn.fetch(
        """
        SELECT
            phc."EPHCF_EPHC_ID"                              AS phc_id,
            COALESCE(e."E_NOME", '(sem cliente)')            AS cliente,
            ROUND(SUM(phc."EPHCF_FACTURADO")::numeric, 0)    AS total_eur
        FROM factory_raw.entidade_phc_fact phc
        LEFT JOIN factory_raw.entidade_phc ephc
               ON ephc."EPHC_PHC_ID" = phc."EPHCF_EPHC_ID"
        LEFT JOIN factory_raw.entidade e
               ON e."E_ID" = ephc."EPHC_E_ID"
        WHERE phc."EPHCF_ANO" = 2024
          AND phc."EPHCF_EPHC_ID" IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 3 DESC
        LIMIT 5
        """
    )
    out["top_clientes_2024"] = [
        {
            "phc_id": r["phc_id"],
            "cliente": r["cliente"],
            "total_eur": float(r["total_eur"]) if r["total_eur"] else None,
        }
        for r in top_clientes
    ]

    # 6. Top disciplinas 2009-2026
    top_disc = await pg_conn.fetch(
        """
        SELECT
            pt."TP_ID"                                       AS tp_id,
            pt."TP_NOME"                                     AS disciplina,
            COUNT(*)::int                                    AS n,
            ROUND(SUM(phc."EPHCF_FACTURADO")::numeric, 0)    AS total_eur
        FROM factory_raw.entidade_phc_fact phc
        LEFT JOIN factory_raw.produto_tipo pt
               ON pt."TP_ID" = phc."EPHCF_TP_ID"
        GROUP BY 1, 2
        ORDER BY 4 DESC NULLS LAST
        LIMIT 6
        """
    )
    out["top_disciplinas"] = [
        {
            "tp_id": r["tp_id"],
            "disciplina": r["disciplina"],
            "n": r["n"],
            "total_eur": float(r["total_eur"]) if r["total_eur"] else None,
        }
        for r in top_disc
    ]

    return out


# ─── Driver ─────────────────────────────────────────────────────────────


async def setup(only: Optional[list[str]] = None) -> dict[str, Any]:
    """Espelha COMERCIAL_TABLES + sanity. Devolve relatório."""
    if not settings.sqlserver_enabled:
        raise SystemExit("SQLSERVER_ENABLED=False — não posso espelhar.")

    selected = (
        [t for t in COMERCIAL_TABLES if t.nelo_name in only]
        if only else COMERCIAL_TABLES
    )
    sql_engine = get_engine()

    pg_dsn = settings.database_url.replace("+asyncpg", "")
    pg_conn = await asyncpg.connect(pg_dsn)

    results: list[dict[str, Any]] = []
    try:
        await pg_conn.execute("CREATE SCHEMA IF NOT EXISTS factory_raw")
        for spec in selected:
            print(f"[{spec.nelo_name}] a espelhar...", flush=True)
            try:
                stats = await _mirror_table_comercial(sql_engine, pg_conn, spec)
            except Exception as exc:
                stats = {
                    "table": spec.nelo_name,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            results.append(stats)
            print(f"  -> {stats}", flush=True)

        try:
            sanity = await _sanity_checks(pg_conn)
        except Exception as exc:
            sanity = {
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
    finally:
        await pg_conn.close()
        await sql_engine.dispose()

    return {"mirror": results, "sanity": sanity}


def _print_sanity(sanity: dict[str, Any]) -> None:
    if sanity.get("status") == "error":
        print(f"\n  SANITY FALHOU: {sanity.get('error')}")
        return

    print("\n=== Sanity pós-espelhamento ===")
    print(f"  entidade_phc_fact rows : {sanity['row_count']:,}")
    print(f"  range ANO              : {sanity['ano_min']} -> {sanity['ano_max']}")
    print(
        f"  pos={sanity['pos']:,}  neg={sanity['neg']:,}  zero={sanity['zero']:,}"
    )
    print()
    print(
        f"  ANCHOR total       : "
        f"{sanity['sum_total_eur']:>15,.0f} EUR  "
        f"(Q.82 = 125,372,058 EUR)"
    )
    print(
        f"  ANCHOR Canoe Sprint: "
        f"{sanity['canoe_sum_eur']:>15,.0f} EUR  "
        f"({sanity.get('canoe_pct', '?')} %)  "
        f"(Q.82 = 73,018,963 EUR / 58.24 %)"
    )
    print()
    print(
        f"  Lookups: entidade_phc={sanity['entidade_phc_rows']}  "
        f"produto_tipo={sanity['produto_tipo_rows']}  "
        f"entidade_tipo={sanity['entidade_tipo_rows']}"
    )

    print("\n  Top 5 clientes 2024:")
    for r in sanity["top_clientes_2024"]:
        cliente = (r['cliente'] or '')[:40]
        print(
            f"    phc_id {r['phc_id']:>5}  {cliente:<40}  "
            f"{r['total_eur']:,.0f} EUR"
        )

    print("\n  Top 6 disciplinas (acumulado):")
    for r in sanity["top_disciplinas"]:
        disc = (r['disciplina'] or '(NULL)')[:30]
        print(
            f"    tp_id {(r['tp_id'] or 'NULL'):>5}  {disc:<30}  "
            f"n={r['n']:>6,}  {r['total_eur']:>15,.0f} EUR"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--only",
        nargs="+",
        default=None,
        help="Espelhar só estas tabelas (nomes NELO).",
    )
    args = parser.parse_args()

    report = asyncio.run(setup(only=args.only))

    ok = [r for r in report["mirror"] if r["status"] == "ok"]
    err = [r for r in report["mirror"] if r["status"] != "ok"]
    total_rows = sum(r.get("rows", 0) for r in ok)
    print()
    print(
        f"=== {len(ok)}/{len(report['mirror'])} tabelas espelhadas, "
        f"{total_rows:,} linhas em factory_raw ==="
    )
    for r in err:
        print(f"  FALHA {r['table']}: {r.get('error')}")

    _print_sanity(report["sanity"])
    return 0 if not err else 1


if __name__ == "__main__":
    sys.exit(main())
