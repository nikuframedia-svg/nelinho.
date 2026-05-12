"""Health-check for the NELO MAR-KAYAKS adapter.

Runs `src.adapters.nelo.services.health_check()` and prints a human-readable
report to stdout. Exit code 0 on success, 1 on connection / query failure.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\health_check_nelo.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime

from src.adapters.nelo.services import close_engine, health_check


def _h(title: str) -> None:
    print()
    print(f"=== {title} " + "=" * max(0, 60 - len(title)))


async def main() -> int:
    started = time.perf_counter()
    print(f"NELO MAR-KAYAKS adapter health-check · {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("Source: fabrica.nelo.eu:1039 / MAR-KAYAKS (read-only via nikufra)")

    rc = 0
    try:
        snap = await health_check()

        elapsed = time.perf_counter() - started

        _h("Open work orders")
        print(f"  Total open (OF_DATAFIM IS NULL): {snap.open_orders_count:,}".replace(",", " "))

        _h("Top 5 products by total work-order count")
        print(f"  {'Product ID':>10}  {'Orders':>10}  Name")
        for p in snap.top_products:
            name_en = f"  [{p.product_name_en}]" if p.product_name_en else ""
            print(
                f"  {p.product_id:>10}  {p.order_count:>10,}  "
                f"{p.product_name}{name_en}".replace(",", " ")
            )

        _h("Current schedule (PLANEAMENTO_DIARIO - last 10 rows)")
        if not snap.current_schedule:
            print("  (no rows)")
        else:
            print(f"  {'ID':>5}  {'Day':<11}  {'Start':>5}  {'End':>5}  {'HC':>3}  {'Hrs':>4}  Transport")
            for s in snap.current_schedule:
                print(
                    f"  {s.schedule_id:>5}  {s.day.isoformat():<11}  "
                    f"{s.start_hour:>5}  {s.end_hour:>5}  "
                    f"{s.headcount:>3}  {s.shift_hours:>4}  "
                    f"{s.transport_id if s.transport_id is not None else '-'}"
                )

        _h("Stock movements (last 30 days)")
        print(f"  Count: {snap.movements_last_30d:,}".replace(",", " "))

        print()
        print(f"[OK] Health-check passed ({elapsed:.2f}s elapsed)")
    except Exception as exc:  # noqa: BLE001 — top-level reporter
        print(f"\n[FAIL] Health-check FAILED: {type(exc).__name__}: {exc}")
        rc = 1
    finally:
        await close_engine()
    return rc


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
