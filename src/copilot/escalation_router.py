"""
ProdPlan ONE — COPILOT escalation router
========================================

Q.66.D.2 — extraído de ``src/copilot/service.py`` (god-file 1708L) durante
a Fase 7 de decomposição. Responsabilidade única: declarar o vocabulário
canónico de "acções escaláveis" que o LLM pode propor no campo
``CopilotResponse.actions[]``.

**Design note** — a execução real dos action handlers (CREATE_DECISION_PR,
RUN_RUNBOOK, DRY_RUN, OPEN_ENTITY) vive em ``src/copilot/api.py`` no
endpoint POST ``/action``, porque depende de FastAPI session/auth/Kafka.
Este módulo mantém apenas:

  1. ``ACTION_TYPES`` — o whitelist (mirrored com o switch em ``api.py``).
  2. ``coerce_action_shape`` — normalização de actions geradas pelo LLM.

Foi mantido como sub-módulo separado em vez de fundido com
``response_renderer.py`` porque a decisão de "que acção propor" é uma
responsabilidade conceptualmente distinta da "como renderizar a resposta":
quando vier a haver escalação automática (Q.61.04 ACTION_WIRING) o
dispatcher orquestrador encaixa aqui sem precisar de re-arquitectar.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.copilot.response_renderer import normalize_actions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Whitelist canónico — mirror do switch em ``src/copilot/api.py`` (POST
# /action). Q.61.04 mantém este mirror sob CI test (ACTION_WIRING roundtrip).
# ---------------------------------------------------------------------------

ACTION_CREATE_DECISION_PR = "CREATE_DECISION_PR"
ACTION_RUN_RUNBOOK = "RUN_RUNBOOK"
ACTION_DRY_RUN = "DRY_RUN"
ACTION_OPEN_ENTITY = "OPEN_ENTITY"

ACTION_TYPES = frozenset({
    ACTION_CREATE_DECISION_PR,
    ACTION_RUN_RUNBOOK,
    ACTION_DRY_RUN,
    ACTION_OPEN_ENTITY,
})


def coerce_actions(actions_raw: Any) -> List[Dict[str, Any]]:
    """Re-export semântico de :func:`response_renderer.normalize_actions`.

    Devolve a lista normalizada de actions prontas para entrar no
    ``CopilotResponse.actions[]``. O nome ``coerce_actions`` deixa claro,
    no caller do orquestrador, que estamos a preparar a escalação (vs.
    a renderização da resposta puramente textual).
    """
    return normalize_actions(actions_raw)
