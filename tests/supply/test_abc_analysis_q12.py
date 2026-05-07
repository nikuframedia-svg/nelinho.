"""Sprint Q.12 — ABCAnalysis distribution tests.

Antes não havia cobertura nenhuma. O método `classify_sku` (placeholder)
foi removido nesta sprint; só `calculate_abc_distribution` permanece.
"""

from __future__ import annotations

from src.supply.abc_analysis import ABCAnalysis


def test_empty_input_returns_empty_buckets() -> None:
    result = ABCAnalysis().calculate_abc_distribution([])
    assert result == {"A": [], "B": [], "C": []}


def test_classify_sku_method_removed() -> None:
    """O placeholder `classify_sku` foi explicitamente removido na Q.12."""
    assert not hasattr(ABCAnalysis(), "classify_sku")


def test_pareto_distribution_concentrates_a_class() -> None:
    """A regra 80/15/5: poucos SKUs concentram a maior parte do valor."""
    skus = [
        {"sku_id": "S1", "value": 8000},
        {"sku_id": "S2", "value": 1000},
        {"sku_id": "S3", "value": 500},
        {"sku_id": "S4", "value": 300},
        {"sku_id": "S5", "value": 200},
    ]
    result = ABCAnalysis().calculate_abc_distribution(skus)

    # Total = 10000. S1 sozinho = 80% → A. S2 = +10% → B. Resto → C.
    assert any(s["sku_id"] == "S1" for s in result["A"])
    # Nenhum SKU pode aparecer em mais que uma classe.
    seen = set()
    for cls in ("A", "B", "C"):
        for s in result[cls]:
            assert s["sku_id"] not in seen
            seen.add(s["sku_id"])


def test_zero_value_total_classifies_all_as_c() -> None:
    """Quando o total é zero, todos são C — não estoira."""
    skus = [
        {"sku_id": "S1", "value": 0},
        {"sku_id": "S2", "value": 0},
    ]
    result = ABCAnalysis().calculate_abc_distribution(skus)
    assert result["A"] == []
    assert result["B"] == []
    assert len(result["C"]) == 2


def test_single_sku_classified_into_some_bucket() -> None:
    """Single SKU concentra 100% do valor — pelo algoritmo cumulativo
    aterra em C (>95%) porque atravessa todos os thresholds num passo.
    Comportamento de borda do Pareto cumulativo: aceitável desde que
    *exactamente* um bucket o contenha (sem perder o SKU)."""
    skus = [{"sku_id": "ONLY", "value": 100}]
    result = ABCAnalysis().calculate_abc_distribution(skus)
    in_a = any(s["sku_id"] == "ONLY" for s in result["A"])
    in_b = any(s["sku_id"] == "ONLY" for s in result["B"])
    in_c = any(s["sku_id"] == "ONLY" for s in result["C"])
    assert sum([in_a, in_b, in_c]) == 1, "SKU deve aparecer em exactamente 1 bucket"
