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

# Q.125: janela do refresh incremental de 5/5 min. Relê só os últimos N dias
# de actividade (por `inc_col`) e faz upsert por `pk_col` — barato e fresco,
# em vez de recopiar 2.5M de MOVIMENTO a cada ciclo.
INCREMENTAL_WINDOW_DAYS = 45


@dataclass
class RawTable:
    """Definição de uma tabela a espelhar."""
    nelo_name: str           # nome SQL Server (case-sensitive)
    date_col: Optional[str]  # coluna de data p/ janela temporal; None = full copy
    window_years: int = WINDOW_YEARS
    pk_col: Optional[str] = None   # Q.125: PK single-col p/ upsert incremental
    inc_col: Optional[str] = None  # Q.125: coluna-watermark do incremental
                                   # (update-ts de preferência; fallback date_col)
    keep_open_col: Optional[str] = None  # Q.158.F: coluna que, quando NULL,
                                   # força incluir a linha FORA da janela temporal
                                   # (ex. OF_DATAFIM null = OF aberta). Sem isto, um
                                   # barco criado há >window_years mas ainda em
                                   # produção caía do mirror (gap 907 vs 1121 live).
    keep_open_via_sql: Optional[str] = None  # Q.158.I: condição SQL extra (OR) na
                                   # cópia FULL p/ incluir linhas que importam mesmo
                                   # fora da janela e já fechadas — ex. ORDEMFABRICO
                                   # com REPARAÇÃO aberta (OF entregue que voltou:
                                   # EXISTS of_fp com offp_datafim NULL). Só no full
                                   # (nightly); o incremental de 5 min não a corre.

    @property
    def pg_name(self) -> str:
        """Nome lowercase no schema factory_raw."""
        return self.nelo_name.lower()

    @property
    def supports_incremental(self) -> bool:
        """Tem PK single-col + coluna-watermark → pode fazer upsert incremental."""
        return bool(self.pk_col and (self.inc_col or self.date_col))


