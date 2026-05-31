"""Q.131.G — fallback de routing-template (routing master do ERP, PRODUTO_FASE).

Recupera modelos sem ≥2 observações por fase em of_fp usando
`plan.model_routing_assignment` JOIN `routing_template_phase` (rota real do ERP +
`duration_p50_h` minerado de of_fp por time_mining). Ainda dados REAIS — NÃO o
buffer 2× sintético, logo `source="db_template"` não conta como fallback.

Unit (sem BD): mocka `session.execute`; a verificação contra a BD real
(cobertura 73%→~99%) está em `_audit/q131/verify_real_schedule.py`.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.plan.cpo.state import FactoryState, _load_route_templates_db
from src.plan.services.routing_resolver import RoutingResolver


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, *result_sets):
        self._results = list(result_sets)
        self._i = 0

    async def execute(self, *args, **kwargs):
        rows = self._results[self._i] if self._i < len(self._results) else []
        self._i += 1
        return _FakeResult(rows)


@pytest.mark.asyncio
async def test_load_route_templates_builds_by_model_ordered():
    rows = [
        {"model_id": "42366", "seq": 11, "phase_id": "2", "phase_name": "Cura",
         "duration_p50_h": 17.38, "requires_mold": False, "team_size_default": 1},
        {"model_id": "42366", "seq": 10, "phase_id": "1", "phase_name": "Laminagem",
         "duration_p50_h": 4.32, "requires_mold": True, "team_size_default": 2},
        {"model_id": "99999", "seq": 1, "phase_id": "18", "phase_name": "Pintura",
         "duration_p50_h": None, "requires_mold": False, "team_size_default": 1},
    ]
    templates = await _load_route_templates_db(_FakeSession(rows), uuid4())

    assert set(templates) == {"42366", "99999"}
    # ordenado por seq dentro de cada modelo
    seqs = [s["sequence"] for s in templates["42366"]]
    assert seqs == [10, 11]
    assert templates["42366"][0]["fase_nome"] == "Laminagem"
    assert templates["42366"][0]["duration_p50_h"] == pytest.approx(4.32)
    # p50 NULL preservado como None (o resolver decide a duração)
    assert templates["99999"][0]["duration_p50_h"] is None


@pytest.mark.asyncio
async def test_load_route_templates_session_none_is_safe():
    assert await _load_route_templates_db(None, uuid4()) == {}


def test_resolver_uses_template_with_db_template_source():
    """Keyspace OF_P_ID: modelo_id numérico casa com a chave do template."""
    state = FactoryState(tenant_id=uuid4())
    state.template_routes_by_model = {
        "42366": [
            {"fase_id": "2", "fase_nome": "Cura", "sequence": 11,
             "duration_p50_h": 17.38, "requires_mold": False, "team_size_default": 1},
            {"fase_id": "1", "fase_nome": "Laminagem", "sequence": 10,
             "duration_p50_h": 4.32, "requires_mold": True, "team_size_default": 2},
        ]
    }
    resolver = RoutingResolver(state)
    rows = resolver._template_for_model_db("42366")

    assert [r.fase_nome for r in rows] == ["Laminagem", "Cura"]  # por seq
    assert all(r.source == "db_template" for r in rows)
    assert rows[0].duration_hours == pytest.approx(4.32)
    # modelo sem template -> [] (cai no standard, depois unplanned)
    assert resolver._template_for_model_db("desconhecido") == []


def test_template_uses_fase_median_when_p50_null():
    state = FactoryState(tenant_id=uuid4())
    state.historical_durations_by_fase = {"18": 3.18}  # mediana real cross-modelo
    state.template_routes_by_model = {
        "42366": [
            {"fase_id": "18", "fase_nome": "Pintura", "sequence": 1,
             "duration_p50_h": None, "requires_mold": False, "team_size_default": 1},
        ]
    }
    rows = RoutingResolver(state)._template_for_model_db("42366")
    assert len(rows) == 1
    assert rows[0].duration_hours == pytest.approx(3.18)  # real, não inventado


def test_template_abandons_order_when_phase_has_no_real_duration():
    """Honestidade Spelke: fase sem p50 NEM mediana-por-fase → ordem inteira
    por planear (return []), NUNCA duração inventada."""
    state = FactoryState(tenant_id=uuid4())
    state.historical_durations_by_fase = {}  # nenhuma mediana
    state.template_routes_by_model = {
        "42366": [
            {"fase_id": "1", "fase_nome": "Laminagem", "sequence": 1,
             "duration_p50_h": 4.32, "requires_mold": True, "team_size_default": 1},
            {"fase_id": "77", "fase_nome": "Fase Rara", "sequence": 2,
             "duration_p50_h": None, "requires_mold": False, "team_size_default": 1},
        ]
    }
    # a 2ª fase não tem duração real -> a ordem inteira é abandonada
    assert RoutingResolver(state)._template_for_model_db("42366") == []


def test_db_template_never_counts_as_synthetic_fallback():
    """Property: rota via template = dados reais (ERP + p50 minerado), logo
    `fallback_ops`/`fallback_fraction` (que só contam `source=='standard'`)
    ficam a zero. O plano não é `degraded` por usar templates."""
    state = FactoryState(tenant_id=uuid4())
    state.template_routes_by_model = {
        "42366": [
            {"fase_id": "1", "fase_nome": "Laminagem", "sequence": 1,
             "duration_p50_h": 4.32, "requires_mold": True, "team_size_default": 1},
            {"fase_id": "2", "fase_nome": "Cura", "sequence": 2,
             "duration_p50_h": 17.38, "requires_mold": False, "team_size_default": 1},
        ]
    }
    resolver = RoutingResolver(state)
    ops = resolver.resolve({"of_id": "OF-1", "modelo_id": "42366"})

    assert len(ops) == 2          # planeado via template
    assert resolver.fallback_ops == 0
    assert resolver.fallback_fraction == 0.0
