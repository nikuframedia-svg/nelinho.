"""Demo package builder — extracts 30-50 representative closed kayak orders
from MAR-KAYAKS, plus their routing/BOM/movements, and writes:

- agent_docs/demo_orders.json  — full nested structure for PP1 import
- agent_docs/demo_orders.csv   — flat one-row-per-order with summary counts

Filters applied:
- OF_DATAFIM IS NOT NULL  (genuinely closed work orders)
- OF_DATA in the last 6 months
- Product TP_ID in {6, 199, 243, 244, 245, 246, 289, 291, 322, 111}
  (kayak types: Canoe Sprint, ONDA, Ocean, Marathon, Fitness Pl./Ep.,
  EvolutionCanoe, Icon, Training)
- Product has at least 1 routing line (PRODUTO_FASE) and 1 BOM line
  (PRODUTO_COMPONENTE), both not soft-deleted
- Up to 5 orders per product, total ~40, ordered by OF_DATA DESC

Run:
    .\\.venv\\Scripts\\python.exe scripts\\build_demo_package.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyodbc

# Connection — reads MAR_KAYAKS_DSN env var (set via .env in dev / systemd in
# prod). Fallback hardcoded for one-shot reproducibility.
_DEFAULT_DSN = (
    "DRIVER={SQL Server};SERVER=fabrica.nelo.eu,1039;"
    "DATABASE=MAR-KAYAKS;UID=nikufra;PWD=arfukin2026;"
    "TrustServerCertificate=yes;Encrypt=no;"
)
CONN_STR = os.environ.get("MAR_KAYAKS_DSN", _DEFAULT_DSN)

KAYAK_TP_IDS = (6, 199, 243, 244, 245, 246, 289, 291, 322, 111)


# ─── JSON encoder for SQL Server types ──────────────────────────────────


def _json_default(o: Any) -> Any:
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, bytes):
        return o.hex()
    raise TypeError(f"Not serializable: {type(o)}")


def _rows_to_dicts(cur: pyodbc.Cursor) -> list[dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# ─── Queries (bodies match vw_pp1_* in agent_docs/views_pp1.sql) ────────


SELECT_ORDERS_SQL = f"""
WITH eligible AS (
    SELECT of_.OF_ID, of_.OF_DATA, of_.OF_DATAFIM, of_.OF_P_ID,
           ROW_NUMBER() OVER (PARTITION BY of_.OF_P_ID ORDER BY of_.OF_DATA DESC) AS rn
    FROM dbo.ORDEMFABRICO of_ WITH (NOLOCK)
    INNER JOIN dbo.PRODUTO p WITH (NOLOCK) ON p.P_ID = of_.OF_P_ID
    WHERE of_.OF_DATAFIM IS NOT NULL
      AND of_.OF_DATA >= DATEADD(month, -6, CAST(GETDATE() AS date))
      AND p.P_TP_ID IN ({",".join(str(x) for x in KAYAK_TP_IDS)})
      AND EXISTS (
        SELECT 1 FROM dbo.PRODUTO_FASE pf WITH (NOLOCK)
        WHERE pf.PRODF_P_ID = of_.OF_P_ID AND pf.PRODF_DATA_ELIMINADO IS NULL
      )
      AND EXISTS (
        SELECT 1 FROM dbo.PRODUTO_COMPONENTE c WITH (NOLOCK)
        WHERE c.COMP_P_ID = of_.OF_P_ID AND c.COMP_ELIMINADO IS NULL
      )
)
SELECT TOP 50
    of_.OF_ID                 AS work_order_id,
    of_.OF_DATA               AS ordered_at,
    of_.OF_DATATRANSPORTE     AS transport_date,
    of_.OF_DATAENTREGA        AS delivery_date,
    of_.OF_DATAINICIO         AS start_date,
    of_.OF_DATAFIM            AS end_date,
    of_.OF_NOME               AS customer_name,
    of_.OF_REFERENCIA         AS reference,
    of_.OF_PRECOCUSTO         AS cost_price,
    of_.OF_PRECOVENDA         AS sale_price,
    of_.OF_DESCONTO           AS discount,
    of_.OF_VALORPAGO          AS paid_amount,
    of_.OF_COEFICIENTE        AS coefficient_eur,
    of_.OF_PAGO               AS is_paid,
    of_.OF_SUPERVISAO         AS supervised,
    of_.OF_SEQUENCIA          AS sequence,
    of_.OF_P_ID               AS product_id,
    p.P_NOME                  AS product_name,
    p.P_NOME_EN               AS product_name_en,
    p.P_TP_ID                 AS product_type_id,
    pt.TP_NOME                AS product_type_name,
    of_.OF_FP_ID              AS current_phase_id,
    of_.OF_ARM_ID             AS warehouse_id,
    of_.OF_ENC_ID             AS encomenda_id,
    est.EE_NOME               AS encomenda_state,
    cust.E_NOME               AS customer_full_name,
    cust.E_PAIS               AS customer_country
