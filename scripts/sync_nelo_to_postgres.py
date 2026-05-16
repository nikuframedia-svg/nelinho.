"""Q.20 — Nelo ERP → Postgres sync (CLI entrypoint).

Reads the ``vw_pp1_*`` views from the NELO ERP and mirrors them into the
operational Postgres schemas. Idempotent: re-running never duplicates.

Each domain is a "mirror" added incrementally:
    Q.20.B  master   — products, employees, BOM, routing templates
    Q.20.C  molds    — plan.mold (via the factory_data_product Excel layer)
    Q.20.D  skills   — hr.skills + hr.employee_skills
    Q.20.E  quality  — quality.error_catalog + quality.rework_entry
    Q.20.F  time_mining — routing_template_phase p50/p90 (historical mining)

Usage::

    python scripts/sync_nelo_to_postgres.py                 # all mirrors
    python scripts/sync_nelo_to_postgres.py --only master   # one mirror
    python scripts/sync_nelo_to_postgres.py --only quality --since 2025-01-01

Requires ``settings.sqlserver_enabled=true`` and ``sqlserver_url`` set —
otherwise the sync logs a skip and exits 0.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("sync_nelo_to_postgres")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nelo ERP → Postgres sync")
    parser.add_argument(
        "--only",
        action="append",
        metavar="MIRROR",
        help="run only this mirror (repeatable): master|molds|skills|quality|time_mining",
    )
    parser.add_argument(
        "--since",
        type=lambda s: date.fromisoformat(s),
        default=None,
        help="watermark (YYYY-MM-DD) for incremental mirrors (quality, times)",
    )
    return parser.parse_args(argv)


async def _run(only: list[str] | None, since: date | None) -> int:
    from src.infrastructure.erp.etl.sync import run_nelo_sync

    results = await run_nelo_sync(only=only, since=since)
    if not results:
        log.info("sync produced no mirror results (disabled or no mirrors)")
        return 0

    errors = 0
    for r in results:
        log.info(
            "  %-12s %-6s read=%d ins=%d upd=%d skip=%d%s",
            r.source, r.status, r.rows_read, r.rows_inserted,
            r.rows_updated, r.rows_skipped,
            f" error={r.error}" if r.error else "",
        )
        if r.status != "ok":
            errors += 1
    log.info("sync done — %d mirror(s), %d error(s)", len(results), errors)
    return 1 if errors else 0


def main() -> None:
    args = _parse_args(sys.argv[1:])
    exit_code = asyncio.run(_run(args.only, args.since))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
