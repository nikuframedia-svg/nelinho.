"""
Tests for src.plan.services.routing_resolver.RoutingResolver.

Strategy: inject a FactoryState with pre-computed durations and a stubbed
semantic engine that returns fixed CuratedOrderPhase rows.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, List
from uuid import UUID

import pytest

from src.plan.cpo.state import FactoryState
from src.plan.services.routing_resolver import RoutingResolver


TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _StubEngine:
    """Mimics the shape RoutingResolver expects from SemanticQueriesInMemory.engine."""

    def __init__(self, phases=None, orders=None, standards=None):
        self._active_ingestion_id = "active"
        self._curated_data = {
            "active": {
                "order_phases": phases or [],
                "orders": orders or [],
                "standards": standards or [],
            }
        }


def _stub_semantic_queries(phases=None, orders=None, standards=None):
    return SimpleNamespace(engine=_StubEngine(phases=phases, orders=orders, standards=standards))


def _make_state(semantic_queries=None) -> FactoryState:
    s = FactoryState(tenant_id=TENANT)
    s.skill_matrix = {"FASE-LAM": {"W1"}, "FASE-PNT": {"W2"}}
    return s


def _phase_row(of_id, fase_id, fase_nome, ordem, horas_reais=None, horas_standard=None):
    return SimpleNamespace(
        of_id=of_id,
        fase_id=fase_id,
        fase_nome=fase_nome,
        ordem=ordem,
        horas_reais=horas_reais,
        horas_finais=horas_reais,
        horas_standard=horas_standard,
    )


def _order_row(of_id, modelo_id):
    return SimpleNamespace(of_id=of_id, modelo_id=modelo_id)


def _standard_row(modelo_id, fase_id, fase_nome, ordem, horas_standard):
    return SimpleNamespace(
        modelo_id=modelo_id,
        fase_id=fase_id,
        fase_nome=fase_nome,
        ordem=ordem,
        horas_standard=horas_standard,
    )


# ---------------------------------------------------------------------------
# History for the specific order
# ---------------------------------------------------------------------------

class TestHistoryResolution:
    def test_uses_own_history_when_available(self, monkeypatch):
        phases = [
            _phase_row("O-1", "FASE-LAM", "Laminagem", ordem=4, horas_reais=8.0),
            _phase_row("O-1", "FASE-PNT", "Pintura Acabamento", ordem=9, horas_reais=12.0),
        ]
        stub = _stub_semantic_queries(phases=phases)
        state = _make_state()
        resolver = RoutingResolver(state)
        monkeypatch.setattr(resolver, "_semantic_engine", lambda: stub.engine)

        ops = resolver.resolve({"of_id": "O-1", "modelo_id": "K1"})

        assert len(ops) == 2
        assert ops[0].sequence == 4
        assert ops[0].phase_id == "FASE-LAM"
        assert ops[0].duration_minutes == pytest.approx(8.0 * 60.0)
        # team_size=2 for Laminagem (NELO rule via state.team_size_for)
        assert ops[0].team_size == 2
        # Second op uses pintura duration
        assert ops[1].duration_minutes == pytest.approx(12.0 * 60.0)


# ---------------------------------------------------------------------------
# History for model (fallback 2)
# ---------------------------------------------------------------------------

class TestModelHistoryFallback:
    def test_uses_model_history_when_no_order_history(self, monkeypatch):
        # Other order's phases for same model
        phases = [
            _phase_row("O-REF", "FASE-LAM", "Laminagem", ordem=4, horas_reais=7.5),
            _phase_row("O-REF", "FASE-PNT", "Pintura Acabamento", ordem=9, horas_standard=1.0),
        ]
        orders = [_order_row("O-REF", "K1")]
        stub = _stub_semantic_queries(phases=phases, orders=orders)
        state = _make_state()
        # Inject median durations directly
        state.historical_durations = {("FASE-LAM", "K1"): 7.4, ("FASE-PNT", "K1"): 25.4}

        resolver = RoutingResolver(state)
        monkeypatch.setattr(resolver, "_semantic_engine", lambda: stub.engine)

        ops = resolver.resolve({"of_id": "O-NEW", "modelo_id": "K1"})

        assert len(ops) == 2
        # Uses medians from state (not the raw horas_reais)
        assert ops[0].duration_minutes == pytest.approx(7.4 * 60.0)
        assert ops[1].duration_minutes == pytest.approx(25.4 * 60.0)


# ---------------------------------------------------------------------------
# Standard template (fallback 3)
# ---------------------------------------------------------------------------

class TestStandardFallback:
    def test_uses_standard_with_2x_buffer_when_no_history(self, monkeypatch):
        standards = [
            _standard_row("K-NEW", "FASE-LAM", "Laminagem", ordem=1, horas_standard=8.0),
        ]
        stub = _stub_semantic_queries(standards=standards)
        state = _make_state()
        resolver = RoutingResolver(state)
        monkeypatch.setattr(resolver, "_semantic_engine", lambda: stub.engine)

        ops = resolver.resolve({"of_id": "O-FRESH", "modelo_id": "K-NEW"})

        assert len(ops) == 1
        # Standard 8h × 2 buffer = 16h = 960 min
        assert ops[0].duration_minutes == pytest.approx(16.0 * 60.0)
        assert ops[0].sequence == 1


# ---------------------------------------------------------------------------
# Empty paths
# ---------------------------------------------------------------------------

class TestEmpty:
    def test_no_data_returns_empty_list(self, monkeypatch):
        stub = _stub_semantic_queries()
        state = _make_state()
        resolver = RoutingResolver(state)
        monkeypatch.setattr(resolver, "_semantic_engine", lambda: stub.engine)

        ops = resolver.resolve({"of_id": "O-NONE", "modelo_id": "?"})
        assert ops == []

    def test_missing_order_id_returns_empty(self):
        state = _make_state()
        resolver = RoutingResolver(state)
        ops = resolver.resolve({"modelo_id": "K1"})
        assert ops == []


# ---------------------------------------------------------------------------
# resolve_many
# ---------------------------------------------------------------------------

class TestResolveMany:
    def test_concatenates_routings(self, monkeypatch):
        phases = [
            _phase_row("O-A", "FASE-LAM", "Laminagem", ordem=1, horas_reais=1.0),
            _phase_row("O-B", "FASE-LAM", "Laminagem", ordem=1, horas_reais=2.0),
        ]
        stub = _stub_semantic_queries(phases=phases)
        state = _make_state()
        resolver = RoutingResolver(state)
        monkeypatch.setattr(resolver, "_semantic_engine", lambda: stub.engine)

        ops = resolver.resolve_many([
            {"of_id": "O-A", "modelo_id": "K1"},
            {"of_id": "O-B", "modelo_id": "K2"},
        ])
        assert len(ops) == 2
        assert {o.order_id for o in ops} == {"O-A", "O-B"}


# ---------------------------------------------------------------------------
# Q.164.C — fallback de rota canónica (modelos sem rota nenhuma)
# ---------------------------------------------------------------------------

class TestCanonicalRouteFallbackQ164C:
    def test_canonical_route_when_no_other_route(self, monkeypatch):
        # Modelo raro/novo sem histórico/template/curada. Com phase_catalog +
        # durações medianas por fase, o resolver usa a sequência-padrão da NELO
        # (Q.164.C) em vez de deixar o barco unplanned (no_route).
        state = FactoryState(tenant_id=TENANT)
        state.skill_matrix = {"1": {"W1"}, "18": {"W2"}}
        state.phase_catalog = [
            {"fase_id": "1", "sequence": 10, "fase_nome": "Laminagem"},
            {"fase_id": "18", "sequence": 9, "fase_nome": "Pintura"},
            {"fase_id": "99", "sequence": 30, "fase_nome": "SemMediana"},
        ]
        # fase 99 SEM mediana real → tem de ser saltada (invariante #8).
        state.historical_durations_by_fase = {"1": 4.0, "18": 0.2}
        stub = _stub_semantic_queries()  # vazio → sem histórico nem standards
        resolver = RoutingResolver(state)
        monkeypatch.setattr(resolver, "_semantic_engine", lambda: stub.engine)

        ops = resolver.resolve({"of_id": "OF-NOVO", "modelo_id": "MODELO-RARO"})

        assert len(ops) == 2  # fase 99 saltada (sem duração real)
        # ordenadas por sequência: Pintura (seq 9) antes de Laminagem (seq 10)
        assert [o.phase_id for o in ops] == ["18", "1"]
        assert ops[0].duration_minutes == pytest.approx(0.2 * 60.0)
        assert "OF-NOVO" in resolver.planned_order_ids
        assert resolver.unplanned == []

    def test_no_catalog_still_unplanned(self, monkeypatch):
        # Sem catálogo (back-compat exacto): modelo sem rota continua no_route.
        state = FactoryState(tenant_id=TENANT)
        state.skill_matrix = {"1": {"W1"}}
        stub = _stub_semantic_queries()
        resolver = RoutingResolver(state)
        monkeypatch.setattr(resolver, "_semantic_engine", lambda: stub.engine)

        ops = resolver.resolve({"of_id": "OF-X", "modelo_id": "MODELO-RARO"})
        assert ops == []
        assert resolver.unplanned[0]["reason"] == "no_route"
