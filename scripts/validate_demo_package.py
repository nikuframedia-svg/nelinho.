"""Q.24.0 — validate the NELO demo package mapping.

The research (`agent_docs/nelo_executive_summary.md` §5) ends with "validate
the demo package" as the concrete next step. This script opens
`agent_docs/demo_orders.json` (50 real closed work orders extracted from
MAR-KAYAKS) and checks it against the read-only adapter's Pydantic contract
(`src.adapters.nelo.schemas`) before Q.24.A builds the ingestion path.

It reports three things:

* **Structural** — every order carries `order` / `routing` / `bom` /
  `movements`, with the rows the filters promise (routing + bom non-empty).
  A structural failure exits 1 — the package is unusable.
* **Schema gaps** — required schema fields the demo package omits. The
  builder selected a trimmed column set, so a few `vw_pp1_*` columns are
  absent. These are NOT failures: they are the exact list `demo_source.py`
  must fill with defaults. Reported as a checklist, exit stays 0.
* **Hard data errors** — wrong types on fields that ARE present. These exit 1.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\validate_demo_package.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from src.adapters.nelo.schemas import BomRow, MovementRow, OrderRow, RoutingRow

_PACKAGE = Path(__file__).resolve().parent.parent / "agent_docs" / "demo_orders.json"

# Each nested section → (schema, "list" or "dict", non-empty expected).
_SECTIONS: list[tuple[str, type[BaseModel], bool]] = [
    ("order", OrderRow, True),
    ("routing", RoutingRow, True),
    ("bom", BomRow, True),
    ("movements", MovementRow, False),
]


def _h(title: str) -> None:
    print()
    print(f"=== {title} " + "=" * max(0, 60 - len(title)))


def _required_fields(schema: type[BaseModel]) -> set[str]:
    """Schema fields with no default — must be present in the source row."""
    return {
        name for name, field in schema.model_fields.items() if field.is_required()
    }


def _rows_of(section: str, payload: Any) -> list[dict[str, Any]]:
    """A section is either a single dict (`order`) or a list of dicts."""
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    return []


def main() -> int:
    print(f"NELO demo package validation · {_PACKAGE}")
    if not _PACKAGE.exists():
        print(f"[FAIL] package not found: {_PACKAGE}")
        return 1

    doc = json.loads(_PACKAGE.read_text(encoding="utf-8"))

    structural_errors: list[str] = []
    hard_errors: list[str] = []
    # section -> required field -> count of rows missing it
    gaps: dict[str, dict[str, int]] = {s: {} for s, _, _ in _SECTIONS}
    row_counts: dict[str, int] = {s: 0 for s, _, _ in _SECTIONS}

    _h("Top-level structure")
    for key in ("generated_at", "source", "order_count", "orders"):
        if key not in doc:
            structural_errors.append(f"top-level key missing: {key}")
    orders = doc.get("orders", [])
    print(f"  generated_at : {doc.get('generated_at')}")
    print(f"  source       : {doc.get('source')}")
    print(f"  order_count  : {doc.get('order_count')}  (orders array: {len(orders)})")
    if doc.get("order_count") != len(orders):
        structural_errors.append(
            f"order_count ({doc.get('order_count')}) != len(orders) ({len(orders)})"
        )

    for idx, order in enumerate(orders):
        tag = f"order[{idx}]"
        if not isinstance(order, dict):
            structural_errors.append(f"{tag}: not an object")
            continue
        for section, schema, want_rows in _SECTIONS:
            if section not in order:
                structural_errors.append(f"{tag}: section '{section}' missing")
                continue
            rows = _rows_of(section, order[section])
            row_counts[section] += len(rows)
            if want_rows and not rows:
                structural_errors.append(f"{tag}: section '{section}' is empty")
            required = _required_fields(schema)
            for row in rows:
                present = set(row)
                for field in required - present:
                    gaps[section][field] = gaps[section].get(field, 0) + 1
                try:
                    schema.model_validate({**{f: None for f in required - present}, **row})
                except ValidationError as exc:
                    # Distinguish "missing" (a known gap) from "wrong type on a
                    # present field" (a hard error the demo_source can't paper over).
                    for err in exc.errors():
                        loc = err.get("loc", ("?",))[0]
                        if str(loc) in present:
                            hard_errors.append(f"{tag}.{section}.{loc}: {err.get('msg')}")

    _h("Section row counts (across 50 orders)")
    for section, _, _ in _SECTIONS:
        print(f"  {section:<11}: {row_counts[section]:>6} rows")

    _h("Schema gaps — required fields the demo package omits")
    print("  (demo_source.py must fill these with documented defaults)")
    any_gap = False
    for section, _, _ in _SECTIONS:
        if gaps[section]:
            any_gap = True
            for field, count in sorted(gaps[section].items()):
                print(f"  - {section}.{field}  (absent in {count} rows)")
    if not any_gap:
        print("  (none — package carries every required column)")

    _h("Result")
    if structural_errors:
        print(f"  structural errors: {len(structural_errors)}")
        for e in structural_errors[:20]:
            print(f"  [FAIL] {e}")
    if hard_errors:
        print(f"  hard data errors: {len(hard_errors)}")
        for e in hard_errors[:20]:
            print(f"  [FAIL] {e}")

    if structural_errors or hard_errors:
        print("\n[FAIL] demo package is NOT ready for ingestion")
        return 1
    print("\n[OK] demo package structurally valid — Q.24.A can build the ingest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
