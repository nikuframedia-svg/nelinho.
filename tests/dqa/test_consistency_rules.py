"""Sprint Q.9 (2.4) — regras de consistencia (Q.61.29 migrado).

Q.61.29: estes testes batiam em `TrustIndexCalculator._calculate_
consistency` (trust_index v1, deprecated). v1 foi apagado; as 3 regras
foram extraidas como funcoes puras em src/dqa/consistency_rules.py.

Tres regras NELO-domain (sem mudar a semantica):
  1. data_inicio / data_entrada nao pode ser apos data_fim / data_conclusao
  2. quantidade_produzida nao pode exceder quantidade
  3. workers list nao pode ter duplicados
"""

from __future__ import annotations

from datetime import date

from src.dqa.consistency_rules import consistency_score


def test_consistency_returns_one_when_no_rules_apply():
    assert consistency_score({"id": "x"}) == 1.0


def test_date_order_violation_drops_score():
    entity = {
        "data_inicio": date(2026, 5, 10),
        "data_fim": date(2026, 5, 5),  # earlier than start
    }
    assert consistency_score(entity) == 0.0


def test_date_order_correct_keeps_full_score():
    entity = {
        "data_entrada": date(2026, 5, 1),
        "data_conclusao": date(2026, 5, 10),
    }
    assert consistency_score(entity) == 1.0


def test_quantity_excess_drops_score():
    entity = {"quantidade": 10, "quantidade_produzida": 12}
    assert consistency_score(entity) == 0.0


def test_quantity_match_or_under_keeps_full_score():
    assert consistency_score(
        {"quantidade": 10, "quantidade_produzida": 8}
    ) == 1.0
    assert consistency_score(
        {"quantidade": 10, "quantidade_produzida": 10}
    ) == 1.0


def test_duplicate_worker_drops_score():
    assert consistency_score(
        {"workers": ["w1", "w2", "w1"]}
    ) == 0.0


def test_unique_workers_keeps_full_score():
    assert consistency_score(
        {"workers": ["w1", "w2", "w3"]}
    ) == 1.0


def test_combined_violations_partial_score():
    """2 rules apply, 1 violated → 0.5."""
    entity = {
        "data_inicio": date(2026, 5, 1),
        "data_fim": date(2026, 5, 10),  # OK
        "quantidade": 10,
        "quantidade_produzida": 15,  # violation
    }
    assert consistency_score(entity) == 0.5


def test_three_rules_one_violation_two_thirds():
    """All 3 rules apply, 1 violated → ~0.667."""
    entity = {
        "data_inicio": date(2026, 5, 1),
        "data_fim": date(2026, 5, 10),
        "quantidade": 10,
        "quantidade_produzida": 8,
        "workers": ["w1", "w1"],  # only violation
    }
    score = consistency_score(entity)
    assert abs(score - (2 / 3)) < 1e-6
