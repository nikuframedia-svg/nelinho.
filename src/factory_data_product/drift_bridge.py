"""
ProdPlan ONE — Drift → Alerts Bridge (Sprint J.3)
==================================================

When a new ingestion is activated, compare its schema snapshot against
the previous snapshot and emit `CopilotAlert` rows when drift crosses
the blocking threshold. Decision-run proposals for model retraining
are optional and gated by env var so they don't fire on every dev boot.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.alerts.models import (
    STATUS_ACTIVE,
    CopilotAlert,
)

logger = logging.getLogger(__name__)


CODE_SCHEMA_DRIFT = "FACTORY_SCHEMA_DRIFT"


def _summarise_drift(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a compact diff between the last two schema snapshots.
    `history` is the list returned by `IngestEngine.get_schema_history()`.
    """
    if len(history) < 2:
        return {"has_drift": False, "reason": "Only one snapshot available"}

    baseline = history[-2]
    current = history[-1]
    base_sheets = set(baseline.get("sheets", {}).keys())
    curr_sheets = set(current.get("sheets", {}).keys())

    sheets_added = list(curr_sheets - base_sheets)
    sheets_removed = list(base_sheets - curr_sheets)

    cols_added: Dict[str, List[str]] = {}
    cols_removed: Dict[str, List[str]] = {}
    for sheet in base_sheets & curr_sheets:
        base_cols = set(baseline.get("sheets", {}).get(sheet, {}).get("columns", []))
        curr_cols = set(current.get("sheets", {}).get(sheet, {}).get("columns", []))
        added = list(curr_cols - base_cols)
        removed = list(base_cols - curr_cols)
        if added:
            cols_added[sheet] = added
        if removed:
            cols_removed[sheet] = removed

    has_drift = bool(sheets_added or sheets_removed or cols_added or cols_removed)
    severity = "CRITICAL" if (sheets_removed or cols_removed) else "WARN"

    return {
        "has_drift": has_drift,
        "severity": severity,
        "baseline_ingestion_id": baseline.get("ingestion_id"),
        "current_ingestion_id": current.get("ingestion_id"),
        "sheets_added": sheets_added,
        "sheets_removed": sheets_removed,
        "columns_added": cols_added,
        "columns_removed": cols_removed,
    }


async def emit_drift_alert_if_any(
    session: AsyncSession,
    tenant_id: UUID,
    ingestion_id: UUID,
    history: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Emit a `CopilotAlert` row when drift is detected between the last two
    schema snapshots. Returns the alert id (as str) or None.

    The caller is responsible for commit; we only flush.
    """
    diff = _summarise_drift(history)
    if not diff.get("has_drift"):
        return None

    severity = diff["severity"]
    parts: List[str] = []
    if diff["sheets_added"]:
        parts.append(f"Sheets adicionadas: {diff['sheets_added']}")
    if diff["sheets_removed"]:
        parts.append(f"Sheets removidas: {diff['sheets_removed']}")
    if diff["columns_added"]:
        parts.append(
            "Colunas novas por sheet: " + ", ".join(
                f"{s}({len(cs)})" for s, cs in diff["columns_added"].items()
            )
        )
    if diff["columns_removed"]:
        parts.append(
            "Colunas removidas por sheet: " + ", ".join(
                f"{s}({len(cs)})" for s, cs in diff["columns_removed"].items()
            )
        )

    alert = CopilotAlert(
        id=uuid4(),
        tenant_id=tenant_id,
        severity=severity,
        code=CODE_SCHEMA_DRIFT,
        title=f"Schema drift detectado na ingestão {ingestion_id}",
        message_pt=(
            f"A ingestão activada apresenta drift de schema vs. a anterior. "
            + " | ".join(parts)
            + ". Revê o ficheiro antes de treinar modelos ML sobre estes dados."
        ),
        context={
            "diff": diff,
            "ingestion_id": str(ingestion_id),
        },
        entity_refs=[f"ingestion:{ingestion_id}"],
        status=STATUS_ACTIVE,
    )
    session.add(alert)
    await session.flush()
    logger.warning(f"Schema drift alert emitted for ingestion {ingestion_id}: {severity}")
    return str(alert.id)
