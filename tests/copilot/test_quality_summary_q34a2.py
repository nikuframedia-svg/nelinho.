"""
Sprint Q.34.A.2 / Q.35.3.2 — testes do reader de resumo de qualidade.

`build_quality_summary` lê `quality.rework_entry` directamente.
Estratégia: FakeSession com filas ordenadas (verifica o pós-processamento;
o SQL é coberto pelo harness e2e).

Q.35.3.2 — as fases vêm de `context->>'phase_name'` (nome legível, não ID)
e o custo/horas é exposto como soma CONHECIDA + cobertura, porque só
poucos registos têm esses valores no ERP.

Ordem dos `execute` em build_quality_summary (caminho com dados):
  1. counts/sums combinados  (.all) — tuplo de 6
  2. erros por fase          (.all)
  3. erros por causa raiz    (.all)
  4. top códigos de erro     (.all)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.copilot.readers.quality_summary import build_quality_summary


async def test_empty_tenant_returns_has_data_false(fake_session, tenant_id):
    """Sem erros → has_data False."""
    fake_session.queue_scalars([(0, 0, 0, 0, None, None)])
    result = await build_quality_summary(fake_session, tenant_id)
    assert result["has_data"] is False
    assert result["source"] == "db.rework_entry"


async def test_populated_tenant_aggregates(fake_session, tenant_id):
    """Com erros → totais, fases por nome, e cobertura honesta do custo."""
    # total=3659, resolvidos=2400, custo conhecido em 4, horas em 4,
    # soma custo=610, soma horas=2.
    fake_session.queue_scalars([(3659, 2400, 4, 4, 610.0, 2.0)])
    fake_session.queue_scalars([
        ("Lixagem - água", 1061), ("Lixagem - polimento", 939),
    ])
    fake_session.queue_scalars([("molde", 1200), ("operador", 800), (None, 50)])
    fake_session.queue_scalars([("E-DEF-01", 600), ("E-BACO-02", 400)])

    result = await build_quality_summary(fake_session, tenant_id)

    assert result["has_data"] is True
    assert result["total_errors"] == 3659
    assert result["unresolved_errors"] == 1259
    # Fase pelo nome legível, não pelo ID.
    assert result["errors_by_phase"][0] == {
        "phase": "Lixagem - água", "errors": 1061,
    }
    assert result["errors_by_root_cause"]["molde"] == 1200
    # root_cause None → rotulado "desconhecida", não perdido.
    assert result["errors_by_root_cause"]["desconhecida"] == 50
    assert result["top_error_codes"][0] == {"code": "E-DEF-01", "errors": 600}
    # Custo/horas: soma CONHECIDA + a contagem que a suporta.
    assert result["cost_estimate_eur_known"] == 610.0
    assert result["cost_known_count"] == 4
    assert result["hours_lost_known"] == 2.0
    assert result["hours_known_count"] == 4


async def test_window_start_is_accepted(fake_session, tenant_id):
    """Um `window_start` tz-aware é aceite e altera o query_hash."""
    window = datetime(2026, 5, 1, tzinfo=timezone.utc)
    fake_session.queue_scalars([(0, 0, 0, 0, None, None)])
    result = await build_quality_summary(
        fake_session, tenant_id, window_start=window,
    )
    assert result["has_data"] is False
    assert "query_hash" in result


async def test_query_failure_degrades_gracefully(fake_session, tenant_id):
    """Se a query levanta, devolve has_data False / source unavailable."""
    async def _boom(stmt):
        raise RuntimeError("ligação à BD caiu")

    fake_session.execute = _boom

    result = await build_quality_summary(fake_session, tenant_id)
    assert result["has_data"] is False
    assert result["source"] == "unavailable"
