"""Schema discovery — MAR-KAYAKS (fabrica.nelo.eu) → agent_docs markdown.

Read-only. Connects via pyodbc, queries INFORMATION_SCHEMA + sys.*, samples
TOP 3 rows per table, and writes a structured markdown reference to
``agent_docs/mar_kayaks_schema_discovery.md``.

Connection params come from env var ``MAR_KAYAKS_DSN`` if set; otherwise
falls back to the credentials Luis provided in-session (one-shot use).
"""

from __future__ import annotations

import datetime as _dt
import decimal
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import pyodbc

# ── Connection ───────────────────────────────────────────────────────────

_DEFAULT_DSN = (
    "DRIVER={SQL Server};"
    "SERVER=fabrica.nelo.eu,1039;"
    "DATABASE=MAR-KAYAKS;"
    "UID=nikufra;"
    "PWD=arfukin2026;"
    "TrustServerCertificate=yes;"
    "Encrypt=no;"
)


def get_conn() -> pyodbc.Connection:
    dsn = os.environ.get("MAR_KAYAKS_DSN", _DEFAULT_DSN)
    return pyodbc.connect(dsn, timeout=20)


# ── Bucket classification ───────────────────────────────────────────────

BUCKETS: list[tuple[str, str, list[str]]] = [
    (
        "ordens",
        "Ordens de fabrico",
        # exact + prefix patterns (case-insensitive match on name)
        [
            r"^ORDEMFABRICO$",
            r"^auxOrdemFabrico$",
            r"^OF_",
            r"^OFFP_",
            r"^OFCH_",
            r"^REP_OF_FP$",
            r"^EstadoOFAgente$",
            r"^PROVAS_OF$",
            r"^TRANSP_OF$",
            r"^auxOrdem",
        ],
    ),
    (
        "artigos",
        "Artigos / Produtos / BOM",
        [
            r"^PRODUTO$",
            r"^PRODUTO_",
            r"^ProdutoTipoAcessorio$",
            r"^ArtigosGrupos$",
            r"^COMPONENTE_TIPO$",
            r"^MEDIDAS$",
            r"^UNIDADE$",
        ],
    ),
    (
        "operacoes",
        "Operações, fases e planeamento",
        [
            r"^FASES_PRODUCAO$",
            r"^FP_FP$",
            r"^COMUNICACAO_FASES_PRODUCAO$",
            r"^LACAGEM$",
            r"^ESTACAO$",
            r"^TURNO$",
            r"^INTERVALO$",
            r"^PLANEAMENTO_DIARIO$",
            r"^Z_PrevisaoPlano$",
            r"^PLANO$",
            r"^DIAS_TRABALHO$",
            r"^DIAS_FERIADOS_FERIAS$",
            r"^FERIAS$",
        ],
    ),
    (
        "recursos",
        "Recursos (entidades, equipas, moldes, RH)",
        [
            r"^ENTIDADE$",
            r"^ENTIDADE_(?!OBS$|OBS_)",  # exclude OBS_* (operational notes)
            r"^ENT_",
            r"^EQUIPA$",
            r"^MOLDES$",
            r"^MOLDES_",
            r"^RH_",
        ],
    ),
    (
        "qualidade",
        "Qualidade, problemas, inspecções",
        [
            r"^AVALIACOES_ITEMS$",
            r"^OFFP_PROBLEMA$",
            r"^OFFP_GRAVIDADE",
            r"^PROBS$",
            r"^PROBS_",
            r"^PROB_CAUSA_SOL",
            r"^PRODUTO_PROB_CAUSA_SOL$",
            r"^RH_PROBLEMA$",
            r"^REPARACOES_PROVAS$",
            r"^AUDIT$",
            r"^AUDIT_",
        ],
    ),
    (
        "stock",
        "Stock, inventário, movimentos, encomendas",
        [
            r"^ARMAZEM$",
            r"^MOVIMENTO$",
            r"^MOVIMENTO_",
            r"^ENT_MOV",
            r"^LISTA$",
            r"^LISTA_",
            r"^PEDIDOS$",
            r"^ENCOMENDA$",
            r"^ENCOMENDA_",
            r"^Encomenda_trk$",
            r"^AgenteEncomenda",
            r"^TRANSPORTE$",
            r"^TRANSP_",
        ],
    ),
]

