"""Sprint Q.9 (2.4) — TrustIndexCalculator._calculate_consistency.

Replaces the previous stub that always returned 1.0. Three concrete
NELO-domain rules:
  1. data_inicio / data_entrada must not be after data_fim / data_conclusao
  2. quantidade_produzida cannot exceed quantidade
  3. workers list cannot contain duplicates
"""

from __future__ import annotations

from datetime import date

import pytest

from src.dqa.trust_index import TrustIndexCalculator


@pytest.fixture
def tic():
    return TrustIndexCalculator(
        required_fields=["id"],
        valid_ranges={},
    )


def test_consistency_returns_one_when_no_rules_apply(tic):
    assert tic._calculate_consistency({"id": "x"}) == 1.0


def test_date_order_violation_drops_score(tic):
    entity = {
        "data_inicio": date(2026, 5, 10),
        "data_fim": date(2026, 5, 5),  # earlier than start
    }
    assert tic._calculate_consistency(entity) == 0.0


def test_date_order_correct_keeps_full_score(tic):
    entity = {
        "data_entrada": date(2026, 5, 1),
        "data_conclusao": date(2026, 5, 10),
    }
    assert tic._calculate_consistency(entity) == 1.0


def test_quantity_excess_drops_score(tic):
    entity = {"quantidade": 10, "quantidade_produzida": 12}
    assert tic._calculate_consistency(entity) == 0.0


def test_quantity_match_or_under_keeps_full_score(tic):
    assert tic._calculate_consistency(
        {"quantidade": 10, "quantidade_produzida": 8}
    ) == 1.0
    assert tic._calculate_consistency(
        {"quantidade": 10, "quantidade_produzida": 10}
    ) == 1.0


def test_duplicate_worker_drops_score(tic):
    assert tic._calculate_consistency(
        {"workers": ["w1", "w2", "w1"]}
    ) == 0.0


def test_unique_workers_keeps_full_score(tic):
    assert tic._calculate_consistency(
        {"workers": ["w1", "w2", "w3"]}
    ) == 1.0


def test_combined_violations_partial_score(tic):
    """2 rules apply, 1 violated → 0.5."""
    entity = {
        "data_inicio": date(2026, 5, 1),
        "data_fim": date(2026, 5, 10),  # OK
        "quantidade": 10,
        "quantidade_produzida": 15,  # violation
    }
    assert tic._calculate_consistency(entity) == 0.5


def test_three_rules_one_violation_two_thirds(tic):
    """All 3 rules apply, 1 violated → ~0.667."""
    entity = {
        "data_inicio": date(2026, 5, 1),
        "data_fim": date(2026, 5, 10),
        "quantidade": 10,
        "quantidade_produzida": 8,
        "workers": ["w1", "w1"],  # only violation
    }
    score = tic._calculate_consistency(entity)
    assert abs(score - (2 / 3)) < 1e-6
