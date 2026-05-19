"""Q.20.G — ERP→Postgres sync CLI.

Runs the registered ETL mirrors (``master``, ``molds``, ``skills``,
``quality``, ``time_mining``, ``stock``) via
:func:`src.adapters.nelo.etl.sync.run_nelo_sync`.
Each mirror writes a ``core.etl_run`` audit row; this CLI prints a
human-readable summary and exits 0 when every mirror succeeded, 1 if any
mirror reported an error.

Prerequisites:
  * ``SQLSERVER_ENABLED=true`` + ``SQLSERVER_URL`` in ``.env`` (the read-only
    NELO MAR-KAYAKS connection);
  * the ProdPlan ONE Postgres reachable (``bootstrap_dev_full.py`` has run).

Usage::

    .\\.venv\\Scripts\\python.exe scripts\\sync_nelo_erp.py
    .\\.venv\\Scripts\\python.exe scripts\\sync_nelo_erp.py --only master skills
    .\\.venv\\Scripts\\python.exe scripts\\sync_nelo_erp.py --exclude time_mining
    .\\.venv\\Scripts\\python.exe scripts\\sync_nelo_erp.py --only quality --since 2026-01-01

The nightly job should run ``--exclude time_mining`` (the heavy historical
mining mirror runs on its own, less frequent, cadence).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime

from src.adapters.nelo.etl.sync import run_nelo_sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sync_nelo_erp",
        description="Sync NELO MAR-KAYAKS ERP -> ProdPlan ONE Postgres.",
    )
    parser.add_argument(
        "--only", nargs="+", metavar="MIRROR",
        help="Run only these mirrors (default: all registered).",
    )
    parser.add_argument(
        "--exclude", nargs="+", metavar="MIRROR",
        help="Skip these mirrors (e.g. the heavy 'time_mining').",
    )
    parser.add_argument(
        "--since", metavar="YYYY-MM-DD",
        help="Watermark for incremental mirrors (quality, time_mining).",
    )
    return parser.parse_args(argv)


async def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    since: date | None = None
    if args.since:
        try:
            since = datetime.strptime(args.since, "%Y-%m-%d").date()
        except ValueError:
            print(f"[FAIL] --since must be YYYY-MM-DD, got: {args.since}")
            return 1

    print(f"NELO ERP-to-Postgres sync at {datetime.now():%Y-%m-%d %H:%M:%S}")
    try:
        results = await run_nelo_sync(only=args.only, exclude=args.exclude, since=since)
    except Exception as exc:  # noqa: BLE001 — top-level reporter
        print(f"[FAIL] sync aborted: {type(exc).__name__}: {exc}")
        return 1

    if not results:
        print(
            "[SKIP] No mirrors ran. Either SQLSERVER_ENABLED is False, "
            "or no mirror matched the selection."
        )
        return 0

    print()
    print(f"  {'Mirror':<14}  {'Status':<8}  {'Read':>8}  {'Ins':>7}  {'Upd':>7}  {'Skip':>7}")
    print("  " + "-" * 62)
    failed = 0
    for r in results:
        if r.status != "ok":
            failed += 1
        print(
            f"  {r.source:<14}  {r.status:<8}  {r.rows_read:>8}  "
            f"{r.rows_inserted:>7}  {r.rows_updated:>7}  {r.rows_skipped:>7}"
        )
        if r.error:
            print(f"      error: {r.error}")

    print()
    if failed:
        print(f"[FAIL] {failed} of {len(results)} mirror(s) failed.")
        return 1
    print(f"[OK] {len(results)} mirror(s) completed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
