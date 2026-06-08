"""Q.166.D — calibração de duração: touch-time consolidado + rota canónica filtrada.

planning_duration_h: estado→~0, FP_VALOR_REF→ele, p25-flow→ele, senão flow. A rota
canónica só inclui fases COMUNS (boat_fraction >= limiar) — fases raras (ex.
Acabamento 3) deixam de ser metidas em barcos sem rota (gargalo fantasma).
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from src.plan.cpo.state import FactoryState
from src.plan.services.routing_resolver import RoutingResolver

TENANT = UUID("11111111-1111-1111-1111-111111111111")


def test_planning_duration_cascade():
    s = FactoryState(tenant_id=TENANT)
    s.phase_std_ref_hours = {"5": {"K1": 3.0}}
    s.model_kayak_class = {"MOD_K1": "K1"}
    s.phase_p25_hours = {"63": 0.75, "5": 99.0}  # 5 tem std_ref → ignora p25

    # 1) fase de estado → ~0 (1 min)
    assert s.planning_duration_h("11", "MOD_K1", 40.0) == 1.0 / 60.0
    assert s.planning_duration_h("32", "qualquer", 40.0) == 1.0 / 60.0
    # 2) FP_VALOR_REF tem precedência sobre p25 e flow
    assert s.planning_duration_h("5", "MOD_K1", 24.0) == 3.0
    # 3) sem std_ref → p25-flow
    assert s.planning_duration_h("63", "MOD_DESCONHECIDO", 27.0) == 0.75
    # 4) sem std_ref nem p25 → fallback flow
    assert s.planning_duration_h("99", "MOD_X", 12.0) == 12.0


def test_canoe_class_map_values():
    from src.plan.cpo.state_loaders import _CANOE_CLASS_MAP
    assert _CANOE_CLASS_MAP["C1"] == "K1"
    assert _CANOE_CLASS_MAP["C2"] == "K2"
    assert _CANOE_CLASS_MAP["C4"] == "K4"
    assert _CANOE_CLASS_MAP["V1"] == "K1"
    assert _CANOE_CLASS_MAP["K5"] == "K4"


def _stub_engine_empty():
    return SimpleNamespace(_active_ingestion_id=None, _curated_data={})


def test_canonical_route_excludes_rare_phases(monkeypatch):
    # Modelo sem rota → canonical. Catálogo: fase comum (50% barcos) + fase rara
    # (3% barcos, ex. Acabamento 3). Só a comum entra.
    s = FactoryState(tenant_id=TENANT)
    s.skill_matrix = {"5": {"W1"}, "35": {"W2"}}
    s.phase_catalog = [
        {"fase_id": "5", "sequence": 16, "fase_nome": "Pintura Acabamento", "boat_fraction": 0.50},
        {"fase_id": "35", "sequence": 21, "fase_nome": "Acabamento 3", "boat_fraction": 0.03},
    ]
    s.historical_durations_by_fase = {"5": 2.0, "35": 18.0}
    resolver = RoutingResolver(s)
    monkeypatch.setattr(resolver, "_semantic_engine", lambda: _stub_engine_empty())

    ops = resolver.resolve({"of_id": "OF1", "modelo_id": "MOD_RARO"})
    fases = [o.phase_id for o in ops]
    assert "5" in fases           # fase comum incluída
    assert "35" not in fases      # fase rara (3% < 15%) excluída


def test_canonical_route_no_fraction_keeps_all(monkeypatch):
    # Catálogo legacy sem boat_fraction → não filtra (back-compat exacto).
    s = FactoryState(tenant_id=TENANT)
    s.skill_matrix = {"5": {"W1"}, "35": {"W2"}}
    s.phase_catalog = [
        {"fase_id": "5", "sequence": 16, "fase_nome": "Pintura"},
        {"fase_id": "35", "sequence": 21, "fase_nome": "Acabamento 3"},
    ]
    s.historical_durations_by_fase = {"5": 2.0, "35": 18.0}
    resolver = RoutingResolver(s)
    monkeypatch.setattr(resolver, "_semantic_engine", lambda: _stub_engine_empty())
    ops = resolver.resolve({"of_id": "OF1", "modelo_id": "MOD"})
    assert {o.phase_id for o in ops} == {"5", "35"}  # sem fraction → tudo