EXCLUDE_EXACT = {
    "migrations",
    "failed_jobs",
    "failed_import_rows",
    "job_batches",
    "notifications",
    "personal_access_tokens",
    "ShopCache",
    "rfid_cache",
    "GASTOS_CACHE",
    "ACTUALIZACOES",
    "sysdiagrams",
    "exports",
    "imports",
    "Report_Table_20171114",
    "logs_web",
    "MAILS",
    "USERS",
    "users_laravel",
    "auxAnexos",
    "country-codes2",
}
EXCLUDE_PREFIX = ("telescope_",)


def classify(name: str) -> str | None:
    """Return bucket key for the table name, or None if not in scope."""
    if name in EXCLUDE_EXACT or any(name.startswith(p) for p in EXCLUDE_PREFIX):
        return None
    for key, _label, patterns in BUCKETS:
        for pat in patterns:
            if re.match(pat, name, re.IGNORECASE):
                return key
    return None


# ── Per-table discovery ─────────────────────────────────────────────────


def row_count(cur: pyodbc.Cursor, schema: str, table: str) -> int | None:
    """Use sys.partitions (catalog, not DMV) — nikufra has no VIEW DATABASE STATE."""
    obj = f"[{schema}].[{table}]"
    try:
        cur.execute(
            "SELECT ISNULL(SUM(rows), 0) "
            "FROM sys.partitions "
            "WHERE object_id = OBJECT_ID(?) AND index_id IN (0, 1)",
            obj,
        )
        r = cur.fetchone()
        return int(r[0]) if r and r[0] is not None else 0
    except pyodbc.Error:
        return None


def columns(cur: pyodbc.Cursor, schema: str, table: str) -> list[dict]:
    cur.execute(
        """
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
               IS_NULLABLE, COLUMN_DEFAULT, ORDINAL_POSITION
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
        """,
        schema,
        table,
    )
    out = []
    for r in cur.fetchall():
        name, dtype, maxlen, nullable, default, ordinal = r
        out.append(
            dict(
                name=name,
                type=dtype,
                maxlen=maxlen,
                nullable=(nullable == "YES"),
                default=default,
                ordinal=ordinal,
            )
        )
    return out


def primary_key(cur: pyodbc.Cursor, schema: str, table: str) -> list[str]:
    cur.execute(
        """
        SELECT c.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE c
          ON c.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
         AND c.TABLE_SCHEMA = tc.TABLE_SCHEMA
        WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
          AND tc.TABLE_SCHEMA = ? AND tc.TABLE_NAME = ?
        ORDER BY c.ORDINAL_POSITION
        """,
        schema,
        table,
    )
    return [r[0] for r in cur.fetchall()]


def foreign_keys_out(cur: pyodbc.Cursor, schema: str, table: str) -> list[dict]:
    """FKs declared on this table referring to others."""
    cur.execute(
        """
        SELECT
            fk.name AS fk_name,
            cs.name AS src_col,
            OBJECT_SCHEMA_NAME(fk.referenced_object_id) AS ref_schema,
            OBJECT_NAME(fk.referenced_object_id) AS ref_table,
            cr.name AS ref_col
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
        JOIN sys.columns cs ON cs.object_id = fkc.parent_object_id AND cs.column_id = fkc.parent_column_id
        JOIN sys.columns cr ON cr.object_id = fkc.referenced_object_id AND cr.column_id = fkc.referenced_column_id
        WHERE OBJECT_SCHEMA_NAME(fk.parent_object_id) = ?
          AND OBJECT_NAME(fk.parent_object_id) = ?
        ORDER BY fk.name, fkc.constraint_column_id
        """,
        schema,
        table,
    )
    return [
        dict(
            name=r.fk_name,
            src=r.src_col,
            ref_schema=r.ref_schema,
            ref_table=r.ref_table,
            ref_col=r.ref_col,
        )
        for r in cur.fetchall()
    ]


