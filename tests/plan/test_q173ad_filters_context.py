"""Q.173.AD — contexto de filtros do Gantt.

O frontend precisa de mapas (nomes/gama/setor/due/risco/boost) para os 12
filtros da Fase 6 sem inchar o payload do plano. Estes testes prendem o
shape e os comportamentos honestos (sem forecast → risco vazio, nunca
inventado; cache TTL etiquetada como stale).
"""
from __future__ import annotations

from uuid import uuid4

import pytest

import src.plan.api.filters_context as fc


@pytest.mark.asyncio
async def test_orders_material_risk_sem_forecast_devolve_vazio(monkeypatch):
    """Forecast indisponível → lista vazia (estado honesto, nunca inventa)."""
    tenant = uuid4()
    fc._risk_cache.pop(tenant, None)

    class _Boom:
        def __init__(self, *a, **kw):
            pass

        async def forecast(self):
            raise ValueError("BD indisponível")

    import src.supply.services.shortage_forecast_service as sfs

    monkeypatch.setattr(sfs, "ShortageForecastService", _Boom)
    out, stale = await fc._orders_material_risk(object(), tenant)
    assert out == []
    assert stale is False


@pytest.mark.asyncio
async def test_orders_material_risk_cache_ttl_marca_stale(monkeypatch):
    tenant = uuid4()
    calls = {"n": 0}

    class _Fake:
        def __init__(self, *a, **kw):
            pass

        async def forecast(self):
            calls["n"] += 1

            class _O:
                order_id = "902252"

            class _M:
                ordens_afetadas = [_O()]

            class _R:
                materiais_em_risco = [_M()]

            return _R()

    import src.supply.services.shortage_forecast_service as sfs

    monkeypatch.setattr(sfs, "ShortageForecastService", _Fake)
    fc._risk_cache.pop(tenant, None)

    out1, stale1 = await fc._orders_material_risk(object(), tenant)
    out2, stale2 = await fc._orders_material_risk(object(), tenant)
    assert out1 == out2 == ["902252"]
    assert stale1 is False and stale2 is True  # 2ª veio da cache TTL
    assert calls["n"] == 1  # o motor caro só correu uma vez


def test_shape_do_contexto_tem_os_campos_dos_12_filtros():
    out = fc.FiltersContextOut()
    campos = set(out.model_dump().keys())
    assert {
        "commit_sha", "product_names", "order_products", "product_gamas",
        "phase_sectors", "orders_boost", "orders_due",
        "orders_material_risk", "repair_phase_ids", "material_risk_stale",
    } <= campos
