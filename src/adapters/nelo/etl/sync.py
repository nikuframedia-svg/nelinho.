"""Q.20.A — ERP→Postgres sync orchestration.

One place that knows how to: check ``settings.sqlserver_enabled``,
health-check the NELO adapter, and run the registered mirror functions.
Both the CLI (``scripts/sync_nelo_erp.py``) and the scheduler job
(``nelo_erp_sync``) call :func:`run_nelo_sync`.

Mirror modules (``master_data``, ``molds``, ``skills``, ``quality``,
``time_mining``) register themselves here via :func:`register_mirror`
when imported. :func:`_load_mirror_modules` imports them on demand so a
mirror added in a later sub-sprint is picked up automatically.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Awaitable, Callable, Dict, List, Optional
from uuid import UUID

from .runner import EtlRunResult

logger = logging.getLogger(__name__)

# A mirror reads from the NELO adapter and writes operational rows. It
# owns its own EtlRunner; the orchestrator hands it a session, tenant and
# an optional ``since`` watermark, and gets back the run tally.
MirrorFn = Callable[..., Awaitable[EtlRunResult]]

_MIRRORS: Dict[str, MirrorFn] = {}


def register_mirror(name: str, fn: MirrorFn) -> None:
    """Register a mirror under ``name`` (the ``--only`` selector value)."""
    _MIRRORS[name] = fn


def _resolve_source(source: Any):
    """Resolve the ``source`` selector to a module exposing the adapter
    interface (``list_*`` + ``health_check`` + ``close_engine``).

    * ``"erp"`` / ``None`` — the live SQL Server (:mod:`services`);
    * ``"demo"`` — the bundled demo package (:mod:`demo_source`);
    * a module/object — used verbatim (tests inject fakes here).
    """
    if source is None or source == "erp":
        from src.adapters.nelo import services
        return services
    if source == "demo":
        from src.adapters.nelo import demo_source
        return demo_source
    if isinstance(source, str):
        raise ValueError(f"unknown source: {source!r}; use 'erp' or 'demo'")
    return source


def registered_mirrors() -> List[str]:
    return sorted(_MIRRORS)


def _load_mirror_modules() -> None:
    """Import the mirror modules so their ``register_mirror`` calls fire.

    Each is optional during the incremental Q.20.B…F rollout — a missing
    module is logged at debug level, not an error.
    """
    for mod in (
        "master_data",   # Q.20.B
        "molds",         # Q.20.C
        "skills",        # Q.20.D
        "quality",       # Q.20.E
        "time_mining",   # Q.20.F
    ):
        try:
            __import__(f"src.adapters.nelo.etl.{mod}")
        except ImportError:  # pragma: no cover - defensive
            logger.debug("etl mirror module not present yet: %s", mod)


async def run_nelo_sync(
    *,
    only: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    tenant_id: Optional[UUID] = None,
    since: Optional[date] = None,
    source: Any = "erp",
) -> List[EtlRunResult]:
    """Run the source→Postgres sync.

    * ``only`` — subset of mirror names; ``None`` runs every registered one.
    * ``exclude`` — mirror names to drop (e.g. the heavy ``time_mining``
      is excluded from the nightly job).
    * ``tenant_id`` — defaults to the dev tenant.
    * ``since`` — watermark forwarded to incremental mirrors (quality,
      time_mining).
    * ``source`` — ``"erp"`` (live SQL Server, the default) or ``"demo"``
      (the bundled demo package). The ``sqlserver_enabled`` gate only
      applies to the ERP source — the demo source has no SQL Server.

    Returns one :class:`EtlRunResult` per mirror that ran. A single
    failing mirror is recorded (``status='error'``) and the others still
    run — one bad table never aborts the whole sync.
    """
    from src.shared.config import settings
    from src.shared.database import async_session_factory

    src_mod = _resolve_source(source)
    is_erp = source is None or source == "erp"

    if tenant_id is None:
        tenant_id = UUID("00000000-0000-0000-0000-000000000001")  # dev tenant

    if is_erp and not getattr(settings, "sqlserver_enabled", False):
        logger.warning(
            "nelo_sync skipped — settings.sqlserver_enabled is False. "
            "Set it (and sqlserver_url) to run the ERP sync, or pass "
            "source='demo' to ingest the bundled demo package."
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

    results: List[EtlRunResult] = []
    try:
        snapshot = await src_mod.health_check()
        logger.info(
            "nelo_sync — source=%s reachable: open_orders=%d movements_30d=%d",
            ("erp" if is_erp else source),
            snapshot.open_orders_count, snapshot.movements_last_30d,
        )

        if not selected:
            logger.info("nelo_sync — no mirrors registered/selected.")
            return []

        for name in selected:
            try:
                async with async_session_factory() as session:
                    result = await _MIRRORS[name](
                        session=session,
                        tenant_id=tenant_id,
                        since=since,
                        source=src_mod,
                    )
                    await session.commit()
                results.append(result)
                logger.info("nelo_sync mirror=%s %r", name, result)
            except Exception as exc:  # noqa: BLE001 - one mirror must not abort the rest
                logger.error(
                    "nelo_sync mirror=%s failed: %s", name, exc, exc_info=True,
                )
                failed = EtlRunResult(name)
                failed.status = "error"
                failed.error = f"{type(exc).__name__}: {exc}"
                results.append(failed)
    finally:
        await src_mod.close_engine()

    return results
