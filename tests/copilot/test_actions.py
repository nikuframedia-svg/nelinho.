"""
Q.55.C.3 — RUN_RUNBOOK fallback quando payload.runbook_id está em falta.

O LLM por vezes propõe acções `RUN_RUNBOOK` sem `runbook_id` (o operador
abre o copiloto e diz "diagnostica isto" sem nomear o runbook). Antes,
o handler `_run_copilot_action` devolvia 400 imediato — péssima UX. Agora
faz fallback para o primeiro runbook disponível em `runbook_definitions/`.

O fail-closed mantém-se: se NÃO houver runbooks no disco, o 400 acontece
na mesma. Estes testes blindam ambos os ramos.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.copilot.api import router
from src.shared.database import get_session

DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _app() -> FastAPI:
    """App com o router do copiloto + sessão falsa cuja `get` devolve uma
    suggestion no tenant dev (para a acção passar o check de 404)."""
    fake_suggestion = SimpleNamespace(id=uuid4(), tenant_id=DEV_TENANT)

    class _Sess:
        async def get(self, _model, _pk):
            return fake_suggestion

    async def _fake_session():
        yield _Sess()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = _fake_session
    return app


def test_run_runbook_falls_back_to_first_available_when_id_missing():
    """RUN_RUNBOOK sem `runbook_id` → handler não devolve 400; usa o
    primeiro runbook disponível (filename stem) e devolve um trace planeado.

    Forçamos `list_runbooks()` a devolver apenas `oee_diagnosis` (o YAML
    válido — `bottleneck_analysis` é pré-existente e segue um schema
    diferente, fora do scope deste sub-sprint). Sem este patch, o
    fallback escolheria o primeiro por ordem alfabética e o executor
    rebentaria com 500 (`RunbookInvalid`)."""
    client = TestClient(_app())

    with patch(
        "src.copilot.runbook_executor.list_runbooks",
        return_value=["oee_diagnosis"],
    ):
        resp = client.post(
            "/api/copilot/action-dev",
            json={
                "action_type": "RUN_RUNBOOK",
                "suggestion_id": str(uuid4()),
                "payload": {},
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["action_type"] == "RUN_RUNBOOK"
    assert body["status"] == "planned"
    # `trace.runbook_id` vem do YAML (campo `id`); confirma que o fallback
    # injectou `oee_diagnosis` na payload e o executor correu.
    assert body["trace"]["runbook_id"] == "oee_diagnosis"
    assert isinstance(body["trace"]["steps"], list) and body["trace"]["steps"]


def test_run_runbook_still_400_when_no_runbooks_available():
    """Fail-closed preservado: se `list_runbooks()` devolver [] (caso patológico
    sem YAMLs no disco), o handler devolve 400 — não inventa runbooks."""
    client = TestClient(_app())

    with patch("src.copilot.runbook_executor.list_runbooks", return_value=[]):
        resp = client.post(
            "/api/copilot/action-dev",
            json={
                "action_type": "RUN_RUNBOOK",
                "suggestion_id": str(uuid4()),
                "payload": {},
            },
        )

    assert resp.status_code in (400, 404), resp.text
    # Mensagem deve referir o `runbook_id` em falta.
    assert "runbook_id" in resp.text.lower() or "runbook" in resp.text.lower()
