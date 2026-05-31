"""Sprint Q.7 Fase 3 — FactoryState + Transport suggestions smoke tests.

The Q.7 audit flagged:
* `src/plan/cpo/state.py` — 34% coverage (`load()` from DB never tested)
* `src/plan/services/transport_suggestions.py` — 35% coverage (5 detectors
  for advance_boat/delay_boat/swap/complete_truck/regroup_by_client never
  exercised)

These tests cover the pure logic surfaces (no DB) so the dashboard
flips both files toward green.
"""

from __future__ import annotations

from uuid import uuid4

from src.plan.cpo.state import (
    NELO_CURING_GAPS_SEED,
    FactoryState,
    MoldInfo,
    normalize_phase_code,
)
from src.plan.services.transport_suggestions import (
    DEFAULT_DELIVERY_BUFFER_DAYS,
    DEFAULT_TRUCK_CAPACITY,
    TransportSuggestion,
    TransportSuggestionsService,
)


# ───────────────────────────────────────────────────────────────────────────
# FactoryState — pure helpers
# ───────────────────────────────────────────────────────────────────────────

def test_normalize_phase_code_canonical_form():
    """The canonical phase ID strips accents and uppercases. Cura gaps use
    the canonical form, so a mismatch silently disables curing constraints."""
    assert normalize_phase_code("Laminagem") == "LAMINAGEM"
    assert normalize_phase_code("Laminagem Infusão") == "LAMINAGEM_INFUSAO"
    assert normalize_phase_code("Pintura Acabamento") == "PINTURA_ACABAMENTO"
    assert normalize_phase_code("  laminagem-infusão  ") == "LAMINAGEM_INFUSAO"
    assert normalize_phase_code(None) == ""
    assert normalize_phase_code("") == ""


def test_curing_gaps_seed_has_16_transitions():
    """Plan v4 §3.8 — the curated layer surfaces 16 transitions where the
    successor phase cannot start before the modal physical gap. A drop
    below 16 means a regression in state.py's seed."""
    assert len(NELO_CURING_GAPS_SEED) == 16


def test_curing_gaps_all_have_positive_hours():
    """Every transition must have min_gap_hours > 0; a zero would mean
    the curing constraint is disabled for that pair."""
    for from_phase, to_phase, hours, reason, n in NELO_CURING_GAPS_SEED:
        assert hours > 0, f"{from_phase} -> {to_phase} has zero gap"
        assert n > 0, f"{from_phase} -> {to_phase} has zero observation count"
        assert reason, "missing reason"


def test_curing_gaps_canonical_codes():
    """Phase codes in the seed must match the canonical form produced
    by `normalize_phase_code` so lookups in the decoder match."""
    for from_phase, to_phase, _, _, _ in NELO_CURING_GAPS_SEED:
        assert normalize_phase_code(from_phase) == from_phase, (
            f"non-canonical from_phase {from_phase!r}"
        )
        assert normalize_phase_code(to_phase) == to_phase, (
            f"non-canonical to_phase {to_phase!r}"
        )


def test_curing_gaps_laminagem_15h_anchor():
    """Plan v4 §3.8 anchor: Laminagem→Cura is 15.0h. If this changes,
    the entire CPO scheduling shifts and downstream tests break."""
    by_pair = {(f, t): h for f, t, h, _, _ in NELO_CURING_GAPS_SEED}
    assert by_pair[("LAMINAGEM", "CURA")] == 15.0
    assert by_pair[("LAMINAGEM_INFUSAO", "CURA")] == 24.0


def test_factory_state_constructible_empty():
    """An empty FactoryState (no skill matrix, no molds) must be a valid
    object — `load()` returns this when the DB is empty."""
    state = FactoryState(tenant_id=uuid4())
    assert state.skill_matrix == {}
    assert state.molds_by_model == {}


def test_factory_state_pair_preferred_phases_includes_laminagem():
    """The dual-resource phase list must contain LAMINAGEM (Plan v4 §3.4
    — 88.5% historical pair). Sprint Q.8 (CEO confirmation 2026-04-26)
    moved Laminagem from REQUIRED (hard) to PREFERRED (soft) — solo runs
    are real, not picking errors. Removing it from PREFERRED breaks the
    pair_assignment optimisation."""
    state = FactoryState(tenant_id=uuid4())
    assert "LAMINAGEM" in state.PAIR_PREFERRED_PHASES
    # No phase is hard-REQUIRED any more.
    assert state.PAIR_REQUIRED_PHASES == ()


def test_factory_state_team_size_for_pair_phases():
    """`team_size_for` returns 2 for any phase matching the
    PAIR_REQUIRED_PHASES list (Laminagem variants), 1 otherwise."""
    state = FactoryState(tenant_id=uuid4())
    # phase_name is normalised internally — accents/case shouldn't matter
    assert state.team_size_for("X-1", "Laminagem") == 2
    assert state.team_size_for("X-2", "LAMINAGEM") == 2
    assert state.team_size_for("X-3", "Pintura") == 1
    assert state.team_size_for("X-4", "") == 1


def test_mold_info_dataclass_defaults():
    info = MoldInfo(molde_id="M-7", modelo_id="K1")
    assert info.pocket_count == 1
    assert info.em_manutencao is False
    assert info.tipo == ""


# ───────────────────────────────────────────────────────────────────────────
# Transport suggestions — pure dataclass + constants
# ───────────────────────────────────────────────────────────────────────────

def test_transport_constants_anchored_to_nelo():
    """Plan v4 §3.6 — the truck capacity default is 50 (CEO confirmed)
    and buffer 1 day. Changing these affects suggestion thresholds."""
    assert DEFAULT_TRUCK_CAPACITY == 50
    assert DEFAULT_DELIVERY_BUFFER_DAYS == 1


def test_transport_suggestion_to_dict_contains_5_required_fields():
    """Plan v4 §11 'Explica sempre' — every suggestion MUST carry
    what / why / if_accept / if_reject. The optional alternative + IDs
    are for follow-up actions in the UI."""
    s = TransportSuggestion(
        type="advance_boat",
        what="Mover X",
        why="Y prazo curto",
        if_accept="Cliente recebe cedo",
        if_reject="Espaço ocupado",
        alternative="Mover só os 2 mais urgentes",
        affected_order_ids=["op-1", "op-2"],
    )
    d = s.to_dict()
    for required in ("type", "what", "why", "if_accept", "if_reject"):
        assert required in d, f"suggestion missing required key {required}"
    assert d["affected_order_ids"] == ["op-1", "op-2"]
    assert d["alternative"] == "Mover só os 2 mais urgentes"


def test_transport_suggestion_minimal_payload():
    """Suggestion without alternative + ids must still serialise — the
    UI tolerates None for optional fields."""
    s = TransportSuggestion(
        type="delay_boat",
        what="Atrasar",
        why="QC alerta",
        if_accept="Evita defeito",
        if_reject="Risco retrabalho",
    )
    d = s.to_dict()
    assert d["alternative"] is None
    assert d["affected_order_ids"] == []
    assert d["target_batch_id"] is None


def test_transport_suggestions_service_constructible():
    svc = TransportSuggestionsService(
        session=None, tenant_id=uuid4(),  # type: ignore[arg-type]
        truck_capacity=42, buffer_days=3,
    )
    assert svc.truck_capacity == 42
    assert svc.buffer_days == 3


def test_transport_suggestions_service_default_capacity():
    """Default capacity comes from the plan v4 anchor (50), not 0."""
    svc = TransportSuggestionsService(session=None, tenant_id=uuid4())  # type: ignore[arg-type]
    assert svc.truck_capacity == DEFAULT_TRUCK_CAPACITY
    assert svc.buffer_days == DEFAULT_DELIVERY_BUFFER_DAYS


def test_preview_delta_service_owns_preview_issue():
    """Sanity check on module ownership: PreviewIssue lives in
    preview_delta_service, NOT transport_suggestions. Catches accidental
    cross-module coupling if someone re-exports it."""
    from src.plan.services import transport_suggestions
    from src.plan.services.preview_delta_service import PreviewIssue

    assert PreviewIssue is not None
    assert not hasattr(transport_suggestions, "PreviewIssue"), (
        "transport_suggestions must not expose PreviewIssue — that "
        "would create a circular conceptual dependency."
    )


# ───────────────────────────────────────────────────────────────────────────
# Q.131.A (Q.126.B) — FactoryState rotas/durações reais de factory_raw.of_fp
# ───────────────────────────────────────────────────────────────────────────

def test_factory_state_has_historical_routes_field():
    """Q.131.A (Q.126.B) — FactoryState deve ter o campo
    historical_routes_by_model (rotas reais reconstruídas de
    factory_raw.of_fp) que o RoutingResolver consome quando a camada
    curada está unavailable (a realidade de produção)."""
    from src.plan.cpo.state import FactoryState

    state = FactoryState(tenant_id=uuid4())
    assert hasattr(state, "historical_routes_by_model"), (
        "FactoryState.historical_routes_by_model ausente — caminho real Q.126.B partido"
    )
    assert state.historical_routes_by_model == {}


def test_routing_resolver_uses_real_history_routes_when_engine_unavailable():
    """Q.131.A (Q.126.B) — quando a camada curada está unavailable, o
    RoutingResolver deve usar state.historical_routes_by_model (rotas reais
    reconstruídas de factory_raw.of_fp, keyed por OF_P_ID) para resolver a
    rota. Sem este caminho o scheduler dá sempre 400 mesmo havendo orders."""
    from src.plan.cpo.state import FactoryState
    from src.plan.services.routing_resolver import RoutingResolver

    state = FactoryState(tenant_id=uuid4())
    # Simula o que _load_historical_durations_routes_db() popula: a rota real
    # do modelo OF_P_ID "20155" reconstruída do histórico (ordem por sequência).
    state.historical_routes_by_model = {
        "20155": [
            {"fase_id": "3", "fase_nome": "Laminagem", "sequence": 1,
             "duration_hours": 4.32},
            {"fase_id": "5", "fase_nome": "Desmolde", "sequence": 2,
             "duration_hours": 0.8},
        ]
    }
    state.loaded_ok = True

    resolver = RoutingResolver(state)
    order = {"of_id": "TEST-001", "modelo_id": "20155", "data_entrega_prevista": None}
    ops = resolver.resolve(order)

    # Deve resolver as 2 operações reais (não cair no template 2x sintético)
    assert len(ops) >= 2, (
        f"Esperava >=2 ops da rota real, got {len(ops)}. "
        "RoutingResolver não usou state.historical_routes_by_model."
    )
    sources = {op.operation_code for op in ops}
    assert "Laminagem" in sources or "3" in sources, (
        "Fase Laminagem não encontrada nas operações resolvidas"
    )


def test_real_db_loaders_have_no_coeficiente_x_in_sql():
    """Q.131.A Spelke CX1 — CoeficienteX (€) não pode ser SELECTado em
    nenhuma query dos loaders de dados reais (Q.126.B/C/D em state.py:
    _load_historical_durations_routes_db / _load_molds_db / _load_skills_db /
    _load_open_orders_db). Pode aparecer em comentário/docstring como aviso,
    nunca como coluna de dados.

    OFFP_COEFICIENTE_X / OF_COEFICIENTE são dinheiro (€), não tempo — CX1."""
    import pathlib

    state_path = (
        pathlib.Path(__file__).resolve().parents[2]
        / "src" / "plan" / "cpo" / "state.py"
    )
    source = state_path.read_text(encoding="utf-8")

    for line in source.splitlines():
        stripped = line.strip()
        # comentários SQL/Python (-- / #) e linhas de docstring (") são OK
        if stripped.startswith("--") or stripped.startswith("#") or stripped.startswith('"'):
            continue
        upper = line.upper()
        if "COEFICIENTE_X" in upper or "OF_COEFICIENTE" in upper:
            assert False, (
                f"Campo de € (CoeficienteX) em código activo de state.py: "
                f"{line!r} — viola Spelke CX1"
            )
