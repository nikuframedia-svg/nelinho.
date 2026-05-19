"""Endpoint tests for /v1/profit/energy/real — Sprint Q.50.B (F8).

The endpoint is a thin wrapper over ``EnergyCostService``. These tests
call the route function directly (no live HTTP server) and assert only
the deterministic wrapper behaviour: the default date window, the tariff
being surfaced, and a well-formed payload. The ERP-offline degradation
itself is covered exhaustively by ``test_energy_cost_service_q50a`` —
asserting ``erp_available`` here would depend on whether SQL Server is
reachable from the test host.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

import pytest

from src.profit.api.energy import get_real_energy_cost

TENANT = UUID("00000000-0000-0000-0000-000000000001")

# Payload keys the energy service contract guarantees (mirrors
# EnergyCostResult.to_dict()).
_EXPECTED_KEYS = {
    "erp_available", "reason", "date_from", "date_to",
    "tariff_eur_per_kwh", "total_kwh", "total_cost_eur",
    "sample_count", "sensor_count", "items",
}


class _FakeSession:
    """Minimal stand-in — TenantConfigService load is wrapped in try/except
    so a bare session degrades cleanly to the default tariff."""

    async def rollback(self) -> None:  # pragma: no cover — defensive
        pass


# ─── explicit window is echoed back ─────────────────────────────────────


@pytest.mark.asyncio
async def test_endpoint_echoes_explicit_window():
    payload = await get_real_energy_cost(
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 7),
        tenant_id=TENANT,
        session=_FakeSession(),
    )

    assert payload["date_from"] == "2026-05-01"
    assert payload["date_to"] == "2026-05-07"
    assert set(payload.keys()) == _EXPECTED_KEYS
    # The tariff is always surfaced so the UI knows the rate in play,
    # even when the ERP has no samples to return.
    assert payload["tariff_eur_per_kwh"] > 0


# ─── default window: last 7 days ────────────────────────────────────────


@pytest.mark.asyncio
async def test_endpoint_defaults_to_last_seven_days():
    """No dates given → window is [today-7d, today]."""
    payload = await get_real_energy_cost(
        date_from=None,
        date_to=None,
        tenant_id=TENANT,
        session=_FakeSession(),
    )

    today = date.today()
    assert payload["date_to"] == today.isoformat()
    assert payload["date_from"] == (today - timedelta(days=7)).isoformat()


@pytest.mark.asyncio
async def test_endpoint_open_ended_to_defaults_to_today():
    """date_from given, date_to omitted → date_to is today."""
    payload = await get_real_energy_cost(
        date_from=date(2026, 5, 1),
        date_to=None,
        tenant_id=TENANT,
        session=_FakeSession(),
    )

    assert payload["date_from"] == "2026-05-01"
    assert payload["date_to"] == date.today().isoformat()
