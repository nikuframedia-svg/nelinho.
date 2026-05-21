"""
Q.55.C.2 — endpoint `/api/copilot/action-dev` (sem auth) espelha o `/ask-dev`.

O frontend dev corre sem sessão iniciada. O `/action` exige `get_current_user`
→ sem token, FastAPI devolve "Not authenticated" e a acção sugerida falha.
O `/ask` já tinha o par `/ask-dev`; o `/action` não tinha. Agora tem.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.copilot.api import router
from src.shared.database import get_session

DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _app() -> FastAPI:
    """App com o router do copiloto e uma sessão falsa cuja `get` devolve
    uma suggestion do tenant dev (para a acção passar o check de 404)."""
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


def test_action_dev_responde_sem_autenticacao():
    """POST /action-dev sem header de auth → 200 (não 401)."""
    client = TestClient(_app())
    resp = client.post(
        "/api/copilot/action-dev",
        json={
            "action_type": "OPEN_ENTITY",
            "suggestion_id": str(uuid4()),
            "payload": {"entity": "order", "id": "42"},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "hint"


def test_action_normal_continua_a_exigir_auth():
    """O `/action` (sem -dev) sem token continua a rejeitar — o par dev não
    abriu um buraco no endpoint autenticado."""
    client = TestClient(_app())
    resp = client.post(
        "/api/copilot/action",
        json={
            "action_type": "OPEN_ENTITY",
            "suggestion_id": str(uuid4()),
            "payload": {},
        },
    )
    assert resp.status_code in (401, 403)
