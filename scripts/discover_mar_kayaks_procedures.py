"""Stored-procedure / function / view discovery — MAR-KAYAKS → agent_docs markdown.

Read-only. Connects via pyodbc (same DSN as ``discover_mar_kayaks.py``), introspects
``sys.objects`` + ``sys.sql_modules`` (definitions) + ``sys.parameters`` (signatures),
and writes a catalogue to ``agent_docs/mar_kayaks_procedures.md`` +
``_dbprof/procedures/catalog.json``.

The whole point is to read the *canonical calculation logic* the NELO production app
(``producao.nelo.eu``) uses — instead of reverse-engineering queries by hand.

Permission gap: ``nikufra`` is ``db_datareader`` and has no ``VIEW DATABASE STATE``
(see ``discover_mar_kayaks.py`` row_count comment). Reading a module body needs
``VIEW DEFINITION``; without it ``sys.sql_modules.definition`` comes back NULL **and**
procedures/functions may be invisible in the catalog entirely (metadata-visibility
rule: you only see an object's metadata if you hold some permission on it; datareader
grants SELECT on tables/views but nothing on procs). This script detects and reports
that gap explicitly so we know to ask Nuno for ``GRANT VIEW DEFINITION``.

Run:
    $env:PYTHONPATH = "C:\\Users\\User\\nelinho"
    .\\.venv\\Scripts\\python.exe scripts\\discover_mar_kayaks_procedures.py
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import pyodbc

# ── Connection (same DSN/env as discover_mar_kayaks.py) ──────────────────

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


# ── Object-type labels ───────────────────────────────────────────────────

TYPE_LABELS: dict[str, str] = {
    "P": "Stored Procedure",
    "PC": "CLR Stored Procedure",
    "FN": "Scalar Function",
    "IF": "Inline Table-Valued Function",
    "TF": "Table-Valued Function",
    "FS": "CLR Scalar Function",
    "FT": "CLR Table-Valued Function",
    "AF": "CLR Aggregate Function",
    "V": "View",
    "TR": "Trigger",
}
# Render order: procs first (the prize), then functions, then views, then triggers.
TYPE_ORDER = ["P", "PC", "FN", "IF", "TF", "FS", "FT", "AF", "V", "TR"]

# Keywords that flag an object as "relevant to a calculation we care about".
# Used only to build a quick index for the human analysis pass — not a filter.
KEYWORDS = [
    "ORDEMFABRICO", "OF_FP", "OFFP", "FP_PRODUCAO", "OF_DATAFIM", "OF_E_ID_ENC",
    "PRODUTO_TIPO", "v_of", "em produc", "producao", "produç",
    "reparac", "reparaç", "retorno", "retrabalho", "CulpadoPelo",
    "KPI", "custo", "preco", "preço", "margem",
    "peso", "CheckPeso", "molde", "OEE", "disciplina", "expedi", "transp",
]


# ── Probes ───────────────────────────────────────────────────────────────


def permission_probe(cur: pyodbc.Cursor) -> dict:
    """What can this login see/do? Drives the plano-B decision."""
    out: dict = {}
    try:
        cur.execute(
            "SELECT CURRENT_USER, DB_NAME(), "
            "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'VIEW DEFINITION'), "
            "IS_MEMBER('db_owner'), IS_MEMBER('db_datareader'), "
            "IS_MEMBER('db_ddladmin')"
        )
        r = cur.fetchone()
        out.update(
            current_user=r[0],
            db_name=r[1],
            db_view_definition=(None if r[2] is None else int(r[2])),
            is_db_owner=(None if r[3] is None else int(r[3])),
            is_db_datareader=(None if r[4] is None else int(r[4])),
            is_db_ddladmin=(None if r[5] is None else int(r[5])),
        )
    except pyodbc.Error as e:  # pragma: no cover - depends on live perms
        out["probe_error"] = str(e)
    return out


def routines_crosscheck(cur: pyodbc.Cursor) -> dict[str, int]:
    """INFORMATION_SCHEMA.ROUTINES counts — a second visibility signal."""
    counts: dict[str, int] = {}
    try:
        cur.execute(
            "SELECT ROUTINE_TYPE, COUNT(*) "
            "FROM INFORMATION_SCHEMA.ROUTINES GROUP BY ROUTINE_TYPE"
        )
        for r in cur.fetchall():
            counts[str(r[0])] = int(r[1])
    except pyodbc.Error as e:  # pragma: no cover
        counts["<error>"] = -1
        print(f"   ! INFORMATION_SCHEMA.ROUTINES failed: {e}", flush=True)
    return counts


# ── Discovery ────────────────────────────────────────────────────────────


def fetch_objects(cur: pyodbc.Cursor) -> list[dict]:
    """All programmable objects + their module body (NULL if no VIEW DEFINITION)."""
    placeholders = ",".join(f"'{t}'" for t in TYPE_ORDER)
    cur.execute(
        f"""
        SELECT s.name AS schema_name, o.name AS object_name, o.type, o.type_desc,
               o.create_date, o.modify_date, m.definition
        FROM sys.objects o
        JOIN sys.schemas s ON s.schema_id = o.schema_id
        LEFT JOIN sys.sql_modules m ON m.object_id = o.object_id
        WHERE o.type IN ({placeholders})
        ORDER BY o.type, s.name, o.name
        """
    )
    out: list[dict] = []
    for r in cur.fetchall():
        defn = r.definition if hasattr(r, "definition") else r[6]
        out.append(
            dict(
                schema=r[0],
                name=r[1],
                type=(r[2].strip() if r[2] else r[2]),
                type_desc=r[3],
                create_date=_fmt_dt(r[4]),
                modify_date=_fmt_dt(r[5]),
                definition=defn,
                has_definition=defn is not None,
            )
        )
    return out


def fetch_result_columns(cur: pyodbc.Cursor) -> dict[tuple[str, str], list[dict]]:
    """Output columns of views + table-valued functions.

    These are readable WITHOUT ``VIEW DEFINITION`` (sys.columns follows metadata
    visibility, which we have), so even with NULL bodies we learn what each object
    *returns* — enough to explain its purpose.
    """
    cols: dict[tuple[str, str], list[dict]] = defaultdict(list)
    try:
        cur.execute(
            """
            SELECT s.name AS sch, o.name AS obj, c.column_id,
                   c.name AS col, TYPE_NAME(c.user_type_id) AS tp,
                   c.max_length, c.is_nullable
            FROM sys.columns c
            JOIN sys.objects o ON o.object_id = c.object_id
            JOIN sys.schemas s ON s.schema_id = o.schema_id
            WHERE o.type IN ('V', 'IF', 'TF')
            ORDER BY sch, obj, c.column_id
            """
        )
        for r in cur.fetchall():
            cols[(r[0], r[1])].append(
                dict(
                    ordinal=int(r[2]),
                    name=r[3],
                    type=r[4],
                    max_length=(None if r[5] is None else int(r[5])),
                    nullable=bool(r[6]),
                )
            )
    except pyodbc.Error as e:  # pragma: no cover
        print(f"   ! sys.columns failed: {e}", flush=True)
    return cols


def fetch_parameters(cur: pyodbc.Cursor) -> dict[tuple[str, str], list[dict]]:
    """parameter_id, name, type, max_length, is_output keyed by (schema, object)."""
    params: dict[tuple[str, str], list[dict]] = defaultdict(list)
    try:
        cur.execute(
            """
            SELECT OBJECT_SCHEMA_NAME(p.object_id) AS sch,
                   OBJECT_NAME(p.object_id)        AS obj,
                   p.parameter_id, p.name,
                   TYPE_NAME(p.user_type_id)       AS type_name,
                   p.max_length, p.is_output
            FROM sys.parameters p
            ORDER BY sch, obj, p.parameter_id
            """
        )
        for r in cur.fetchall():
            sch, obj = r[0], r[1]
            if sch is None or obj is None:
                continue
            params[(sch, obj)].append(
                dict(
                    ordinal=int(r[2]),
                    name=(r[3] or "(return)"),
                    type=r[4],
                    max_length=(None if r[5] is None else int(r[5])),
                    is_output=bool(r[6]),
                )
            )
    except pyodbc.Error as e:  # pragma: no cover
        print(f"   ! sys.parameters failed: {e}", flush=True)
    return params


def _fmt_dt(v) -> str | None:
    if isinstance(v, _dt.datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, _dt.date):
        return v.isoformat()
    return None if v is None else str(v)


def keyword_hits(definition: str | None) -> list[str]:
    if not definition:
        return []
    low = definition.lower()
    return [kw for kw in KEYWORDS if kw.lower() in low]


# ── Markdown rendering ───────────────────────────────────────────────────


def _sig(obj: dict, params: list[dict]) -> str:
    """Render a parameter signature like (@a int, @b varchar(50) OUTPUT)."""
    parts = []
    for p in params:
        if p["name"] == "(return)":
            continue
        t = p["type"] or "?"
        if p["max_length"] not in (None, -1) and t in ("varchar", "nvarchar", "char", "nchar"):
            t = f"{t}({p['max_length']})"
        elif p["max_length"] == -1 and t in ("varchar", "nvarchar", "varbinary"):
            t = f"{t}(max)"
        suffix = " OUTPUT" if p["is_output"] and p["name"] != "(return)" else ""
        parts.append(f"{p['name']} {t}{suffix}")
    return "(" + ", ".join(parts) + ")" if parts else "()"


def _cols_str(cols: list[dict]) -> str:
    parts = []
    for c in cols:
        t = c["type"] or "?"
        if c["max_length"] not in (None, -1) and t in ("varchar", "nvarchar", "char", "nchar"):
            t = f"{t}({c['max_length']})"
        parts.append(f"`{c['name']}` {t}")
    return ", ".join(parts)


def render(objects: list[dict], params: dict, columns: dict, perms: dict, routines: dict) -> str:
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    md: list[str] = []
    md.append("# MAR-KAYAKS — programmable objects (SPs / functions / views / triggers)\n")
    md.append(f"> Generated {now} via `scripts/discover_mar_kayaks_procedures.py`.")
    md.append("> Server: `fabrica.nelo.eu:1039` · DB: `MAR-KAYAKS`.")
    md.append("> Objetivo: ler a lógica canónica de cálculo que a app `producao.nelo.eu` usa.\n")

    # ── Permission summary ──
    md.append("## Permissões do login\n")
    md.append("| Sinal | Valor |")
    md.append("|---|---|")
    md.append(f"| `CURRENT_USER` | `{perms.get('current_user', '?')}` |")
    md.append(f"| DB | `{perms.get('db_name', '?')}` |")
    md.append(f"| `VIEW DEFINITION` (DB) | `{perms.get('db_view_definition', '?')}` |")
    md.append(f"| membro `db_owner` | `{perms.get('is_db_owner', '?')}` |")
    md.append(f"| membro `db_datareader` | `{perms.get('is_db_datareader', '?')}` |")
    md.append(f"| membro `db_ddladmin` | `{perms.get('is_db_ddladmin', '?')}` |")
    if perms.get("probe_error"):
        md.append(f"| probe error | `{perms['probe_error']}` |")
    md.append("")
    if routines:
        md.append("`INFORMATION_SCHEMA.ROUTINES` (cross-check de visibilidade): "
                  + ", ".join(f"`{k}`={v}" for k, v in sorted(routines.items())) + "\n")

    # ── Counts by type ──
    by_type: dict[str, list[dict]] = defaultdict(list)
    for o in objects:
        by_type[o["type"]].append(o)
    n_total = len(objects)
    n_with_def = sum(1 for o in objects if o["has_definition"])
    n_null = n_total - n_with_def

    md.append("## Resumo por tipo\n")
    md.append("| Tipo | Objetos | Com corpo | Corpo NULL |")
    md.append("|---|---:|---:|---:|")
    for t in TYPE_ORDER:
        items = by_type.get(t, [])
        if not items:
            continue
        with_def = sum(1 for o in items if o["has_definition"])
        md.append(f"| {TYPE_LABELS.get(t, t)} (`{t}`) | {len(items)} | {with_def} | {len(items) - with_def} |")
    md.append(f"| **TOTAL** | **{n_total}** | **{n_with_def}** | **{n_null}** |")
    md.append("")

    # ── Honest verdict on the permission gap ──
    md.append("## Veredicto\n")
    n_procs = len(by_type.get("P", [])) + len(by_type.get("PC", []))
    if n_total == 0:
        md.append("> ⛔ **Zero objetos visíveis.** O login `nikufra` não tem permissão para ver "
                  "metadados de SPs/funções (regra de metadata-visibility do SQL Server). "
                  "**Plano B:** pedir ao Nuno `GRANT VIEW DEFINITION TO nikufra;` (ou script-out/"
                  "`sp_helptext` das SPs e colar o texto).\n")
    elif n_with_def == 0:
        md.append("> ⚠️ **Objetos visíveis mas corpos todos NULL.** Falta `VIEW DEFINITION`. "
                  "**Plano B:** pedir ao Nuno `GRANT VIEW DEFINITION TO nikufra;`.\n")
    elif n_null > 0:
        md.append(f"> 🟡 **Parcial:** {n_with_def}/{n_total} corpos legíveis; {n_null} NULL "
                  "(provavelmente objetos sem permissão específica). Os legíveis chegam para "
                  "começar a análise.\n")
    else:
        md.append(f"> ✅ **Tudo legível** ({n_with_def}/{n_total} corpos). Análise pode prosseguir.\n")

    # ── Keyword index (only meaningful if we have bodies) ──
    if n_with_def > 0:
        hits: dict[str, list[str]] = defaultdict(list)
        for o in objects:
            for kw in keyword_hits(o["definition"]):
                hits[kw].append(f"{o['schema']}.{o['name']}")
        if hits:
            md.append("## Índice por palavra-chave (ajuda à análise)\n")
            md.append("| Palavra-chave | Objetos que a mencionam |")
            md.append("|---|---|")
            for kw in KEYWORDS:
                objs = hits.get(kw, [])
                if objs:
                    shown = ", ".join(f"`{x}`" for x in objs[:12])
                    extra = f" … (+{len(objs) - 12})" if len(objs) > 12 else ""
                    md.append(f"| `{kw}` | {shown}{extra} |")
            md.append("")

    # ── Full catalogue ──
    md.append("## Catálogo completo\n")
    for t in TYPE_ORDER:
        items = by_type.get(t, [])
        if not items:
            continue
        md.append(f"### {TYPE_LABELS.get(t, t)} (`{t}`) — {len(items)}\n")
        for o in items:
            key = (o["schema"], o["name"])
            sig = _sig(o, params.get(key, [])) if t in ("P", "PC", "FN", "TF", "IF") else ""
            kws = keyword_hits(o["definition"])
            kw_str = (" · 🔎 " + ", ".join(f"`{k}`" for k in kws)) if kws else ""
            md.append(f"#### `{o['schema']}.{o['name']}`{sig}")
            md.append(f"*{TYPE_LABELS.get(t, t)} · criado {o['create_date']} · "
                      f"modificado {o['modify_date']}*{kw_str}\n")
            out_cols = columns.get(key, [])
            if out_cols:
                md.append(f"**Devolve:** {_cols_str(out_cols)}\n")
            if o["definition"]:
                md.append("```sql")
                md.append(o["definition"].strip())
                md.append("```\n")
            else:
                md.append("_(definition NULL — sem permissão `VIEW DEFINITION` para este objeto)_\n")
        md.append("")

    return "\n".join(md)


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> int:
    # Windows consoles default to cp1252 → emoji/… in prints crash. Force utf-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pragma: no cover - older streams
        pass

    print("> Connecting to MAR-KAYAKS @ fabrica.nelo.eu:1039 ...", flush=True)
    conn = get_conn()
    cur = conn.cursor()

    perms = permission_probe(cur)
    print(f"> CURRENT_USER={perms.get('current_user')} "
          f"VIEW DEFINITION={perms.get('db_view_definition')} "
          f"db_owner={perms.get('is_db_owner')}", flush=True)

    routines = routines_crosscheck(cur)
    if routines:
        print(f"> INFORMATION_SCHEMA.ROUTINES: {routines}", flush=True)

    print("> Fetching sys.objects + sys.sql_modules ...", flush=True)
    objects = fetch_objects(cur)
    params = fetch_parameters(cur)
    columns = fetch_result_columns(cur)

    n_total = len(objects)
    n_with_def = sum(1 for o in objects if o["has_definition"])
    by_type: dict[str, int] = defaultdict(int)
    for o in objects:
        by_type[o["type"]] += 1
    print(f"> {n_total} programmable objects visible · {n_with_def} with a readable body", flush=True)
    for t in TYPE_ORDER:
        if by_type.get(t):
            print(f"   {TYPE_LABELS.get(t, t):<32} {by_type[t]}", flush=True)

    # Write markdown
    root = Path(__file__).resolve().parent.parent
    md_path = root / "agent_docs" / "mar_kayaks_procedures.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md = render(objects, params, columns, perms, routines)
    md_path.write_text(md, encoding="utf-8")
    print(f"> Wrote {md_path} ({len(md)} chars)", flush=True)

    # Write JSON (for grep / programmatic analysis)
    json_path = root / "_dbprof" / "procedures" / "catalog.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "server": "fabrica.nelo.eu:1039",
        "database": "MAR-KAYAKS",
        "permissions": perms,
        "routines_crosscheck": routines,
        "counts": {TYPE_LABELS.get(t, t): by_type.get(t, 0) for t in TYPE_ORDER if by_type.get(t)},
        "total": n_total,
        "with_definition": n_with_def,
        "objects": [
            {
                **{k: o[k] for k in ("schema", "name", "type", "type_desc",
                                     "create_date", "modify_date", "has_definition")},
                "parameters": params.get((o["schema"], o["name"]), []),
                "result_columns": columns.get((o["schema"], o["name"]), []),
                "keyword_hits": keyword_hits(o["definition"]),
                "definition": o["definition"],
            }
            for o in objects
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"> Wrote {json_path}", flush=True)

    # Honest exit signal for the plano-B decision
    if n_total == 0:
        print("\n⛔ ZERO objetos visíveis — nikufra não vê metadados de SPs. "
              "Pedir ao Nuno: GRANT VIEW DEFINITION TO nikufra;", flush=True)
    elif n_with_def == 0:
        print("\n⚠️ Objetos visíveis mas corpos NULL — falta VIEW DEFINITION. "
              "Pedir ao Nuno: GRANT VIEW DEFINITION TO nikufra;", flush=True)
    else:
        print(f"\n✅ {n_with_def} corpos legíveis — análise pode prosseguir.", flush=True)

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