# Lista curada — tabelas-core de produção (não top-by-rowcount).
# Q.125: pk_col + inc_col nas tabelas de alta velocidade → refresh incremental
# de 5/5 min. As de PK composto / lookups mantêm full copy (nightly/atómico).
RAW_TABLES: list[RawTable] = [
    RawTable("PRODUTO", None),
    RawTable("FASES_PRODUCAO", None),
    RawTable("MOLDES", None),
    RawTable("ENTIDADE", None),
    RawTable("PRODUTO_FASE", None),
    RawTable("PRODUTO_COMPONENTE", None),
    RawTable("OFFP_EQ", None),                           # 1.4M, PK composto → nightly
    RawTable("ORDEMFABRICO", "OF_DATA", 2,
             pk_col="OF_ID", inc_col="OF_DATAACTUALIZACAO",
             keep_open_col="OF_DATAFIM",
             # Q.158.I — além das abertas (keep_open_col), trazer OFs JÁ FECHADAS
             # que voltaram para REPARAÇÃO (têm op aberta em of_fp). 83 dos ~830
             # "em produção" da NELO são OFs com OF_DATAFIM preenchido. Só no full.
             keep_open_via_sql=(
                 "EXISTS (SELECT 1 FROM OF_FP r "
                 "WHERE r.OFFP_OF_ID = OF_ID AND r.OFFP_DATAFIM IS NULL)"
             )),
    RawTable("OF_FP", "OFFP_DATAINICIO", 2,
             pk_col="OFFP_ID", inc_col="OFFP_DATAINICIO",
             keep_open_col="OFFP_DATAFIM"),  # Q.158.H: nunca deixar cair uma
             # operação ABERTA (datafim null), incl. não-iniciadas (datainicio
             # null) — a janela por OFFP_DATAINICIO dropava-as e a regra
             # "em produção" da NELO (CROSS APPLY) precisa delas.
    RawTable("OF_CHECKLIST", "OFCH_DATA_VERIFICACAO", 1,
             pk_col="OFCH_ID", inc_col="OFCH_DATA_ACTUALIZACAO"),
    RawTable("MOVIMENTO", "MOV_DATA", 2,
             pk_col="MOV_ID", inc_col="MOV_DATA"),
    # Q.108.M — apontamentos de horas trabalhadas (mão-de-obra real).
    # Watermark canónica: AT_DATA. O reflection q75 lê INFORMATION_SCHEMA
    # automaticamente; colunas reais são descobertas em runtime. Marts
    # downstream assumem: AT_DATA (date/text), AT_E_ID (operador FK),
    # AT_OF_ID (work order FK), AT_FP_ID (phase FK), AT_HORAS (numeric).
    # Se schema divergir, sanity checks dos marts falham loud — corrigir
    # então. Destrava KPIs 8.2/8.5 (horas trabalhadas, custo labor).
    RawTable("APONTAMENTO_TRABALHO", "AT_DATA", 2),
    # Q.167.C.1 — movimentos de pessoal (ausências/horas-extra). Desbloqueia a
    # capacidade-disponível (Report_ProducaoCapacidade: E_PRODUTIVIDADE − faltas
    # MET_MET_ID=2) e conserta a marts.v_workforce_horas_extra_mes (que referencia
    # factory_raw.ent_mov, ausente em dev → latente-partida). Full copy (166k, ~2s)
    # para manter o histórico completo (o anchor de 60k eventos MET=1 da horas-extra
    # exige-o); pk+inc → o incremental de 5 min mantém os recentes frescos.
    RawTable("ENT_MOV", None, pk_col="MOVENT_ID", inc_col="MOVENT_DATA_I"),
    RawTable("ENT_MOV_TIPO", None),  # lookup (15 linhas: MET_MET_ID=2 = Faltas)
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

    # 1. CREATE idempotente — DROP-free. Q.157.0: o DROP anterior rebentava com
    #    `DependentObjectsStillExistError` nas tabelas com VIEWs marts
    #    dependentes (produto/fases_producao/entidade/offp_eq), por isso o
    #    full-copy nocturno dessas falhava em silêncio e ficavam dias stale.
    col_defs = ", ".join(f'"{name}" {pgtype}' for name, pgtype in cols)
    await pg_conn.execute(
        f'CREATE TABLE IF NOT EXISTS factory_raw."{pg_table}" ({col_defs}, '
        f'_synced_at timestamptz DEFAULT now())',
    )

    # 2. SELECT do SQL Server (com janela temporal se aplicável).
    select_cols = ", ".join(f"[{c}]" for c in col_names)
    where = ""
    if spec.date_col:
        cond = (
            f"[{spec.date_col}] >= "
            f"DATEADD(year, -{spec.window_years}, GETDATE())"
        )
        # Q.158.F — nunca deixar cair uma OF aberta (em produção), por muito
        # antiga que seja a sua criação: o critério "barco em produção" tem de
        # ver TODAS as abertas, não só as criadas na janela.
        if spec.keep_open_col:
            cond = f"({cond} OR [{spec.keep_open_col}] IS NULL)"
        # Q.158.I — condição SQL extra (OR) só no FULL: traz linhas que importam
        # mesmo fora da janela e já fechadas (ex. ORDEMFABRICO com REPARAÇÃO
        # aberta — OF entregue que voltou). O incremental de 5 min não a corre.
        if spec.keep_open_via_sql:
            cond = f"({cond} OR {spec.keep_open_via_sql})"
        where = f" WHERE {cond}"
    select_sql = text(f"SELECT {select_cols} FROM [{spec.nelo_name}]{where}")

    # 3. TRUNCATE + bulk copy numa SÓ transação (DROP-free e atómico p/ as
    #    VIEWs — nunca veem a tabela vazia; TRUNCATE mantém o OID). `conn.stream`
    #    faz server-side cursor — não carrega milhões de rows em memória
    #    (offp_eq ~1.4M). Se a leitura ao ERP falhar a meio, o rollback mantém
    #    os dados antigos (melhor que o DROP, que deixava a tabela apagada).
    total = 0
    async with pg_conn.transaction():
        await pg_conn.execute(f'TRUNCATE factory_raw."{pg_table}"')
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


async def _mirror_table_incremental(
    sql_engine,
    pg_conn: asyncpg.Connection,
    spec: RawTable,
    window_days: int = INCREMENTAL_WINDOW_DAYS,
) -> dict[str, Any]:
    """Q.125 — refresh incremental: relê os últimos `window_days` por `inc_col`
    e faz upsert por `pk_col`. Não faz DROP (a tabela vive) → sem janela de
    leitura vazia para as views/marts que leem `factory_raw`. Idempotente.

    Se a tabela ainda não existir, cai para o full mirror (primeiro arranque).
    """
    t0 = time.monotonic()
    pg_table = spec.pg_name
    inc_col = spec.inc_col or spec.date_col
    assert spec.pk_col and inc_col, "incremental exige pk_col + inc_col"

    exists = await pg_conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='factory_raw' AND table_name=$1)", pg_table,
    )
    if not exists:
        # Primeira vez: full mirror cria a tabela com a janela de anos.
        return await _mirror_table(sql_engine, pg_conn, spec)

    cols = await _reflect_columns(sql_engine, spec.nelo_name)
    if not cols:
        return {"table": spec.nelo_name, "status": "error",
                "error": "0 colunas reflectidas"}
    col_names = [c[0] for c in cols]
    if spec.pk_col not in col_names:
        return {"table": spec.nelo_name, "status": "error",
                "error": f"pk_col {spec.pk_col} ausente das colunas"}

    # Índice único no PK (idempotente) — alvo do ON CONFLICT.
    await pg_conn.execute(
        f'CREATE UNIQUE INDEX IF NOT EXISTS "ux_{pg_table}_pk" '
        f'ON factory_raw."{pg_table}" ("{spec.pk_col}")'
    )

    # Lê do SQL Server só a janela recente por inc_col.
    # Q.158.F — além da janela recente, relê SEMPRE as linhas abertas
    # (keep_open_col IS NULL): apanha barcos abertos antigos cujo inc_col
    # (ex. OF_DATAACTUALIZACAO, 96.8% null) nunca dispara o watermark.
    select_cols = ", ".join(f"[{c}]" for c in col_names)
    inc_cond = f"[{inc_col}] >= DATEADD(day, -{window_days}, GETDATE())"
    if spec.keep_open_col:
        inc_cond = f"({inc_cond} OR [{spec.keep_open_col}] IS NULL)"
    select_sql = text(
        f"SELECT {select_cols} FROM [{spec.nelo_name}] WHERE {inc_cond}"
    )

    # Temp table com a mesma forma (sem _synced_at) para o upsert.
    tmp = f"_inc_{pg_table}"
    col_defs = ", ".join(f'"{name}" {pgtype}' for name, pgtype in cols)
    # Sem ON COMMIT DROP: asyncpg faz autocommit por statement, o que dropava a
    # temp table logo a seguir. Cai no fecho da sessão; DROP IF EXISTS limpa.
    await pg_conn.execute(f'DROP TABLE IF EXISTS "{tmp}"')
    await pg_conn.execute(f'CREATE TEMP TABLE "{tmp}" ({col_defs})')

    read = 0
    async with sql_engine.connect() as conn:
        result = await conn.stream(select_sql)
        batch: list[tuple] = []
        async for row in result:
            batch.append(tuple(_coerce_value(v) for v in row))
            if len(batch) >= READ_CHUNK:
                await pg_conn.copy_records_to_table(
                    tmp, columns=col_names, records=batch,
                )
                read += len(batch)
                batch = []
        if batch:
            await pg_conn.copy_records_to_table(
                tmp, columns=col_names, records=batch,
            )
            read += len(batch)

    # Upsert por PK: insere novos, actualiza alterados, carimba _synced_at.
    non_pk = [c for c in col_names if c != spec.pk_col]
    set_clause = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in non_pk)
    set_clause = (set_clause + ", " if set_clause else "") + '_synced_at = now()'
    insert_cols = ", ".join(f'"{c}"' for c in col_names)
    upsert = (
        f'INSERT INTO factory_raw."{pg_table}" ({insert_cols}) '
        f'SELECT {insert_cols} FROM pg_temp."{tmp}" '
        f'ON CONFLICT ("{spec.pk_col}") DO UPDATE SET {set_clause}'
    )
    status_before = await pg_conn.fetchval(
        f'SELECT COUNT(*) FROM factory_raw."{pg_table}"'
    )
    await pg_conn.execute(upsert)
    status_after = await pg_conn.fetchval(
        f'SELECT COUNT(*) FROM factory_raw."{pg_table}"'
    )

    return {
        "table": spec.nelo_name, "pg_table": f"factory_raw.{pg_table}",
        "status": "ok", "mode": "incremental",
        "window_days": window_days, "rows_read": read,
        "rows_inserted": status_after - status_before,
        "rows_total": status_after,
        "elapsed_s": round(time.monotonic() - t0, 1),
    }


