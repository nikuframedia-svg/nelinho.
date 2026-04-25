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
            m.health = "green"  # nothing to test
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
    t0 = time.monotonic()
    try:
        from src.shared.kafka_client import get_producer
        producer = await get_producer()
        if producer is None:
            return InfraCheck(
                component="kafka",
                healthy=False,
                detail="get_producer() returned None",
            )
        return InfraCheck(
            component="kafka",
            healthy=True,
            detail="producer ready",
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
    """Hit Ollama's /api/version. Cheap and doesn't burn GPU."""
    t0 = time.monotonic()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get("http://127.0.0.1:11434/api/version")
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

        calc = TrustIndexV2Calculator(session, tenant_id)
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
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}", "source": "fallback"}


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
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}", "source": "fallback"}
