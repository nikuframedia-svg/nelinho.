"""
ProdPlan ONE - Copilot Action Handlers
======================================

Q.37.D — handlers reais para as acções que o copiloto propõe e que,
depois de aprovadas por um humano (invariante 4), o `ActionExecutor`
executa em modo EXECUTE / SANDBOX.

Princípio de segurança (risco do plano Q.37): **zero** importações de
`src/plan/cpo/decoder|fitness|pair_assignment|state|chromosome`. Os
handlers de scheduling orquestram apenas a API pública
`POST /v1/plan/cpo/schedule` — que reaproveita todos os guardrails do
`CPOv4Engine` e o hook `yaml_policy`. O handler de inventário escreve
directamente em `Product.safety_stock` mas recusa descer abaixo do
baseline (axioma 7 — safety_net ≥ baseline).

`register_all_action_handlers()` é chamado uma vez no lifespan de
`src/main.py`.
"""

from __future__ import annotations

import logging

from src.copilot.actions import register_action_handler
from src.copilot.action_handlers import inventory, scheduling

logger = logging.getLogger(__name__)

# action_type → handler. As chaves casam com `ActionType` em
# `src/copilot/actions.py` (valores em snake_case).
_HANDLER_MAP = {
    "adjust_inventory": inventory.adjust_inventory,
    "reschedule_order": scheduling.reschedule_order,
    "optimize_capacity": scheduling.optimize_capacity,
    "reduce_setup": scheduling.reduce_setup,
}


def register_all_action_handlers(*, overwrite: bool = True) -> int:
    """Regista todos os handlers reais no registo de `actions.py`.

    Idempotente quando ``overwrite=True`` (default) — pode ser chamado
    em cada arranque sem rebentar com "already registered".

    Devolve o número de handlers registados.
    """
    for action_type, handler in _HANDLER_MAP.items():
        register_action_handler(action_type, handler, overwrite=overwrite)
    logger.info(
        "Copilot action handlers registados: %s", sorted(_HANDLER_MAP)
    )
    return len(_HANDLER_MAP)


__all__ = ["register_all_action_handlers"]
