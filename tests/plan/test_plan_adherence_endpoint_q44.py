"""Sprint Q.44.B (F13) — endpoint GET /v1/plan/adherence.

Liga o ScheduleCommit (plano) ao OF_FP real (realizado). Cobre:
* sem commit → 404
* commit sem operações com horas → status="sem_plano_temporal"
* ERP indisponível (RuntimeError) → status="sem_execucao_real", 200,
  sem número de aderência inventado (degradação honesta)
* caminho real → aderência calculada com janela derivada do plano
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.adapters.nelo.services as nelo_services
from src.plan.api.plan_adherence import router as adherence_router
from src.plan.cpo.commits import ScheduleCommit
from src.shared.database import get_session


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
T0 = datetime(2026, 5, 18, 8, 0, 0)


def _commit(operations) -> ScheduleCommit:
    return ScheduleCommit(
        id=uuid4(),
        tenant_id=TENANT,
        parent_id=None,
        commit_sha256="c" * 64,
        author="test",
        message="",
        kpis={},
        operations=operations,
        delta={},
        alternatives=[],
        cpo_meta={},
        trust_index=0.0,
        operations_count=len(operations),
    )


class _Op:
    """OperationRow-like — só os atributos que o conversor lê."""

    def __init__(self, woid, pid, start, end=None):
        self.work_order_id = woid
        self.phase_id = pid
        self.start_at = start
        self.end_at = end


def _build_app(commit: Optional[ScheduleCommit]) -> FastAPI:
    """App cuja session devolve `commit` em qualquer get_latest/get_by_sha."""

    class _FakeSession:
        async def execute(self, stmt):
            class _Result:
                def scalar_one_or_none(self_):
                    return commit

                def scalars(self_):
                    class _S:
                        def all(self__):
                            return [commit] if commit else []
                    return _S()
            return _Result()

    async def _fake_session():
        yield _FakeSession()

    app = FastAPI()
    app.include_router(adherence_router, prefix="/v1/plan")
    app.dependency_overrides[get_session] = _fake_session
    return app


def test_no_commit_returns_404():
    client = TestClient(_build_app(None))
    resp = client.get("/v1/plan/adherence", headers={"x-tenant-id": str(TENANT)})
    assert resp.status_code == 404


def test_commit_without_timed_operations_is_sem_plano_temporal():
    commit = _commit([{"order_id": "1001", "phase_id": "10"}])  # sem start/end
    client = TestClient(_build_app(commit))
    resp = client.get("/v1/plan/adherence", headers={"x-tenant-id": str(TENANT)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "sem_plano_temporal"
    assert "adherence_pct" not in body  # nenhum número inventado


def test_erp_unavailable_is_sem_execucao_real(monkeypatch):
    """Em dev sqlserver_enabled=False — degradação honesta, sem número."""

    async def _raise(*args, **kwargs):
        raise RuntimeError("sqlserver_enabled=False or sqlserver_url=None.")

    monkeypatch.setattr(nelo_services, "list_operations", _raise)

    commit = _commit([
        {"order_id": "1001", "phase_id": "10",
         "start_time": T0.isoformat(),
         "end_time": (T0 + timedelta(hours=4)).isoformat()},
    ])
    client = TestClient(_build_app(commit))
    resp = client.get("/v1/plan/adherence", headers={"x-tenant-id": str(TENANT)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "sem_execucao_real"
    assert "adherence_pct" not in body  # CRÍTICO — nada inventado
    assert "ERP" in body["detail"]
    assert body["window"]["from"] == T0.date().isoformat()


def test_real_path_computes_adherence(monkeypatch):
    """ERP ligado — devolve % de aderência real."""

    captured = {}

    async def _list_ops(date_from, date_to, **kwargs):
        captured["from"] = date_from
        captured["to"] = date_to
        return [_Op("1001", "10", T0, T0 + timedelta(hours=4))]

    monkeypatch.setattr(nelo_services, "list_operations", _list_ops)

    commit = _commit([
        {"order_id": "1001", "phase_id": "10",
         "start_time": T0.isoformat(),
         "end_time": (T0 + timedelta(hours=4)).isoformat()},
    ])
    client = TestClient(_build_app(commit))
    resp = client.get("/v1/plan/adherence", headers={"x-tenant-id": str(TENANT)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["adherence_pct"] == 100.0
    assert body["matched_total"] == 1
    # janela do reader derivada das horas do plano
    assert captured["from"] == T0.date()


def test_real_path_reports_missing_operations(monkeypatch):
    """Operação planeada sem execução real → conta como não aderente."""

    async def _list_ops(date_from, date_to, **kwargs):
        return [_Op("1001", "10", T0)]  # só a fase 10 executou

    monkeypatch.setattr(nelo_services, "list_operations", _list_ops)

    commit = _commit([
        {"order_id": "1001", "phase_id": "10", "start_time": T0.isoformat()},
        {"order_id": "1001", "phase_id": "20",
         "start_time": (T0 + timedelta(hours=4)).isoformat()},
    ])
    client = TestClient(_build_app(commit))
    resp = client.get("/v1/plan/adherence", headers={"x-tenant-id": str(TENANT)})
    body = resp.json()
    assert body["adherence_pct"] == 50.0
    assert body["missing"] == [{"order_id": "1001", "phase_id": "20"}]


def test_tolerance_query_param_is_applied(monkeypatch):
    async def _list_ops(date_from, date_to, **kwargs):
        return [_Op("1001", "10", T0 + timedelta(hours=5))]  # 5 h de deriva

    monkeypatch.setattr(nelo_services, "list_operations", _list_ops)

    commit = _commit([
        {"order_id": "1001", "phase_id": "10", "start_time": T0.isoformat()},
    ])
    client = TestClient(_build_app(commit))

    strict = client.get(
        "/v1/plan/adherence?tolerance_hours=2",
        headers={"x-tenant-id": str(TENANT)},
    ).json()
    assert strict["adherence_pct"] == 0.0

    loose = client.get(
        "/v1/plan/adherence?tolerance_hours=8",
        headers={"x-tenant-id": str(TENANT)},
    ).json()
    assert loose["adherence_pct"] == 100.0
