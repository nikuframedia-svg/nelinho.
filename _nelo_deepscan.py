"""
Deep-scan READ-ONLY ao SQL Server MAR-KAYAKS (ERP vivo da NELO).

- Utilizador `nikufra` e DataReader -> NUNCA escreve. Apenas SELECT / catalog views.
- A password vem da env var NELO_DB_PWD (nunca em ficheiro / nunca em git).
- Produz nelo_deepscan_2.md (relatorio completo) + sumario no stdout.

Uso:
    $env:NELO_DB_PWD = "..."; .\.venv\Scripts\python.exe _nelo_deepscan.py
"""
import os
import sys
import datetime
import pyodbc

PWD = os.environ.get("NELO_DB_PWD")
if not PWD:
    sys.exit("ERRO: define a env var NELO_DB_PWD primeiro.")

CONN = (
    "DRIVER={SQL Server};"
    "SERVER=fabrica.nelo.eu,1039;"
    "DATABASE=MAR-KAYAKS;"
    "UID=nikufra;"
    f"PWD={PWD};"
    "TrustServerCertificate=yes;Encrypt=no"
)

OUT = open("nelo_deepscan_2.md", "w", encoding="utf-8")


def w(line=""):
    OUT.write(line + "\n")


def log(msg):
    print(msg, flush=True)


def cell(v):
    """Render um valor de celula de forma segura e curta."""
    if v is None:
        return "NULL"
    if isinstance(v, (bytes, bytearray)):
        return f"<bin {len(v)}b>"
    s = str(v).replace("\n", " ").replace("\r", " ").replace("|", "/")
    return s[:80]


log("A ligar ao SQL Server MAR-KAYAKS ...")
cn = pyodbc.connect(CONN, timeout=30)
cn.timeout = 120
cur = cn.cursor()
log("Ligado. A vasculhar...")

w(f"# NELO MAR-KAYAKS — deep-scan completo")
w(f"_Gerado {datetime.datetime.now():%Y-%m-%d %H:%M} — read-only, user nikufra (DataReader)._")
w()

# ---------------------------------------------------------------- versao / info
try:
    cur.execute("SELECT @@VERSION")
    ver = cur.fetchone()[0].splitlines()[0]
    cur.execute("SELECT DB_NAME(), SUSER_SNAME(), GETDATE()")
    dbn, usr, now = cur.fetchone()
    w("## 0. Servidor")
    w(f"- Versao: `{ver}`")
    w(f"- DB: `{dbn}` | login: `{usr}` | hora servidor: `{now}`")
    w()
except Exception as e:
    w(f"_(info servidor falhou: {e})_")

# ---------------------------------------------------------------- inventario
log("[1/7] Inventario de tabelas + contagens...")
cur.execute("""
    SELECT s.name AS sch, t.name AS tbl, SUM(p.rows) AS nrows,
           t.create_date, t.modify_date
    FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1)
    GROUP BY s.name, t.name, t.create_date, t.modify_date
    ORDER BY SUM(p.rows) DESC
""")
tables = cur.fetchall()  # (sch, tbl, nrows, create, modify)
total_rows = sum((r[2] or 0) for r in tables)

cur.execute("""
    SELECT TABLE_SCHEMA, TABLE_NAME
    FROM INFORMATION_SCHEMA.VIEWS
    ORDER BY TABLE_NAME
""")
views = cur.fetchall()

w("## 1. Inventario")
w(f"- **{len(tables)} tabelas**, **{len(views)} views**, **~{total_rows:,} linhas** (tabelas).")
w()
w("### 1.1 Tabelas (ordenado por nr. de linhas)")
w()
w("| # | schema.tabela | linhas | criada | modificada (schema) |")
w("|---|---|--:|---|---|")
for i, (sch, tbl, nrows, cre, mod) in enumerate(tables, 1):
    w(f"| {i} | {sch}.{tbl} | {(nrows or 0):,} | {cre:%Y-%m-%d} | {mod:%Y-%m-%d} |")
w()

# ---------------------------------------------------------------- views + count
log("[2/7] Views + contagens (COUNT pode demorar)...")
w("### 1.2 Views")
w()
w("| # | schema.view | linhas |")
w("|---|---|--:|")
view_counts = {}
for i, (vsch, vname) in enumerate(views, 1):
    try:
        cur.execute(f"SELECT COUNT(*) FROM [{vsch}].[{vname}]")
        c = cur.fetchone()[0]
    except Exception as e:
        c = f"ERRO: {str(e)[:60]}"
    view_counts[vname] = c
    w(f"| {i} | {vsch}.{vname} | {c if isinstance(c,int) else c:,}" if isinstance(c, int)
      else f"| {i} | {vsch}.{vname} | {c} |")
    if isinstance(c, int):
        OUT.seek(OUT.tell())
