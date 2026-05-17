"""Q.24.D — time-mining runs on the demo package's operation history.

The Q.24.D builder extension bundles each OF's `OF_FP` rows. Driving the
time_mining mirror with the demo source then fills
`routing_template_phase.duration_p50_h/p90_h` from the **real** operation
spans — never from standard coefficients.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from src.adapters.nelo import demo_source
from src.adapters.nelo.etl.master_data import mirror_master_data
from src.adapters.nelo.etl.time_mining import mirror_time_mining
from src.plan.models.routing_template import RoutingTemplatePhase


@pytest.fixture(autouse=True)
def _clean_cache():
    demo_source._load.cache_clear()
    yield
    demo_source._load.cache_clear()


def _routing(routing_id: int, product_id: int, phase_id: int, seq: int) -> dict:
    return {
        "routing_id": routing_id,
        "product_id": product_id,
        "phase_id": phase_id,
        "phase_name": f"Fase {phase_id}",
        "sequence": seq,
        "time_hours": 1.0,
        "phase_hour_coefficient": 1.0,
        "k1_reference_hours": 1.0,
        "k2_reference_hours": 1.0,
        "k4_reference_hours": 1.0,
        "phase_is_production": True,
        "phase_is_automatic": False,
        "routing_in_production": True,
        "routing_coefficient": 1.0,
        "routing_coefficient_x": 0.0,
    }


def _op(operation_id: int, phase_id: int, start: str, end: str) -> dict:
    return {
        "operation_id": operation_id,
        "work_order_id": 9001,
        "phase_id": phase_id,
        "phase_name": f"Fase {phase_id}",
        "start_at": start,
        "end_at": end,
    }


def _package() -> dict:
    """One order, product 42, two phases — operations give phase 3 a real
    4 h span and phase 4 a 2 h span."""
    return {
        "generated_at": "2026-03-01T00:00:00",
        "source": "test",
        "order_count": 1,
        "orders": [
            {
                "order": {
                    "work_order_id": 9001,
                    "cost_price": 100.0,
                    "sale_price": 200.0,
                    "discount": 0.0,
                    "paid_amount": 200.0,
                    "coefficient_eur": 0.0,
                    "is_paid": True,
                    "supervised": False,
                    "sequence": 1,
                    "product_id": 42,
                    "current_phase_id": 3,
                    "warehouse_id": 1,
                },
                "routing": [_routing(1, 42, 3, 1), _routing(2, 42, 4, 2)],
                "bom": [],
                "movements": [],
                "operations": [
                    _op(1, 3, "2026-03-01T08:00:00", "2026-03-01T12:00:00"),
                    _op(2, 4, "2026-03-02T08:00:00", "2026-03-02T10:00:00"),
                ],
            }
        ],
    }


async def test_time_mining_fills_durations_from_real_spans(
    recording_session, monkeypatch, tmp_path
):
    path = tmp_path / "demo.json"
    path.write_text(json.dumps(_package()), encoding="utf-8")
    monkeypatch.setenv("DEMO_PACKAGE_PATH", str(path))
    demo_source._load.cache_clear()

    tenant = uuid4()
    # 1. master mirror builds the routing template (durations stay NULL).
    await mirror_master_data(
        session=recording_session, tenant_id=tenant, source=demo_source
    )
    phases = [
        o for o in recording_session.added if isinstance(o, RoutingTemplatePhase)
    ]
    assert len(phases) == 2
    assert all(p.duration_p50_h is None for p in phases)

    # 2. time_mining mines the real spans into p50/p90.
    result = await mirror_time_mining(
        session=recording_session, tenant_id=tenant, source=demo_source
    )
    assert result.status == "ok"
    assert result.rows_updated == 2

    by_phase = {p.phase_id: p for p in phases}
    assert float(by_phase["3"].duration_p50_h) == pytest.approx(4.0, abs=0.01)
    assert float(by_phase["4"].duration_p50_h) == pytest.approx(2.0, abs=0.01)
