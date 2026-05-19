"""
Sprint Q.34.A.4 — testes do FACT PACK de produção & qualidade.

`_render_production_fact_pack` / `_render_quality_fact_pack` constroem o
bloco de texto que o `_render_prompt` injecta no prompt, dizendo ao LLM
que números reais usar e como os citar.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.copilot.service import (
    CopilotService,
    _render_production_fact_pack,
    _render_quality_fact_pack,
)

PRODUCTION = {
    "has_data": True,
    "source": "db.production_orders",
    "query_hash": "abc123",
    "orders_total": 521,
    # Q.35.3.1 — WIP real (164) ≠ ordens totais; 357 já entregues.
    "orders_in_production": 164,
    "orders_delivered_or_stored": 357,
    "wip_by_phase": [{"phase": "Laminagem", "orders": 120}],
    "delivered_or_stored_by_phase": [{"phase": "Entregue", "orders": 329}],
    "wip_by_product_type": {"K1": 300},
    "orders_by_transport_date": [{"date": "2026-05-20", "orders": 14}],
    "oldest_in_progress_created": "2026-05-01",
}
QUALITY = {
    "has_data": True,
    "source": "db.rework_entry",
    "query_hash": "def456",
    "total_errors": 3659,
    "unresolved_errors": 1259,
    "errors_by_phase": [{"phase": "Lixagem - água", "errors": 1061}],
    "errors_by_root_cause": {"molde": 1200},
    # Q.35.3.2 — custo conhecido em poucos registos, com a contagem.
    "cost_estimate_eur_known": 610.0,
    "cost_known_count": 4,
    "hours_lost_known": 2.0,
    "hours_known_count": 4,
}


def test_production_fact_pack_renders_real_numbers():
    block = _render_production_fact_pack(PRODUCTION)
    assert "PRODUÇÃO" in block
    assert "521" in block
    assert "table:plan.production_orders;query_hash:abc123" in block
    assert "Laminagem 120" in block
    # O WIP real é dito ao LLM — não confundir com as 521 ordens totais.
    assert "164" in block


def test_production_fact_pack_marks_delivered_not_wip():
    """O fact pack diz explicitamente que Entregue/Armazem não são WIP —
    senão o copiloto chama a fase 'Entregue' o maior gargalo."""
    block = _render_production_fact_pack(PRODUCTION)
    assert "357" in block
    assert "não são produção" in block


def test_production_fact_pack_empty_when_no_data():
    assert _render_production_fact_pack({"has_data": False}) == ""
    assert _render_production_fact_pack({}) == ""


def test_quality_fact_pack_renders_real_numbers():
    block = _render_quality_fact_pack(QUALITY)
    assert "QUALIDADE" in block
    assert "3659" in block
    assert "table:quality.rework_entry;query_hash:def456" in block
    assert "Lixagem - água 1061" in block


def test_quality_fact_pack_marks_cost_coverage():
    """O custo só existe em 4 de 3659 erros — o fact pack tem de o dizer,
    senão o copiloto reporta €610 como o custo total da qualidade."""
    block = _render_quality_fact_pack(QUALITY)
    assert "4 de 3659" in block
    assert "NÃO apresentar este valor como o custo total" in block


def test_quality_fact_pack_skips_legacy_source():
    """A camada antiga (factory_data_product) não tem o mesmo contrato
    (query_hash) — não se renderiza para não dar uma citação inválida."""
    legacy = {
        "has_data": True, "source": "factory_data_product", "total_errors": 5,
    }
    assert _render_quality_fact_pack(legacy) == ""


async def test_render_prompt_includes_production_fact_pack(
    fake_session, tenant_id,
):
    """`_render_prompt` num intent genérico injecta o FACT PACK de
    produção & qualidade com números reais."""
    svc = CopilotService(fake_session, tenant_id, uuid4(), "OPERATOR")
    ctx = {"production": PRODUCTION, "quality": QUALITY}
    prompt = await svc._render_prompt(
        "estado da fábrica", ctx, [], intent="generic",
    )
    assert "FACT PACK (Produção & Qualidade" in prompt
    assert "521" in prompt
    assert "table:plan.production_orders" in prompt
    assert "3659" in prompt
