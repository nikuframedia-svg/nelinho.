"""Q.153.B1 — PUT /v1/plan/cpo/commits/{sha}/approve (DRAFT → LIVE).

O robô cria DRAFTs cujo job Arq expira em 1h → inaprováveis via job_id.
Este endpoint promove por commit_sha (o botão "Aprovar plano" do /overall).

Cobre: rota registada, happy path DRAFT→LIVE + audit na mesma tx, SoD 403
(proponente == aprovador), e 409 quando já LIVE.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")


def test_approve_by_sha_route_registered():
    from src.plan.api.cpo import router

    paths = {r.path for r in router.routes}
    assert "/v1/plan/cpo/commits/{sha}/approve" in paths


def _make_app(monkeypatch, commit, approver_id="alice"):
    """App com get_session/_resolve/audit/auth mockados."""
    from src.plan.api.cpo import router as cpo_router
    from src.plan.api._cpo_common import _tenant_id
    from src.shared.auth.headers import get_current_user_or_dev_header
    from src.shared.database import get_session
    import src.plan.api.cpo_routers.commits as commits_mod

    fake_session = SimpleNamespace(commit=AsyncMock(return_value=None))

    async def _resolve(_service, _sha):
        return commit

    audit_spy = AsyncMock(return_value=None)
    monkeypatch.setattr(commits_mod, "_resolve_commit_or_404", _resolve)
    monkeypatch.setattr(commits_mod, "audit_change", audit_spy)

    app = FastAPI()
    app.include_router(cpo_router)
    app.dependency_overrides[_tenant_id] = lambda: DEV_TENANT
    app.dependency_overrides[get_session] = lambda: fake_session
    app.dependency_overrides[get_current_user_or_dev_header] = lambda: SimpleNamespace(
        user_id=approver_id, role="manager_operations",
    )
    return app, fake_session, audit_spy


def _commit(status="DRAFT", author="system"):
    return SimpleNamespace(
        id=uuid4(), commit_sha256="a" * 64, status=status, author=author,
    )


@pytest.mark.asyncio
async def test_approve_promotes_draft_to_live_and_audits(monkeypatch):
    commit = _commit(status="DRAFT", author="system")
    app, fake_session, audit_spy = _make_app(monkeypatch, commit)
    client = TestClient(app)

    resp = client.put(f"/v1/plan/cpo/commits/{'a' * 64}/approve",
                      headers={"X-Tenant-Id": str(DEV_TENANT)})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["previous_status"] == "DRAFT"
    assert body["new_status"] == "LIVE"
    assert commit.status == "LIVE"                 # mutado in-place
    audit_spy.assert_awaited_once()                # axioma 7 (mesma tx)
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_approve_rejects_self_approval_sod(monkeypatch):
    # Proponente humano == aprovador → 403 SoD.
    commit = _commit(status="DRAFT", author="alice")
    app, _fs, audit_spy = _make_app(monkeypatch, commit, approver_id="alice")
    client = TestClient(app)

    resp = client.put(f"/v1/plan/cpo/commits/{'a' * 64}/approve",
                      headers={"X-Tenant-Id": str(DEV_TENANT)})

    assert resp.status_code == 403
    assert "Segregação de funções" in resp.json()["detail"]
    assert commit.status == "DRAFT"               # não promovido
    audit_spy.assert_not_awaited()


@pytest.mark.asyncio
async def test_approve_already_live_is_409(monkeypatch):
    commit = _commit(status="LIVE", author="system")
    app, _fs, _audit = _make_app(monkeypatch, commit)
    client = TestClient(app)

    resp = client.put(f"/v1/plan/cpo/commits/{'a' * 64}/approve",
                      headers={"X-Tenant-Id": str(DEV_TENANT)})

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_approve_system_draft_by_any_approver(monkeypatch):
    # author=system (robô) → qualquer aprovador autorizado promove.
    commit = _commit(status="DRAFT", author="system")
    app, _fs, _audit = _make_app(monkeypatch, commit, approver_id="bob")
    client = TestClient(app)

    resp = client.put(f"/v1/plan/cpo/commits/{'a' * 64}/approve",
                      headers={"X-Tenant-Id": str(DEV_TENANT)})

    assert resp.status_code == 200
    assert commit.status == "LIVE"
