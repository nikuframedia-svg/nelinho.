"""Sprint Q.9 (2.8) — minimal RUN_RUNBOOK executor.

Reads a YAML definition from ``src/copilot/runbook_definitions/`` and
returns a structured trace describing each step. Advisory only — does
NOT run the SQL queries against a live DB. Until Sprint G (NELO ERP
wired), the executor produces a plan + the parameters the operator
can hand to a DBA.

The catalogue is keyed on the YAML filename (without extension): the
YAML must declare ``id``, ``name``, ``description``, and a list of
``queries`` (each with ``name`` + ``sql``). Inputs (e.g. ``date_range``)
are interpolated when present.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


RUNBOOK_DIR = Path(__file__).parent / "runbook_definitions"


class RunbookNotFound(Exception):
    """Raised when the requested runbook id does not exist on disk."""


class RunbookInvalid(Exception):
    """Raised when the YAML is missing required fields."""


def list_runbooks() -> List[str]:
    """Return the available runbook ids (filename stems)."""
    return sorted(p.stem for p in RUNBOOK_DIR.glob("*.yaml"))


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


def _resolve_inputs(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translate the operator's payload into SQL bind parameters.

    Currently supports only ``date_range`` (e.g. ``"24h"``, ``"7d"``)
    which is converted into ``start_date`` / ``end_date`` ISO strings.
    Unknown payload keys are passed through verbatim so future runbooks
    can extend without changing the executor.
    """
    out: Dict[str, Any] = {}

    raw_range = payload.get("date_range") or "24h"
    end = datetime.utcnow()
    if isinstance(raw_range, str) and raw_range.endswith("h"):
        try:
            hours = int(raw_range[:-1])
            start = end - timedelta(hours=hours)
        except ValueError:
            start = end - timedelta(hours=24)
    elif isinstance(raw_range, str) and raw_range.endswith("d"):
        try:
            days = int(raw_range[:-1])
            start = end - timedelta(days=days)
        except ValueError:
            start = end - timedelta(days=1)
    else:
        start = end - timedelta(hours=24)

    out["start_date"] = start.isoformat()
    out["end_date"] = end.isoformat()

    for k, v in payload.items():
        if k != "date_range":
            out[k] = v

    return out


def execute_runbook(
    runbook_id: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build an execution trace for ``runbook_id``.

    The trace contains the resolved inputs, the planned queries (with
    parameters interpolated as ``:name`` placeholders), and a status
    of ``"planned"`` until Sprint G wires real DB execution. Caller is
    expected to render the trace back to the operator (Copilot UI) and
    optionally hand the SQL to a DBA / runbook runner.
    """
    payload = payload or {}
    rb = load_runbook(runbook_id)
    params = _resolve_inputs(payload)

    steps = []
    for q in rb["queries"]:
        steps.append({
            "name": q["name"],
            "sql": q["sql"],
            "parameters": {
                k: params[k]
                for k in params
                if f":{k}" in q["sql"]
            },
            "status": "planned",
        })

    return {
        "runbook_id": rb["id"],
        "runbook_name": rb["name"],
        "description": rb.get("description", ""),
        "inputs": params,
        "steps": steps,
        "status": "planned",
        "advisory_mode": True,
        "executed_at": datetime.utcnow().isoformat(),
    }
