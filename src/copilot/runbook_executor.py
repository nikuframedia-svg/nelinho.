"""Sprint Q.9 (2.8) — RUN_RUNBOOK executor.

Reads a YAML definition from ``src/copilot/runbook_definitions/`` and
returns a structured trace describing each step.

Q.35.5.2 — the executor now actually RUNS the queries when given an
``AsyncSession``: each query is a read-only ``SELECT`` against the live
Postgres, tenant-scoped via ``:tenant_id``. Without a session it falls
back to the old advisory mode (``status="planned"``) — handy for tests
and for callers that only want the plan.

The catalogue is keyed on the YAML filename (without extension): the
YAML must declare ``id``, ``name``, and a list of ``queries`` (each
with ``name`` + ``sql``). Inputs (e.g. ``date_range``) are interpolated
when present.
"""

from __future__ import annotations

import decimal
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


RUNBOOK_DIR = Path(__file__).parent / "runbook_definitions"


class RunbookNotFound(Exception):
    """Raised when the requested runbook id does not exist on disk."""


class RunbookInvalid(Exception):
    """Raised when the YAML is missing required fields."""


def list_runbooks() -> List[str]:
    """Return every runbook id on disk (filename stems)."""
    return sorted(p.stem for p in RUNBOOK_DIR.glob("*.yaml"))


def loadable_runbooks() -> List[str]:
    """Runbook ids that exist AND parse with the structure this executor
    needs (``id`` + ``queries``).

    Q.35.5.1 — ``list_runbooks`` lists every ``*.yaml``, but some belong
    to the *other* runbook engine (``runbooks.py``, step-based format)
    and don't satisfy :func:`load_runbook`. Only the ids returned here
    can actually be executed — the Copilot must not propose the rest.
    """
    ok: List[str] = []
    for rid in list_runbooks():
        try:
            load_runbook(rid)
            ok.append(rid)
        except (RunbookNotFound, RunbookInvalid):
            continue
    return ok


def load_runbook(runbook_id: str) -> Dict[str, Any]:
    """Load a runbook definition. Raises ``RunbookNotFound`` on miss
    and ``RunbookInvalid`` when required fields are missing."""
    path = RUNBOOK_DIR / f"{runbook_id}.yaml"
    if not path.exists():
        raise RunbookNotFound(runbook_id)

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise RunbookInvalid(f"YAML parse failed for {runbook_id}: {exc}") from exc

    for key in ("id", "name", "queries"):
        if key not in data:
            raise RunbookInvalid(
                f"runbook {runbook_id!r} is missing required key {key!r}"
            )

    if not isinstance(data["queries"], list) or not data["queries"]:
        raise RunbookInvalid(
            f"runbook {runbook_id!r} declares no queries"
        )

    for q in data["queries"]:
        if "name" not in q or "sql" not in q:
            raise RunbookInvalid(
                f"runbook {runbook_id!r} has a query missing name/sql"
            )

    return data


def _parse_range(raw_range: Any) -> timedelta:
    """Parse a ``date_range`` token (``"24h"``, ``"7d"``) → timedelta."""
    if isinstance(raw_range, str) and raw_range.endswith("h"):
        try:
            return timedelta(hours=int(raw_range[:-1]))
        except ValueError:
            return timedelta(hours=24)
    if isinstance(raw_range, str) and raw_range.endswith("d"):
        try:
            return timedelta(days=int(raw_range[:-1]))
        except ValueError:
            return timedelta(days=1)
    return timedelta(hours=24)


def _resolve_inputs(
    payload: Dict[str, Any], default_range: Optional[str] = None,
) -> Dict[str, Any]:
    """Translate the operator's payload into SQL bind parameters.

    ``date_range`` (from the payload, else the runbook's declared
    default, else ``24h``) becomes ``start_date`` / ``end_date`` as
    timezone-aware ``datetime`` objects — asyncpg binds those directly
    against ``timestamptz`` columns. Unknown payload keys pass through.
    """
    out: Dict[str, Any] = {}

    raw_range = payload.get("date_range") or default_range or "24h"
    end = datetime.now(timezone.utc)
    start = end - _parse_range(raw_range)

    out["start_date"] = start
    out["end_date"] = end

    for k, v in payload.items():
        if k != "date_range":
            out[k] = v

    return out


def _is_select(sql: str) -> bool:
    """True only for a single read-only SELECT — the executor refuses
    anything else (defence-in-depth; the YAMLs are repo-controlled)."""
    stripped = sql.strip().rstrip(";").strip()
    if ";" in stripped:  # no statement chaining
        return False
    return stripped.lower().startswith(("select", "with"))


def _jsonable(value: Any) -> Any:
    """Make a query result value JSON-serializable."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


async def execute_runbook(
    runbook_id: str,
    payload: Optional[Dict[str, Any]] = None,
    session: Optional[AsyncSession] = None,
    tenant_id: Optional[uuid.UUID] = None,
) -> Dict[str, Any]:
    """Build (and, with a ``session``, run) an execution trace.

    With ``session`` + ``tenant_id`` each ``SELECT`` runs against the
    live DB and the step carries ``rows`` / ``row_count``. Without a
    session the trace stays advisory (``status="planned"``) — the SQL
    and resolved parameters are returned for inspection.
    """
    payload = payload or {}
    rb = load_runbook(runbook_id)

    default_range = None
    rb_inputs = rb.get("inputs")
    if isinstance(rb_inputs, dict):
        dr = rb_inputs.get("date_range")
        if isinstance(dr, dict):
            default_range = dr.get("default")

    params = _resolve_inputs(payload, default_range=default_range)
    if tenant_id is not None:
        params["tenant_id"] = tenant_id

    steps: List[Dict[str, Any]] = []
    for q in rb["queries"]:
        sql = q["sql"]
        step_params = {k: params[k] for k in params if f":{k}" in sql}
        # Versão JSON-friendly dos parâmetros para o trace.
        display_params = {k: _jsonable(v) for k, v in step_params.items()}
        step: Dict[str, Any] = {
            "name": q["name"],
            "sql": sql,
            "parameters": display_params,
        }

        if session is None:
            step["status"] = "planned"
        elif not _is_select(sql):
            step["status"] = "rejected"
            step["error"] = "runbook só pode correr SELECT read-only"
            logger.warning(
                f"runbook {runbook_id!r} query {q['name']!r} rejeitada — não é SELECT"
            )
        else:
            try:
                result = await session.execute(text(sql), step_params)
                rows = [
                    {k: _jsonable(v) for k, v in dict(r._mapping).items()}
                    for r in result.fetchall()
                ]
                step["status"] = "executed"
                step["rows"] = rows
                step["row_count"] = len(rows)
            except Exception as exc:  # noqa: BLE001 — uma query má não mata o runbook
                step["status"] = "failed"
                step["error"] = str(exc)
                logger.warning(
                    f"runbook {runbook_id!r} query {q['name']!r} falhou: {exc}"
                )

        steps.append(step)

    executed = session is not None
    statuses = {s["status"] for s in steps}
    if not executed:
        overall = "planned"
    elif statuses == {"executed"}:
        overall = "executed"
    elif "executed" in statuses:
        overall = "partial"
    else:
        overall = "failed"

    return {
        "runbook_id": rb["id"],
        "runbook_name": rb["name"],
        "description": rb.get("description", ""),
        "inputs": {k: _jsonable(v) for k, v in params.items()},
        "steps": steps,
        "status": overall,
        "advisory_mode": not executed,
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }
