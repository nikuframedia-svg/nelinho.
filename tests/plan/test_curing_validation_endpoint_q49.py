"""Sprint Q.49.B (F12) — endpoint GET /v1/plan/curing-validation.

Cruza as operações de cura/desmolde de um período com as leituras reais de
temperatura/humidade da tabela ERP `TH`. Cobre:
* date_to < date_from → 400
* janela demasiado larga → 400
* ERP/sensor indisponível (RuntimeError) → status="sem_dados_sensor", 200,
  sem % de conformidade inventada (degradação honesta)
* caminho real → operação de cura conforme dentro do range
* caminho real → operação fora de range é sinalizada
* só operações de fases de cura/desmolde entram na validação
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.adapters.nelo.services as nelo_services
from src.plan.api.curing_validation import router as curing_router
from src.shared.database import get_session

TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
T0 = datetime(2026, 5, 18, 8, 0, 0)
D_FROM = date(2026, 5, 18)
D_TO = date(2026, 5, 19)


class _Op:
    """OperationRow-like — só os atributos que o conversor lê."""

    def __init__(self, opid, woid, phase_name, start, end):
        self.operation_id = opid
        self.work_order_id = woid
        self.phase_name = phase_name
        self.start_at = start
        self.end_at = end


class _Reading:
    """TempHumidityRow-like."""

    def __init__(self, measured_at, temperature, humidity=50.0):
        self.measured_at = measured_at
        self.temperature = temperature
        self.humidity = humidity
        self.phase_id = None


def _build_app() -> FastAPI:
    """App cuja session é um stub — o endpoint só a usa para TenantConfig,
    que degrada para os defaults documentados quando indisponível."""

    class _FakeSession:
        async def execute(self, stmt):
            raise RuntimeError("config indisponível no teste — usa defaults")

    async def _fake_session():
        yield _FakeSession()

    app = FastAPI()
    app.include_router(curing_router, prefix="/v1/plan")
    app.dependency_overrides[get_session] = _fake_session
    return app


def _get(client, **params):
    qs = {"date_from": D_FROM.isoformat(), "date_to": D_TO.isoformat()}
    qs.update(params)
    return client.get(
        "/v1/plan/curing-validation",
        params=qs,
        headers={"x-tenant-id": str(TENANT)},
    )


def test_date_to_before_date_from_is_400():
    client = TestClient(_build_app())
    resp = _get(client, date_from="2026-05-19", date_to="2026-05-18")
    assert resp.status_code == 400


def test_window_too_wide_is_400():
    client = TestClient(_build_app())
    resp = _get(client, date_from="2026-01-01", date_to="2026-12-31")
    assert resp.status_code == 400


def test_erp_unavailable_is_sem_dados_sensor(monkeypatch):
    """Em dev sqlserver_enabled=False — degradação honesta, sem número."""

    async def _raise(*args, **kwargs):
        raise RuntimeError("sqlserver_enabled=False or sqlserver_url=None.")

    monkeypatch.setattr(nelo_services, "list_operations", _raise)
    monkeypatch.setattr(nelo_services, "list_temperature_humidity", _raise)

    client = TestClient(_build_app())
    resp = _get(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "sem_dados_sensor"
    assert "conformity_pct" not in body  # CRÍTICO — nada inventado
    assert "TH" in body["detail"]
    assert body["window"]["from"] == D_FROM.isoformat()
    assert "environment_range" in body  # o range continua visível


def test_real_path_conforme_operation(monkeypatch):
    """ERP ligado, cura dentro do range → conforme."""

    async def _list_ops(date_from, date_to, **kwargs):
        return [_Op(1, 1001, "Cura", T0, T0 + timedelta(hours=15))]

    async def _list_th(date_from, date_to, **kwargs):
        return [_Reading(T0 + timedelta(hours=2), 22.0, 50.0)]

    monkeypatch.setattr(nelo_services, "list_operations", _list_ops)
    monkeypatch.setattr(nelo_services, "list_temperature_humidity", _list_th)

    client = TestClient(_build_app())
    body = _get(client).json()
    assert body["status"] == "ok"
    assert body["operations_total"] == 1
    assert body["conforme_total"] == 1
    assert body["conformity_pct"] == 100.0


def test_real_path_flags_out_of_range_operation(monkeypatch):
    """Cura a 12 °C → fora_range, com breach descrito."""

    async def _list_ops(date_from, date_to, **kwargs):
        return [_Op(2, 1002, "Cura", T0, T0 + timedelta(hours=15))]

    async def _list_th(date_from, date_to, **kwargs):
        return [_Reading(T0 + timedelta(hours=3), 12.0, 50.0)]

    monkeypatch.setattr(nelo_services, "list_operations", _list_ops)
    monkeypatch.setattr(nelo_services, "list_temperature_humidity", _list_th)

    client = TestClient(_build_app())
    body = _get(client).json()
    assert body["fora_range_total"] == 1
    assert body["conformity_pct"] == 0.0
    verdict = body["verdicts"][0]
    assert verdict["status"] == "fora_range"
    assert any("temperatura" in b for b in verdict["breaches"])


def test_real_path_ignores_non_curing_phases(monkeypatch):
    """Operações fora de cura/desmolde não entram na validação."""

    async def _list_ops(date_from, date_to, **kwargs):
        return [
            _Op(3, 1003, "Laminagem", T0, T0 + timedelta(hours=4)),
            _Op(4, 1003, "Desmolde", T0 + timedelta(hours=20),
                T0 + timedelta(hours=21)),
        ]

    async def _list_th(date_from, date_to, **kwargs):
        return [_Reading(T0 + timedelta(hours=20, minutes=30), 22.0, 50.0)]

    monkeypatch.setattr(nelo_services, "list_operations", _list_ops)
    monkeypatch.setattr(nelo_services, "list_temperature_humidity", _list_th)

    client = TestClient(_build_app())
    body = _get(client).json()
    # só o Desmolde conta
    assert body["operations_total"] == 1
    assert body["verdicts"][0]["phase_code"] == "DESMOLDE"
