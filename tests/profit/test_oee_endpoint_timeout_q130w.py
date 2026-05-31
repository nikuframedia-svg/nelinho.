"""Q.130.W — `/v1/profit/oee` degrada honestamente em vez de pendurar.

O `OEEService.calculate` lê o ERP NELO (SQL Server / OF_FP) via aioodbc.
O `connect_args={"timeout": ...}` (Q.130.T) NÃO é honrado pelo aioodbc no
TCP connect — um host inalcançável pendurava >20s no endpoint. O endpoint
agora envolve a chamada num `asyncio.wait_for(timeout=connect_timeout)` e,
em timeout, devolve HTTP 200 + `erp_available=false` (a MESMA shape do
caminho ERP-offline) com um `unavailable_reason` honesto — nunca pendura
nem inventa números.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.profit.api.dashboard import router as profit_router
from src.profit.services.oee_service import OEEService

TENANT = "00000000-0000-0000-0000-000000000001"
_HDRS = {"X-Tenant-Id": TENANT}


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(profit_router, prefix="/v1/profit")
    return TestClient(app)


def test_oee_timeout_degrades_honestly(monkeypatch):
    """Fetcher que demora mais que o connect_timeout → 200 + erp_available:false.

    Encurtamos o teto para 1s e fazemos o `calculate` dormir 5s. O
    `asyncio.wait_for` corta ao 1s e o endpoint devolve a degradação
    honesta — não pendura nem rebenta com 500.
    """
    from src.profit.api import dashboard as dash_mod

    monkeypatch.setattr(dash_mod.settings, "sqlserver_connect_timeout_s", 1)

    async def _slow_calculate(self, date_from, date_to, group_by="none"):
        await asyncio.sleep(5)  # mais que o teto de 1s
        raise AssertionError("não deveria chegar aqui — o wait_for corta antes")

    monkeypatch.setattr(OEEService, "calculate", _slow_calculate)

    client = _client()
    resp = client.get("/v1/profit/oee", headers=_HDRS)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["erp_available"] is False
    assert body["overall"] is None
    assert body["breakdown"] == []
    assert "não respondeu a tempo" in body["unavailable_reason"]


def test_oee_success_path_unaffected(monkeypatch):
    """Caminho feliz: fetcher rápido com dados → erp_available:true, números reais.

    Garante que o wrap `asyncio.wait_for` não estrangula o caso normal.
    """
    from datetime import datetime

    from src.adapters.nelo.schemas import OperationRow

    def _op(op_id: int) -> OperationRow:
        return OperationRow(
            operation_id=op_id,
            work_order_id=op_id * 10,
            phase_id=1,
            phase_name="Laminagem",
            start_at=datetime(2026, 5, 14, 9, 0),
            end_at=datetime(2026, 5, 14, 11, 0),
            expected_at=None,
            standard_time_hours=2.0,
            temperature=20.0,
            humidity=50.0,
            problem_neck=None,
            problem_interior_id=None,
            problem_paint_id=None,
            problem_mold_id=None,
            problem_lamination_id=None,
            problem_logged_at=None,
            is_return=False,
            severe_return=False,
            product_id=100,
            shift_id=1,
            mold_work_order_id=None,
            product_type_name="Canoe Sprint Ep.",
            phase_is_automatic=False,
        )

    async def _fast_fetch(date_from, date_to, limit):
        return [_op(i) for i in range(1, 6)]

    # Substitui o fetcher por dentro: o endpoint cria OEEService() sem
    # injecção, por isso patcheamos o default usado no __init__.
    monkeypatch.setattr(
        "src.profit.services.oee_service.list_operations", _fast_fetch
    )

    client = _client()
    resp = client.get("/v1/profit/oee", headers=_HDRS)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["erp_available"] is True
    assert body["overall"] is not None
    assert body["overall"]["sample_size"] == 5
