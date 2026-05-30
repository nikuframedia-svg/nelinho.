"""Q.75.B+C — Espelhar tabelas-core NELO para `factory_raw.*` no Postgres.

Motivação (medida em Q.74): o LLM acerta 85.6% via Postgres vs 73.6% via
SQL Server NELO directo (latência p95 159s, Tailscale). Espelhar as
~11 tabelas-core para o Postgres local resolve hit-rate + latência.

Estratégia:
  * **Schema-reflection** — para cada tabela, lê `INFORMATION_SCHEMA.COLUMNS`
    do SQL Server e gera `CREATE TABLE factory_raw.<lower>` com tipos
    Postgres equivalentes. Sem ORM models (são cache lido via `run_sql`).
  * **Janela temporal** — tabelas grandes (MOVIMENTO 12M, OF_FP 2.6M,
    OF_CHECKLIST 3M) só copiam os últimos `WINDOW_YEARS` anos via
    `WHERE <date_col> >= DATEADD(year, -N, GETDATE())`.
  * **Bulk copy** — lê em chunks de 5000 do SQL Server, escreve via
    asyncpg `copy_records_to_table` (muito mais rápido que INSERT).

Uso::

    $env:PYTHONPATH = "C:\\Users\\User\\nelinho"
    .\\.venv\\Scripts\\python.exe scripts/q75_setup_raw_mirror.py
    .\\.venv\\Scripts\\python.exe scripts/q75_setup_raw_mirror.py --only PRODUTO MOLDES
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass
from typing import Any, Optional

import asyncpg
from sqlalchemy import text

from src.adapters.nelo.services import get_engine
from src.shared.config import settings

WINDOW_YEARS = 2
READ_CHUNK = 5000


@dataclass
class RawTable:
    """Definição de uma tabela a espelhar."""
    nelo_name: str           # nome SQL Server (case-sensitive)
    date_col: Optional[str]  # coluna de data p/ janela temporal; None = full copy
    window_years: int = WINDOW_YEARS

    @property
    def pg_name(self) -> str:
        """Nome lowercase no schema factory_raw."""
        return self.nelo_name.lower()


# Lista curada — tabelas-core de produção (não top-by-rowcount).
RAW_TABLES: list[RawTable] = [
    RawTable("PRODUTO", None),
    RawTable("FASES_PRODUCAO", None),
    RawTable("MOLDES", None),
    RawTable("ENTIDADE", None),
    RawTable("PRODUTO_FASE", None),
    RawTable("PRODUTO_COMPONENTE", None),
    RawTable("OFFP_EQ", None),                           # 1.4M mas só 3 cols
    RawTable("ORDEMFABRICO", "OF_DATA", 2),
    RawTable("OF_FP", "OFFP_DATAINICIO", 2),
    RawTable("OF_CHECKLIST", "OFCH_DATA_VERIFICACAO", 1),
    RawTable("MOVIMENTO", "MOV_DATA", 2),
    # Q.108.M — apontamentos de horas trabalhadas (mão-de-obra real).
    # Watermark canónica: AT_DATA. O reflection q75 lê INFORMATION_SCHEMA
    # automaticamente; colunas reais são descobertas em runtime. Marts
    # downstream assumem: AT_DATA (date/text), AT_E_ID (operador FK),
    # AT_OF_ID (work order FK), AT_FP_ID (phase FK), AT_HORAS (numeric).
    # Se schema divergir, sanity checks dos marts falham loud — corrigir
    # então. Destrava KPIs 8.2/8.5 (horas trabalhadas, custo labor).
    RawTable("APONTAMENTO_TRABALHO", "AT_DATA", 2),
]


# ─── Type mapping SQL Server → Postgres ─────────────────────────────────

# Nota: datas mapeadas para `text` (ISO-8601). O aioodbc devolve
# datetimes do SQL Server de forma inconsistente (str vs datetime),
# e `copy_records_to_table` é estrito — text elimina o mismatch.
# ISO strings comparam-se correctamente em WHERE/ORDER BY; agregações
# de data exigem `col::timestamp` (raro). numeric/integer vêm sempre
# tipados do driver, mantêm-se.
_TYPE_MAP = {
    "int": "integer", "smallint": "integer", "tinyint": "integer",
    "bigint": "bigint",
    "bit": "boolean",
    "decimal": "numeric", "numeric": "numeric", "money": "numeric",
    "smallmoney": "numeric",
    "float": "double precision", "real": "double precision",
    "varchar": "text", "nvarchar": "text", "char": "text", "nchar": "text",
    "text": "text", "ntext": "text", "xml": "text",
    "date": "text",
    "datetime": "text", "datetime2": "text",
    "smalldatetime": "text", "datetimeoffset": "text",
    "time": "text",
    "uniqueidentifier": "text",
    "varbinary": "bytea", "binary": "bytea", "image": "bytea",
}


def _pg_type(sqlserver_type: str) -> str:
    return _TYPE_MAP.get(sqlserver_type.lower(), "text")


def _coerce_value(val: Any) -> Any:
    """Coerce valores para tipos que asyncpg copy aceita.

    Datas/horas → ISO string (as colunas são `text`); resto inalterado.
    """
    import datetime as _dt

    if isinstance(val, (_dt.datetime, _dt.date, _dt.time)):
        return val.isoformat()
    return val


# ─── Schema reflection ──────────────────────────────────────────────────


async def _reflect_columns(sql_engine, table: str) -> list[tuple[str, str]]:
    """Devolve [(col_name, pg_type)] lendo INFORMATION_SCHEMA.COLUMNS."""
    query = text(
        """
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = :t
        ORDER BY ORDINAL_POSITION
        """,
    )
    async with sql_engine.connect() as conn:
        result = await conn.execute(query, {"t": table})
        rows = list(result)
    # Exclui colunas bytea (binários grandes que não interessam ao LLM).
    return [
        (r[0], _pg_type(r[1]))
        for r in rows
        if _pg_type(r[1]) != "bytea"
    ]


# ─── Mirror de 1 tabela ─────────────────────────────────────────────────


async def _mirror_table(
    sql_engine,
    pg_conn: asyncpg.Connection,
    spec: RawTable,
) -> dict[str, Any]:
    """Espelha 1 tabela NELO → factory_raw. Devolve stats."""
    t0 = time.monotonic()
    cols = await _reflect_columns(sql_engine, spec.nelo_name)
    if not cols:
        return {"table": spec.nelo_name, "status": "error",
                "error": "0 colunas reflectidas"}

    col_names = [c[0] for c in cols]
    pg_table = spec.pg_name

    # 1. DROP + CREATE factory_raw.<t>
    col_defs = ", ".join(f'"{name}" {pgtype}' for name, pgtype in cols)
    await pg_conn.execute(f'DROP TABLE IF EXISTS factory_raw."{pg_table}"')
    await pg_conn.execute(
        f'CREATE TABLE factory_raw."{pg_table}" ({col_defs}, '
        f'_synced_at timestamptz DEFAULT now())',
    )

    # 2. SELECT do SQL Server (com janela temporal se aplicável).
    select_cols = ", ".join(f"[{c}]" for c in col_names)
    where = ""
    if spec.date_col:
        where = (
            f" WHERE [{spec.date_col}] >= "
            f"DATEADD(year, -{spec.window_years}, GETDATE())"
        )
    select_sql = text(f"SELECT {select_cols} FROM [{spec.nelo_name}]{where}")

    # 3. Bulk copy via asyncpg copy_records_to_table. `conn.stream()`
    #    faz server-side cursor — não carrega milhões de rows em memória.
    total = 0
    async with sql_engine.connect() as conn:
        result = await conn.stream(select_sql)
        batch: list[tuple] = []
        async for row in result:
            batch.append(tuple(_coerce_value(v) for v in row))
            if len(batch) >= READ_CHUNK:
                await pg_conn.copy_records_to_table(
                    pg_table, schema_name="factory_raw",
                    columns=col_names, records=batch,
                )
                total += len(batch)
                batch = []
        if batch:
            await pg_conn.copy_records_to_table(
                pg_table, schema_name="factory_raw",
                columns=col_names, records=batch,
            )
            total += len(batch)

    elapsed = time.monotonic() - t0
    return {
        "table": spec.nelo_name, "pg_table": f"factory_raw.{pg_table}",
        "status": "ok", "cols": len(cols), "rows": total,
        "window": f"{spec.window_years}y" if spec.date_col else "full",
        "elapsed_s": round(elapsed, 1),
    }


async def setup(only: Optional[list[str]] = None) -> list[dict[str, Any]]:
    """Espelha todas as RAW_TABLES (ou subset `only`)."""
    if not settings.sqlserver_enabled:
        raise SystemExit("SQLSERVER_ENABLED=False — não posso espelhar.")

    selected = (
        [t for t in RAW_TABLES if t.nelo_name in only] if only else RAW_TABLES
    )
    sql_engine = get_engine()

    # asyncpg connection directa (copy_records_to_table não existe no
    # SQLAlchemy async wrapper).
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    pg_conn = await asyncpg.connect(pg_dsn)

    results: list[dict[str, Any]] = []
    try:
        await pg_conn.execute("CREATE SCHEMA IF NOT EXISTS factory_raw")
        for spec in selected:
            print(f"[{spec.nelo_name}] a espelhar...", flush=True)
            try:
                stats = await _mirror_table(sql_engine, pg_conn, spec)
            except Exception as exc:
                stats = {"table": spec.nelo_name, "status": "error",
                         "error": f"{type(exc).__name__}: {exc}"}
            results.append(stats)
            print(f"  → {stats}", flush=True)
    finally:
        await pg_conn.close()
        await sql_engine.dispose()
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--only", nargs="+", default=None,
                        help="Espelhar só estas tabelas (nomes NELO).")
    args = parser.parse_args()

    results = asyncio.run(setup(only=args.only))

    ok = [r for r in results if r["status"] == "ok"]
    err = [r for r in results if r["status"] != "ok"]
    total_rows = sum(r.get("rows", 0) for r in ok)
    print()
    print(f"=== {len(ok)}/{len(results)} tabelas espelhadas, "
          f"{total_rows:,} linhas em factory_raw ===")
    for r in err:
        print(f"  FALHA {r['table']}: {r.get('error')}")
    return 0 if not err else 1


if __name__ == "__main__":
    sys.exit(main())