def foreign_keys_in(cur: pyodbc.Cursor, schema: str, table: str) -> list[dict]:
    """FKs declared on other tables pointing to this one."""
    cur.execute(
        """
        SELECT
            fk.name AS fk_name,
            OBJECT_SCHEMA_NAME(fk.parent_object_id) AS src_schema,
            OBJECT_NAME(fk.parent_object_id) AS src_table,
            cs.name AS src_col,
            cr.name AS ref_col
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
        JOIN sys.columns cs ON cs.object_id = fkc.parent_object_id AND cs.column_id = fkc.parent_column_id
        JOIN sys.columns cr ON cr.object_id = fkc.referenced_object_id AND cr.column_id = fkc.referenced_column_id
        WHERE OBJECT_SCHEMA_NAME(fk.referenced_object_id) = ?
          AND OBJECT_NAME(fk.referenced_object_id) = ?
        ORDER BY fk.name, fkc.constraint_column_id
        """,
        schema,
        table,
    )
    return [
        dict(
            name=r.fk_name,
            src_schema=r.src_schema,
            src_table=r.src_table,
            src_col=r.src_col,
            ref_col=r.ref_col,
        )
        for r in cur.fetchall()
    ]


# Implicit relations: heuristic that flags columns whose name ends with
# `_ID / _COD / _REF / _KEY / _FK / Id` and tries to guess a target table.
_IMPLICIT_SUFFIX_RE = re.compile(r"(.+?)(_ID|_COD|_REF|_KEY|_FK|Id)$", re.IGNORECASE)


def implicit_relations(
    cols: list[dict], declared_fk_cols: set[str], all_tables: set[str]
) -> list[dict]:
    """Find columns that look like FKs but aren't declared."""
    out = []
    for c in cols:
        cname = c["name"]
        if cname in declared_fk_cols:
            continue
        m = _IMPLICIT_SUFFIX_RE.match(cname)
        if not m:
            continue
        base, _suffix = m.group(1), m.group(2)
        # Try the base as a literal table name match (case-insensitive),
        # then try common transformations (singular/plural agnostic).
        candidates = {base.upper(), base.lower(), base}
        target = next(
            (t for t in all_tables if t.upper() == base.upper()),
            None,
        )
        if not target:
            # base = PRODUTO → also try PRODUTOS, PRODUTO_*
            target = next(
                (t for t in all_tables if t.upper().startswith(base.upper())),
                None,
            )
        out.append(dict(col=cname, base=base, guess=target))
    return out


def sample_rows(cur: pyodbc.Cursor, schema: str, table: str, limit: int = 3) -> tuple[list[str], list[list]]:
    obj = f"[{schema}].[{table}]"
    try:
        cur.execute(f"SELECT TOP {limit} * FROM {obj} WITH (NOLOCK)")
    except pyodbc.Error as e:
        return [f"<error: {e}>"], []
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = []
    for r in cur.fetchall():
        rows.append([_format_value(v) for v in r])
    return cols, rows


