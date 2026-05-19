"""Q.53.A / Q.54.F — Seed the ML registry from the durable DB tables.

Trains `QualityRiskModel` + `DurationModel` + `OTDRiskModel` against the
real factory history (`factory_curated.order_phase` ⋈
`quality.rework_entry` ⋈ `plan.production_orders`), registers the
artifacts and promotes them to ACTIVE so:

  * `load_active_quality_risk_predictor()` / `..._duration_predictor()` /
    `..._otd_risk_predictor()` stop returning ``None``;
  * the CPO fitness + routing resolver pick up the trained models;
  * `GET /v1/quality/defect-risk` and `GET /v1/plan/orders/otd-risk`
    have a model to orchestrate.

This is the one-shot seed. The cron `RetrainJob` keeps retraining weekly /
daily through the governed path afterwards.

Usage::

    $env:PYTHONPATH = "c:/Users/User/nelinho"
    .\\.venv\\Scripts\\python.exe scripts/train_ml_models.py
    .\\.venv\\Scripts\\python.exe scripts/train_ml_models.py --tenant <uuid>
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from uuid import UUID

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("train_ml_models")

DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")


async def _run(tenant_id: UUID) -> int:
    from src.ml.training_service import (
        TrainingError,
        train_duration,
        train_otd_risk,
        train_quality_risk,
    )
    from src.shared.database import get_session_context

    failures = 0
    async with get_session_context() as session:
        for label, fn in (
            ("quality_risk", train_quality_risk),
            ("duration", train_duration),
            ("otd_risk", train_otd_risk),
        ):
            try:
                summary = await fn(session, tenant_id)
                await session.commit()
                logger.info(
                    "%s: v%s ACTIVE — metrics=%s",
                    label, summary["version"], summary["metrics"],
                )
            except TrainingError as exc:
                await session.rollback()
                logger.error("%s: training skipped — %s", label, exc)
                failures += 1
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the ML registry from the DB.")
    parser.add_argument(
        "--tenant", default=str(DEV_TENANT), help="Tenant UUID (default: dev tenant)."
    )
    args = parser.parse_args()
    failures = asyncio.run(_run(UUID(args.tenant)))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
