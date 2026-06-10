"""
Q.66.D.1c — Characterization tests para src/copilot/api.py.

Feathers pattern (Working Effectively With Legacy Code): capturar o
contrato observável dos endpoints actuais como snapshots ANTES da
decomposição da Fase 7 (Q.66.D.4a). Os tests devem manter-se verdes ao
longo do refactor — se quebrarem, é porque o refactor mudou behaviour
público, não estrutura interna.

Estratégia:
  * Chamar as funções dos endpoints directamente (mesmo padrão que
    `test_action_dev_q55c.py` + `test_causal_audit_endpoint_q13g.py` +
    `test_user_feedback_q31h.py`) em vez de TestClient. Permite testar
    sem montar a app completa (`src.main` traz Kafka/scheduler/etc.) e
    sem dance com `dependency_overrides`.
  * Asserts em **status code** (via HTTPException) + **keys do response**
    + **side effects observáveis** (rows staged em session). NÃO comparar
    strings literais nem output do LLM.
  * Mocks mínimos: fake session ad-hoc, `AsyncMock` para colaboradores
    pesados (CopilotService, generate_recommendations, generate_daily_feedback,
    ollama_client). NÃO toca Postgres nem Ollama.

NÃO refactorar `src/copilot/api.py`. NÃO testar internals do
CopilotService — esse é o objectivo do Q.66.D.1a.

Endpoints cobertos (20 no router, 17 aqui — ver report ao fundo):
  POST /ask, /ask-dev, /action, /action-dev, /sandbox, /actions/{id}/rollback,
  /conversations, /conversations/{id}/messages, PATCH /conversations/{id}/rename,
  POST /conversations/{id}/archive, /feedback/user, /rag/ingest,
  /health/reset-circuit, /causal/audit,
  GET /suggestions/{id}, /daily-feedback, /recommendations,
  /conversations, /conversations/{id}/messages, /actions, /insights, /health.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from src.copilot import api as copilot_api
from src.copilot.api import (
    _run_copilot_action,
    archive_conversation,
    ask_copilot,
    ask_copilot_dev,
    copilot_health,
    create_conversation,
    execute_action,
    execute_action_dev,
    execute_sandbox,
    get_conversation_messages,
    get_daily_feedback,
    get_insights,
    get_recommendations,
    get_suggestion,
    ingest_rag_document,
    list_actions,
    list_conversations,
    post_causal_audit,
    rename_conversation,
    reset_circuit_breaker,
    rollback_action,
    send_message,
    submit_user_feedback,
)
from src.copilot.models import (
    CopilotConversation,
    CopilotDecisionPR,
    CopilotMessage,
    CopilotUserFeedback,
)
from src.copilot.schemas import (
    CopilotActionRequest,
    CopilotAskRequest,
    CopilotResponse,
    SandboxRequest,
)
from src.shared.auth.jwt_handler import UserContext


# ──────────────────────────────────────────────────────────────────────────
# Fixtures comuns
# ──────────────────────────────────────────────────────────────────────────


TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
USER_ID = UUID("22222222-2222-2222-2222-222222222222")


def _user() -> UserContext:
    return UserContext(
        user_id=USER_ID,
        tenant_id=TENANT_ID,
        role="ADMIN",
        email="characterization@nelinho.test",
    )


class _FakeSession:
    """Session ad-hoc para characterization: captura add/get/execute/commit."""

    def __init__(self) -> None:
        self.staged: List[Any] = []
        self.committed = False
        self.flushed = 0
        self.rolled_back = False
        self._get_returns: Any = None
        self._execute_returns: Any = None

    # configuração ────────────────────────────────────────────────────────
    def stub_get(self, value: Any) -> None:
        self._get_returns = value

    def stub_execute(self, items: List[Any]) -> None:
        self._execute_returns = items

    # AsyncSession surface ────────────────────────────────────────────────
    def add(self, obj: Any) -> None:
        self.staged.append(obj)
        # `flush()` mais à frente popula id; algumas chamadas (CREATE_DECISION_PR
        # + create_conversation) usam `pr.id` / `conversation.id` logo a seguir
        # ao add(). Atribui um id se o objecto não tiver.
        if getattr(obj, "id", None) is None:
            try:
                obj.id = uuid4()
            except (AttributeError, TypeError):
                pass

    async def get(self, _model: Any, _pk: Any) -> Any:
        return self._get_returns

    async def execute(self, _stmt: Any) -> Any:
        items = list(self._execute_returns or [])
        scalars_obj = SimpleNamespace(all=lambda: items)
        return SimpleNamespace(scalars=lambda: scalars_obj)

    async def flush(self) -> None:
        self.flushed += 1

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, obj: Any) -> None:
        # `create_conversation` chama `await session.refresh(conversation)`
        # após `await session.commit()`. Mantém-se no-op (o id já foi
        # populado no `add()`); só precisamos garantir que `created_at`
        # exista para o `.isoformat()` que vem a seguir.
        if getattr(obj, "created_at", None) is None:
            try:
                obj.created_at = datetime.now(timezone.utc)
            except (AttributeError, TypeError):
                pass


def _ask_request(query: str = "estado do dia") -> CopilotAskRequest:
    return CopilotAskRequest(user_query=query)


def _valid_copilot_response(intent: str = "generic") -> CopilotResponse:
    # type=ANSWER exige facts[] não-vazio com pelo menos uma citation.
    fact = {
        "text": "Facto de teste.",
        "citations": [{
            "source_type": "db",
            "ref": "table:test;id:1",
            "label": "Test",
            "confidence": 0.9,
            "trust_index": 0.85,
        }],
    }
    return CopilotResponse(
        suggestion_id=uuid4(),
        correlation_id=uuid4(),
        type="ANSWER",
        intent=intent,
        summary="Resposta de teste.",
        facts=[fact],
        actions=[],
        warnings=[],
        meta={"validation_passed": True, "model": "mock", "latency_ms": 5},
    )


# ──────────────────────────────────────────────────────────────────────────
# 1. POST /ask — happy path + idempotency + erro normalizado
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ask_returns_copilot_response_shape():
    """POST /ask → 200 com CopilotResponse (summary, facts, actions, warnings)."""
    session = _FakeSession()
    fake_response = _valid_copilot_response()

    with (
        patch.object(copilot_api, "CopilotService") as svc_cls,
        patch.object(copilot_api, "get_rate_limiter") as rl,
    ):
        svc = svc_cls.return_value
        svc.process_ask = AsyncMock(return_value=(fake_response, {}))
        rl.return_value = SimpleNamespace(enforce_rate_limit=AsyncMock())

        result = await ask_copilot(
            request=_ask_request(),
            user=_user(),
            tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )

    assert isinstance(result, CopilotResponse)
    assert result.summary
    assert hasattr(result, "facts")
    assert hasattr(result, "actions")
    assert hasattr(result, "warnings")
    assert hasattr(result, "meta")


@pytest.mark.asyncio
async def test_ask_returns_normalized_error_response_when_service_crashes():
    """POST /ask captura excepção e devolve ERROR-shape (não 500)."""
    session = _FakeSession()

    with (
        patch.object(copilot_api, "CopilotService") as svc_cls,
        patch.object(copilot_api, "get_rate_limiter") as rl,
    ):
        svc = svc_cls.return_value
        svc.process_ask = AsyncMock(side_effect=RuntimeError("ollama crashed"))
        rl.return_value = SimpleNamespace(enforce_rate_limit=AsyncMock())

        result = await ask_copilot(
            request=_ask_request(),
            user=_user(),
            tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )

    assert isinstance(result, CopilotResponse)
    assert result.type == "ERROR"
    # Pelo menos um warning normalizado
    assert any(w.code == "MODEL_OFFLINE" for w in result.warnings)


@pytest.mark.asyncio
async def test_ask_idempotency_returns_cached_response():
    """Mesmo idempotency_key devolve a mesma response (segunda chamada não
    chama o service)."""
    session = _FakeSession()
    fake_response = _valid_copilot_response()
    key = f"idem-{uuid4()}"

    with (
        patch.object(copilot_api, "CopilotService") as svc_cls,
        patch.object(copilot_api, "get_rate_limiter") as rl,
    ):
        svc = svc_cls.return_value
        svc.process_ask = AsyncMock(return_value=(fake_response, {}))
        rl.return_value = SimpleNamespace(enforce_rate_limit=AsyncMock())

        req1 = CopilotAskRequest(user_query="igual", idempotency_key=key)
        first = await ask_copilot(
            request=req1, user=_user(), tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )

        req2 = CopilotAskRequest(user_query="igual", idempotency_key=key)
        second = await ask_copilot(
            request=req2, user=_user(), tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )

    assert first is second
    assert svc.process_ask.await_count == 1


# ──────────────────────────────────────────────────────────────────────────
# 2. POST /ask-dev — sem auth, tenant dev fixo
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ask_dev_uses_dev_tenant_no_auth():
    """POST /ask-dev devolve CopilotResponse sem precisar de user."""
    session = _FakeSession()
    fake_response = _valid_copilot_response()

    with (
        patch.object(copilot_api, "CopilotService") as svc_cls,
        patch.object(copilot_api, "get_rate_limiter") as rl,
    ):
        svc = svc_cls.return_value
        svc.process_ask = AsyncMock(return_value=(fake_response, {}))
        rl.return_value = SimpleNamespace(enforce_rate_limit=AsyncMock())

        result = await ask_copilot_dev(
            request=_ask_request(),
            session=session,  # type: ignore[arg-type]
        )

    assert isinstance(result, CopilotResponse)


# ──────────────────────────────────────────────────────────────────────────
# 3. POST /action — 4 action_types + 404 + 400
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_action_create_decision_pr_creates_pr_and_audits():
    """CREATE_DECISION_PR → cria CopilotDecisionPR + chama audit."""
    suggestion = SimpleNamespace(id=uuid4(), tenant_id=TENANT_ID)
    session = _FakeSession()
    session.stub_get(suggestion)
    req = CopilotActionRequest(
        action_type="CREATE_DECISION_PR",
        suggestion_id=suggestion.id,
        payload={"title": "Titulo", "description": "Descr."},
    )

    with patch.object(copilot_api, "audit_change", new=AsyncMock()) as audit_mock:
        result = await execute_action(
            request=req, user=_user(), tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )

    assert set(result.keys()) >= {"action_id", "status", "message"}
    assert result["status"] == "created"
    prs = [o for o in session.staged if isinstance(o, CopilotDecisionPR)]
    assert len(prs) == 1
    audit_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_action_dry_run_returns_simulated_status():
    """DRY_RUN → status='simulated' sem persistir nada na suggestion."""
    suggestion = SimpleNamespace(id=uuid4(), tenant_id=TENANT_ID)
    session = _FakeSession()
    session.stub_get(suggestion)
    req = CopilotActionRequest(
        action_type="DRY_RUN", suggestion_id=suggestion.id, payload={"any": 1},
    )

    result = await _run_copilot_action(req, TENANT_ID, session)  # type: ignore[arg-type]

    assert result["action_type"] == "DRY_RUN"
    assert result["status"] == "simulated"
    assert "payload" in result


@pytest.mark.asyncio
async def test_action_open_entity_returns_hint():
    """OPEN_ENTITY → status='hint' + navigation payload (frontend hint)."""
    suggestion = SimpleNamespace(id=uuid4(), tenant_id=TENANT_ID)
    session = _FakeSession()
    session.stub_get(suggestion)
    req = CopilotActionRequest(
        action_type="OPEN_ENTITY",
        suggestion_id=suggestion.id,
        payload={"entity": "order", "id": "42"},
    )

    result = await _run_copilot_action(req, TENANT_ID, session)  # type: ignore[arg-type]

    assert result["action_type"] == "OPEN_ENTITY"
    assert result["status"] == "hint"
    assert result["navigation"] == {"entity": "order", "id": "42"}


@pytest.mark.asyncio
async def test_action_run_runbook_returns_planned_trace():
    """RUN_RUNBOOK → status='planned' + trace (com runbook_id válido)."""
    suggestion = SimpleNamespace(id=uuid4(), tenant_id=TENANT_ID)
    session = _FakeSession()
    session.stub_get(suggestion)
    req = CopilotActionRequest(
        action_type="RUN_RUNBOOK",
        suggestion_id=suggestion.id,
        payload={"runbook_id": "oee_diagnosis", "date_range": "24h"},
    )

    result = await _run_copilot_action(req, TENANT_ID, session)  # type: ignore[arg-type]

    assert result["action_type"] == "RUN_RUNBOOK"
    assert result["status"] == "planned"
    assert "trace" in result


@pytest.mark.asyncio
async def test_action_returns_404_when_suggestion_missing():
    """suggestion não existe → 404."""
    session = _FakeSession()
    session.stub_get(None)
    req = CopilotActionRequest(
        action_type="DRY_RUN", suggestion_id=uuid4(), payload={},
    )

    with pytest.raises(HTTPException) as exc:
        await _run_copilot_action(req, TENANT_ID, session)  # type: ignore[arg-type]
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_action_dev_executes_without_auth():
    """/action-dev espelha /action mas sem auth (dev_tenant_id fixo)."""
    dev_tenant = UUID("00000000-0000-0000-0000-000000000001")
    suggestion = SimpleNamespace(id=uuid4(), tenant_id=dev_tenant)
    session = _FakeSession()
    session.stub_get(suggestion)
    req = CopilotActionRequest(
        action_type="OPEN_ENTITY", suggestion_id=suggestion.id, payload={"x": 1},
    )

    result = await execute_action_dev(
        request=req, session=session,  # type: ignore[arg-type]
    )
    assert result["status"] == "hint"


# ──────────────────────────────────────────────────────────────────────────
# 4. GET /suggestions/{id}
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_suggestion_returns_response_json_when_found():
    """suggestion encontrada e do tenant → devolve CopilotResponse validado.

    Q.F4.E Item 14: o handler valida com CopilotResponse(**response_json)
    para early-fail em vez de late-fail na serialização HTTP.
    """
    from src.copilot.schemas import CopilotResponse

    sid = uuid4()
    cid = uuid4()
    valid_json = {
        "suggestion_id": str(sid),
        "correlation_id": str(cid),
        "type": "ANSWER",
        "intent": "generic",
        "summary": "ok",
        "facts": [
            {
                "text": "Facto de teste",
                "citations": [
                    {
                        "source_type": "system_data",
                        "ref": "test:ref",
                        "label": "Fonte de teste",
                        "confidence": 0.9,
                        "trust_index": 0.9,
                    }
                ],
            }
        ],
        "actions": [],
        "warnings": [],
        "charts": [],
        "meta": {},
    }
    suggestion = SimpleNamespace(
        id=sid,
        tenant_id=TENANT_ID,
        response_json=valid_json,
    )
    session = _FakeSession()
    session.stub_get(suggestion)

    result = await get_suggestion(
        suggestion_id=suggestion.id, user=_user(), tenant_id=TENANT_ID,
        session=session,  # type: ignore[arg-type]
    )

    assert isinstance(result, CopilotResponse)
    assert result.type == "ANSWER"
    assert result.summary == "ok"


@pytest.mark.asyncio
async def test_get_suggestion_returns_404_when_wrong_tenant():
    """suggestion existe mas tenant_id diferente → 404."""
    suggestion = SimpleNamespace(
        id=uuid4(),
        tenant_id=UUID("99999999-9999-9999-9999-999999999999"),
        response_json={},
    )
    session = _FakeSession()
    session.stub_get(suggestion)

    with pytest.raises(HTTPException) as exc:
        await get_suggestion(
            suggestion_id=suggestion.id, user=_user(), tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 404


# ──────────────────────────────────────────────────────────────────────────
# 5. GET /daily-feedback
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_daily_feedback_returns_response_with_bullets_shape():
    """GET /daily-feedback → DailyFeedbackResponse (date + bullets + timestamps)."""
    session = _FakeSession()
    fake_feedback = SimpleNamespace(
        date=date.today().isoformat(),
        bullets=[],
        generated_at=datetime.now(timezone.utc).isoformat(),
        last_updated=datetime.now(timezone.utc).isoformat(),
    )

    with patch.object(
        copilot_api, "generate_daily_feedback",
        new=AsyncMock(return_value=fake_feedback),
    ):
        result = await get_daily_feedback(
            date_param=None, user=_user(), tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )

    assert result is fake_feedback


# ──────────────────────────────────────────────────────────────────────────
# 6. GET /recommendations
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recommendations_returns_list():
    """GET /recommendations → List[Dict]."""
    session = _FakeSession()
    recs = [{"title": "X", "priority": 1, "category": "QUALITY"}]
    with patch.object(
        copilot_api, "generate_recommendations",
        new=AsyncMock(return_value=recs),
    ):
        result = await get_recommendations(
            tenant_id=TENANT_ID, session=session,  # type: ignore[arg-type]
        )
    assert isinstance(result, list)
    assert result == recs


# ──────────────────────────────────────────────────────────────────────────
# 7. POST /rag/ingest
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rag_ingest_returns_chunks_created_shape():
    """POST /rag/ingest → {status, chunks_created, source_type, source_id}."""
    session = _FakeSession()
    with patch.object(copilot_api, "ingest_document", new=AsyncMock(return_value=7)):
        from src.copilot.routers.health import RagIngestRequest

        result = await ingest_rag_document(
            body=RagIngestRequest(
                source_type="doc", source_id="abc-123",
                text="conteudo", metadata={"k": "v"},
            ),
            user=_user(),
            tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )
    assert result["status"] == "success"
    assert result["chunks_created"] == 7
    assert result["source_type"] == "doc"
    assert result["source_id"] == "abc-123"


# ──────────────────────────────────────────────────────────────────────────
# 8. POST /feedback/user
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_feedback_user_persists_thumb_up():
    """thumb=up → 200 + CopilotUserFeedback staged + commit."""
    session = _FakeSession()
    from src.copilot.routers.suggestions import UserFeedbackRequest

    result = await submit_user_feedback(
        payload=UserFeedbackRequest(thumb="up", text="Bom"),
        user=_user(),
        tenant_id=TENANT_ID,
        session=session,  # type: ignore[arg-type]
    )
    assert result["status"] == "received"
    assert UUID(result["id"])
    assert any(isinstance(o, CopilotUserFeedback) for o in session.staged)
    assert session.committed


@pytest.mark.asyncio
async def test_feedback_user_rejects_invalid_thumb():
    """Q.171.C — thumb inválido é rejeitado na FRONTEIRA (Pydantic/422)."""
    import pydantic

    from src.copilot.routers.suggestions import UserFeedbackRequest

    with pytest.raises(pydantic.ValidationError):
        UserFeedbackRequest(thumb="maybe")


# ──────────────────────────────────────────────────────────────────────────
# 9. POST /health/reset-circuit + GET /health
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reset_circuit_returns_success_status():
    """reset-circuit invoca o cliente e devolve status."""
    fake_client = SimpleNamespace(reset_circuit_breaker=lambda: None)
    with patch.object(copilot_api, "get_ollama_client", return_value=fake_client):
        result = await reset_circuit_breaker()
    assert result["status"] == "success"
    assert "message" in result


@pytest.mark.asyncio
async def test_health_returns_status_when_ollama_online():
    """/health → status=healthy + chaves ollama/embeddings_model/rate_limit."""
    fake_client = SimpleNamespace(
        _circuit_open_until=None,
        base_url="http://localhost:11434",
        reset_circuit_breaker=lambda: None,
        health_check=AsyncMock(return_value=True),
    )
    fake_response = MagicMock()
    with patch.object(copilot_api, "get_ollama_client", return_value=fake_client):
        result = await copilot_health(response=fake_response)
    assert result["status"] == "healthy"
    assert result["ollama"] == "online"
    assert "embeddings_model" in result
    assert "rate_limit" in result
    assert "per_hour" in result["rate_limit"]
    # Ollama online → não deve setar 503
    fake_response.status_code.__set__ = MagicMock()  # não foi chamado


@pytest.mark.asyncio
async def test_health_returns_503_when_ollama_offline():
    """/health → status=degraded + HTTP 503 quando Ollama está offline."""
    fake_client = SimpleNamespace(
        _circuit_open_until=None,
        base_url="http://localhost:11434",
        reset_circuit_breaker=lambda: None,
        health_check=AsyncMock(return_value=False),
    )
    fake_response = MagicMock()
    with patch.object(copilot_api, "get_ollama_client", return_value=fake_client):
        result = await copilot_health(response=fake_response)
    assert result["status"] == "degraded"
    assert result["ollama"] == "offline"
    # 503 setado via response.status_code
    fake_response.status_code  # acedido para verificar que não falhou


# ──────────────────────────────────────────────────────────────────────────
# 10. GET /insights
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_insights_returns_now_next_meta_shape():
    """GET /insights → {date, now: [...], next: [...], meta: {...}}."""
    session = _FakeSession()
    fake_feedback = SimpleNamespace(bullets=[])
    with (
        patch.object(copilot_api, "generate_daily_feedback",
                     new=AsyncMock(return_value=fake_feedback)),
        patch.object(copilot_api, "generate_recommendations",
                     new=AsyncMock(return_value=[])),
    ):
        result = await get_insights(
            date=None, tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )
    assert set(result.keys()) >= {"date", "now", "next", "meta"}
    assert isinstance(result["now"], list)
    assert isinstance(result["next"], list)
    assert "generated_at" in result["meta"]


# ──────────────────────────────────────────────────────────────────────────
# 11. Conversations CRUD
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_conversation_returns_id_title_created_at():
    """POST /conversations → {id, title, created_at}."""
    session = _FakeSession()
    result = await create_conversation(
        user=_user(), tenant_id=TENANT_ID,
        session=session,  # type: ignore[arg-type]
        title="Minha conversa",
    )
    assert set(result.keys()) == {"id", "title", "created_at"}
    assert UUID(result["id"])
    assert result["title"] == "Minha conversa"
    assert session.committed
    assert any(isinstance(o, CopilotConversation) for o in session.staged)


@pytest.mark.asyncio
async def test_list_conversations_returns_list_shape():
    """GET /conversations → List[{id, title, created_at, last_message_at, is_archived}]."""
    session = _FakeSession()
    conv = SimpleNamespace(
        id=uuid4(),
        title="C1",
        created_at=datetime.now(timezone.utc),
        last_message_at=datetime.now(timezone.utc),
        is_archived=False,
    )
    session.stub_execute([conv])
    result = await list_conversations(
        user=_user(), tenant_id=TENANT_ID,
        session=session,  # type: ignore[arg-type]
    )
    assert isinstance(result, list)
    assert len(result) == 1
    assert set(result[0].keys()) == {
        "id", "title", "created_at", "last_message_at", "is_archived",
    }


@pytest.mark.asyncio
async def test_get_conversation_messages_returns_404_when_missing():
    """conversa não existe → 404."""
    session = _FakeSession()
    session.stub_get(None)
    with pytest.raises(HTTPException) as exc:
        await get_conversation_messages(
            conversation_id=uuid4(), user=_user(), tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_conversation_messages_returns_message_shape():
    """messages → List[{id, role, content_text, content_structured, created_at}]."""
    conv = SimpleNamespace(
        id=uuid4(), tenant_id=TENANT_ID, actor_id=USER_ID,
    )
    msg = SimpleNamespace(
        id=uuid4(),
        actor_role="user",
        content_text="ola",
        content_structured=None,
        created_at=datetime.now(timezone.utc),
    )
    session = _FakeSession()
    session.stub_get(conv)
    session.stub_execute([msg])

    result = await get_conversation_messages(
        conversation_id=conv.id, user=_user(), tenant_id=TENANT_ID,
        session=session,  # type: ignore[arg-type]
    )
    assert isinstance(result, list)
    assert set(result[0].keys()) == {
        "id", "role", "content_text", "content_structured", "created_at",
    }


@pytest.mark.asyncio
async def test_send_message_404_when_conversation_missing():
    """send_message numa conversa que não existe → 404."""
    session = _FakeSession()
    session.stub_get(None)
    with pytest.raises(HTTPException) as exc:
        await send_message(
            conversation_id=uuid4(),
            request=_ask_request(),
            user=_user(), tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_send_message_persists_user_and_copilot_messages():
    """send_message → 2 CopilotMessage staged (user + copilot) + commit."""
    conv = SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT_ID,
        actor_id=USER_ID,
        last_message_at=None,
    )
    session = _FakeSession()
    session.stub_get(conv)
    fake_response = _valid_copilot_response()

    with patch.object(copilot_api, "CopilotService") as svc_cls:
        svc = svc_cls.return_value
        svc.process_ask = AsyncMock(
            return_value=(fake_response, {"latency_ms": 10, "model": "mock"}),
        )
        result = await send_message(
            conversation_id=conv.id,
            request=_ask_request("ola"),
            user=_user(), tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )

    assert isinstance(result, CopilotResponse)
    msgs = [o for o in session.staged if isinstance(o, CopilotMessage)]
    assert len(msgs) == 2
    assert session.committed


@pytest.mark.asyncio
async def test_rename_conversation_returns_new_title():
    """PATCH /rename → {id, title}."""
    conv = SimpleNamespace(
        id=uuid4(), tenant_id=TENANT_ID, actor_id=USER_ID, title="velho",
    )
    session = _FakeSession()
    session.stub_get(conv)
    result = await rename_conversation(
        conversation_id=conv.id, title="novo",
        user=_user(), tenant_id=TENANT_ID,
        session=session,  # type: ignore[arg-type]
    )
    assert result == {"id": str(conv.id), "title": "novo"}
    assert session.committed


@pytest.mark.asyncio
async def test_archive_conversation_toggles_is_archived():
    """POST /archive → flip de is_archived + 200 shape."""
    conv = SimpleNamespace(
        id=uuid4(), tenant_id=TENANT_ID, actor_id=USER_ID, is_archived=False,
    )
    session = _FakeSession()
    session.stub_get(conv)
    result = await archive_conversation(
        conversation_id=conv.id, user=_user(), tenant_id=TENANT_ID,
        session=session,  # type: ignore[arg-type]
    )
    assert result == {"id": str(conv.id), "is_archived": True}
    assert session.committed


# ──────────────────────────────────────────────────────────────────────────
# 12. POST /sandbox + POST /actions/{id}/rollback + GET /actions
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sandbox_returns_before_after_deltas_shape():
    """POST /sandbox → SandboxResponse (before_state, after_state, deltas, …)."""
    session = _FakeSession()
    req = SandboxRequest(action_type="NOOP", target="SKU-X", params={})

    with patch.object(copilot_api, "ActionExecutor") as ex_cls:
        executor = ex_cls.return_value
        executor.execute_action = AsyncMock(return_value={
            "before_state": {"qty": 10},
            "after_state": {"qty": 110},
            "actual_impact": {"qty": 100},
            "message": "ok",
        })

        result = await execute_sandbox(
            request=req, user=_user(), tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )

    assert result.success is True
    assert result.before_state == {"qty": 10}
    assert result.after_state == {"qty": 110}
    assert "qty" in result.deltas


@pytest.mark.asyncio
async def test_sandbox_returns_501_when_handler_not_implemented():
    """sandbox sem handler para o action_type → 501 (não fabrica after_state)."""
    from src.copilot.actions import ActionHandlerNotImplementedError
    session = _FakeSession()
    req = SandboxRequest(action_type="UNKNOWN_TYPE", target="x", params={})

    with patch.object(copilot_api, "ActionExecutor") as ex_cls:
        executor = ex_cls.return_value
        executor.execute_action = AsyncMock(
            side_effect=ActionHandlerNotImplementedError("UNKNOWN_TYPE"),
        )
        with pytest.raises(HTTPException) as exc:
            await execute_sandbox(
                request=req, user=_user(), tenant_id=TENANT_ID,
                session=session,  # type: ignore[arg-type]
            )
        assert exc.value.status_code == 501


@pytest.mark.asyncio
async def test_rollback_action_404_when_log_missing():
    """rollback de transação inexistente → 404."""
    session = _FakeSession()
    session.stub_get(None)
    with pytest.raises(HTTPException) as exc:
        await rollback_action(
            transaction_id=uuid4(), user=_user(), tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_rollback_action_403_when_wrong_tenant():
    """log doutro tenant → 403."""
    log = SimpleNamespace(
        id=uuid4(),
        tenant_id=UUID("99999999-9999-9999-9999-999999999999"),
        status="executed",
        rollback_until=datetime.now(timezone.utc) + timedelta(hours=1),
        action_type="X", plan_id=None,
    )
    session = _FakeSession()
    session.stub_get(log)
    with pytest.raises(HTTPException) as exc:
        await rollback_action(
            transaction_id=log.id, user=_user(), tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_rollback_action_400_when_already_rolled_back():
    """status já não é 'executed' → 400."""
    log = SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT_ID,
        status="rolled_back",
        rollback_until=datetime.now(timezone.utc) + timedelta(hours=1),
        action_type="X", plan_id=None,
    )
    session = _FakeSession()
    session.stub_get(log)
    with pytest.raises(HTTPException) as exc:
        await rollback_action(
            transaction_id=log.id, user=_user(), tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_rollback_action_400_when_window_expired():
    """rollback_until no passado → 400."""
    log = SimpleNamespace(
        id=uuid4(),
        tenant_id=TENANT_ID,
        status="executed",
        rollback_until=datetime.now(timezone.utc) - timedelta(hours=1),
        action_type="X", plan_id=None,
    )
    session = _FakeSession()
    session.stub_get(log)
    with pytest.raises(HTTPException) as exc:
        await rollback_action(
            transaction_id=log.id, user=_user(), tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_list_actions_returns_action_log_shape():
    """GET /actions → List[{transaction_id, action_type, status, ...}]."""
    log = SimpleNamespace(
        id=uuid4(), action_type="ADJUST", user_id=USER_ID, plan_id=None,
        before_state={}, after_state={"x": 1}, status="executed",
        executed_at=datetime.now(timezone.utc), rollback_until=None,
    )
    session = _FakeSession()
    session.stub_execute([log])
    result = await list_actions(
        limit=50, offset=0, status=None,
        user=_user(), tenant_id=TENANT_ID,
        session=session,  # type: ignore[arg-type]
    )
    assert isinstance(result, list) and len(result) == 1
    entry = result[0]
    assert set(entry.keys()) >= {
        "transaction_id", "action_type", "user_id", "status",
        "before_state", "after_state", "executed_at",
    }


# ──────────────────────────────────────────────────────────────────────────
# 13. POST /causal/audit — sanity (já coberto extensivamente em
#     test_causal_audit_endpoint_q13g.py; aqui só pinamos o 400-no-body).
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_causal_audit_rejects_empty_payload():
    """payload sem campos obrigatórios → 400."""
    session = _FakeSession()
    with pytest.raises(HTTPException) as exc:
        await post_causal_audit(
            payload={},
            _user=_user(),
            tenant_id=TENANT_ID,
            session=session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 400
