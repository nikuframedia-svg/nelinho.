"""
Tests for src.factory_data_product.drift_bridge.

Coverage:
- `_summarise_drift`:
  * single snapshot → no drift
  * new sheet added → WARN
  * sheet removed → CRITICAL
  * columns added → WARN
  * columns removed → CRITICAL
- `emit_drift_alert_if_any`:
  * no drift → returns None, no alert persisted
  * drift detected → alert row added with expected fields
"""

from __future__ import annotations

from typing import List
from uuid import UUID, uuid4

import pytest

from src.copilot.alerts.models import CopilotAlert
from src.factory_data_product.drift_bridge import (
    CODE_SCHEMA_DRIFT,
    _summarise_drift,
    emit_drift_alert_if_any,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")
INGESTION = UUID("22222222-2222-2222-2222-222222222222")


def _snapshot(sheets: dict, ingestion_id: str = "ing"):
    """Build a snapshot in the shape produced by SchemaSnapshot.to_dict():
    {sheet_name: list[column_name]} — not {sheet_name: {"columns": [...]}}.
    Onda 1.9 fix: the previous wrapping caused drift_bridge to read columns
    as `.get("columns")` on a list, raising AttributeError silently."""
    return {
        "ingestion_id": ingestion_id,
        "sheets": {name: list(cols) for name, cols in sheets.items()},
    }


class TestSummariseDrift:
    def test_single_snapshot_reports_no_drift(self):
        history = [_snapshot({"A": ["x"]})]
        assert _summarise_drift(history)["has_drift"] is False

    def test_identical_snapshots_report_no_drift(self):
        snap = _snapshot({"A": ["x", "y"]})
        assert _summarise_drift([snap, snap])["has_drift"] is False

    def test_new_sheet_is_warn(self):
        base = _snapshot({"A": ["x"]}, ingestion_id="v1")
        curr = _snapshot({"A": ["x"], "B": ["z"]}, ingestion_id="v2")
        diff = _summarise_drift([base, curr])
        assert diff["has_drift"] is True
        assert diff["severity"] == "WARN"
        assert "B" in diff["sheets_added"]

    def test_sheet_removed_is_critical(self):
        base = _snapshot({"A": ["x"], "B": ["y"]})
        curr = _snapshot({"A": ["x"]})
        diff = _summarise_drift([base, curr])
        assert diff["severity"] == "CRITICAL"
        assert "B" in diff["sheets_removed"]

    def test_column_added_is_warn(self):
        base = _snapshot({"A": ["x"]})
        curr = _snapshot({"A": ["x", "y"]})
        diff = _summarise_drift([base, curr])
        assert diff["severity"] == "WARN"
        assert diff["columns_added"] == {"A": ["y"]}

    def test_column_removed_is_critical(self):
        base = _snapshot({"A": ["x", "y"]})
        curr = _snapshot({"A": ["x"]})
        diff = _summarise_drift([base, curr])
        assert diff["severity"] == "CRITICAL"
        assert diff["columns_removed"] == {"A": ["y"]}


class _FakeSession:
    """Minimal async-compatible session: captures added rows + flush."""

    def __init__(self):
        self.added: List = []
        self.flush_calls = 0

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flush_calls += 1


class TestEmitDriftAlert:
    @pytest.mark.asyncio
    async def test_no_drift_emits_nothing(self):
        session = _FakeSession()
        snap = _snapshot({"A": ["x"]})
        alert_id = await emit_drift_alert_if_any(session, TENANT, INGESTION, [snap, snap])
        assert alert_id is None
        assert session.added == []

    @pytest.mark.asyncio
    async def test_drift_emits_alert(self):
        session = _FakeSession()
        history = [
            _snapshot({"A": ["x"]}, ingestion_id="v1"),
            _snapshot({"A": ["x", "y"]}, ingestion_id="v2"),
        ]
        alert_id = await emit_drift_alert_if_any(session, TENANT, INGESTION, history)

        assert alert_id is not None
        assert len(session.added) == 1
        alert = session.added[0]
        assert isinstance(alert, CopilotAlert)
        assert alert.code == CODE_SCHEMA_DRIFT
        assert alert.severity == "WARN"
        assert alert.tenant_id == TENANT
        assert alert.entity_refs == [f"ingestion:{INGESTION}"]
        assert "y" in str(alert.context.get("diff", {}).get("columns_added", {}))

    @pytest.mark.asyncio
    async def test_critical_when_column_removed(self):
        session = _FakeSession()
        history = [
            _snapshot({"A": ["x", "y"]}),
            _snapshot({"A": ["x"]}),
        ]
        alert_id = await emit_drift_alert_if_any(session, TENANT, INGESTION, history)
        assert alert_id is not None
        assert session.added[0].severity == "CRITICAL"
