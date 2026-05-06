"""
ProdPlan ONE — Factory Data Watcher (Sprint J)
================================================

Periodic file-hash check that triggers `IngestEngine.ingest()` when the
configured XLSX changes. Designed to be registered with APScheduler via
`src/shared/scheduler.py`.

Deduplication is guaranteed by `IngestEngine` itself (file_sha256 check),
so the watcher is cheap to run even when nothing changed.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.factory_data_product.ingest import IngestEngine
from src.factory_data_product.models.meta import SourceType

logger = logging.getLogger(__name__)


DEFAULT_WATCH_PATH_ENV = "PRODPLAN_FACTORY_FILE"
DEFAULT_WATCH_INTERVAL_MINUTES = 60
DEFAULT_AUTO_ACTIVATE_ENV = "PRODPLAN_FACTORY_AUTO_ACTIVATE"


@dataclass
class WatcherState:
    """Module-level state so the hash is remembered between ticks."""
    last_hash: Optional[str] = None
    last_ingestion_id: Optional[str] = None
    last_error: Optional[str] = None


_state = WatcherState()
# Onda 2.3 — APScheduler is configured with `max_instances=1` + `coalesce`,
# which prevents the registered tick from running concurrently. But callers
# from outside the scheduler (tests, ops endpoints, future cron triggers)
# can still race on `_state`. The lock keeps the hash check + ingest +
# state mutation atomic with respect to the module-level `_state`.
_state_lock = asyncio.Lock()


def _hash_file(path: Path) -> str:
    """Streaming SHA256 so we don't load 57 MB into memory per tick."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_watch_path() -> Optional[Path]:
    raw = os.environ.get(DEFAULT_WATCH_PATH_ENV, "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.exists() else None


def _auto_activate() -> bool:
    return os.environ.get(DEFAULT_AUTO_ACTIVATE_ENV, "").lower() in ("1", "true", "yes")


async def watcher_tick(engine: Optional[IngestEngine] = None) -> dict:
    """
    One poll: if the configured file has a new hash, trigger an ingest.

    Returns a summary dict for observability / tests.

    Onda 2.3 — entire body protected by ``_state_lock``: the hash check,
    ingest call, and state mutation must be atomic. Without it, two
    overlapping ticks could both read the same `last_hash`, both trigger
    an ingest of the same file, and the second one would only succeed
    because of the engine's separate dedupe (which itself is in-memory
    and not safe across processes — see Onda 0 notes).
    """
    summary = {
        "file_found": False,
        "hash_changed": False,
        "triggered_ingest": False,
        "ingestion_id": None,
        "error": None,
    }

    async with _state_lock:
        path = _resolve_watch_path()
        if path is None:
            summary["error"] = f"{DEFAULT_WATCH_PATH_ENV} not set or file missing"
            return summary

        summary["file_found"] = True

        try:
            new_hash = _hash_file(path)
        except Exception as e:
            summary["error"] = f"hash failed: {e}"
            logger.warning(f"Watcher hash failed for {path}: {e}")
            return summary

        if new_hash == _state.last_hash:
            return summary

        summary["hash_changed"] = True
        logger.info(f"Watcher: new hash for {path.name} (was {_state.last_hash!r})")

        eng = engine or IngestEngine()
        try:
            result = eng.ingest(
                file_path=path,
                source_type=(
                    SourceType.WATCHER if hasattr(SourceType, "WATCHER")
                    else SourceType.UPLOAD
                ),
                created_by="watcher",
                auto_activate=_auto_activate(),
            )
            summary["triggered_ingest"] = True
            summary["ingestion_id"] = (
                str(result.ingestion_id) if result.ingestion_id else None
            )
            _state.last_hash = new_hash
            _state.last_ingestion_id = summary["ingestion_id"]
            _state.last_error = None
            logger.info(
                f"Watcher ingested {path.name}: status={result.status.value} "
                f"rows_raw={result.total_rows_raw} "
                f"rows_curated={result.total_rows_curated}"
            )
        except Exception as e:
            summary["error"] = str(e)
            _state.last_error = str(e)
            logger.error(
                f"Watcher ingest failed for {path.name}: {e}", exc_info=True,
            )

        return summary


def register_with_scheduler(
    scheduler,
    interval_minutes: int = DEFAULT_WATCH_INTERVAL_MINUTES,
) -> None:
    """
    Hook into an existing AsyncIOScheduler. No-op if the file env var is
    unset so dev boxes without the XLSX don't get noisy job logs.
    """
    if _resolve_watch_path() is None:
        logger.info(
            f"Factory watcher disabled: {DEFAULT_WATCH_PATH_ENV} not set. "
            f"Set it to an absolute path to enable auto-ingest."
        )
        return

    try:
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:  # pragma: no cover
        logger.warning("APScheduler not installed — watcher cannot be registered")
        return

    scheduler.add_job(
        watcher_tick,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="factory_data_watcher",
        name="factory_data_watcher",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    logger.info(f"Factory watcher registered (every {interval_minutes} min)")


def get_state() -> WatcherState:
    """Expose the module-level state for tests / ops endpoints."""
    return _state


def reset_state() -> None:
    """Test helper."""
    _state.last_hash = None
    _state.last_ingestion_id = None
    _state.last_error = None
