"""
Sprint Q.34.A.1 / Q.35.3.1 — testes do reader de resumo de produção.

`build_production_summary` lê `plan.production_orders` directamente.
Estratégia: FakeSession com filas ordenadas — o FakeSession devolve o que
está em fila pela ordem dos `execute`, ignorando o SQL. Os testes
verificam o pós-processamento (nomes de chaves, agregação); a correcção
do SQL é coberta pelo harness e2e contra o Postgres real.

Q.35.3.1 — o `status` vem todo IN_PROGRESS do sync, não é sinal. O estado
real está no `current_phase_name`. O reader separa WIP real (fases de
produção) de ordens já entregues/armazenadas/embaladas.

Ordem dos `execute` em build_production_summary (caminho com dados):
  1. contagem por fase actual  (.all)
  2. WIP por tipo de produto   (.all)
  3. ordens por transporte     (.all)
  4. ordem mais antiga         (.scalar_one_or_none)
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.copilot.readers.production_summary import build_production_summary


async def test_empty_tenant_returns_has_data_false(fake_session, tenant_id):
    """Sem ordens → has_data False, sem inventar agregados."""
    fake_session.queue_scalars([])  # contagem por fase: vazio
    result = await build_production_summary(fake_session, tenant_id)
    assert result["has_data"] is False
    assert result["source"] == "db.production_orders"
    assert "query_hash" in result


async def test_non_production_phases_excluded_from_wip(
    fake_session, tenant_id,
):
    """Entregue/Armazem/Embalado NÃO contam como WIP — são ordens que já
    saíram do chão de fábrica. WIP real = só as fases de produção."""
    d1 = date.today() + timedelta(days=2)
    # "Armazem" sem acento, como o ERP grava — tem de bater com a config
    # "Armazém" mesmo assim (comparação accent-insensitive).
    fake_session.queue_scalars([
        ("Entregue", 329),
        ("Laminagem peças", 64),
        ("Corte peças", 55),
        ("Armazem", 26),
        ("Embalado", 2),
        ("Cura", 3),
    ])
    fake_session.queue_scalars([("K1", 300), ("K2", 150)])
    fake_session.queue_scalars([(d1, 14)])
    # `oldest` é o 4.º execute → 3 placeholders no scalar queue + a data.
    fake_session.queue_scalar(None)
    fake_session.queue_scalar(None)
    fake_session.queue_scalar(None)
    fake_session.queue_scalar(date(2026, 5, 1))

    result = await build_production_summary(fake_session, tenant_id)

    assert result["has_data"] is True
    assert result["orders_total"] == 479
    # 329 Entregue + 26 Armazem + 2 Embalado = 357 fora de produção.
    assert result["orders_delivered_or_stored"] == 357
    # 64 + 55 + 3 = 122 em produção real.
    assert result["orders_in_production"] == 122
    # WIP por fase só lista fases de produção, ordenadas desc.
    assert result["wip_by_phase"] == [
        {"phase": "Laminagem peças", "orders": 64},
        {"phase": "Corte peças", "orders": 55},
        {"phase": "Cura", "orders": 3},
    ]
    # As fases administrativas ficam num bucket separado, não perdidas.
    assert {"phase": "Entregue", "orders": 329} in (
        result["delivered_or_stored_by_phase"]
    )
    assert result["wip_by_product_type"]["K1"] == 300
    assert result["orders_by_transport_date"] == [
        {"date": d1.isoformat(), "orders": 14},
    ]
    assert result["oldest_in_progress_created"] == "2026-05-01"


async def test_all_phases_productive_means_no_delivered(
    fake_session, tenant_id,
):
    """Sem fases administrativas → tudo é WIP, delivered = 0."""
    fake_session.queue_scalars([("Laminagem", 120), ("Montagem", 40)])
    fake_session.queue_scalars([("K1", 160)])
    fake_session.queue_scalars([])
    fake_session.queue_scalar(None)
    fake_session.queue_scalar(None)
    fake_session.queue_scalar(None)
    fake_session.queue_scalar(None)

    result = await build_production_summary(fake_session, tenant_id)

    assert result["orders_total"] == 160
    assert result["orders_in_production"] == 160
    assert result["orders_delivered_or_stored"] == 0
    assert result["delivered_or_stored_by_phase"] == []


async def test_query_failure_degrades_gracefully(fake_session, tenant_id):
    """Se a query levanta, devolve has_data False / source unavailable —
    o copiloto cai em "sem dados", não rebenta."""
    async def _boom(stmt):
        raise RuntimeError("ligação à BD caiu")

    fake_session.execute = _boom

    result = await build_production_summary(fake_session, tenant_id)
    assert result["has_data"] is False
    assert result["source"] == "unavailable"
