"""Q.104.A — Espelhar tabelas Logística NELO para `factory_raw.*` Postgres.

Continuação de Q.75/Q.98/Q.102. Foco: domínio LOGÍSTICA (6 tabelas).
Desbloqueia as 2 medidas Q.104:

  * `logistica_ofs_expedidas.total` (CONTAGEM): OFs expedidas por
    `TROF_ENVIADO=1` + `TR_DATA`. Anchor 2024 = **5 874**.
  * `logistica_atrasos_culpa.total` (CONTAGEM): atrasos por classificação
    NELO. Anchor total = 3 027; repartição 70/26/4 (Cliente/Nelo/
    Transportador).

**Tabelas espelhadas** (todas full copy — máximo 93K rows):

| Tabela                       | Rows  | Notas                            |
|------------------------------|-------|----------------------------------|
| TRANSPORTE                   | 11 380| Mestra; TR_ID + TR_DATA + TR_DEST_ID + TR_TRTP_ID |
| TRANSP_OF                    | 93 041| Junção N:M (TROF_TR_ID + TROF_OF_ID + TROF_ENVIADO) |
| TRANSP_DESTINO               | 4     | Lookup: DEST_ID, DEST_NOME (Nac/UE/Outros/Todos) |
| TRANSP_TIPO                  | 58    | Lookup hierárquico: TRTP_ID, TRTP_NOME, TRTP_TRTP_ID (parent) |
| TRANSP_DATAS                 | 3 027 | Histórico alterações datas + TRDT_TRDTCL_ID (culpa) |
| TRANSP_DATAS_CLASSIFICACAO   | 3     | Lookup: TRDTCL_ID, TRDTCL_NOME |

Reutiliza Q.75 (`_reflect_columns`, `_coerce_value`, `_TYPE_MAP`).

NÃO toca em `measure_contract.py` — Q.104.A é ETL puro. Medidas
registadas em Q.104.B/Q.104.C.

Uso::

    $env:PYTHONPATH = "C:\\Users\\User\\nelinho"
    $env:PYTHONIOENCODING = "utf-8"
    .\\.venv\\Scripts\\python.exe scripts/q104_setup_logistica_mirror.py
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


# ─── Tabelas Logística a espelhar ───────────────────────────────────────

LOGISTICA_TABLES: list[RawTable] = [
    RawTable("TRANSP_DESTINO", None),               # 4 rows lookup
    RawTable("TRANSP_TIPO", None),                  # 58 rows lookup hierárquico
    RawTable("TRANSP_DATAS_CLASSIFICACAO", None),   # 3 rows lookup
    RawTable("TRANSP_DATAS", None),                 # 3 027 rows
    RawTable("TRANSPORTE", None),                   # 11 380 rows mestra
    RawTable("TRANSP_OF", None),                    # 93 041 rows junção
]


async def _mirror_table_logistica(
    sql_engine,
    pg_conn: asyncpg.Connection,
    spec: RawTable,
) -> dict[str, Any]:
    """Espelha 1 tabela NELO Logística → factory_raw (Q.125: refresh atómico
    DROP-free partilhado com q75 — seguro com as marts dependentes; 5/5 min)."""
    return await _refresh_table_atomic(sql_engine, pg_conn, spec)


# ─── Sanity pós-espelhamento ────────────────────────────────────────────


async def _sanity_checks(pg_conn: asyncpg.Connection) -> dict[str, Any]:
    """Valida que o espelho bate anchors Q.82."""
    out: dict[str, Any] = {}

    out["transporte_rows"] = await pg_conn.fetchval(
        'SELECT COUNT(*) FROM factory_raw.transporte'
    )
    out["transp_of_rows"] = await pg_conn.fetchval(
        'SELECT COUNT(*) FROM factory_raw.transp_of'
    )
    out["transp_datas_rows"] = await pg_conn.fetchval(
        'SELECT COUNT(*) FROM factory_raw.transp_datas'
    )
    out["transp_destino_rows"] = await pg_conn.fetchval(
        'SELECT COUNT(*) FROM factory_raw.transp_destino'
    )
    out["transp_tipo_rows"] = await pg_conn.fetchval(
        'SELECT COUNT(*) FROM factory_raw.transp_tipo'
    )
    out["classif_rows"] = await pg_conn.fetchval(
        'SELECT COUNT(*) FROM factory_raw.transp_datas_classificacao'
    )

    # Anchor 1: OFs expedidas 2024 = 5 874
    # TROF_ENVIADO bool — em Postgres, comparar True. Q.75 mapeia bit→boolean.
    out["ofs_expedidas_2024"] = await pg_conn.fetchval(
        """
        SELECT COUNT(DISTINCT tof."TROF_OF_ID")
        FROM factory_raw.transp_of tof
        JOIN factory_raw.transporte tr ON tr."TR_ID" = tof."TROF_TR_ID"
        WHERE tof."TROF_ENVIADO" = TRUE
          AND tr."TR_DATA" IS NOT NULL
          AND NULLIF(tr."TR_DATA", '') IS NOT NULL
          AND CAST(tr."TR_DATA" AS date) >= '2024-01-01'
          AND CAST(tr."TR_DATA" AS date) <  '2025-01-01'
        """
    )

    # Anchor 2: distribuição culpa (3027 atrasos = 2110 + 791 + 126)
    culpa_dist = await pg_conn.fetch(
        """
        SELECT cl."TRDTCL_NOME" AS culpa,
               COUNT(*)::int    AS n
        FROM factory_raw.transp_datas td
        LEFT JOIN factory_raw.transp_datas_classificacao cl
               ON cl."TRDTCL_ID" = td."TRDT_TRDTCL_ID"
        GROUP BY 1 ORDER BY 2 DESC
        """
    )
    out["culpa_distribution"] = [
        {"culpa": r["culpa"], "n": r["n"]} for r in culpa_dist
    ]

    # Anchor 3: top destinos OFs expedidas (validation)
    top_dest = await pg_conn.fetch(
        """
        SELECT
            COALESCE(d."DEST_NOME", 'Desconhecido') AS destino,
            COUNT(DISTINCT tof."TROF_OF_ID")::int   AS n_ofs
        FROM factory_raw.transp_of tof
        JOIN factory_raw.transporte tr ON tr."TR_ID" = tof."TROF_TR_ID"
        LEFT JOIN factory_raw.transp_destino d ON d."DEST_ID" = tr."TR_DEST_ID"
        WHERE tof."TROF_ENVIADO" = TRUE
          AND CAST(NULLIF(tr."TR_DATA", '') AS date) >= '2024-01-01'
          AND CAST(NULLIF(tr."TR_DATA", '') AS date) <  '2025-01-01'
        GROUP BY 1 ORDER BY 2 DESC
        """
    )
    out["top_destinos_2024"] = [
        {"destino": r["destino"], "n_ofs": r["n_ofs"]} for r in top_dest
    ]

    return out


async def setup(only: Optional[list[str]] = None) -> dict[str, Any]:
    """Espelha LOGISTICA_TABLES + sanity. Devolve relatório."""
    if not settings.sqlserver_enabled:
        raise SystemExit("SQLSERVER_ENABLED=False — não posso espelhar.")

    selected = (
        [t for t in LOGISTICA_TABLES if t.nelo_name in only]
        if only else LOGISTICA_TABLES
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
                stats = await _mirror_table_logistica(sql_engine, pg_conn, spec)
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
            sanity = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        await pg_conn.close()
        await sql_engine.dispose()

    return {"mirror": results, "sanity": sanity}


def _print_sanity(sanity: dict[str, Any]) -> None:
    if sanity.get("status") == "error":
        print(f"\n  SANITY FALHOU: {sanity.get('error')}")
        return

    print("\n=== Sanity pós-espelhamento ===")
    print(
        f"  transporte={sanity['transporte_rows']:,}  "
        f"transp_of={sanity['transp_of_rows']:,}  "
        f"transp_datas={sanity['transp_datas_rows']:,}"
    )
    print(
        f"  Lookups: destino={sanity['transp_destino_rows']}  "
        f"tipo={sanity['transp_tipo_rows']}  "
        f"classif={sanity['classif_rows']}"
    )

    print(
        f"\n  ANCHOR OFs expedidas 2024: {sanity['ofs_expedidas_2024']:,} "
        f"(Q.82 = 5 874)"
    )

    print("\n  ANCHOR Distribuição culpa (Q.82 = Cliente 2110 / Nelo 791 / Transp 126):")
    for r in sanity["culpa_distribution"]:
        culpa = (r['culpa'] or '(NULL)')[:30]
        print(f"    {culpa:<30}  n={r['n']:>6,}")

    print("\n  Top destinos OFs 2024:")
    for r in sanity["top_destinos_2024"]:
        d = (r['destino'] or '?')[:25]
        print(f"    {d:<25}  n_ofs={r['n_ofs']:,}")


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
