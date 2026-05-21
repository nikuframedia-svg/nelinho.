"""src/app/lifespan.py — FastAPI lifespan context (Q.67.6.C2).

Thin wrapper that defers to `startup.run_startup` and `startup.run_shutdown`.
The 30s `asyncio.wait_for` upper bound on shutdown is preserved here so
systemd's 60s grace is comfortably honoured (Sprint Q.13.B B5).
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.app.startup import run_shutdown, run_startup

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management.

    Startup runs unconditionally (errors are swallowed per-subsystem so a
    single subsystem failure does not block the process). Shutdown is
    bounded at 30s; if it overruns, systemd will SIGKILL and in-flight
    outbox events will be drained on next boot via the periodic dispatcher.
    """
    await run_startup(app)
    try:
        yield
    finally:
        logger.info("Shutting down ProdPlan ONE...")
        try:
            await asyncio.wait_for(run_shutdown(), timeout=30.0)
            logger.info("ProdPlan ONE shut down cleanly")
        except asyncio.TimeoutError:
            logger.error(
                "Shutdown exceeded 30s grace period — systemd will SIGKILL. "
                "Some pending events may not have flushed; check outbox table "
                "on next boot."
            )