async def _refresh_table_atomic(
    sql_engine,
    pg_conn: asyncpg.Connection,
    spec: RawTable,
    where: str = "",
) -> dict[str, Any]:
    """Q.125 — full refresh DROP-FREE e atómico: lê tudo do SQL Server, depois
    ``TRUNCATE + COPY`` numa transação. Seguro com views/marts dependentes
    (TRUNCATE mantém o OID da tabela; ``DROP`` falharia por dependência). O lock
    ACCESS EXCLUSIVE só dura o COPY (in-memory), não a leitura ao ERP.

    Para tabelas de PK composto / lookups (≤100k). Tabelas enormes usam o
    incremental por upsert.
    """
    t0 = time.monotonic()
    cols = await _reflect_columns(sql_engine, spec.nelo_name)
    if not cols:
        return {"table": spec.nelo_name, "status": "error",
                "error": "0 colunas reflectidas"}
    col_names = [c[0] for c in cols]
    pg_table = spec.pg_name

    col_defs = ", ".join(f'"{name}" {pgtype}' for name, pgtype in cols)
    await pg_conn.execute(
        f'CREATE TABLE IF NOT EXISTS factory_raw."{pg_table}" ({col_defs}, '
        f'_synced_at timestamptz DEFAULT now())'
    )

    select_cols = ", ".join(f"[{c}]" for c in col_names)
    select_sql = text(f"SELECT {select_cols} FROM [{spec.nelo_name}]{where}")

    rows: list[tuple] = []
    async with sql_engine.connect() as conn:
        result = await conn.stream(select_sql)
        async for row in result:
            rows.append(tuple(_coerce_value(v) for v in row))

    async with pg_conn.transaction():
        await pg_conn.execute(f'TRUNCATE factory_raw."{pg_table}"')
        if rows:
            await pg_conn.copy_records_to_table(
                pg_table, schema_name="factory_raw",
                columns=col_names, records=rows,
            )

    return {
        "table": spec.nelo_name, "pg_table": f"factory_raw.{pg_table}",
        "status": "ok", "mode": "atomic_full", "rows": len(rows),
        "elapsed_s": round(time.monotonic() - t0, 1),
    }


