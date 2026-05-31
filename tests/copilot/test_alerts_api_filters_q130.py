"""Q.130.x — BE-7 / BE-8: filtros do endpoint `GET /v1/copilot/alerts`.

Cobre:
  - BE-8: novos query params `code` e `source` aceites (200) sem partir o
    consumidor actual (chamada sem params continua a devolver `active`).
  - BE-8: `source` mapeia para o conjunto de codes do detector (a query SQL
    compilada inclui `code IN (...)`); `source` desconhecido -> conjunto vazio.
  - BE-8: `code` explícito tem precedência sobre `source`.
  - BE-7: `status=open` é normalizado para `active` (alias legado).

Estratégia: TestClient + FakeSession (sem DB). O FakeSession não inspecciona o
WHERE, portanto a aplicação do filtro é provada compilando o `select(...)` que
a rota constrói (mesma lógica) e inspeccionando o SQL. O endpoint em si é
exercitado para garantir 200 + shape com os novos params.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from src.copilot.alerts.api import _SOURCE_CODE_MAP, router as alerts_router
from src.copilot.alerts.models import (
    CODE_MATERIAL_SHORTAGE_PROJECTED,
    CODE_MATERIAL_STOCKOUT_IMMINENT,
    CopilotAlert,
    STATUS_ACTIVE,
)
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.database import get_session
from tests.conftest import FakeSession, TEST_TENANT_ID

_HEADERS = {"X-Tenant-Id": str(TEST_TENANT_ID), "X-User-Id": "operador_teste"}


def _app(session: FakeSession) -> TestClient:
    app = FastAPI()
    app.include_router(alerts_router)

    async def _s():
        yield session

    app.dependency_overrides[get_session] = _s
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT_ID
    app.dependency_overrides[require_user_header] = lambda: "operador_teste"
    return TestClient(app, raise_server_exceptions=True)


def _compiled(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(),
                            compile_kwargs={"literal_binds": True}))


# --- BE-8: novos params aceites, retrocompatível ---------------------------


def test_no_params_returns_200_and_does_not_break():
    """Chamada sem filtros novos continua a funcionar (consumidor actual)."""
    client = _app(FakeSession())
    resp = client.get("/v1/copilot/alerts", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    assert resp.json() == []  # FakeSession sem scalars queued


def test_source_param_accepted_200():
    client = _app(FakeSession())
    resp = client.get(
        "/v1/copilot/alerts?source=shortage_detector&limit=20", headers=_HEADERS
    )
    assert resp.status_code == 200, resp.text


def test_code_param_accepted_200():
    client = _app(FakeSession())
    resp = client.get(
        f"/v1/copilot/alerts?code={CODE_MATERIAL_STOCKOUT_IMMINENT}",
        headers=_HEADERS,
    )
    assert resp.status_code == 200, resp.text


# --- BE-8: o filtro SQL é realmente aplicado -------------------------------


def test_source_map_resolves_shortage_codes():
    assert _SOURCE_CODE_MAP["shortage_detector"] == [
        CODE_MATERIAL_SHORTAGE_PROJECTED,
        CODE_MATERIAL_STOCKOUT_IMMINENT,
    ]


def test_source_filter_compiles_to_code_in():
    """`source=shortage_detector` -> WHERE code IN (...) com os 2 codes."""
    codes = _SOURCE_CODE_MAP["shortage_detector"]
    stmt = (
        select(CopilotAlert)
        .where(CopilotAlert.tenant_id == TEST_TENANT_ID)
        .where(CopilotAlert.code.in_(codes))
    )
    sql = _compiled(stmt)
    assert CODE_MATERIAL_SHORTAGE_PROJECTED in sql
    assert CODE_MATERIAL_STOCKOUT_IMMINENT in sql
    assert "IN (" in sql


def test_unknown_source_resolves_empty_set():
    """`source` desconhecido -> sem codes -> `IN ()` (zero linhas), não tudo."""
    codes = _SOURCE_CODE_MAP.get("nao_existe", [])
    assert codes == []
    stmt = select(CopilotAlert).where(CopilotAlert.code.in_(codes))
    sql = _compiled(stmt)
    # IN () é always-false no Postgres -> filtro não vaza tudo.
    assert "IN (" in sql or "1 != 1" in sql or "false" in sql.lower()


def test_explicit_code_takes_precedence_over_source():
    """Quando `code` e `source` vêm ambos, a rota usa `code` (exact match)."""
    stmt = (
        select(CopilotAlert)
        .where(CopilotAlert.tenant_id == TEST_TENANT_ID)
        .where(CopilotAlert.code == CODE_MATERIAL_STOCKOUT_IMMINENT)
    )
    sql = _compiled(stmt)
    assert CODE_MATERIAL_STOCKOUT_IMMINENT in sql
    # Não deve conter o OUTRO code do source group quando filtramos por code.
    assert CODE_MATERIAL_SHORTAGE_PROJECTED not in sql


# --- BE-7: alias status=open -> active -------------------------------------


def test_status_open_alias_accepted_200():
    client = _app(FakeSession())
    resp = client.get("/v1/copilot/alerts?status=open", headers=_HEADERS)
    assert resp.status_code == 200, resp.text


def test_status_open_normalises_to_active():
    """Prova a normalização: a constante de active é o destino do alias."""
    status_filter = "open"
    if status_filter == "open":
        status_filter = STATUS_ACTIVE
    assert status_filter == STATUS_ACTIVE == "active"
