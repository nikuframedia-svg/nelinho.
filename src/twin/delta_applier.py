"""
ProdPlan ONE - Twin: Delta validation + application
===================================================

Q.67.6.B1 - extraido de `src/twin/service.py` (god-file 1192L). Validacao
de delta-patches (Q.54.I) + aplicacao deterministica de cada
`entity_type` ao estado projectado. Whitelist fechada - tipos
desconhecidos sao REJEITADOS, nao ignorados em silencio.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Dict


# =============================================================================
# Q.54.I - validacao robusta de simulacoes
# =============================================================================


class TwinValidationError(ValueError):
    """Input invalido numa simulacao Twin.

    Subclasse de :class:`ValueError` (por isso o codigo existente que faz
    ``except ValueError`` continua a apanha-la), mas o endpoint distingue-a
    para devolver **HTTP 422** em vez de 400/404 - e erro do *input*, nao
    "cenario nao encontrado". Mensagens sempre em PT-PT.
    """


# entity_type -> conjunto de patch-keys que TEM de ser uma percentagem [-100, 100].
# Q.54.I - `apply_delta_to_state` e uma whitelist fechada; estas sao as
# chaves que afectam KPIs e por isso precisam de validacao numerica estrita.
_PERCENTAGE_PATCH_KEYS: Dict[str, tuple[str, ...]] = {
    "capacity_adjustment": ("capacity_increase_pct",),
    "standard_time": ("reduction_pct",),
    "quality_improvement": ("error_reduction_pct",),
}

# entity_type -> patch-keys que tem de ser uma contagem nao-negativa.
_NON_NEGATIVE_PATCH_KEYS: Dict[str, tuple[str, ...]] = {
    "skills_training": ("phases_trained",),
    "wip_policy": ("wip_limit",),
}

# Todos os entity_type que `apply_delta_to_state` sabe aplicar. Um delta com
# um tipo fora desta lista e REJEITADO (Q.54.I) - antes era ignorado em
# silencio, o que dava ao utilizador uma simulacao sem efeito sem o avisar.
SUPPORTED_DELTA_ENTITY_TYPES: tuple[str, ...] = (
    "capacity_adjustment",
    "standard_time",
    "skills_training",
    "quality_improvement",
    "wip_policy",
    "scheduling_input",
)


def is_finite_number(value: Any) -> bool:
    """True so se ``value`` e um numero real finito (exclui bool/NaN/inf)."""
    # bool e subclasse de int - um patch com `True` nao e uma percentagem.
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def validate_delta_patch(entity_type: str, patch: Dict[str, Any]) -> None:
    """Q.54.I - valida um delta de simulacao antes de o aceitar.

    Rejeita com :class:`TwinValidationError` (-> HTTP 422):

    * ``entity_type`` desconhecido (fora de
      :data:`SUPPORTED_DELTA_ENTITY_TYPES`) - antes era ignorado em silencio;
    * valores nao-numericos, ``NaN`` ou ``inf`` em chaves numericas;
    * percentagens fora da gama ``[-100, 100]``;
    * contagens negativas (``phases_trained``, ``wip_limit``).

    ``scheduling_input`` nao traz chaves numericas de KPI - a sua estrutura
    (operations[]+machines[]) e validada pelo solver, por isso aqui so
    confirmamos que o tipo e conhecido.
    """
    if entity_type not in SUPPORTED_DELTA_ENTITY_TYPES:
        raise TwinValidationError(
            f"entity_type desconhecido: {entity_type!r}. "
            f"Tipos suportados: {', '.join(SUPPORTED_DELTA_ENTITY_TYPES)}."
        )

    patch = patch or {}

    for key in _PERCENTAGE_PATCH_KEYS.get(entity_type, ()):
        if key not in patch:
            continue
        value = patch[key]
        if not is_finite_number(value):
            raise TwinValidationError(
                f"{entity_type}.{key} tem de ser um número finito — "
                f"recebido {value!r} (NaN/inf/texto não são aceites)."
            )
        if not (-100.0 <= float(value) <= 100.0):
            raise TwinValidationError(
                f"{entity_type}.{key} tem de ser uma percentagem entre "
                f"-100 e 100 — recebido {value!r}."
            )

    for key in _NON_NEGATIVE_PATCH_KEYS.get(entity_type, ()):
        if key not in patch:
            continue
        value = patch[key]
        if not is_finite_number(value):
            raise TwinValidationError(
                f"{entity_type}.{key} tem de ser um número finito — "
                f"recebido {value!r}."
            )
        if float(value) < 0:
            raise TwinValidationError(
                f"{entity_type}.{key} não pode ser negativo — "
                f"recebido {value!r}."
            )


def apply_delta_to_state(
    state: Dict[str, Any], delta: Dict[str, Any]
) -> Dict[str, Any]:
    """Apply a delta to a state and return new state.

    Q.54.I - `deepcopy` (nao `.copy()` shallow): cada KPI no estado e
    um dict aninhado `{"value": ...}`; um shallow copy partilharia
    esses dicts e a escrita `new_state[k]["value"] *= ...` mutava
    tambem o `state` de entrada. `entity_type` desconhecido e
    rejeitado em vez de devolver o estado intacto sem aviso.
    """
    new_state = copy.deepcopy(state)

    entity_type = delta.get("entity_type", "")
    patch = delta.get("patch", {}) or {}

    # Q.54.I - `apply_delta_to_state` e uma whitelist fechada. Um tipo
    # fora dela nao tem efeito nenhum - antes caia pelo fim da cadeia
    # de `if` e devolvia `new_state` igual, deixando o utilizador a
    # crer que o cenario tinha sido modelado. Falha alto.
    if entity_type not in SUPPORTED_DELTA_ENTITY_TYPES:
        raise TwinValidationError(
            f"entity_type desconhecido: {entity_type!r}. "
            f"Tipos suportados: {', '.join(SUPPORTED_DELTA_ENTITY_TYPES)}."
        )

    if entity_type == "capacity_adjustment":
        if "capacity_increase_pct" in patch:
            increase = patch["capacity_increase_pct"]
            if "backlog_horas_theoretical" in new_state:
                current = new_state["backlog_horas_theoretical"]
                if isinstance(current, dict) and current.get("value"):
                    new_state["backlog_horas_theoretical"]["value"] *= (1 - increase / 100)

    elif entity_type == "standard_time":
        if "reduction_pct" in patch:
            reduction = patch["reduction_pct"]
            if "backlog_horas_theoretical" in new_state:
                current = new_state["backlog_horas_theoretical"]
                if isinstance(current, dict) and current.get("value"):
                    new_state["backlog_horas_theoretical"]["value"] *= (1 - reduction / 100)

    elif entity_type == "skills_training":
        if "phases_trained" in patch:
            trained = patch["phases_trained"]
            if "skills_at_risk_count" in new_state:
                current = new_state["skills_at_risk_count"]
                if isinstance(current, dict) and current.get("value"):
                    new_state["skills_at_risk_count"]["value"] = max(0, current["value"] - trained)

    elif entity_type == "quality_improvement":
        if "error_reduction_pct" in patch:
            reduction = patch["error_reduction_pct"]
            if "quality_errors_total" in new_state:
                current = new_state["quality_errors_total"]
                if isinstance(current, dict) and current.get("value"):
                    new_state["quality_errors_total"]["value"] *= (1 - reduction / 100)

    elif entity_type == "wip_policy":
        if "wip_limit" in patch:
            limit = patch["wip_limit"]
            if "wip_theoretical" in new_state:
                current = new_state["wip_theoretical"]
                if isinstance(current, dict) and current.get("value"):
                    new_state["wip_theoretical"]["value"] = min(current["value"], limit)

    return new_state