async def setup(
    only: Optional[list[str]] = None,
    incremental: bool = False,
    window_days: int = INCREMENTAL_WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """Espelha todas as RAW_TABLES (ou subset `only`).

    Q.125: ``incremental=True`` faz upsert da janela recente nas tabelas com
    ``supports_incremental`` (PK + watermark); as restantes são saltadas
    (mantêm o full mirror nocturno). ``incremental=False`` = full rebuild.
    """
    if not settings.sqlserver_enabled:
        raise SystemExit("SQLSERVER_ENABLED=False — não posso espelhar.")

    selected = (
        [t for t in RAW_TABLES if t.nelo_name in only] if only else RAW_TABLES
    )
    if incremental:
        selected = [t for t in selected if t.supports_incremental]
    sql_engine = get_engine()

    # asyncpg connection directa (copy_records_to_table não existe no
    # SQLAlchemy async wrapper).
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    pg_conn = await asyncpg.connect(pg_dsn)

    results: list[dict[str, Any]] = []
    try:
        await pg_conn.execute("CREATE SCHEMA IF NOT EXISTS factory_raw")
        for spec in selected:
            verb = "incremental" if incremental else "full"
            print(f"[{spec.nelo_name}] a espelhar ({verb})...", flush=True)
            try:
                if incremental:
                    stats = await _mirror_table_incremental(
                        sql_engine, pg_conn, spec, window_days,
                    )
                else:
                    stats = await _mirror_table(sql_engine, pg_conn, spec)
            except Exception as exc:
                stats = {"table": spec.nelo_name, "status": "error",
                         "error": f"{type(exc).__name__}: {exc}"}
            results.append(stats)
            # ASCII-only: Windows console (cp1252/colorama) rebenta com '→'
            # (UnicodeEncodeError) e abortava o loop de espelho a meio (Q.144.A).
            print(f"  -> {stats}", flush=True)
    finally:
        await pg_conn.close()
        await sql_engine.dispose()
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--only", nargs="+", default=None,
                        help="Espelhar só estas tabelas (nomes NELO).")
    parser.add_argument("--incremental", action="store_true",
                        help="Q.125: upsert da janela recente (5/5 min) em vez "
                             "de full rebuild. Só tabelas com PK+watermark.")
    parser.add_argument("--window-days", type=int, default=INCREMENTAL_WINDOW_DAYS,
                        help="Janela do incremental em dias (default %(default)s).")
    args = parser.parse_args()

    results = asyncio.run(setup(
        only=args.only, incremental=args.incremental, window_days=args.window_days,
    ))

    ok = [r for r in results if r["status"] == "ok"]
    err = [r for r in results if r["status"] != "ok"]
    # Full mirror reporta `rows` (copiadas); incremental reporta `rows_read`.
    total_rows = sum(r.get("rows", r.get("rows_read", 0)) for r in ok)
    inserted = sum(r.get("rows_inserted", 0) for r in ok)
    print()
    print(f"=== {len(ok)}/{len(results)} tabelas, {total_rows:,} linhas lidas"
          f"{f', {inserted:,} novas (upsert)' if any('mode' in r for r in ok) else ' copiadas'}"
          f" ===")
    for r in err:
        print(f"  FALHA {r['table']}: {r.get('error')}")
    return 0 if not err else 1


if __name__ == "__main__":
    sys.exit(main())
