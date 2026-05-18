"""Q.36.D — popular `factory_curated.*` a partir do ERP MAR-KAYAKS.

CLI fino que corre, em série:

1. o mirror de qualidade ERP→Postgres (``OF_CHECKLIST`` →
   ``quality.rework_entry`` + ``error_catalog``);
2. o ``curated_loader`` (``OF_FP`` / ``OF_CHECKLIST`` / ``OFFP_EQ`` →
   ``factory_curated.{order_phase,quality_event,allocation}``).

Depois disto os 3 detectores causais (``erro_tree``, ``reichenbach``,
``mill_diff``) deixam de correr contra tabelas vazias.

Pré-requisitos:
  * ``SQLSERVER_ENABLED=true`` + ``SQLSERVER_URL`` no ``.env`` (a ligação
    read-only ao ERP);
  * o Postgres do ProdPlan ONE acessível (``bootstrap_dev_full.py`` correu);
  * o mirror ``master`` já correu (o ``curated_loader`` resolve o
    causador via ``core.employees``).

Uso::

    .\\.venv\\Scripts\\python.exe scripts\\populate_curated.py
    .\\.venv\\Scripts\\python.exe scripts\\populate_curated.py --since 2026-01-01
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime
from uuid import UUID

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DEV_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="populate_curated",
        description="Popular factory_curated.* a partir do ERP MAR-KAYAKS.",
    )
    parser.add_argument(
        "--since", metavar="YYYY-MM-DD",
        help="Watermark da janela (default: 365 dias atrás).",
    )
    return parser.parse_args(argv)


async def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    since: date | None = None
    if args.since:
        try:
            since = datetime.strptime(args.since, "%Y-%m-%d").date()
        except ValueError:
            print(f"[FAIL] --since tem de ser YYYY-MM-DD, recebeu: {args.since}")
            return 1

    from src.adapters.nelo.etl.quality import mirror_quality
    from src.adapters.nelo.services import close_engine, health_check
    from src.factory_data_product.etl.curated_loader import load_curated
    from src.shared.config import settings
    from src.shared.database import async_session_factory

    if not getattr(settings, "sqlserver_enabled", False):
        print(
            "[SKIP] SQLSERVER_ENABLED=False. Configura SQLSERVER_URL no .env "
            "para correr o populate."
        )
        return 0

    print(f"populate_curated em {datetime.now():%Y-%m-%d %H:%M:%S}")
    try:
        snapshot = await health_check()
        print(
            f"  ERP acessível — open_orders={snapshot.open_orders_count} "
            f"movements_30d={snapshot.movements_last_30d}"
        )

        # 1. Mirror de qualidade ERP → quality.rework_entry.
        async with async_session_factory() as session:
            q_result = await mirror_quality(
                session=session, tenant_id=DEV_TENANT_ID, since=since,
            )
            await session.commit()
        print(
            f"  [quality] {q_result.status} — read={q_result.rows_read} "
            f"ins={q_result.rows_inserted} upd={q_result.rows_updated}"
        )
        if q_result.status != "ok":
            print(f"  erro: {q_result.error}")
            return 1

        # 2. curated_loader → factory_curated.*.
        async with async_session_factory() as session:
            counts = await load_curated(
                session, DEV_TENANT_ID, since=since,
            )
            await session.commit()
        print(
            f"  [curated] order_phase={counts['order_phase']} "
            f"allocation={counts['allocation']} "
            f"quality_event={counts['quality_event']} "
            f"(ingestion {counts['ingestion_id']})"
        )
    except Exception as exc:  # noqa: BLE001 — top-level reporter
        print(f"[FAIL] populate abortado: {type(exc).__name__}: {exc}")
        return 1
    finally:
        await close_engine()

    print("[OK] factory_curated.* populado.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
