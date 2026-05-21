"""Q.66.D.4a — router agregador do copiloto.

Sub-routers por endpoint domain vivem em `src/copilot/routers/`:

* ``ask`` — `/ask(-dev)`, `/recommendations(-dev)`,
  `/recommendations/explain(-dev)`, `/insights(-dev)`,
  `/daily-feedback(-dev)`.
* ``actions`` — `/action(-dev)`, `/actions`, `/actions/{id}/rollback`
  (+ helper `_run_copilot_action`).
* ``suggestions`` — `/suggestions/{id}`, `/feedback/user`.
* ``conversations`` — CRUD do chat (`/conversations*`).
* ``health`` — `/health(-reset-circuit)`, `/sandbox`, `/rag/ingest`,
  `/causal/audit`.

Os símbolos de cada sub-router (handlers + colaboradores que entram em
`patch.object(copilot_api, ...)` nos characterization tests da Q.66.D.1c)
são re-exportados aqui para preservar o contrato público — chamadas
directas a `src.copilot.api.<handler>` e patches em
`src.copilot.api.<dep>` continuam a funcionar.
"""

from __future__ import annotations

from fastapi import APIRouter

# ──────────────────────────────────────────────────────────────────────────
# Re-exports de colaboradores que os characterization tests da Q.66.D.1c
# patcham via ``patch.object(copilot_api, "<name>", ...)``. Os sub-routers
# acedem a estes nomes através de ``from src.copilot import api as _api``
# e ``_api.<name>(...)`` para que o monkey-patch propague.
# ──────────────────────────────────────────────────────────────────────────

from src.copilot.actions import (
    ActionExecutor,
    ActionHandlerNotImplementedError,
    ActionMode,
)
from src.copilot.jobs.daily_feedback import (
    generate_daily_feedback,
)
from src.copilot.ollama_client import get_ollama_client
from src.copilot.rag import ingest_document
from src.copilot.rate_limiter import get_rate_limiter
from src.copilot.recommendations import (
    generate_recommendations,
)
from src.copilot.service import CopilotService
from src.governance.audit_service import audit_change

# Dependencies partilhadas (precisam de estar disponíveis quando os
# sub-routers fazem ``from src.copilot import api as _api`` para evitar
# import circular — vivem em ``routers/_common.py``).
from src.copilot.routers._common import (
    dev_only,
    get_tenant_id,
)

# ──────────────────────────────────────────────────────────────────────────
# Sub-routers — IMPORTANTE: importar DEPOIS dos re-exports acima para que
# o ciclo "api.py → routers/*.py → api.py" encontre `_api.<dep>` populado
# quando os handlers forem invocados.
# ──────────────────────────────────────────────────────────────────────────

from src.copilot.routers.actions import (
    _run_copilot_action,
    execute_action,
    execute_action_dev,
    list_actions,
    rollback_action,
)
from src.copilot.routers.actions import router as _actions_router
from src.copilot.routers.ask import (
    ask_copilot,
    ask_copilot_dev,
    explain_recommendations,
    explain_recommendations_dev,
    get_daily_feedback,
    get_daily_feedback_dev,
    get_insights,
    get_insights_dev,
    get_recommendations,
    get_recommendations_dev,
)
from src.copilot.routers.ask import router as _ask_router
from src.copilot.routers.conversations import (
    archive_conversation,
    create_conversation,
    get_conversation_messages,
    list_conversations,
    rename_conversation,
    send_message,
)
from src.copilot.routers.conversations import router as _conversations_router
from src.copilot.routers.health import (
    copilot_health,
    execute_sandbox,
    ingest_rag_document,
    post_causal_audit,
    reset_circuit_breaker,
)
from src.copilot.routers.health import router as _health_router
from src.copilot.routers.suggestions import (
    get_suggestion,
    submit_user_feedback,
)
from src.copilot.routers.suggestions import router as _suggestions_router

# ──────────────────────────────────────────────────────────────────────────
# Router agregador — mantém o prefix `/api/copilot` legado para não partir
# o contrato URL com o frontend (src/lib/api/copilotApi.ts, PainelDiario,
# etc.) nem o `src.main:app.include_router(copilot_router)`.
# ──────────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/copilot", tags=["COPILOT"])
router.include_router(_ask_router)
router.include_router(_actions_router)
router.include_router(_suggestions_router)
router.include_router(_conversations_router)
router.include_router(_health_router)

__all__ = [
    # Aggregator
    "router",
    # Shared deps
    "dev_only",
    "get_tenant_id",
    # Patch targets (characterization tests)
    "ActionExecutor",
    "ActionHandlerNotImplementedError",
    "ActionMode",
    "CopilotService",
    "audit_change",
    "generate_daily_feedback",
    "generate_recommendations",
    "get_ollama_client",
    "get_rate_limiter",
    "ingest_document",
    # Handlers — ask
    "ask_copilot",
    "ask_copilot_dev",
    "explain_recommendations",
    "explain_recommendations_dev",
    "get_daily_feedback",
    "get_daily_feedback_dev",
    "get_insights",
    "get_insights_dev",
    "get_recommendations",
    "get_recommendations_dev",
    # Handlers — actions
    "_run_copilot_action",
    "execute_action",
    "execute_action_dev",
    "list_actions",
    "rollback_action",
    # Handlers — suggestions
    "get_suggestion",
    "submit_user_feedback",
    # Handlers — conversations
    "archive_conversation",
    "create_conversation",
    "get_conversation_messages",
    "list_conversations",
    "rename_conversation",
    "send_message",
    # Handlers — health
    "copilot_health",
    "execute_sandbox",
    "ingest_rag_document",
    "post_causal_audit",
    "reset_circuit_breaker",
]
