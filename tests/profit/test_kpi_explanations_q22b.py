"""Sprint Q.22.B — `/snapshot-explained` explains more than just OTD.

Before Q.22.B the endpoint only populated ``explanations["otd"]``. The
``ExplanationEngine`` already knew how to explain margin, inventory
turnover and machine breakdown — they just were not wired in. These
tests assert the three extra keys now appear, each with the expected
shape (``reason`` + ``topFactors``).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.profit.api.kpis import router as kpis_router
from src.shared.database import get_session

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _build_app():
    """The session yields empty result sets, so calculate_kpis falls
    back to empty metrics and the test exercises only the explanation
    wiring (margin/inventory are static; machine_breakdown sees 0 rows)."""
    empty_result = SimpleNamespace(
        scalar=lambda: 0,
        all=lambda: [],
        fetchall=lambda: [],
        scalars=lambda: SimpleNamespace(all=lambda: []),
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=empty_result)

    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(kpis_router, prefix="/v1/profit")
    app.dependency_overrides[get_session] = _fake_session
    return app


@pytest.fixture
def client():
    return TestClient(_build_app())


def test_snapshot_explained_includes_margin_and_inventory(client):
    resp = client.get(
        "/v1/profit/kpis/snapshot-explained",
        headers={"X-Tenant-Id": str(TENANT)},
    )
    assert resp.status_code == 200
    explanations = resp.json()["explanations"]

    for kpi in ("margin", "inventory_turnover", "machine_breakdown"):
        assert kpi in explanations, f"{kpi} missing from explanations"
        assert "reason" in explanations[kpi]
        assert "topFactors" in explanations[kpi]


def test_margin_explanation_is_advisory(client):
    resp = client.get(
        "/v1/profit/kpis/snapshot-explained",
        headers={"X-Tenant-Id": str(TENANT)},
    )
    margin = resp.json()["explanations"]["margin"]
    assert margin["advisory_mode"] is True
    assert margin["kpi"] == "margin"
    assert len(margin["topFactors"]) == 3
