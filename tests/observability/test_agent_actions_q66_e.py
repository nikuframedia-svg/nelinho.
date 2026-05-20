"""Q.66.E.3 — GET /v1/observability/agent-actions.

Pina:
  * Endpoint montado em /v1/observability/agent-actions.
  * Tenant scope (header obrigatorio).
  * Forma da resposta paginada.
  * Filtros (intent, outcome, escalated, trace_id, user_id, since/until).
  * Validacao enum do `outcome`.
  * Campos da entry (frontend consome estes).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.models.agent_action import AgentAction
from src.observability import router as observability_router
from src.shared.database import get_session


TENANT = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _row(
    intent: str = "kpi_current",
    outcome: str = "success",
    escalated: bool = False,
    user_id: UUID | None = None,
    model: str | None = "gemma3:e4b",
    latency_ms: int = 120,
    trace_id: str | None = None,
    error_message: str | None = None,
    created_at: datetime | None = None,
) -> AgentAction:
    return AgentAction(
        id=uuid4(),
        tenant_id=TENANT,
        user_id=user_id,
        intent=intent,
        model=model,
        latency_ms=latency_ms,
        outcome=outcome,
        escalated=escalated,
        decision_run_id=None,
        trace_id=trace_id,
        error_message=error_message,
        created_at=created_at or datetime.now(timezone.utc),
    )


class _StubSession:
    """Devolve `rows` em SELECT AgentAction e `len(rows)` em count.

    Ignora filtros — testamos a API + shape; o SQL é responsabilidade
    do Postgres real (pattern Q.61.19).
    """

    def __init__(self, rows: list[AgentAction]) -> None:
        self.rows = rows

    async def execute(self, stmt):
        sql = str(stmt).lower()
        is_count = "count" in sql

        rows = self.rows

        class _Scalars:
            def all(self_inner):
                return list(rows)

        class _R:
            def scalars(self_inner):
                return _Scalars()

            def scalar(self_inner):
                return len(rows)

        return _R()


def _app(rows: list[AgentAction]) -> FastAPI:
    app = FastAPI()
    app.include_router(observability_router)

    session = _StubSession(rows)

    async def _fake_session():
        yield session

    app.dependency_overrides[get_session] = _fake_session
    return app


# ─── tests ─────────────────────────────────────────────────────────────


def test_endpoint_returns_paginated_shape():
    rows = [_row(intent="kpi_current"), _row(intent="schedule_propose")]
    client = TestClient(_app(rows))
    resp = client.get(
        "/v1/observability/agent-actions",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) >= {"entries", "total", "page", "page_size"}
    assert isinstance(body["entries"], list)
    assert body["total"] == 2
    assert body["page"] == 1
    assert 1 <= body["page_size"] <= 200


def test_endpoint_requires_tenant_header():
    client = TestClient(_app([]))
    resp = client.get("/v1/observability/agent-actions")
    # Sem tenant header -> 401 (require_tenant_header).
    assert resp.status_code in (400, 401, 422)


def test_endpoint_rejects_invalid_outcome_enum():
    client = TestClient(_app([]))
    resp = client.get(
        "/v1/observability/agent-actions?outcome=banana",
        headers={"x-tenant-id": str(TENANT)},
    )
    # FastAPI/Pydantic devolve 422 para Literal invalido.
    assert resp.status_code == 422


def test_endpoint_accepts_valid_outcome_filters():
    """Cada um dos 4 valores enum tem que passar."""
    client = TestClient(_app([]))
    for outcome in ("success", "error", "timeout", "skipped"):
        resp = client.get(
            f"/v1/observability/agent-actions?outcome={outcome}",
            headers={"x-tenant-id": str(TENANT)},
        )
        assert resp.status_code == 200, (outcome, resp.text)


def test_endpoint_accepts_intent_filter():
    rows = [_row(intent="kpi_current")]
    client = TestClient(_app(rows))
    resp = client.get(
        "/v1/observability/agent-actions?intent=kpi_current",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 200
    assert resp.json()["entries"][0]["intent"] == "kpi_current"


def test_endpoint_accepts_escalated_filter():
    rows = [_row(escalated=True)]
    client = TestClient(_app(rows))
    resp = client.get(
        "/v1/observability/agent-actions?escalated=true",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 200
    assert resp.json()["entries"][0]["escalated"] is True


def test_endpoint_accepts_trace_id_substring():
    rows = [_row(trace_id="abc123def456")]
    client = TestClient(_app(rows))
    resp = client.get(
        "/v1/observability/agent-actions?trace_id=abc",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 200
    assert "abc" in resp.json()["entries"][0]["trace_id"]


def test_endpoint_returns_entry_fields():
    """Estrutura de cada entry — frontend / observability tools
    consomem estes campos."""
    user = uuid4()
    rows = [
        _row(
            user_id=user,
            intent="schedule_propose",
            model="ollama-llama",
            latency_ms=4200,
            outcome="error",
            escalated=True,
            trace_id="trace-xyz-789",
            error_message="ollama timeout after 5s",
        )
    ]
    client = TestClient(_app(rows))
    resp = client.get(
        "/v1/observability/agent-actions",
        headers={"x-tenant-id": str(TENANT)},
    )
    entry = resp.json()["entries"][0]
    assert {
        "id",
        "tenant_id",
        "user_id",
        "intent",
        "model",
        "latency_ms",
        "outcome",
        "escalated",
        "decision_run_id",
        "trace_id",
        "error_message",
        "created_at",
    } <= set(entry)
    assert entry["user_id"] == str(user)
    assert entry["intent"] == "schedule_propose"
    assert entry["model"] == "ollama-llama"
    assert entry["latency_ms"] == 4200
    assert entry["outcome"] == "error"
    assert entry["escalated"] is True
    assert entry["trace_id"] == "trace-xyz-789"
    assert entry["error_message"] == "ollama timeout after 5s"


def test_endpoint_pagination_params_bounds():
    """page>=1 e page_size entre 1 e 200."""
    client = TestClient(_app([]))
    # page_size > 200 -> 422
    resp = client.get(
        "/v1/observability/agent-actions?page_size=500",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 422
    # page < 1 -> 422
    resp = client.get(
        "/v1/observability/agent-actions?page=0",
        headers={"x-tenant-id": str(TENANT)},
    )
    assert resp.status_code == 422


def test_endpoint_mounted_in_main_app():
    """Garantir que o router e include_router'd no app real (catch
    a regressao classica de criar endpoint sem o montar)."""
    from src.main import app

    paths = {route.path for route in app.routes}
    assert "/v1/observability/agent-actions" in paths
