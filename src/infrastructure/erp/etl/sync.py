"""Q.20.A — ERP→Postgres sync orchestration.

One place that knows how to: check ``settings.sqlserver_enabled``, build
the :class:`NeloERPAdapter`, health-check it, and run the registered
mirror functions. Both the CLI (``scripts/sync_nelo_to_postgres.py``)
and the scheduler job (``nelo_erp_sync``) call :func:`run_nelo_sync`.

Mirror modules (``master_data``, ``molds``, ``skills``, ``quality``,
``time_mining`` — added in Q.20.B…F) register themselves here via
:func:`register_mirror`. In Q.20.A the registry is empty: the sync
connects, probes the views, and logs "no mirrors registered".
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Awaitable, Callable, Dict, List, Optional
from uuid import UUID

from .runner import EtlRunResult

logger = logging.getLogger(__name__)

# A mirror reads from the adapter and writes operational rows. It owns its
# own EtlRunner; the orchestrator hands it a session, tenant, adapter and
# an optional `since` watermark, and gets back the run tally.
MirrorFn = Callable[..., Awaitable[EtlRunResult]]

_MIRRORS: Dict[str, MirrorFn] = {}


def register_mirror(name: str, fn: MirrorFn) -> None:
    """Register a mirror under ``name`` (the ``--only`` selector value)."""
    _MIRRORS[name] = fn


def registered_mirrors() -> List[str]:
    return sorted(_MIRRORS)


def _load_mirror_modules() -> None:
    """Import the mirror modules so their ``register_mirror`` calls fire.

    Each is optional — Q.20.A ships none of them, Q.20.B…F add one each.
    A missing module is normal during the incremental rollout.
    """
    for mod in (
        "master_data",   # Q.20.B
        "molds",         # Q.20.C
        "skills",        # Q.20.D
        "quality",       # Q.20.E
        "time_mining",   # Q.20.F
    ):
        try:
            __import__(f"src.infrastructure.erp.etl.{mod}")
        except ImportError:
            logger.debug("etl mirror module not present yet: %s", mod)


async def run_nelo_sync(
    *,
    only: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    tenant_id: Optional[UUID] = None,
    since: Optional[date] = None,
) -> List[EtlRunResult]:
    """Run the ERP→Postgres sync.

    * ``only`` — subset of mirror names; ``None`` runs every registered one.
    * ``exclude`` — mirror names to drop (e.g. the weekly ``time_mining``
      is excluded from the daily job).
    * ``tenant_id`` — defaults to the dev tenant.
    * ``since`` — watermark forwarded to incremental mirrors (quality, times).

    Returns one :class:`EtlRunResult` per mirror that ran. Raises
    :class:`NeloERPError` only when the ERP itself is unreachable; a
    single failing mirror is recorded (``status='error'``) and the
    others still run.
    """
    from src.infrastructure.erp.sqlserver import NeloERPAdapter, NeloERPError
    from src.shared.config import settings
    from src.shared.database import get_session_context

    if tenant_id is None:
        tenant_id = UUID("00000000-0000-0000-0000-000000000001")  # dev tenant

    if not getattr(settings, "sqlserver_enabled", False):
        logger.warning(
            "nelo_sync skipped — settings.sqlserver_enabled is False. "
            "Set it (and sqlserver_url) to run the ERP sync."
        )
        return []

    _load_mirror_modules()
    selected = list(only) if only else registered_mirrors()
    if exclude:
        selected = [m for m in selected if m not in set(exclude)]
    unknown = [m for m in selected if m not in _MIRRORS]
    if unknown:
        raise ValueError(
            f"unknown mirror(s): {unknown}; known: {registered_mirrors()}"
        )

    adapter = NeloERPAdapter.from_settings(settings)
    results: List[EtlRunResult] = []
    try:
        if not await adapter.health_check():
            raise NeloERPError("Nelo ERP health check failed — ERP unreachable")

        if not selected:
            logger.info(
                "nelo_sync — no mirrors registered yet (Q.20.A foundation). "
                "ERP reachable, %d views to probe.", 10,
            )
            return []

        for name in selected:
            try:
                async with get_session_context() as session:
                    result = await _MIRRORS[name](
                        session=session,
                        tenant_id=tenant_id,
                        adapter=adapter,
                        since=since,
                    )
                    await session.commit()
                results.append(result)
                logger.info("nelo_sync mirror=%s %r", name, result)
            except Exception as exc:
                logger.error(
                    "nelo_sync mirror=%s failed: %s", name, exc, exc_info=True,
                )
                failed = EtlRunResult(name)
                failed.status = "error"
                failed.error = f"{type(exc).__name__}: {exc}"
                results.append(failed)
    finally:
        await adapter.close()

    return results
