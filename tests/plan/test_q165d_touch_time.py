"""Q.165.D — tempo-padrão (touch-time) do ERP substitui o flow-time.

A duração das ops vinha da mediana de of_fp (OFFP_DATAFIM-OFFP_DATAINICIO) =
FLOW-TIME (fase aberta, inclui secagem) → inflava o makespan ~5× (provado live:
durações×0.2 → makespan 31118h→6662h). O ERP tem o trabalho REAL em
fases_producao.FP_VALOR_REF_K1/K2/K4 (horas-padrão por fase×classe). Este é o
tier de TOPO de median_duration_h e o override no RoutingResolver.

Invariantes:
* std_ref_duration_h devolve FP_VALOR_REF p/ modelo K-classe; None senão.
* median_duration_h prefere std-ref a calibrado/histórico.
* mapas vazios → back-compat exacto (cai no histórico).
* o resolver usa o std-ref para a duração da op (override do flow-time).
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from src.plan.cpo.state import FactoryState
from src.plan.services.routing_resolver import RoutingResolver

TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _state_with_ref() -> FactoryState:
    s = FactoryState(tenant_id=TENANT)
    # Fase "5" (Pintura Acabamento): K1=3h, K2=4h, K4=5h (horas-padrão).
    s.phase_std_ref_hours = {"5": {"K1": 3.0, "K2": 4.0, "K4": 5.0}}
    s.model_kayak_class = {"MOD_K1": "K1", "MOD_K2": "K2"}
    return s


def test_std_ref_duration_h_by_class():
    s = _state_with_ref()
    assert s.std_ref_duration_h("5", "MOD_K1") == 3.0
    assert s.std_ref_duration_h("5", "MOD_K2") == 4.0
    # modelo sem classe conhecida → None (cai no cascade)
    assert s.std_ref_duration_h("5", "MOD_DESCONHECIDO") is None
    # fase sem valor de referência → None
    assert s.std_ref_duration_h("99", "MOD_K1") is None


def test_median_duration_prefers_std_ref_over_history():
    s = _state_with_ref()
    # histórico (flow-time) seria 24h; o std-ref (touch) tem de ganhar.
    s.historical_durations = {("5", "MOD_K1"): 24.0}
    s.calibrated_durations = {("5", "MOD_K1"): (20.0, 50)}
    assert s.median_duration_h("5", "MOD_K1", fallback_hours=99.0) == 3.0


def test_empty_maps_fall_back_to_history():
    s = FactoryState(tenant_id=TENANT)  # sem std-ref nem classes
    s.historical_durations = {("5", "MOD_K1"): 24.0}
    # back-compat exacto: sem std-ref usa o histórico
    assert s.std_ref_duration_h("5", "MOD_K1") is None
    assert s.median_duration_h("5", "MOD_K1", fallback_hours=99.0) == 24.0


def test_resolver_uses_std_ref_for_op_duration(monkeypatch):
    # O resolver constrói uma rota com duração de of_fp (flow 24h) mas o std-ref
    # (touch 3h) tem de substituir na op final.
    s = _state_with_ref()
    s.skill_matrix = {"5": {"W1"}}
    # rota real do modelo (uma fase, flow 24h)
    s.historical_routes_by_model = {
        "MOD_K1": [{"fase_id": "5", "fase_nome": "Pintura Acabamento",
                    "sequence": 16, "duration_hours": 24.0}],
    }
    resolver = RoutingResolver(s)
    # sem semantic engine → cai no _history_for_model_db (usa o route acima)
    monkeypatch.setattr(resolver, "_semantic_engine", lambda: SimpleNamespace(
        _active_ingestion_id=None, _curated_data={}))

    ops = resolver.resolve({"of_id": "OF1", "modelo_id": "MOD_K1"})
    assert len(ops) == 1
    # 3h std-ref (não 24h flow): 180 min
    assert ops[0].duration_minutes == 180.0
