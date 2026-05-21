"""
ProdPlan ONE - Diagnostics service (Sprint Q.7 Fase 1)
======================================================

Collects live runtime signals for the diagnostics dashboard:

* Per-module rollup (imports OK, route count, test files, TODO count) —
  same shape as `scripts/audit.py` but computed against the loaded app.
* Infrastructure health (DB, Redis, Kafka, Ollama).
* Trust Index v2 factory composite + effective gates.
* ScheduleCommit cadence (last 7 days) — a pulse of how often the CPO is
  producing plans.

Designed to answer "is the factory safe to operate right now?" in <1s.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Module catalogue
# ─────────────────────────────────────────────────────────────────────────────

MODULES: tuple[str, ...] = (
    "core",
    "plan",
    "profit",
    "hr",
    "copilot",
    "ml",
    "explain",
    "factory_data_product",
    "governance",
    "shared",
    "twin",
    "sandbox",
    "supply",
    "workforce",
    "dqa",
    "improve",
    "legacy",
)

_TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# Data shapes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ModuleHealth:
    module: str
    src_files: int = 0
    test_files: int = 0
    routes: int = 0
    todo_count: int = 0
    import_errors: list[str] = field(default_factory=list)
    health: str = "unknown"  # green | yellow | red

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "src_files": self.src_files,
            "test_files": self.test_files,
            "routes": self.routes,
            "todo_count": self.todo_count,
            "import_errors": self.import_errors,
            "import_error_count": len(self.import_errors),
            "health": self.health,
        }


@dataclass
class InfraCheck:
    component: str
    healthy: bool
    detail: str
    latency_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "healthy": self.healthy,
            "detail": self.detail,
            "latency_ms": (
                round(self.latency_ms, 1) if self.latency_ms is not None else None
            ),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Per-module health (cheap — no subprocess)
# ─────────────────────────────────────────────────────────────────────────────

def _list_py(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [
        p for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
    ]


def _try_import(file_path: Path) -> str | None:
    """Returns error string if the import fails, None on success."""
    rel = file_path.relative_to(_REPO_ROOT)
    if rel.name == "__init__.py":
        if file_path.stat().st_size == 0:
            return None
        dotted = ".".join(rel.parent.parts)
    else:
        dotted = ".".join(rel.with_suffix("").parts)
    try:
        importlib.import_module(dotted)
        return None
    except Exception as exc:
        return f"{rel}: {type(exc).__name__}: {str(exc)[:200]}"


def _count_todos(files: list[Path]) -> int:
    n = 0
    for f in files:
        try:
            with f.open(encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            n += len(_TODO_RE.findall(content))
        except OSError:
            pass
    return n


def collect_module_health(routes_by_module: dict[str, int]) -> list[ModuleHealth]:
    out: list[ModuleHealth] = []
    for name in MODULES:
        src_dir = _REPO_ROOT / "src" / name
        test_dir = _REPO_ROOT / "tests" / name
        src_files = _list_py(src_dir)
        test_files = _list_py(test_dir)

        m = ModuleHealth(module=name)
        m.src_files = len(src_files)
        m.test_files = len(test_files)
        m.routes = routes_by_module.get(name, 0)
        m.todo_count = _count_todos(src_files)

        for f in src_files:
            err = _try_import(f)
            if err is not None:
                m.import_errors.append(err)

        if m.import_errors:
            m.health = "red"
        elif m.src_files == 0:
            # Onda 1.5 — module without source is unknown, not green.
            # Marking green hid accidentally-deleted modules from the
            # dashboard. "unknown" surfaces them without inflating red.
            m.health = "unknown"
        elif m.test_files == 0:
            m.health = "yellow"
        else:
            m.health = "green"

        out.append(m)
    return out


def collect_routes_by_module(app) -> dict[str, int]:
    """For every registered route, bucket it under the module whose prefix
    appears in the path."""
    counts: dict[str, int] = {m: 0 for m in MODULES}
    for r in app.routes:
        if not hasattr(r, "path"):
            continue
        path = r.path
        for m in MODULES:
            if path.startswith(f"/v1/{m}/") or path.startswith(f"/{m}/"):
                counts[m] += 1
                break
    return counts


# ─────────────────────────────────────────────────────────────────────────────
# Infrastructure pings
# ─────────────────────────────────────────────────────────────────────────────

async def check_database(session) -> InfraCheck:
    """Round-trip a SELECT 1."""
    t0 = time.monotonic()
    try:
        from sqlalchemy import text
        await session.execute(text("SELECT 1"))
        return InfraCheck(
            component="postgresql",
            healthy=True,
            detail="SELECT 1 OK",
            latency_ms=(time.monotonic() - t0) * 1000.0,
        )
    except Exception as exc:
        return InfraCheck(
            component="postgresql",
            healthy=False,
            detail=f"{type(exc).__name__}: {str(exc)[:150]}",
            latency_ms=(time.monotonic() - t0) * 1000.0,
        )


async def check_redis() -> InfraCheck:
    t0 = time.monotonic()
    try:
        from src.shared.redis_client import get_redis
        client = await get_redis()
        if client is None:
            return InfraCheck(
                component="redis",
                healthy=False,
                detail="get_redis() returned None",
            )
        await client.ping()
        return InfraCheck(
            component="redis",
            healthy=True,
            detail="PING OK",
            latency_ms=(time.monotonic() - t0) * 1000.0,
        )
    except Exception as exc:
        return InfraCheck(
            component="redis",
            healthy=False,
            detail=f"{type(exc).__name__}: {str(exc)[:150]}",
            latency_ms=(time.monotonic() - t0) * 1000.0,
        )


async def check_kafka() -> InfraCheck:
    """Real broker ping (Onda 1.5).

    The previous version returned `healthy=True` whenever `get_producer()`
    yielded a non-None client — even with brokers down. We now hit the
    broker for metadata of `__consumer_offsets` (an internal Kafka topic
    that always exists on any cluster), capped at 2s. Failure to reach
    the broker propagates as `healthy=False`.
    """
    t0 = time.monotonic()
    try:
        from src.shared.kafka_client import get_producer
        client = await get_producer()
        producer = getattr(client, "_producer", None)
        if client is None or producer is None:
            return InfraCheck(
                component="kafka",
                healthy=False,
                detail="producer not initialised",
                latency_ms=(time.monotonic() - t0) * 1000.0,
            )
        partitions = await asyncio.wait_for(
            producer.partitions_for("__consumer_offsets"),
            timeout=2.0,
        )
        return InfraCheck(
            component="kafka",
            healthy=bool(partitions),
            detail=(
                f"metadata OK ({len(partitions)} partitions)"
                if partitions else "no partitions returned"
            ),
            latency_ms=(time.monotonic() - t0) * 1000.0,
        )
    except asyncio.TimeoutError:
        return InfraCheck(
            component="kafka",
            healthy=False,
            detail="metadata fetch timed out (2s)",
            latency_ms=(time.monotonic() - t0) * 1000.0,
        )
    except Exception as exc:
        return InfraCheck(
            component="kafka",
            healthy=False,
            detail=f"{type(exc).__name__}: {str(exc)[:150]}",
            latency_ms=(time.monotonic() - t0) * 1000.0,
        )


async def check_ollama() -> InfraCheck:
    """Hit Ollama's /api/version. Cheap and doesn't burn GPU.

    Onda 3.6 — URL and timeout configurable via env so deployments outside
    the local-dev box can point the check at a remote daemon. Defaults
    match the historical hardcoded values for backwards compatibility.
    """
    import os
    ollama_url = os.environ.get("PRODPLAN_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        ollama_timeout = float(os.environ.get("PRODPLAN_OLLAMA_TIMEOUT_S", "2.0"))
    except ValueError:
        ollama_timeout = 2.0

    t0 = time.monotonic()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=ollama_timeout) as client:
            r = await client.get(f"{ollama_url}/api/version")
            r.raise_for_status()
            ver = r.json().get("version", "unknown")
        return InfraCheck(
            component="ollama",
            healthy=True,
            detail=f"version={ver}",
            latency_ms=(time.monotonic() - t0) * 1000.0,
        )
    except Exception as exc:
        return InfraCheck(
            component="ollama",
            healthy=False,
            detail=f"{type(exc).__name__}: {str(exc)[:150]}",
            latency_ms=(time.monotonic() - t0) * 1000.0,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Trust Index + commit cadence
# ─────────────────────────────────────────────────────────────────────────────

async def collect_trust_index(session, tenant_id: UUID) -> dict[str, Any]:
    try:
        from src.dqa.trust_v2 import SCOPE_FACTORY, TrustIndexV2Calculator
        from src.dqa.trust_gates import effective_mode, load_gate_config
        from src.dqa.trust_signals import curated_signals_provider

        calc = TrustIndexV2Calculator(
            session, tenant_id, signals_provider=curated_signals_provider,
        )
        result = await calc.compute_for_scope(SCOPE_FACTORY)
        gate_cfg = await load_gate_config(session, tenant_id)
        gates = effective_mode(result.composite, gate_cfg)
        return {
            "composite": round(result.composite, 4),
            "components": {
                k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in result.components.as_dict().items()
            },
            "effective_gates": gates,
            "source": "live",
        }
    except Exception as exc:
        # Onda 1.5 / 2.2 — fail-loud + sanitised: full detail goes to logs;
        # the API response only exposes the exception type to avoid
        # leaking DB/role internals to the dashboard.
        logger.warning(
            "collect_trust_index fallback for tenant=%s: %r", tenant_id, exc,
        )
        return {"error": type(exc).__name__, "source": "fallback"}


# ─────────────────────────────────────────────────────────────────────────────
# ERP connection diagnostics (Sprint Q.53.F)
# ─────────────────────────────────────────────────────────────────────────────

# The five ERP→Postgres mirrors. Each writes one `core.etl_run` row per
# run (`source` column). The dashboard wants "when did this last sync".
ERP_MIRRORS: tuple[str, ...] = (
    "master",
    "molds",
    "skills",
    "quality",
    "time_mining",
    "stock",
)


def mask_db_url(url: str | None) -> str:
    """Mask a SQLAlchemy connection URL for safe display.

    Strips the password (and, defensively, the username) so the
    dashboard can show *which* server the ERP adapter points at without
    leaking credentials. ``mssql+aioodbc://nelo:secret@erp.lan:1433/DB``
    becomes ``mssql+aioodbc://***@erp.lan:1433/DB``.
    """
    if not url:
        return "(não configurado)"
    # Split scheme://rest
    if "://" not in url:
        return "***"
    scheme, _, rest = url.partition("://")
    # rest = [credentials@]host[/path][?query]
    if "@" in rest:
        _creds, _, host_part = rest.partition("@")
        rest = f"***@{host_part}"
    return f"{scheme}://{rest}"


async def _erp_health_check() -> tuple[bool, str, float | None]:
    """Round-trip a trivial query against the configured Nelo ERP.

    Returns ``(connected, detail, latency_ms)``. When the ERP is disabled
    in config we never open a connection — ``connected`` is False with a
    clear "disabled" detail rather than a misleading error.
    """
    from src.shared.config import settings

    if not getattr(settings, "sqlserver_enabled", False):
        return False, "sqlserver_enabled=False (ERP desligado na config)", None
    if not getattr(settings, "sqlserver_url", None):
        return False, "sqlserver_url não configurado", None

    t0 = time.monotonic()
    try:
        from sqlalchemy import text
        from src.adapters.nelo.services import get_engine

        async def _ping() -> bool:
            engine = get_engine()
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                return result.scalar() == 1

        healthy = await asyncio.wait_for(_ping(), timeout=5.0)
        latency = (time.monotonic() - t0) * 1000.0
        if healthy:
            return True, "SELECT 1 OK", latency
        return False, "SELECT 1 não devolveu 1", latency
    except asyncio.TimeoutError:
        return False, "health check expirou (5s)", (time.monotonic() - t0) * 1000.0
    except Exception as exc:
        # Sanitised — type only, never raw connection-string fragments.
        logger.warning("ERP health check failed: %r", exc)
        return False, type(exc).__name__, (time.monotonic() - t0) * 1000.0


async def collect_erp_connection(session, tenant_id: UUID) -> dict[str, Any]:
    """Live status of the Nelo ERP integration.

    Surfaces, for the admin health page:

    * masked connection URL + enabled flag;
    * connected/offline — a real round-trip when the ERP is enabled;
    * per-mirror last sync from ``core.etl_run`` (status, row counts);
    * lag (seconds + human) since the most recent successful sync.

    All sub-parts are best-effort: a missing ``core.etl_run`` table or a
    dead ERP yields a degraded-but-shaped response, never a 500.
    """
    from datetime import datetime, timezone

    from src.shared.config import settings

    enabled = bool(getattr(settings, "sqlserver_enabled", False))
    masked_url = mask_db_url(getattr(settings, "sqlserver_url", None))

    connected, detail, latency_ms = await _erp_health_check()

    # Per-mirror last run from core.etl_run.
    mirrors: list[dict[str, Any]] = []
    last_sync_at: datetime | None = None
    sync_error: str | None = None
    try:
        from sqlalchemy import desc, select
        from src.core.models.etl_run import EtlRun

        for source in ERP_MIRRORS:
            stmt = (
                select(EtlRun)
                .where((EtlRun.tenant_id == tenant_id) & (EtlRun.source == source))
                .order_by(desc(EtlRun.started_at))
                .limit(1)
            )
            run = (await session.execute(stmt)).scalar_one_or_none()
            if run is None:
                mirrors.append({
                    "source": source,
                    "status": "never_synced",
                    "last_run_at": None,
                    "finished_at": None,
                    "rows_read": 0,
                    "rows_inserted": 0,
                    "rows_updated": 0,
                    "rows_skipped": 0,
                    "error": None,
                })
                continue
            finished = run.finished_at
            mirrors.append({
                "source": source,
                "status": run.status,
                "last_run_at": (
                    run.started_at.isoformat() if run.started_at else None
                ),
                "finished_at": finished.isoformat() if finished else None,
                "rows_read": int(run.rows_read or 0),
                "rows_inserted": int(run.rows_inserted or 0),
                "rows_updated": int(run.rows_updated or 0),
                "rows_skipped": int(run.rows_skipped or 0),
                "error": run.error,
            })
            # Track the latest *successful* finished sync for lag.
            if run.status == "ok" and finished is not None:
                cand = finished
                if cand.tzinfo is None:
                    cand = cand.replace(tzinfo=timezone.utc)
                if last_sync_at is None or cand > last_sync_at:
                    last_sync_at = cand
    except Exception as exc:
        logger.warning("collect_erp_connection etl_run read failed: %r", exc)
        sync_error = type(exc).__name__

    # Lag since last successful sync.
    lag_seconds: int | None = None
    lag_human: str | None = None
    if last_sync_at is not None:
        now = datetime.now(timezone.utc)
        delta = now - last_sync_at
        lag_seconds = max(0, int(delta.total_seconds()))
        hours, rem = divmod(lag_seconds, 3600)
        minutes = rem // 60
        if hours >= 24:
            lag_human = f"{hours // 24}d {hours % 24}h"
        elif hours:
            lag_human = f"{hours}h {minutes}m"
        else:
            lag_human = f"{minutes}m"

    total_rows = sum(m["rows_read"] for m in mirrors)

    return {
        "enabled": enabled,
        "url_masked": masked_url,
        "connected": connected,
        "detail": detail,
        "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
        "mirrors": mirrors,
        "last_sync_at": last_sync_at.isoformat() if last_sync_at else None,
        "lag_seconds": lag_seconds,
        "lag_human": lag_human,
        "total_rows_last_sync": total_rows,
        "sync_history_error": sync_error,
        "sampled_at": datetime.now(timezone.utc).isoformat(),
    }


async def collect_commit_cadence(session, tenant_id: UUID) -> dict[str, Any]:
    """How many ScheduleCommit rows in the last 7 days, plus the latest."""
    try:
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import desc, func, select
        from src.plan.cpo.commits import ScheduleCommit

        since = datetime.now(timezone.utc) - timedelta(days=7)
        count_stmt = select(func.count(ScheduleCommit.id)).where(
            (ScheduleCommit.tenant_id == tenant_id)
            & (ScheduleCommit.created_at >= since)
        )
        count = int((await session.execute(count_stmt)).scalar_one() or 0)

        latest_stmt = (
            select(ScheduleCommit)
            .where(ScheduleCommit.tenant_id == tenant_id)
            .order_by(desc(ScheduleCommit.created_at))
            .limit(1)
        )
        latest = (await session.execute(latest_stmt)).scalar_one_or_none()

        return {
            "commits_last_7_days": count,
            "latest_commit_sha": (
                latest.commit_sha256[:12] if latest is not None else None
            ),
            "latest_commit_at": (
                latest.created_at.isoformat()
                if latest is not None and latest.created_at is not None
                else None
            ),
            "source": "live",
        }
    except Exception as exc:
        # Onda 1.5 / 2.2 — fail-loud + sanitised (same rationale).
        logger.warning(
            "collect_commit_cadence fallback for tenant=%s: %r", tenant_id, exc,
        )
        return {"error": type(exc).__name__, "source": "fallback"}
