"""Q.61.29 — regras de consistencia puras (extraidas de trust_index v1).

Antes do Q.61.29 estas 3 regras viviam dentro de
`TrustIndexCalculator._calculate_consistency` (trust_index.py v1,
deprecated desde Q.1). v2 (`trust_v2.py`) tem 7+1 componentes baseados
em factory/order/phase database state — semantica DIFERENTE de v1
(request-shape) e nao expoe esta logica.

Os 8 testes em tests/dqa/test_consistency_rules.py eram a unica razao
para o v1 continuar a existir. Q.61.29 extrai as regras como funcoes
puras + apaga o v1.

Cada regra:
  * Pure function — recebe entity dict, devolve `(applied, violated)`
    onde `applied=True` se os campos relevantes estavam presentes e
    `violated=True` se a regra foi quebrada.
  * `consistency_score()` agrega as 3.
"""

from __future__ import annotations

from typing import Any, Mapping


def check_date_ordering(entity: Mapping[str, Any]) -> tuple[bool, bool]:
    """Regra 1: data_inicio / data_entrada NAO pode ser depois de
    data_fim / data_conclusao. Falha aplica se algum par esta presente.
    """
    start = entity.get("data_inicio") or entity.get("data_entrada")
    end = entity.get("data_fim") or entity.get("data_conclusao")
    if start is None or end is None:
        return False, False
    try:
        return True, start > end
    except TypeError:
        # Tipos nao-comparaveis — conta como violacao (em vez de crashar).
        return True, True


def check_quantity_sanity(entity: Mapping[str, Any]) -> tuple[bool, bool]:
    """Regra 2: quantidade_produzida NAO pode exceder quantidade ordered."""
    ordered = entity.get("quantidade")
    produced = entity.get("quantidade_produzida")
    if ordered is None or produced is None:
        return False, False
    try:
        return True, float(produced) > float(ordered)
    except (TypeError, ValueError):
        return True, True


def check_worker_uniqueness(entity: Mapping[str, Any]) -> tuple[bool, bool]:
    """Regra 3: lista de workers nao pode ter duplicados (uma pessoa
    nao pode estar duas vezes na mesma operacao)."""
    workers = entity.get("workers")
    if not isinstance(workers, (list, tuple)):
        return False, False
    return True, len(workers) != len(set(workers))


def consistency_score(entity: Mapping[str, Any]) -> float:
    """Agrega as 3 regras: cada violacao subtrai 1/N (N = regras que
    foram aplicaveis). Sem regras aplicaveis devolve 1.0.
    """
    applied = 0
    violations = 0
    for check in (check_date_ordering, check_quantity_sanity, check_worker_uniqueness):
        is_applied, is_violated = check(entity)
        if is_applied:
            applied += 1
            if is_violated:
                violations += 1
    if applied == 0:
        return 1.0
    return max(0.0, 1.0 - (violations / applied))


__all__ = [
    "check_date_ordering",
    "check_quantity_sanity",
    "check_worker_uniqueness",
    "consistency_score",
]