w()

# ---------------------------------------------------------------- colunas
log("[3/7] Colunas de todas as tabelas/views...")
cur.execute("""
    SELECT TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION, COLUMN_NAME,
           DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE, COLUMN_DEFAULT
    FROM INFORMATION_SCHEMA.COLUMNS
    ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
""")
cols_rows = cur.fetchall()
cols_by_tbl = {}
for sch, tbl, pos, cname, dtype, clen, nullable, cdef in cols_rows:
    cols_by_tbl.setdefault((sch, tbl), []).append(
        (cname, dtype, clen, nullable, cdef))

w("## 2. Colunas (todas as tabelas e views)")
w()
for (sch, tbl), cl in sorted(cols_by_tbl.items()):
    w(f"### {sch}.{tbl}  ({len(cl)} colunas)")
    w("| col | tipo | len | null | default |")
    w("|---|---|--:|:--:|---|")
    for cname, dtype, clen, nullable, cdef in cl:
        w(f"| {cname} | {dtype} | {clen if clen is not None else ''} "
          f"| {'Y' if nullable=='YES' else 'N'} | {cell(cdef)} |")
    w()

# ---------------------------------------------------------------- PK / FK
log("[4/7] Chaves primarias e estrangeiras...")
w("## 3. Relacoes (chaves estrangeiras)")
w()
try:
    cur.execute("""
        SELECT
            fk.name AS fk_name,
            sch.name + '.' + tp.name AS parent_tbl,
            cp.name AS parent_col,
            rsch.name + '.' + tr.name AS ref_tbl,
            cr.name AS ref_col
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
        JOIN sys.tables tp ON tp.object_id = fk.parent_object_id
        JOIN sys.schemas sch ON sch.schema_id = tp.schema_id
        JOIN sys.columns cp ON cp.object_id = tp.object_id AND cp.column_id = fkc.parent_column_id
        JOIN sys.tables tr ON tr.object_id = fk.referenced_object_id
        JOIN sys.schemas rsch ON rsch.schema_id = tr.schema_id
        JOIN sys.columns cr ON cr.object_id = tr.object_id AND cr.column_id = fkc.referenced_column_id
        ORDER BY parent_tbl, fk_name
    """)
    fks = cur.fetchall()
    if fks:
        w("| FK | tabela.coluna | -> | referencia |")
        w("|---|---|:--:|---|")
        for fk_name, ptbl, pcol, rtbl, rcol in fks:
            w(f"| {fk_name} | {ptbl}.{pcol} | -> | {rtbl}.{rcol} |")
    else:
        w("_Nenhuma foreign key declarada (ERP PHC raramente declara FKs)._")
    w()
except Exception as e:
    w(f"_(FK scan falhou: {e})_")
    w()

# ---------------------------------------------------------------- indices
log("[5/7] Indices...")
w("## 4. Indices")
w()
try:
    cur.execute("""
        SELECT s.name + '.' + t.name AS tbl, i.name AS idx, i.type_desc,
               i.is_primary_key, i.is_unique,
               STUFF((SELECT ', ' + c.name
                      FROM sys.index_columns ic
                      JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
                      WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id
                      ORDER BY ic.key_ordinal
                      FOR XML PATH('')), 1, 2, '') AS cols
        FROM sys.indexes i
        JOIN sys.tables t ON t.object_id = i.object_id
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        WHERE i.type > 0
        ORDER BY tbl, i.is_primary_key DESC, idx
    """)
    idxs = cur.fetchall()
    w("| tabela | indice | tipo | PK | unico | colunas |")
    w("|---|---|---|:--:|:--:|---|")
    for tbl, idx, tdesc, ispk, isuniq, icols in idxs:
        w(f"| {tbl} | {idx} | {tdesc} | {'Y' if ispk else ''} "
          f"| {'Y' if isuniq else ''} | {icols} |")
    w()
except Exception as e:
    w(f"_(indices falharam: {e})_")
    w()

# ---------------------------------------------------------------- liveness
log("[6/7] Liveness — MAX de colunas de data (deteta tabelas vivas)...")
w("## 5. Liveness — ultima escrita por tabela")
w()
w("_MAX() da 'melhor' coluna de data de cada tabela. Mostra o que ainda esta vivo._")
w()
date_types = {"datetime", "datetime2", "smalldatetime", "date"}
liveness = []
for (sch, tbl, nrows, cre, mod) in tables:
    if not nrows:
        continue
    dcols = [c[0] for c in cols_by_tbl.get((sch, tbl), []) if c[1] in date_types]
    if not dcols:
        continue
    best = None  # (coluna, valor_str) — str para sort estavel (driver antigo
                 # devolve date/datetime2 como texto e datetime como objecto)
    for dc in dcols:
        try:
            cur.execute(f"SELECT MAX([{dc}]) FROM [{sch}].[{tbl}]")
            mx = cur.fetchone()[0]
            if mx is None:
                continue
            mxs = str(mx)
            if best is None or mxs > best[1]:
                best = (dc, mxs)
        except Exception:
            pass
    if best:
        liveness.append((sch, tbl, nrows, best[0], best[1]))