FROM eligible e
INNER JOIN dbo.ORDEMFABRICO    of_  WITH (NOLOCK) ON of_.OF_ID  = e.OF_ID
INNER JOIN dbo.PRODUTO         p    WITH (NOLOCK) ON p.P_ID    = of_.OF_P_ID
INNER JOIN dbo.PRODUTO_TIPO    pt   WITH (NOLOCK) ON pt.TP_ID  = p.P_TP_ID
LEFT JOIN  dbo.ENCOMENDA       enc  WITH (NOLOCK) ON enc.ENC_ID = of_.OF_ENC_ID
LEFT JOIN  dbo.ENCOMENDA_ESTADO est WITH (NOLOCK) ON est.EE_ID  = enc.ENC_EE_ID
LEFT JOIN  dbo.ENTIDADE        cust WITH (NOLOCK) ON cust.E_ID  = of_.OF_E_ID
WHERE e.rn <= 5
ORDER BY of_.OF_DATA DESC
"""

ROUTING_SQL = """
SELECT
    pf.PRODF_ID               AS routing_id,
    pf.PRODF_P_ID             AS product_id,
    pf.PRODF_FP_ID            AS phase_id,
    fp.FP_NOME                AS phase_name,
    pf.PRODF_DESCRICAO        AS routing_description,
    pf.PRODF_SEQUENCIA        AS sequence,
    pf.PRODF_TEMPO            AS time_hours,
    fp.FP_HORA_COEF           AS phase_hour_coefficient,
    fp.FP_VALOR_REF_K1        AS k1_reference_hours,
    fp.FP_VALOR_REF_K2        AS k2_reference_hours,
    fp.FP_VALOR_REF_K4        AS k4_reference_hours,
    fp.FP_PRODUCAO            AS phase_is_production,
    fp.FP_AUTOMATICA          AS phase_is_automatic,
    pf.PRODF_FABRICO          AS routing_in_production,
    pf.PRODF_COEFICIENTE      AS routing_coefficient,
    pf.PRODF_COEFICIENTE_X    AS routing_coefficient_x
FROM dbo.PRODUTO_FASE   pf  WITH (NOLOCK)
INNER JOIN dbo.FASES_PRODUCAO fp WITH (NOLOCK) ON fp.FP_ID = pf.PRODF_FP_ID
WHERE pf.PRODF_P_ID = ? AND pf.PRODF_DATA_ELIMINADO IS NULL
ORDER BY pf.PRODF_SEQUENCIA
"""

BOM_SQL = """
SELECT
    c.COMP_ID                AS bom_id,
    c.COMP_P_ID              AS parent_product_id,
    c.COMP_P_P_ID            AS component_product_id,
    cp.P_NOME                AS component_product_name,
    cp.P_NOME_EN             AS component_product_name_en,
    cp.P_STOCK               AS component_stock,
    cp.P_STOCKMIN            AS component_stock_min,
    cp.P_PRECOCUSTO          AS component_cost_price,
    c.COMP_QUANTIDADE        AS quantity,
    c.COMP_TPCOMP_ID         AS component_type_id,
    c.COMP_FP_ID             AS consumption_phase_id,
    c.COMP_FASE_FINAL        AS is_final_phase,
    c.COMP_OBS               AS observations
FROM dbo.PRODUTO_COMPONENTE c WITH (NOLOCK)
INNER JOIN dbo.PRODUTO cp WITH (NOLOCK) ON cp.P_ID = c.COMP_P_P_ID
WHERE c.COMP_P_ID = ? AND c.COMP_ELIMINADO IS NULL
ORDER BY c.COMP_FP_ID, c.COMP_P_P_ID
"""

MOVEMENTS_SQL = """
SELECT
    m.MOV_ID                 AS movement_id,
    m.MOV_DATA               AS moved_at,
    m.MOV_QUANTIDADE         AS quantity,
    m.MOV_PRECOUNITARIO      AS unit_price,
    m.MOV_TPMOV_ID           AS movement_type_id,
    m.MOV_P_ID               AS product_id,
    m.MOV_FP_ID              AS phase_id,
    m.MOV_OFFP_ID            AS work_order_phase_id,
    m.MOV_ARM_ID             AS warehouse_id,
    m.MOV_DEFEITUOSO         AS is_defective,
    m.MOV_OBSERVACOES        AS observations
