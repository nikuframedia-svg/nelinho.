"""Q.116.D — testes do boost_service.

Funcoes puras: zero DB, zero mocks. Cobertura:

  client_boost_from_priority:
    * priority=1 -> 100
    * priority=5 -> 20
    * priority=None -> 0
    * priority=999 ou string invalida -> 0

  compute_effective_boost:
    * soma normal de client+order+boat
    * cap a 200 (MAX_TOTAL_BOOST)
    * componentes negativos clamped a 0
    * tudo zero -> 0
"""
from __future__ import annotations

import pytest

from src.plan.services.boost_service import (
    MAX_TOTAL_BOOST,
    client_boost_from_priority,
    compute_effective_boost,
)


# ─── client_boost_from_priority ──────────────────────────────────────────────


def test_client_boost_priority_1_returns_100():
    """Prioridade maxima (1) -> client_boost 100."""
    assert client_boost_from_priority(1) == 100


def test_client_boost_priority_5_returns_20():
    """Prioridade minima (5) -> client_boost 20."""
    assert client_boost_from_priority(5) == 20


def test_client_boost_priority_3_returns_60():
    """Prioridade media (3) -> client_boost 60 ((6-3)*20)."""
    assert client_boost_from_priority(3) == 60


def test_client_boost_none_returns_0():
    """None -> 0 (sem boost por cliente)."""
    assert client_boost_from_priority(None) == 0


def test_client_boost_invalid_above_range_returns_0():
    """Prioridade > 5 -> 0 (fora do dominio definido)."""
    assert client_boost_from_priority(6) == 0
    assert client_boost_from_priority(999) == 0


def test_client_boost_invalid_below_range_returns_0():
    """Prioridade < 1 -> 0 (fora do dominio definido)."""
    assert client_boost_from_priority(0) == 0
    assert client_boost_from_priority(-3) == 0


def test_client_boost_non_int_returns_0():
    """Tipos invalidos (str nao numerica) -> 0."""
    assert client_boost_from_priority("abc") == 0  # type: ignore[arg-type]


# ─── compute_effective_boost ─────────────────────────────────────────────────


def test_effective_basic_sum():
    """client(60) + order(20) + boat(10) = 90, abaixo do cap."""
    # priority=3 -> client_boost=60
    assert compute_effective_boost(client_priority=3, order_boost=20, boat_boost=10) == 90


def test_effective_caps_at_200():
    """Soma > 200 -> capped a MAX_TOTAL_BOOST (200)."""
    # priority=1 -> 100 ; order=80 ; boat=80 -> 260 -> capped 200
    result = compute_effective_boost(client_priority=1, order_boost=80, boat_boost=80)
    assert result == MAX_TOTAL_BOOST
    assert result == 200


def test_effective_negative_components_clamped_to_zero():
    """Componentes negativos sao tratados como 0, nao subtraem."""
    # client=0 (None) ; order=-50 -> 0 ; boat=30 -> total 30
    assert compute_effective_boost(client_priority=None, order_boost=-50, boat_boost=30) == 30


def test_effective_zero_when_all_inputs_zero():
    """Todos os componentes a 0 -> 0."""
    assert compute_effective_boost(client_priority=None, order_boost=0, boat_boost=0) == 0


def test_effective_none_order_and_boat_treated_as_zero():
    """order_boost=None e boat_boost=None viram 0."""
    # priority=2 -> 80 ; order=None -> 0 ; boat=None -> 0 -> 80
    assert (
        compute_effective_boost(client_priority=2, order_boost=None, boat_boost=None)  # type: ignore[arg-type]
        == 80
    )


def test_effective_exact_cap_boundary():
    """Soma exactamente igual ao cap (200) -> 200."""
    # priority=1 -> 100 ; order=50 ; boat=50 -> 200 exact
    assert compute_effective_boost(client_priority=1, order_boost=50, boat_boost=50) == 200


def test_max_total_boost_constant():
    """MAX_TOTAL_BOOST e 200 (contrato com o decoder)."""
    assert MAX_TOTAL_BOOST == 200