liveness.sort(key=lambda r: r[4], reverse=True)
w("| schema.tabela | linhas | coluna de data | ultimo valor |")
w("|---|--:|---|---|")
for sch, tbl, nrows, dc, mx in liveness:
    w(f"| {sch}.{tbl} | {nrows:,} | {dc} | {mx} |")
w()

# ---------------------------------------------------------------- profiling + samples
log("[7/7] Profiling + amostras das tabelas de alto valor...")
# tabelas/views de interesse explicito + as 30 maiores tabelas
HIGH_VALUE = [
    "ENTIDADE_PHC_FACT", "IOT_SENSOR_DATA", "TH", "ORDEMFABRICO",
    "FaseOf", "produto_stocks_por_armazem", "vTrackingTransporte",
    "vOF_Transporte", "FuncionariosActivos", "OF_PRODUTOS_V2",
    "RetornosFuncionario", "OF_ESTADOS", "ENTIDADE", "PRODUTO",
]
top30 = [(s, t) for (s, t, n, c, m) in tables[:30]]
seen = set()
profile_targets = []
for name in HIGH_VALUE:
    for (s, t, n, c, m) in tables:
        if t == name and (s, t) not in seen:
            profile_targets.append((s, t, n)); seen.add((s, t))
    for (vs, vn) in views:
        if vn == name and ("V:" + vn) not in seen:
            profile_targets.append((vs, vn, None)); seen.add("V:" + vn)
for (s, t) in top30:
    if (s, t) not in seen:
        n = next((r[2] for r in tables if r[0] == s and r[1] == t), None)
        profile_targets.append((s, t, n)); seen.add((s, t))

w("## 6. Profiling + amostras (tabelas de alto valor + 30 maiores)")
w()
for sch, tbl, nrows in profile_targets:
    w(f"### {sch}.{tbl}")
    is_view = ("V:" + tbl) in seen and nrows is None
    cl = cols_by_tbl.get((sch, tbl), [])
    # null % por coluna (limitado a tabelas; views tambem servem)
    try:
        if cl:
            parts = []
            for cname, dtype, *_ in cl:
                parts.append(f"SUM(CASE WHEN [{cname}] IS NULL THEN 1 ELSE 0 END) AS n_{len(parts)}")
            q = f"SELECT COUNT(*), {', '.join(parts)} FROM [{sch}].[{tbl}]"
            cur.execute(q)
            row = cur.fetchone()
            cnt = row[0] or 0
            w(f"- linhas: **{cnt:,}**")
            if cnt:
                w("- nulos por coluna (so colunas com >0% nulo):")
                nullbits = []
                for j, (cname, dtype, *_ ) in enumerate(cl):
                    nn = row[1 + j] or 0
                    if nn:
                        nullbits.append(f"{cname} {100*nn/cnt:.0f}%")
                w("  - " + (", ".join(nullbits) if nullbits else "_(nenhuma)_"))
    except Exception as e:
        w(f"- _(profiling falhou: {str(e)[:80]})_")
    # amostra TOP 3
    try:
        cur.execute(f"SELECT TOP 3 * FROM [{sch}].[{tbl}]")
        scols = [d[0] for d in cur.description]
        srows = cur.fetchall()
        w()
        w("| " + " | ".join(scols) + " |")
        w("|" + "|".join(["---"] * len(scols)) + "|")
        for r in srows:
            w("| " + " | ".join(cell(v) for v in r) + " |")
    except Exception as e:
        w(f"- _(amostra falhou: {str(e)[:80]})_")
    w()

OUT.close()
cur.close()
cn.close()

# ----------------------------------------------------------------- sumario
log("")
log("=== SUMARIO ===")
log(f"Tabelas: {len(tables)}  Views: {len(views)}  Linhas (tabelas): ~{total_rows:,}")
log("")
log("TOP 15 tabelas por linhas:")
for (s, t, n, c, m) in tables[:15]:
    log(f"  {(n or 0):>14,}  {s}.{t}")
log("")
log("TOP 12 tabelas mais recentemente escritas (liveness):")
for s, t, n, dc, mx in liveness[:12]:
    log(f"  {mx}  {s}.{t}  ({dc})")
log("")
log("Relatorio completo -> nelo_deepscan_2.md")
