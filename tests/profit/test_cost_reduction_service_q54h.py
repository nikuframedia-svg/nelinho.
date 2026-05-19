"""Q.54.H — POST /v1/profit/cost-reduction-suggestions.

Turns the persisted COGS into actionable € reduction suggestions:
detect boats/cost-centres above the per-product-type median, have the
LLM phrase the finding (numbers stay deterministic), and promote an
accepted suggestion into a governance `DecisionRun`.

The LLM is always mocked here (`AsyncMock`) — ZERO live Ollama in tests.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.plan.models.order import OrderStatus, ProductionOrder
from src.profit.models.cost import CalculationStatus, CostCalculation
from src.profit.services.cost_reduction_service import (
    COST_REDUCTION_DECISION_TYPE,
    CostReductionService,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _order(hull: int, ptype: str = "K2") -> ProductionOrder:
    return ProductionOrder(
        id=uuid4(),
        tenant_id=TENANT,
        legacy_id=hull,
        product_name=f"{ptype} Vanquish {hull}",
        product_type=ptype,
        current_phase_name="Lixagem",
        status=OrderStatus.IN_PROGRESS,
    )


def _cost(
    hull: int,
    *,
    material="0",
    labor="0",
    machine="0",
    setup="0",
    overhead="0",
    scrap="0",
    version: int = 1,
) -> CostCalculation:
    total = (
        Decimal(material)
        + Decimal(labor)
        + Decimal(machine)
        + Decimal(setup)
        + Decimal(overhead)
        + Decimal(scrap)
    )
    return CostCalculation(
        id=uuid4(),
        tenant_id=TENANT,
        order_id=str(hull),
        product_id=uuid4(),
        quantity=Decimal("1"),
        calculation_version=version,
        material_cost=Decimal(material),
        labor_cost=Decimal(labor),
        machine_cost=Decimal(machine),
        setup_cost=Decimal(setup),
        overhead_cost=Decimal(overhead),
        scrap_cost=Decimal(scrap),
        total_cogs=total,
        cogs_per_unit=total,
        status=CalculationStatus.CALCULATED,
    )


def _mock_llm(text: str = "Texto LLM redigido.") -> AsyncMock:
    """An LLM client whose `.chat()` returns an Ollama-shaped envelope."""
    client = AsyncMock()
    client.chat = AsyncMock(return_value={"message": {"content": text}})
    return client


@pytest.mark.asyncio
async def test_empty_when_no_orders(fake_session):
    fake_session.queue_scalars([])  # no orders

    out = await CostReductionService(fake_session, TENANT).suggestions(
        llm_client=_mock_llm()
    )
    assert out["count"] == 0
    assert out["suggestions"] == []
    assert "ordens" in out["reason"]


@pytest.mark.asyncio
async def test_empty_when_no_cost_calculations(fake_session):
    fake_session.queue_scalars([_order(101), _order(102), _order(103)])
    fake_session.queue_scalars([])  # no CostCalculation rows

    out = await CostReductionService(fake_session, TENANT).suggestions(
        llm_client=_mock_llm()
    )
    assert out["count"] == 0
    assert "COGS calculado" in out["reason"]


@pytest.mark.asyncio
async def test_no_outliers_when_costs_are_uniform(fake_session):
    # Three K2 boats, all ~equal — no boat above 1.25x the median.
    fake_session.queue_scalars([_order(201), _order(202), _order(203)])
    fake_session.queue_scalars([
        _cost(201, labor="3000", material="5000"),
        _cost(202, labor="3100", material="5050"),
        _cost(203, labor="2950", material="4900"),
    ])

    out = await CostReductionService(fake_session, TENANT).suggestions(
        llm_client=_mock_llm()
    )
    assert out["count"] == 0
    assert "dentro do esperado" in out["reason"]


@pytest.mark.asyncio
async def test_detects_outlier_above_type_median(fake_session):
    # K2 lixagem/labour: 3 boats at ~3000, one at 6000 → outlier.
    fake_session.queue_scalars([
        _order(301), _order(302), _order(303), _order(304),
    ])
    fake_session.queue_scalars([
        _cost(301, labor="3000", material="5000"),
        _cost(302, labor="3000", material="5000"),
        _cost(303, labor="3000", material="5000"),
        _cost(304, labor="6000", material="5000"),  # labour outlier
    ])

    out = await CostReductionService(fake_session, TENANT).suggestions(
        llm_client=_mock_llm("Mão de obra muito acima da mediana.")
    )
    assert out["count"] == 1
    sug = out["suggestions"][0]
    assert sug["order_id"] == "304"
    assert sug["cost_center"] == "labor"
    assert sug["boat_cost_eur"] == 6000.0
    assert sug["baseline_cost_eur"] == 3000.0
    assert sug["overspend_eur"] == 3000.0
    assert sug["overspend_ratio"] == 2.0
    assert sug["explanation"] == "Mão de obra muito acima da mediana."
    assert out["total_opportunity_eur"] == 3000.0


@pytest.mark.asyncio
async def test_numbers_are_deterministic_not_from_llm(fake_session):
    """The LLM only writes prose — the figures come from the analysis.

    Even if the LLM hallucinates numbers in its text, the structured
    fields stay the deterministic median-based figures.
    """
    fake_session.queue_scalars([
        _order(401), _order(402), _order(403), _order(404),
    ])
    fake_session.queue_scalars([
        _cost(401, material="4000"),
        _cost(402, material="4000"),
        _cost(403, material="4000"),
        _cost(404, material="9000"),  # material outlier
    ])

    out = await CostReductionService(fake_session, TENANT).suggestions(
        llm_client=_mock_llm("Custo de 999999 EUR completamente errado.")
    )
    sug = out["suggestions"][0]
    # LLM text is whatever it returned…
    assert "999999" in sug["explanation"]
    # …but the figures are the real ones.
    assert sug["boat_cost_eur"] == 9000.0
    assert sug["baseline_cost_eur"] == 4000.0
    assert sug["overspend_eur"] == 5000.0


@pytest.mark.asyncio
async def test_llm_offline_falls_back_to_deterministic_text(fake_session):
    """Ollama down → suggestion still ships, with templated prose."""
    fake_session.queue_scalars([
        _order(501), _order(502), _order(503), _order(504),
    ])
    fake_session.queue_scalars([
        _cost(501, labor="2000"),
        _cost(502, labor="2000"),
        _cost(503, labor="2000"),
        _cost(504, labor="5000"),
    ])

    crashing = AsyncMock()
    crashing.chat = AsyncMock(side_effect=RuntimeError("Ollama offline"))

    out = await CostReductionService(fake_session, TENANT).suggestions(
        llm_client=crashing
    )
    assert out["count"] == 1
    sug = out["suggestions"][0]
    # Deterministic fallback sentence still carries the real figures.
    assert "5000" in sug["explanation"]
    assert "2000" in sug["explanation"]
    assert "mão de obra" in sug["explanation"]


@pytest.mark.asyncio
async def test_small_sample_type_gets_no_baseline(fake_session):
    """A type with < 3 calculated boats has no median → no false outlier."""
    fake_session.queue_scalars([_order(601, "K4"), _order(602, "K4")])
    fake_session.queue_scalars([
        _cost(601, material="5000"),
        _cost(602, material="20000"),  # huge, but only 2 boats → no baseline
    ])

    out = await CostReductionService(fake_session, TENANT).suggestions(
        llm_client=_mock_llm()
    )
    assert out["count"] == 0


@pytest.mark.asyncio
async def test_outliers_ranked_by_overspend(fake_session):
    fake_session.queue_scalars([
        _order(701), _order(702), _order(703), _order(704), _order(705),
    ])
    fake_session.queue_scalars([
        _cost(701, labor="2000"),
        _cost(702, labor="2000"),
        _cost(703, labor="2000"),
        _cost(704, labor="5000"),   # +3000
        _cost(705, labor="10000"),  # +8000 — biggest leak
    ])

    out = await CostReductionService(fake_session, TENANT).suggestions(
        llm_client=_mock_llm()
    )
    assert out["count"] == 2
    assert out["suggestions"][0]["order_id"] == "705"
    assert out["suggestions"][0]["overspend_eur"] == 8000.0
    assert out["suggestions"][1]["order_id"] == "704"


@pytest.mark.asyncio
async def test_create_decision_from_suggestion(fake_session, monkeypatch):
    """A suggestion promoted to a DecisionRun carries eur_saved so the
    PP1-impact KPI can count it once executed."""
    captured: dict = {}

    async def _fake_propose(**kwargs):
        captured.update(kwargs)
        return {"id": "decision-1", "status": "pending_approval"}

    import src.governance.service as gov_mod

    def _fake_ctor(session, tenant_id):
        inst = AsyncMock()
        inst.propose_decision = _fake_propose
        return inst

    monkeypatch.setattr(gov_mod, "GovernanceService", _fake_ctor)

    suggestion = {
        "order_id": "304",
        "product_type": "K2",
        "cost_center": "labor",
        "boat_cost_eur": 6000.0,
        "baseline_cost_eur": 3000.0,
        "overspend_eur": 3000.0,
        "title": "Barco K2 304: mão de obra +3000 EUR vs mediana K2",
        "explanation": "Mão de obra acima da mediana.",
    }

    out = await CostReductionService(
        fake_session, TENANT
    ).create_decision_from_suggestion(suggestion, proposed_by="luis")

    assert out["status"] == "pending_approval"
    assert captured["decision_type"] == COST_REDUCTION_DECISION_TYPE
    assert captured["proposed_by"] == "luis"
    # The euro figure that the PP1 KPI reads.
    assert captured["expected_impact"]["eur_saved"] == 3000.0
    assert captured["risk_level"] == "low"
    assert captured["action_data"]["order_id"] == "304"
