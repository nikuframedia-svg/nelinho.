"""
Sprint Q.34.A.3 — testes do wiring dos readers no `build_context_facts`.

O `context_builder` passa a ler `plan.production_orders` e
`quality.rework_entry` (populados) em vez da camada Factory Data Product
in-memory (vazia). Estratégia: mockar os dois readers e verificar que o
contexto resultante vira o `data_status` e expõe os dados.
"""

from __future__ import annotations

import pytest

from src.copilot.context_builder import (
    _build_operational_snapshot,
    build_context_facts,
)


async def test_operational_snapshot_prefers_production_summary():
    """Com production_summary com dados → has_data True, contagens reais,
    e os KPIs sem evidência (oee/availability) ficam None — honesto."""
    prod = {
        "has_data": True,
        "orders_total": 521,
        "orders_in_production": 164,
        "orders_delivered_or_stored": 357,
        "wip_by_phase": [{"phase": "Laminagem", "orders": 120}],
    }
    snap = await _build_operational_snapshot(
        None, None, None, False,
        kpi_snapshot=None, production_summary=prod,
    )
    assert snap["has_data"] is True
    assert snap["data_status"] == "DATA_AVAILABLE"
    assert snap["orders_total"] == 521
    # Q.35.3.1 — WIP real, não as 521 ordens totais.
    assert snap["orders_in_production"] == 164
    assert snap["orders_delivered_or_stored"] == 357
    assert snap["top_phases_by_wip"] == [{"phase": "Laminagem", "orders": 120}]
    # Sem actuals em Postgres → não se inventa OEE.
    assert snap["oee"] is None
    assert snap["availability"] is None


async def test_operational_snapshot_no_data_when_both_sources_empty():
    """Sem kpi_snapshot e sem production_summary → NO_DATA_AVAILABLE."""
    snap = await _build_operational_snapshot(
        None, None, None, False,
        kpi_snapshot=None, production_summary={"has_data": False},
    )
    assert snap["has_data"] is False
    assert snap["data_status"] == "NO_DATA_AVAILABLE"


async def test_build_context_facts_uses_db_readers(
    fake_session, tenant_id, monkeypatch,
):
    """`build_context_facts` engata os readers DB: o operational_snapshot
    fica DATA_AVAILABLE e a quality vem de `db.rework_entry`."""
    async def _fake_prod(session, tid):
        return {
            "has_data": True,
            "source": "db.production_orders",
            "orders_total": 521,
            "orders_in_production": 164,
            "orders_delivered_or_stored": 357,
            "wip_by_phase": [{"phase": "Laminagem", "orders": 120}],
        }

    async def _fake_qual(session, tid, window_start=None):
        return {
            "has_data": True,
            "source": "db.rework_entry",
            "total_errors": 3659,
        }

    monkeypatch.setattr(
        "src.copilot.context_builder.build_production_summary", _fake_prod,
    )
    monkeypatch.setattr(
        "src.copilot.context_builder.build_quality_summary", _fake_qual,
    )

    ctx = await build_context_facts(fake_session, tenant_id, 24, "OPERATOR")

    assert ctx["production"]["has_data"] is True
    assert ctx["operational_snapshot"]["has_data"] is True
    assert ctx["operational_snapshot"]["data_status"] == "DATA_AVAILABLE"
    assert ctx["operational_snapshot"]["orders_total"] == 521
    assert ctx["operational_snapshot"]["top_phases_by_wip"]
    assert ctx["quality"]["source"] == "db.rework_entry"
    assert ctx["quality"]["total_errors"] == 3659
