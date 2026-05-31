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
# Q.130.1 — FactoryState.route_templates fallback (BE-4)
# ───────────────────────────────────────────────────────────────────────────

def test_factory_state_has_route_templates_field():
    """Q.130.1 — FactoryState deve ter o campo route_templates para o
    fallback BD-real quando a camada curada está unavailable."""
    from src.plan.cpo.state import FactoryState

    state = FactoryState(tenant_id=uuid4())
    assert hasattr(state, "route_templates"), (
        "FactoryState.route_templates ausente — fallback Q.130.1 não funciona"
    )
    assert state.route_templates == {}


def test_routing_resolver_uses_route_templates_when_engine_unavailable():
    """Q.130.1 — quando a camada curada está unavailable, o RoutingResolver
    deve usar state.route_templates (populado da BD real) para resolver o
    standard_template. Sem este fallback o scheduler dá sempre 400 mesmo
    quando há orders abertas."""
    from src.plan.cpo.state import FactoryState
    from src.plan.services.routing_resolver import RoutingResolver

    state = FactoryState(tenant_id=uuid4())
    # Simula o que _load_from_real_db() popula: templates de BD para model_id "K1"
    state.route_templates = {
        "K1": [
            {"fase_id": "3", "fase_nome": "Laminagem", "seq": 1,
             "horas_standard": 4.0, "requires_mold": True, "team_size_default": 2},
            {"fase_id": "5", "fase_nome": "Desmolde", "seq": 2,
             "horas_standard": 1.0, "requires_mold": False, "team_size_default": 1},
        ]
    }
    state.loaded_ok = True

    resolver = RoutingResolver(state)
    order = {"of_id": "TEST-001", "modelo_id": "K1", "data_entrega_prevista": None}
    ops = resolver.resolve(order)

    # Deve resolver pelo menos 2 operações usando route_templates
    assert len(ops) >= 2, (
        f"Esperava >=2 ops de route_templates, got {len(ops)}. "
        "RoutingResolver não usou state.route_templates como fallback."
    )
    # As fontes devem indicar db_template (ou duration_model_p50 se predictor wired)
    sources = {op.operation_code for op in ops}
    assert "Laminagem" in sources or "3" in sources, (
        "Fase Laminagem não encontrada nas operações resolvidas"
    )


def test_route_templates_coeficiente_x_not_in_sql(tmp_path):
    """Q.130.1 Spelke CX1 — CoeficienteX (€) não deve aparecer em SELECT
    SQL dentro de _load_from_real_db. Pode aparecer em comentários/docstrings
    como aviso, mas não pode ser seleccionado como coluna de dados.

    OFFP_COEFICIENTE_X é dinheiro (€), não tempo — Spelke CX1."""
    import pathlib
    import re

    state_path = pathlib.Path("C:/Users/User/nelinho/src/plan/cpo/state.py")
    source = state_path.read_text(encoding="utf-8")
    fn_start = source.find("async def _load_from_real_db(")
    fn_end = source.find("\ndef _extract_error_rates(", fn_start)
    fn_body = source[fn_start:fn_end] if fn_end > fn_start else source[fn_start:]

    # Procura COEFICIENTE_X em linhas SQL não-comentadas (sem # no início)
    for line in fn_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or stripped.startswith("#"):
            continue  # comentários SQL e Python são OK
        if "COEFICIENTE_X" in line.upper() and "COEFICIENTE_X" not in (stripped[:2]):
            # Linha de código activo com CoeficienteX — violação
            assert False, (
                f"COEFICIENTE_X (campo de €) em código activo de _load_from_real_db: "
                f"{line!r} — viola Spelke CX1"
            )