def _format_value(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, (bytes, bytearray, memoryview)):
        b = bytes(v)
        return f"0x{b[:8].hex()}…" if len(b) > 8 else f"0x{b.hex()}"
    if isinstance(v, _dt.datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, _dt.date):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return str(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    s = str(v).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    if len(s) > 40:
        return s[:37] + "..."
    return s


# ── Markdown rendering ──────────────────────────────────────────────────


def md_escape(s: str) -> str:
    return s.replace("|", "\\|") if s else s


def render_table(tinfo: dict, all_tables: set[str]) -> str:
    name = tinfo["name"]
    rc = tinfo["row_count"]
    rc_str = f"{rc:,}".replace(",", " ") if isinstance(rc, int) else "?"

    lines: list[str] = []
    anchor = name.lower().replace("_", "-").replace(" ", "-")
    lines.append(f"### `{name}` — *{rc_str} rows*")
    lines.append("")

    # Columns table
    lines.append("| # | Column | Type | Null | Default | Notes |")
    lines.append("|---|---|---|---|---|---|")
    pk_cols = set(tinfo["pk"])
    fk_out_cols = {fk["src"]: fk for fk in tinfo["fk_out"]}
    for c in tinfo["columns"]:
        cn = c["name"]
        tname = c["type"]
        if c["maxlen"] not in (None, -1) and c["type"] in ("varchar", "nvarchar", "char", "nchar"):
            tname = f"{c['type']}({c['maxlen']})"
        elif c["maxlen"] == -1 and c["type"] in ("varchar", "nvarchar"):
            tname = f"{c['type']}(max)"
        notes = []
        if cn in pk_cols:
            notes.append("**PK**")
        if cn in fk_out_cols:
            fk = fk_out_cols[cn]
            notes.append(f"FK → `{fk['ref_table']}.{fk['ref_col']}`")
        null = "YES" if c["nullable"] else "NO"
        default = md_escape(str(c["default"]))[:30] if c["default"] else ""
        lines.append(
            f"| {c['ordinal']} | `{cn}` | {tname} | {null} | {default} | {' '.join(notes)} |"
        )
    lines.append("")

    # PK
    if tinfo["pk"]:
        lines.append(f"**PK**: `{', '.join(tinfo['pk'])}`")
    else:
        lines.append("**PK**: _(none declared)_")
    lines.append("")

    # FKs out
    if tinfo["fk_out"]:
        lines.append("**FKs declared (out)**:")
        for fk in tinfo["fk_out"]:
            lines.append(f"- `{fk['src']}` → `{fk['ref_table']}.{fk['ref_col']}`")
    else:
        lines.append("**FKs declared (out)**: _(none)_")
    lines.append("")

    # FKs in
    if tinfo["fk_in"]:
        lines.append(f"**FKs declared (in)** — *{len(tinfo['fk_in'])} references*:")
        for fk in tinfo["fk_in"][:20]:
            lines.append(f"- `{fk['src_table']}.{fk['src_col']}`")
        if len(tinfo["fk_in"]) > 20:
            lines.append(f"- … *(+{len(tinfo['fk_in']) - 20} more)*")
    lines.append("")

    # Implicit
    if tinfo["implicit"]:
        lines.append("**Implicit relations** _(by column naming)_:")
        for r in tinfo["implicit"]:
            tgt = f"`{r['guess']}`" if r["guess"] else "_(no obvious target)_"
            lines.append(f"- `{r['col']}` → likely {tgt}")
        lines.append("")

    # Sample
    sample_cols, sample_rows_ = tinfo["sample"]
    if sample_rows_:
        # Truncate to first 8 cols to keep markdown readable
        max_cols = 8
        display_cols = sample_cols[:max_cols]
        suffix = f" *(showing {max_cols} of {len(sample_cols)} cols)*" if len(sample_cols) > max_cols else ""
        lines.append(f"**Sample (TOP 3)**{suffix}:")
        lines.append("")
        lines.append("| " + " | ".join(f"`{c}`" for c in display_cols) + " |")
        lines.append("|" + "|".join(["---"] * len(display_cols)) + "|")
        for row in sample_rows_:
            lines.append("| " + " | ".join(md_escape(str(v)) for v in row[:max_cols]) + " |")
        lines.append("")
    else:
        lines.append("**Sample**: _(table empty or unreadable)_")
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────


def main() -> int:
    print("> Connecting to MAR-KAYAKS @ fabrica.nelo.eu:1039 …", flush=True)
    conn = get_conn()
    cur = conn.cursor()

    # All tables in dbo (for naming-relation guesses + scope filter)
    cur.execute(
        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo' "
        "ORDER BY TABLE_NAME"
    )
    all_tables = [r[0] for r in cur.fetchall()]
    all_tables_set = set(all_tables)
    print(f"> {len(all_tables)} base tables in dbo", flush=True)

    # Filter to scope
    in_scope: dict[str, list[str]] = defaultdict(list)
    for t in all_tables:
        b = classify(t)
        if b:
            in_scope[b].append(t)
    total_targets = sum(len(v) for v in in_scope.values())
    print(f"> Filtered {total_targets} candidate tables across {len(in_scope)} buckets", flush=True)
    for bk, _label, _ in BUCKETS:
        print(f"   [{bk}] {len(in_scope.get(bk, []))} tables", flush=True)

    # Discover each table
    discoveries: dict[str, list[dict]] = defaultdict(list)
    started = time.time()
    counter = 0
    for bk, _label, _ in BUCKETS:
        for t in in_scope.get(bk, []):
            counter += 1
            t0 = time.time()
            try:
                rc = row_count(cur, "dbo", t)
                cols = columns(cur, "dbo", t)
                pk = primary_key(cur, "dbo", t)
                fk_out = foreign_keys_out(cur, "dbo", t)
                fk_in = foreign_keys_in(cur, "dbo", t)
                declared = {fk["src"] for fk in fk_out}
                implicit = implicit_relations(cols, declared, all_tables_set)
                sample = sample_rows(cur, "dbo", t)
                discoveries[bk].append(
                    dict(
                        name=t,
                        row_count=rc,
                        columns=cols,
                        pk=pk,
                        fk_out=fk_out,
                        fk_in=fk_in,
                        implicit=implicit,
                        sample=sample,
                    )
                )
                rc_str = f"{rc:,}".replace(",", " ") if isinstance(rc, int) else "?"
                print(
                    f"   [{counter}/{total_targets}] {t:<40} rows={rc_str:>10}  "
                    f"cols={len(cols):>3}  fk_out={len(fk_out):>2}  fk_in={len(fk_in):>2}  "
                    f"({time.time() - t0:.1f}s)",
                    flush=True,
                )
            except pyodbc.Error as e:
                print(f"   [{counter}/{total_targets}] {t:<40} ERROR: {e}", flush=True)

    elapsed = time.time() - started
    print(f"> Discovery finished in {elapsed:.0f}s", flush=True)

    # Render markdown
    out_path = Path(__file__).resolve().parent.parent / "agent_docs" / "mar_kayaks_schema_discovery.md"
    md = []
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    md.append("# MAR-KAYAKS schema discovery\n")
    md.append(f"> Generated {now} via `scripts/discover_mar_kayaks.py`.")
    md.append(f"> Server: `fabrica.nelo.eu:1039` · DB: `MAR-KAYAKS` · {len(all_tables)} base tables in `dbo`.")
    md.append(f"> Filtered {total_targets} tables across {len(in_scope)} production-relevant buckets.\n")

    # TOC
    md.append("## Índice\n")
    for bk, label, _ in BUCKETS:
        n = len(discoveries.get(bk, []))
        slug = re.sub(r"[^a-z0-9-]", "", label.lower().replace(" ", "-"))
        md.append(f"- [{label}](#{slug}) — {n} tabelas")
    md.append("- [Recomendação de integração com ProdPlan ONE](#recomendacao-de-integracao-com-prodplan-one)\n")

    # Per-bucket
    for bk, label, _ in BUCKETS:
        slug = re.sub(r"[^a-z0-9-]", "", label.lower().replace(" ", "-"))
        md.append(f"<a id=\"{slug}\"></a>\n## {label}\n")
        tables = sorted(discoveries.get(bk, []), key=lambda t: -(t["row_count"] or 0))
        if not tables:
            md.append("_(nenhuma tabela)_\n")
            continue
        # mini-toc within bucket sorted by row count
        md.append("| Tabela | Linhas | Cols | PK | FK out | FK in |")
        md.append("|---|---:|---:|---|---:|---:|")
        for t in tables:
            rc_str = f"{t['row_count']:,}".replace(",", " ") if isinstance(t["row_count"], int) else "?"
            pk_str = ", ".join(t["pk"]) if t["pk"] else "—"
            md.append(
                f"| `{t['name']}` | {rc_str} | {len(t['columns'])} | {pk_str} | "
                f"{len(t['fk_out'])} | {len(t['fk_in'])} |"
            )
        md.append("")
        for t in tables:
            md.append(render_table(t, all_tables_set))

    # Final recommendation
    md.append("<a id=\"recomendacao-de-integracao-com-prodplan-one\"></a>")
    md.append("## Recomendação de integração com ProdPlan ONE\n")
    md.append("Baseado em row counts, FKs declaradas e cobertura semântica:\n")

    # Build recommendation lists dynamically from observed top tables
    def top_n(bucket: str, n: int) -> list[dict]:
        items = discoveries.get(bucket, [])
        return sorted(items, key=lambda t: -(t["row_count"] or 0))[:n]

    md.append("### Master data — espelhar localmente (read sync)\n")
    md.append("| Tabela | Linhas | Porquê |")
    md.append("|---|---:|---|")
    masters_candidates = [
        ("PRODUTO", "Catálogo de produtos — root da hierarquia."),
        ("PRODUTO_FASE", "Routings: produto × fase. Define operações esperadas."),
        ("PRODUTO_COMPONENTE", "BOM — componentes por produto."),
        ("FASES_PRODUCAO", "Master de fases (= work centres do MES)."),
        ("FP_FP", "Precedências entre fases (DAG do routing)."),
        ("ENTIDADE", "Pessoas / clientes / fornecedores / operadores."),
        ("MOLDES", "Master de moldes — recurso crítico (510 esperados)."),
        ("ARMAZEM", "Master de armazéns."),
        ("ESTACAO", "Master de estações."),
        ("TURNO", "Calendário de turnos."),
    ]
    for cand, why in masters_candidates:
        for bk in in_scope:
            for t in discoveries.get(bk, []):
                if t["name"] == cand:
                    rc = f"{t['row_count']:,}".replace(",", " ") if isinstance(t["row_count"], int) else "?"
                    md.append(f"| `{cand}` | {rc} | {why} |")
                    break
    md.append("")

    md.append("### Transactional — ler via adapter (nunca escrever)\n")
    md.append("| Tabela | Linhas | Porquê |")
    md.append("|---|---:|---|")
    tx_candidates = [
        ("ORDEMFABRICO", "Ordens de fabrico — fonte de demand para o scheduler."),
        ("OF_FP", "OF × Fase — estado de execução por operação."),
        ("OFFP_PROBLEMA", "Problemas registados durante execução de fases."),
        ("MOVIMENTO", "Movimentos de stock — base para WIP / cura."),
        ("MOLDES_MOV", "Movimentos de moldes — utilização do recurso."),
        ("ENCOMENDA", "Encomendas de cliente — demand."),
        ("PLANEAMENTO_DIARIO", "Planeamento manual do gestor (baseline)."),
        ("Z_PrevisaoPlano", "Previsão de plano gerada por sistema."),
    ]
    for cand, why in tx_candidates:
        for bk in in_scope:
            for t in discoveries.get(bk, []):
                if t["name"] == cand:
                    rc = f"{t['row_count']:,}".replace(",", " ") if isinstance(t["row_count"], int) else "?"
                    md.append(f"| `{cand}` | {rc} | {why} |")
                    break
    md.append("")

    md.append("### Reference / lookup — incluir em mirror inicial\n")
    md.append("- `PRODUTO_TIPO`, `PRODUTO_ESTADO`, `PRODUTO_MODELO`, `PRODUTO_TAMANHO`")
    md.append("- `MOLDES_TIPO`, `MOVIMENTO_TIPO`, `OFFP_GRAVIDADE`")
    md.append("- `ENCOMENDA_ESTADO`, `EstadoOFAgente`, `OF_TIPOUSO`")
    md.append("- `UNIDADE`, `MEDIDAS`, `EQUIPA`")
    md.append("")

    md.append("### Skip — não usar no scope ProdPlan\n")
    md.append("- Laravel infra: `migrations`, `failed_jobs`, `telescope_*`, `personal_access_tokens`, `notifications`, `job_batches`")
    md.append("- Caches: `ShopCache`, `rfid_cache`, `GASTOS_CACHE`")
    md.append("- One-shot exports: `Report_Table_20171114`, `exports`, `imports`, `failed_import_rows`")
    md.append("- Auth legacy: `USERS`, `users_laravel` (usar a auth do ProdPlan)")
    md.append("")

    md.append("### Notas\n")
    md.append("- Sample rows com strings > 40 chars truncadas (`...`). Datas e números raw.")
    md.append("- FKs **declaradas** são as únicas com integridade referencial garantida pela DB.")
    md.append("  As **implícitas** (`_ID`, `_COD`, `_REF`) requerem validação de aplicação.")
    md.append("- Row counts via `sys.dm_db_partition_stats` — instantâneo, mas precisão até ao último checkpoint (não 100% live).")
    md.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(md), encoding="utf-8")
    print(f"> Wrote {out_path} ({sum(len(l) for l in md)} chars, {len(md)} lines)", flush=True)

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
