"""Unit tests for EnergyCostService — Sprint Q.50.A (F8).

Synthetic ``IotSensorDataRow`` fixtures, no live DB. The service takes an
injectable sensor fetcher: tests feed canned IoT samples and a fetcher
that raises ``RuntimeError`` simulates the ERP being offline
(``sqlserver_enabled=False``).

The kWh maths is deliberately exercised with a known sampling cadence so
the expected energy is hand-computable: power (W) × step (h) / 1000.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from src.adapters.nelo.schemas import IotSensorDataRow
from src.profit.services.energy_cost_service import (
    DEFAULT_TARIFF_EUR_PER_KWH,
    ERP_OFFLINE_REASON,
    EnergyCostService,
)


def _sample(
    *,
    sample_id: int = 1,
    sensor_id: int = 1,
    sampled_at: datetime,
    power_1: int | None = 1000,
    power_2: int | None = 1000,
    power_3: int | None = 1000,
) -> IotSensorDataRow:
    return IotSensorDataRow(
        sample_id=sample_id,
        sensor_id=sensor_id,
        sampled_at=sampled_at,
        power_1=power_1,
        power_2=power_2,
        power_3=power_3,
    )


def _fetcher(samples: list[IotSensorDataRow]):
    async def _fetch(date_from, date_to) -> list[IotSensorDataRow]:
        return samples

    return _fetch


# ─── kWh integration: known cadence ─────────────────────────────────────


@pytest.mark.asyncio
async def test_energy_kwh_from_hourly_samples():
    """Four hourly samples at 3 kW total → step 1 h → 3 kWh per interval.

    The integration multiplies each sample's power by the median step,
    so 4 samples × 3000 W × 1 h / 1000 = 12 kWh on the day.
    """
    samples = [
        _sample(sample_id=i, sampled_at=datetime(2026, 5, 1, 8 + i))
        for i in range(4)
    ]
    svc = EnergyCostService(
        tariff_eur_per_kwh=Decimal("0.20"),
        sensor_fetcher=_fetcher(samples),
    )
    from datetime import date

    result = await svc.energy_cost(date(2026, 5, 1), date(2026, 5, 1))

    assert result.erp_available is True
    assert result.total_kwh == 12.0
    # 12 kWh × €0.20/kWh = €2.40
    assert result.total_cost_eur == 2.40
    assert result.sample_count == 4
    assert result.sensor_count == 1


@pytest.mark.asyncio
async def test_energy_cost_uses_configured_tariff():
    """The € figure scales with the tariff — same kWh, different €."""
    samples = [
        _sample(sample_id=i, sampled_at=datetime(2026, 5, 1, 8 + i))
        for i in range(4)
    ]
    from datetime import date

    cheap = EnergyCostService(
        tariff_eur_per_kwh=Decimal("0.10"), sensor_fetcher=_fetcher(samples)
    )
    expensive = EnergyCostService(
        tariff_eur_per_kwh=Decimal("0.30"), sensor_fetcher=_fetcher(samples)
    )
    r_cheap = await cheap.energy_cost(date(2026, 5, 1), date(2026, 5, 1))
    r_exp = await expensive.energy_cost(date(2026, 5, 1), date(2026, 5, 1))

    assert r_cheap.total_kwh == r_exp.total_kwh == 12.0
    assert r_cheap.total_cost_eur == 1.20
    assert r_exp.total_cost_eur == 3.60


# ─── three phases summed, NULL treated as zero ──────────────────────────


@pytest.mark.asyncio
async def test_null_phase_power_treated_as_zero():
    """A sample with one NULL phase counts only the populated phases."""
    samples = [
        _sample(
            sample_id=1, sampled_at=datetime(2026, 5, 1, 8),
            power_1=2000, power_2=None, power_3=1000,
        ),
        _sample(
            sample_id=2, sampled_at=datetime(2026, 5, 1, 9),
            power_1=2000, power_2=None, power_3=1000,
        ),
    ]
    from datetime import date

    svc = EnergyCostService(
        tariff_eur_per_kwh=Decimal("1.00"), sensor_fetcher=_fetcher(samples)
    )
    result = await svc.energy_cost(date(2026, 5, 1), date(2026, 5, 1))

    # 3000 W per sample, step 1 h → 2 × 3 kWh = 6 kWh
    assert result.total_kwh == 6.0


# ─── per sensor × day grain ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rows_split_by_sensor_and_day():
    """Two sensors over two days → four sensor×day rows."""
    samples = [
        _sample(sample_id=1, sensor_id=10, sampled_at=datetime(2026, 5, 1, 8)),
        _sample(sample_id=2, sensor_id=10, sampled_at=datetime(2026, 5, 1, 9)),
        _sample(sample_id=3, sensor_id=10, sampled_at=datetime(2026, 5, 2, 8)),
        _sample(sample_id=4, sensor_id=10, sampled_at=datetime(2026, 5, 2, 9)),
        _sample(sample_id=5, sensor_id=20, sampled_at=datetime(2026, 5, 1, 8)),
        _sample(sample_id=6, sensor_id=20, sampled_at=datetime(2026, 5, 1, 9)),
        _sample(sample_id=7, sensor_id=20, sampled_at=datetime(2026, 5, 2, 8)),
        _sample(sample_id=8, sensor_id=20, sampled_at=datetime(2026, 5, 2, 9)),
    ]
    from datetime import date

    svc = EnergyCostService(
        tariff_eur_per_kwh=Decimal("0.18"), sensor_fetcher=_fetcher(samples)
    )
    result = await svc.energy_cost(date(2026, 5, 1), date(2026, 5, 2))

    assert result.sensor_count == 2
    assert len(result.rows) == 4
    # Ordered by (day, sensor_id).
    assert [(r.day, r.sensor_id) for r in result.rows] == [
        ("2026-05-01", 10),
        ("2026-05-01", 20),
        ("2026-05-02", 10),
        ("2026-05-02", 20),
    ]


# ─── single sample → no measurable interval ─────────────────────────────


@pytest.mark.asyncio
async def test_single_sample_yields_zero_energy():
    """One sample for a sensor has no interval — energy is 0, not invented."""
    samples = [_sample(sample_id=1, sampled_at=datetime(2026, 5, 1, 8))]
    from datetime import date

    svc = EnergyCostService(
        tariff_eur_per_kwh=Decimal("0.18"), sensor_fetcher=_fetcher(samples)
    )
    result = await svc.energy_cost(date(2026, 5, 1), date(2026, 5, 1))

    assert result.total_kwh == 0.0
    assert result.total_cost_eur == 0.0
    assert result.sample_count == 1


@pytest.mark.asyncio
async def test_duplicate_timestamps_do_not_break_step():
    """Two samples at the very same instant give no positive interval —
    energy stays 0 rather than dividing by a zero step."""
    samples = [
        _sample(sample_id=1, sampled_at=datetime(2026, 5, 1, 8)),
        _sample(sample_id=2, sampled_at=datetime(2026, 5, 1, 8)),
    ]
    from datetime import date

    svc = EnergyCostService(
        tariff_eur_per_kwh=Decimal("0.18"), sensor_fetcher=_fetcher(samples)
    )
    result = await svc.energy_cost(date(2026, 5, 1), date(2026, 5, 1))

    assert result.total_kwh == 0.0


# ─── ERP offline degradation ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_erp_offline_yields_explicit_empty_result():
    """When the ERP adapter raises RuntimeError (sqlserver_enabled=False)
    the service returns erp_available=False with a reason — never a
    fabricated kWh number. ZERO MOCKS."""

    async def _explode(date_from, date_to):
        raise RuntimeError("sqlserver_enabled=False or sqlserver_url=None.")

    from datetime import date

    svc = EnergyCostService(
        tariff_eur_per_kwh=Decimal("0.18"), sensor_fetcher=_explode
    )
    result = await svc.energy_cost(date(2026, 5, 1), date(2026, 5, 1))

    assert result.erp_available is False
    assert result.reason == ERP_OFFLINE_REASON
    assert result.rows == []
    assert result.total_kwh == 0.0
    assert result.total_cost_eur == 0.0
    # The tariff is still echoed back so the UI knows the rate in play.
    assert result.tariff_eur_per_kwh == 0.18


# ─── default tariff fallback ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_default_tariff_when_none_passed():
    """Constructing without a tariff falls back to the documented default."""
    svc = EnergyCostService(sensor_fetcher=_fetcher([]))
    assert svc.tariff_eur_per_kwh == DEFAULT_TARIFF_EUR_PER_KWH

    from datetime import date

    result = await svc.energy_cost(date(2026, 5, 1), date(2026, 5, 1))
    assert result.tariff_eur_per_kwh == float(DEFAULT_TARIFF_EUR_PER_KWH)
    assert result.erp_available is True
    assert result.total_kwh == 0.0


# ─── to_dict shape ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_result_to_dict_shape():
    samples = [
        _sample(sample_id=i, sampled_at=datetime(2026, 5, 1, 8 + i))
        for i in range(3)
    ]
    from datetime import date

    svc = EnergyCostService(
        tariff_eur_per_kwh=Decimal("0.18"), sensor_fetcher=_fetcher(samples)
    )
    result = await svc.energy_cost(date(2026, 5, 1), date(2026, 5, 1))
    payload = result.to_dict()

    assert set(payload.keys()) == {
        "erp_available", "reason", "date_from", "date_to",
        "tariff_eur_per_kwh", "total_kwh", "total_cost_eur",
        "sample_count", "sensor_count", "items",
    }
    assert isinstance(payload["items"], list)
    item = payload["items"][0]
    assert set(item.keys()) == {
        "sensor_id", "day", "kwh", "cost_eur", "sample_count",
    }