FROM dbo.MOVIMENTO m WITH (NOLOCK)
WHERE m.MOV_OF_ID = ?
ORDER BY m.MOV_DATA
"""


def main() -> int:
    print("Connecting to MAR-KAYAKS …", flush=True)
    conn = pyodbc.connect(CONN_STR, timeout=20)
    cur = conn.cursor()

    print("Selecting eligible kayak orders (closed, last 6m, has routing+BOM) …", flush=True)
    cur.execute(SELECT_ORDERS_SQL)
    orders = _rows_to_dicts(cur)
    print(f"  → {len(orders)} orders", flush=True)
    if not orders:
        print("No orders matched filters. Aborting.", flush=True)
        return 1

    # Enrich each with routing + bom + movements
    out: list[dict[str, Any]] = []
    for i, order in enumerate(orders, start=1):
        pid = order["product_id"]
        wo_id = order["work_order_id"]

        cur.execute(ROUTING_SQL, pid)
        routing = _rows_to_dicts(cur)
        cur.execute(BOM_SQL, pid)
        bom = _rows_to_dicts(cur)
        cur.execute(MOVEMENTS_SQL, wo_id)
        movements = _rows_to_dicts(cur)

        out.append(
            {
                "order": order,
                "routing": routing,
                "bom": bom,
                "movements": movements,
                "counts": {
                    "routing_steps": len(routing),
                    "bom_lines": len(bom),
                    "movements": len(movements),
                },
            }
        )
        print(
            f"  [{i:>2}/{len(orders)}] WO {wo_id:>10}  "
            f"product={order['product_name']:<40.40}  "
            f"route={len(routing):>3}  bom={len(bom):>3}  mov={len(movements):>4}",
            flush=True,
        )

    # Output paths
    root = Path(__file__).resolve().parent.parent / "agent_docs"
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "demo_orders.json"
    csv_path = root / "demo_orders.csv"

    # JSON
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "fabrica.nelo.eu:1039 / MAR-KAYAKS",
        "filters": {
            "of_datafim_is_not_null": True,
            "of_data_window_months": 6,
            "kayak_tp_ids": list(KAYAK_TP_IDS),
            "requires_routing_and_bom": True,
            "max_per_product": 5,
        },
        "order_count": len(out),
        "orders": out,
    }
    json_path.write_text(
        json.dumps(payload, default=_json_default, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {json_path}  ({json_path.stat().st_size:,} bytes)".replace(",", " "))

    # CSV — one row per order with summary counts (BOM/routing/movements
    # aggregated). For flat import into PP1 staging, the order header is what
    # matters; sub-records live in the JSON.
    csv_cols = [
        "work_order_id",
        "ordered_at",
        "end_date",
        "delivery_date",
        "transport_date",
        "customer_name",
        "customer_country",
        "reference",
        "product_id",
        "product_name",
        "product_name_en",
        "product_type_id",
        "product_type_name",
        "current_phase_id",
        "warehouse_id",
        "sequence",
        "cost_price",
        "sale_price",
        "discount",
        "paid_amount",
        "coefficient_eur",
        "is_paid",
        "supervised",
        "encomenda_id",
        "encomenda_state",
        "routing_steps",
        "bom_lines",
        "movements",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_cols)
        writer.writeheader()
        for record in out:
            o = record["order"]
            row: dict[str, Any] = {k: o.get(k) for k in csv_cols if k in o}
            row["routing_steps"] = record["counts"]["routing_steps"]
            row["bom_lines"] = record["counts"]["bom_lines"]
            row["movements"] = record["counts"]["movements"]
            # Serialize dates / decimals to strings
            for k, v in list(row.items()):
                if isinstance(v, (datetime, date)):
                    row[k] = v.isoformat()
                elif isinstance(v, Decimal):
                    row[k] = float(v)
            writer.writerow(row)
    print(f"Wrote {csv_path}  ({csv_path.stat().st_size:,} bytes)".replace(",", " "))

    # Summary
    print()
    print("=== Demo package summary ===")
    print(f"  Orders:           {len(out)}")
    print(f"  Distinct products: {len({r['order']['product_id'] for r in out})}")
    print(f"  Total movements:   {sum(r['counts']['movements'] for r in out)}")
    print(f"  Total BOM lines:   {sum(r['counts']['bom_lines'] for r in out)}")
    print(f"  Total routing:     {sum(r['counts']['routing_steps'] for r in out)}")
    types_seen = {(r["order"]["product_type_id"], r["order"]["product_type_name"]) for r in out}
    print(f"  Product types:     {len(types_seen)}")
    for tid, tname in sorted(types_seen):
        n = sum(1 for r in out if r["order"]["product_type_id"] == tid)
        print(f"     {tid:>4}  {tname:<30}  {n} orders")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
