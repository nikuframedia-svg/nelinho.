"""Q.158.E — property test: rotas-template nunca incluem fases terminais.

Spelke invariant: nenhuma operação de uma fase com FP_PRODUCAO=false pode
aparecer numa rota-template resolvida.  O ponto de controlo é
`RoutingResolver._template_for_model_db`, que lê de
`FactoryState.template_routes_by_model` (carregado por
`state._load_route_templates_db`).

A SQL de _load_route_templates_db faz INNER JOIN com
`factory_raw.fases_producao WHERE FP_PRODUCAO=true` (correcção Slice-E) —
este teste confirma que o contrato se mantém mesmo se por alguma razão
`template_routes_by_model` contiver fases terminais (defesa-em-profundidade
ao nível do resolver, e testa o invariant de forma pura, sem BD).
"""
from __future__ import annotations

from typing import List
from uuid import UUID

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from src.plan.cpo.state import NON_PRODUCTION_PHASE_IDS, FactoryState
from src.plan.services.routing_resolver import RoutingResolver

# Fases de produção legítimas (amostra representativa para os testes)
_PROD_PHASE_IDS = ["1", "2", "3", "4", "5", "6", "8", "11", "14", "18", "19", "40"]

_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _make_state(template_steps: list[dict]) -> FactoryState:
    """Cria um FactoryState minimal com template_routes_by_model injectado."""
    s = FactoryState(tenant_id=_TENANT)
    s.template_routes_by_model = {"999": template_steps}
    s.historical_durations_by_fase = {p: 2.0 for p in _PROD_PHASE_IDS}
    s.skill_matrix = {}
    return s


def _resolver(state: FactoryState) -> RoutingResolver:
    return RoutingResolver(state=state)


# ─── Strategy: gera steps que incluem fases terminais ───────────────────────

@st.composite
def _steps_with_terminal_phases(draw):
    """Gera lista de steps onde PELO MENOS UM tem fase terminal."""
    terminal_id = draw(st.sampled_from(sorted(NON_PRODUCTION_PHASE_IDS)))
    prod_ids = draw(st.lists(
        st.sampled_from(_PROD_PHASE_IDS),
        min_size=1, max_size=5,
        unique=True,
    ))
    insert_pos = draw(st.integers(min_value=0, max_value=len(prod_ids)))
    all_ids = prod_ids[:insert_pos] + [terminal_id] + prod_ids[insert_pos:]
    steps = [
        {
            "fase_id": fid,
            "fase_nome": f"Fase_{fid}",
            "sequence": seq,
            "duration_p50_h": 2.5,
            "requires_mold": False,
            "team_size_default": 1,
        }
        for seq, fid in enumerate(all_ids, start=1)
    ]
    return steps, terminal_id


@st.composite
def _steps_only_production(draw):
    """Gera lista de steps com apenas fases de produção."""
    prod_ids = draw(st.lists(
        st.sampled_from(_PROD_PHASE_IDS),
        min_size=1, max_size=6,
        unique=True,
    ))
    steps = [
        {
            "fase_id": fid,
            "fase_nome": f"Fase_{fid}",
            "sequence": seq,
            "duration_p50_h": 2.5,
            "requires_mold": False,
            "team_size_default": 1,
        }
        for seq, fid in enumerate(prod_ids, start=1)
    ]
    return steps


# ─── Property 1: fases terminais nunca entram na rota resolvida ─────────────

@settings(deadline=None, max_examples=200,
          suppress_health_check=[HealthCheck.too_slow])
@given(_steps_with_terminal_phases())
def test_terminal_phases_absent_from_resolved_route(steps_and_terminal):
    """Se template_routes_by_model contiver uma fase terminal (FP_PRODUCAO=false),
    essa fase NÃO deve aparecer nas RoutingRows devolvidas por
    _template_for_model_db — nem directamente nem através do fallback.

    Este é o invariant de defesa-em-profundidade (Spelke): mesmo que a SQL
    deixe entrar uma fase terminal por bug, o resolver filtra-a antes de
    construir operações agendáveis."""
    steps, terminal_id = steps_and_terminal
    state = _make_state(steps)
    resolver = _resolver(state)
    rows = resolver._template_for_model_db("999")
    row_phase_ids = {r.fase_id for r in rows}
    assert terminal_id not in row_phase_ids, (
        f"Fase terminal {terminal_id!r} apareceu na rota resolvida: "
        f"phases={sorted(row_phase_ids)}"
    )


# ─── Property 2: fases de produção passam sem filtragem incorrecta ──────────

@settings(deadline=None, max_examples=100,
          suppress_health_check=[HealthCheck.too_slow])
@given(_steps_only_production())
def test_production_phases_pass_through(steps):
    """Fases legítimas de produção (FP_PRODUCAO=true) devem aparecer todas
    na rota resolvida (sem filtragem incorrecta)."""
    state = _make_state(steps)
    resolver = _resolver(state)
    rows = resolver._template_for_model_db("999")
    row_phase_ids = {r.fase_id for r in rows}
    expected = {s["fase_id"] for s in steps}
    assert row_phase_ids == expected, (
        f"Fases de produção foram filtradas indevidamente: "
        f"expected={sorted(expected)} got={sorted(row_phase_ids)}"
    )


# ─── Teste de regressão directo (fases mais críticas) ───────────────────────

@pytest.mark.parametrize("terminal_id,name", [
    ("10", "Embalado"),
    ("12", "Entregue"),
    ("9",  "Armazem"),
    ("15", "Em Uso"),
    ("7",  "Parque Acabamento"),
])
def test_critical_terminal_phases_never_scheduled(terminal_id, name):
    """Regressão directa: as fases terminais mais críticas (barcos já
    fora de produção) nunca aparecem num schedule gerado."""
    steps = [
        {"fase_id": "1",       "fase_nome": "Laminagem",   "sequence": 1,
         "duration_p50_h": 3.0, "requires_mold": True,  "team_size_default": 2},
        {"fase_id": terminal_id, "fase_nome": name,         "sequence": 2,
         "duration_p50_h": 1.0, "requires_mold": False, "team_size_default": 1},
        {"fase_id": "3",       "fase_nome": "Pintura",     "sequence": 3,
         "duration_p50_h": 2.0, "requires_mold": False, "team_size_default": 1},
    ]
    state = _make_state(steps)
    resolver = _resolver(state)
    rows = resolver._template_for_model_db("999")
    row_ids = [r.fase_id for r in rows]
    assert terminal_id not in row_ids, (
        f"Fase terminal '{name}' (id={terminal_id}) apareceu na rota: {row_ids}"
    )
