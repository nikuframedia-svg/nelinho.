"""
Q.67.6.A4 — Characterization tests para src/supply/api.py (1009L).

Feathers pattern (Working Effectively With Legacy Code): pinpoint o
contrato observavel dos endpoints supply ANTES da decomposicao da Fase
Q.67.6.B4. Os testes devem manter-se verdes ao longo do refactor — se
quebrarem, e porque o refactor mudou behaviour publico, nao a estrutura
interna.

Estrategia:
  * TestClient com `dependency_overrides` para require_tenant_header +
    get_session — evita montar src.main (que traz Kafka/scheduler/Ollama).
  * Mocks minimos: AsyncMock para os colaboradores pesados (ARIMAForecaster,
    InventoryLedger, MaterialService, PurchaseOrderService, StockoutPredictor,
    ABCAnalysis, ROPCalculator, recompute_rop_configs).
  * Asserts em **status code** + **keys do response body** + **shape**.
    NAO comparar strings literais nem output do LLM.

NAO refactorar `src/supply/api.py`. Read-only.

Endpoints cobertos (16 no router):
  POST  /v1/supply/forecast
  GET   /v1/supply/inventory/{sku_id}
  POST  /v1/supply/inventory/movement
  GET   /v1/supply/rop/{sku_id}
  POST  /v1/supply/abc
  POST  /v1/supply/rop-configs/recompute
  GET   /v1/supply/materials
  GET   /v1/supply/materials/from-bom
  GET   /v1/supply/purchase-orders
  GET   /v1/supply/materials/{sku_id}/stockout-forecast
  POST  /v1/supply/materials
  GET   /v1/supply/materials/{sku_id}/position
  PATCH /v1/supply/materials/{sku_id}/min-stock
  POST  /v1/supply/materials/{sku_id}/adjust
  GET   /v1/supply/materials/{sku_id}/movements
  POST  /v1/supply/reconciliation
  GET   /v1/supply/reconciliation
  POST  /v1/supply/reconciliation/{id}/resolve
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, AsyncIterator, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.auth.headers import require_tenant_header
from src.shared.config import settings
from src.shared.database import get_session
from src.supply import api as supply_api
from src.supply.api import router as supply_router
from src.supply.material_service import (
    MaterialNotFoundError,
    NegativeStockBlockedError,
)


DEV_TENANT = "00000000-0000-0000-0000-000000000001"
TENANT = UUID(DEV_TENANT)
ZERO_UUID = "00000000-0000-0000-0000-000000000000"


# ──────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────


async def _stub_session() -> AsyncIterator[Any]:
    """Sessao stub generica — services sao mockados, sessao nunca executa."""
    sess = AsyncMock()
    yield sess


def _client(monkeypatch) -> TestClient:
    """App isolada com supply_router montado."""
    monkeypatch.setattr(settings, "environment", "development", raising=False)
    app = FastAPI()
    app.include_router(supply_router)
    app.dependency_overrides[get_session] = _stub_session
    app.dependency_overrides[require_tenant_header] = lambda: TENANT
    return TestClient(app, raise_server_exceptions=False)


def _gate_client(monkeypatch) -> TestClient:
    """App sem override do require_tenant_header — para testar o gate."""
    monkeypatch.setattr(settings, "environment", "development", raising=False)
    app = FastAPI()
    app.include_router(supply_router)
    app.dependency_overrides[get_session] = _stub_session
    return TestClient(app, raise_server_exceptions=False)


def _material_row(sku_id: str = "MAT-001") -> SimpleNamespace:
    """Linha-fake de MaterialMaster — atributos que `_material_to_dict` le."""
    return SimpleNamespace(
        id=uuid4(),
        sku_id=sku_id,
        name="Resina epoxi",
        description=None,
        unit_of_measure="KG",
        category="resinas",
        default_supplier_id=None,
        lead_time_days=14,
        min_stock_qty=Decimal("10"),
        reorder_qty=Decimal("50"),
        safety_stock_days=None,
        critical_flag=False,
        active=True,
    )


def _reconciliation_row(sku_id: str = "MAT-001") -> SimpleNamespace:
    """Linha-fake de StockReconciliation."""
    return SimpleNamespace(
        id=uuid4(),
        sku_id=sku_id,
        theoretical_qty=Decimal("100"),
        physical_qty=Decimal("95"),
        variance_qty=Decimal("-5"),
        variance_pct=-5.0,
        counted_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        counted_by="alice",
        comments="contagem manual",
        resolved=False,
        resolved_at=None,
        resolved_by=None,
    )


# ──────────────────────────────────────────────────────────────────────────
# Fail-closed tenant gate (Q.12 Onda 0.1) — pin invariante
# ──────────────────────────────────────────────────────────────────────────


def test_missing_tenant_header_returns_401(monkeypatch):
    """Pelo menos um endpoint rejeita header em falta com 401."""
    client = _gate_client(monkeypatch)
    resp = client.get("/v1/supply/materials")
    assert resp.status_code == 401, resp.text


def test_zero_uuid_tenant_rejected(monkeypatch):
    """Zero UUID continua proibido (fail-closed)."""
    client = _gate_client(monkeypatch)
    resp = client.get(
        "/v1/supply/materials", headers={"X-Tenant-Id": ZERO_UUID}
    )
    assert resp.status_code == 401, resp.text


# ──────────────────────────────────────────────────────────────────────────
# POST /forecast
# ──────────────────────────────────────────────────────────────────────────


def test_forecast_returns_response_shape(monkeypatch):
    """POST /forecast → 200 com sku_id, forecast[], method, quality, extra."""
    client = _client(monkeypatch)

    fake_forecast = {
        "forecast": [{"ds": "2026-05-22", "yhat": 12.5}],
        "method": "ARIMA",
        "quality": {"mape": 0.05},
        "n_history": 30,
    }
    with patch.object(supply_api, "ARIMAForecaster") as cls:
        cls.return_value.forecast = AsyncMock(return_value=fake_forecast)
        resp = client.post(
            "/v1/supply/forecast",
            json={
                "sku_id": "MAT-001",
                "historical_data": [
                    {"date": "2026-05-01", "quantity": 10.0},
                    {"date": "2026-05-02", "quantity": 11.0},
                ],
                "periods_ahead": 7,
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sku_id"] == "MAT-001"
    assert body["forecast"] == fake_forecast["forecast"]
    assert body["method"] == "ARIMA"
    assert body["quality"] == {"mape": 0.05}
    assert body["extra"] == {"n_history": 30}


def test_forecast_error_returns_400(monkeypatch):
    """POST /forecast → 400 quando forecaster devolve {error: ...}."""
    client = _client(monkeypatch)

    with patch.object(supply_api, "ARIMAForecaster") as cls:
        cls.return_value.forecast = AsyncMock(
            return_value={"error": "insufficient history"}
        )
        resp = client.post(
            "/v1/supply/forecast",
            json={
                "sku_id": "MAT-001",
                "historical_data": [{"date": "2026-05-01", "quantity": 10.0}],
                "periods_ahead": 7,
            },
        )
    assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────────────
# GET /inventory/{sku_id}
# ──────────────────────────────────────────────────────────────────────────


def test_get_inventory_returns_sku_and_on_hand(monkeypatch):
    """GET /inventory/{sku_id} → 200 com {sku_id, on_hand: float}."""
    client = _client(monkeypatch)

    with patch.object(supply_api, "InventoryLedger") as cls:
        cls.return_value.get_current_on_hand = AsyncMock(
            return_value=Decimal("42.5")
        )
        resp = client.get("/v1/supply/inventory/MAT-001")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"sku_id": "MAT-001", "on_hand": 42.5}


# ──────────────────────────────────────────────────────────────────────────
# POST /inventory/movement
# ──────────────────────────────────────────────────────────────────────────


def test_record_movement_returns_201_with_shape(monkeypatch):
    """POST /inventory/movement → 201 com sku_id, on_hand_after, qty_*, ref."""
    client = _client(monkeypatch)
    ref_id = uuid4()

    with patch.object(supply_api, "InventoryLedger") as cls:
        cls.return_value.record_movement = AsyncMock(
            return_value={
                "sku_id": "MAT-001",
                "on_hand_after": Decimal("15"),
                "qty_opening": Decimal("10"),
                "qty_closing": Decimal("15"),
                "reference_id": ref_id,
            }
        )
        resp = client.post(
            "/v1/supply/inventory/movement",
            json={
                "sku_id": "MAT-001",
                "qty_change": 5.0,
                "transaction_type": "receive",
                "reference_id": str(ref_id),
            },
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["sku_id"] == "MAT-001"
    assert body["on_hand_after"] == 15.0
    assert body["qty_opening"] == 10.0
    assert body["qty_closing"] == 15.0
    assert body["reference_id"] == str(ref_id)


def test_record_movement_value_error_returns_422(monkeypatch):
    """POST /inventory/movement → 422 quando ledger levanta ValueError."""
    client = _client(monkeypatch)

    with patch.object(supply_api, "InventoryLedger") as cls:
        cls.return_value.record_movement = AsyncMock(
            side_effect=ValueError("would-be negative on-hand")
        )
        resp = client.post(
            "/v1/supply/inventory/movement",
            json={
                "sku_id": "MAT-001",
                "qty_change": -100.0,
                "transaction_type": "consume",
            },
        )
    assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────────────────
# GET /rop/{sku_id}
# ──────────────────────────────────────────────────────────────────────────


def test_calculate_rop_returns_shape(monkeypatch):
    """GET /rop/{sku_id} → 200 com rop, base_rop, safety_stock, z_score, service_level."""
    client = _client(monkeypatch)

    fake_calc = {
        "rop": 50.0,
        "base_rop": 40.0,
        "safety_stock": 10.0,
        "z_score": 1.645,
        "service_level": 0.95,
    }
    with patch.object(supply_api, "ROPCalculator") as cls:
        cls.return_value.calculate_rop = MagicMock(return_value=fake_calc)
        resp = client.get(
            "/v1/supply/rop/MAT-001",
            params={
                "avg_daily_demand": 4.0,
                "lead_time_days": 10,
                "lead_time_std_dev": 1.5,
                "service_level": 0.95,
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sku_id"] == "MAT-001"
    assert body["rop"] == 50.0
    assert body["service_level"] == 0.95


def test_calculate_rop_rejects_invalid_service_level(monkeypatch):
    """service_level fora de {0.90, 0.95, 0.99} → 400."""
    client = _client(monkeypatch)
    resp = client.get(
        "/v1/supply/rop/MAT-001",
        params={
            "avg_daily_demand": 4.0,
            "lead_time_days": 10,
            "lead_time_std_dev": 1.5,
            "service_level": 0.80,
        },
    )
    assert resp.status_code == 400


def test_calculate_rop_rejects_negative_inputs(monkeypatch):
    """avg_daily_demand < 0 → 400."""
    client = _client(monkeypatch)
    resp = client.get(
        "/v1/supply/rop/MAT-001",
        params={
            "avg_daily_demand": -1.0,
            "lead_time_days": 10,
            "lead_time_std_dev": 1.5,
        },
    )
    assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────────────
# POST /abc
# ──────────────────────────────────────────────────────────────────────────


def test_abc_analysis_returns_distribution(monkeypatch):
    """POST /abc → 200 com distribution.{A,B,C}.{count, skus[]}."""
    client = _client(monkeypatch)

    fake_buckets = {
        "A": [{"sku_id": "X", "value": 1000.0}],
        "B": [{"sku_id": "Y", "value": 100.0}],
        "C": [],
    }
    with patch.object(supply_api, "ABCAnalysis") as cls:
        cls.return_value.calculate_abc_distribution = MagicMock(
            return_value=fake_buckets
        )
        resp = client.post(
            "/v1/supply/abc",
            json={
                "skus_list": [
                    {"sku_id": "X", "value": 1000.0},
                    {"sku_id": "Y", "value": 100.0},
                ]
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body["distribution"].keys()) == {"A", "B", "C"}
    assert body["distribution"]["A"]["count"] == 1
    assert body["distribution"]["B"]["count"] == 1
    assert body["distribution"]["C"]["count"] == 0


# ──────────────────────────────────────────────────────────────────────────
# POST /rop-configs/recompute
# ──────────────────────────────────────────────────────────────────────────


def test_recompute_rop_configs_returns_metrics(monkeypatch):
    """POST /rop-configs/recompute → 200 com rows_processed/upserted/skipped."""
    client = _client(monkeypatch)

    fake_result = {
        "rows_processed": 5,
        "rows_upserted": 4,
        "rows_skipped": 1,
    }
    with patch.object(
        supply_api,
        "recompute_rop_configs",
        new=AsyncMock(return_value=fake_result),
    ):
        resp = client.post(
            "/v1/supply/rop-configs/recompute",
            params={"lookback_days": 30, "service_level": 0.95},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == fake_result


def test_recompute_rop_configs_rejects_bad_lookback(monkeypatch):
    """lookback_days < 7 → 422 (Query(ge=7))."""
    client = _client(monkeypatch)
    resp = client.post(
        "/v1/supply/rop-configs/recompute", params={"lookback_days": 1}
    )
    assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────────────────
# GET /materials
# ──────────────────────────────────────────────────────────────────────────


def test_list_materials_returns_list(monkeypatch):
    """GET /materials → 200 com lista de MaterialResponse."""
    client = _client(monkeypatch)

    with patch.object(supply_api, "MaterialService") as cls:
        cls.return_value.list_materials = AsyncMock(
            return_value=[_material_row("MAT-001"), _material_row("MAT-002")]
        )
        resp = client.get("/v1/supply/materials")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2
    row = body[0]
    assert {
        "id",
        "sku_id",
        "name",
        "unit_of_measure",
        "lead_time_days",
        "min_stock_qty",
        "reorder_qty",
        "critical_flag",
        "active",
    } <= row.keys()


# ──────────────────────────────────────────────────────────────────────────
# GET /materials/from-bom
# ──────────────────────────────────────────────────────────────────────────


def test_list_materials_from_bom_empty_returns_envelope(monkeypatch):
    """GET /materials/from-bom (sem dados) → 200 com envelope completo."""
    client = _client(monkeypatch)

    # SessionStub que devolve listas vazias (sem BOM, sem stock).
    class _EmptySession:
        async def execute(self, _stmt):
            class _R:
                def all(self_inner):
                    return []

                def scalars(self_inner):
                    class _S:
                        def all(self_s):
                            return []

                    return _S()

            return _R()

        async def commit(self):
            pass

    async def _override() -> AsyncIterator[Any]:
        yield _EmptySession()

    app = FastAPI()
    app.include_router(supply_router)
    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[require_tenant_header] = lambda: TENANT
    c = TestClient(app, raise_server_exceptions=False)

    resp = c.get("/v1/supply/materials/from-bom")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 0
    assert body["items"] == []
    assert body["stock_available"] is False
    assert body["stock_source"] == "indisponivel"
    assert body["unavailable_reason"] is not None


# ──────────────────────────────────────────────────────────────────────────
# GET /purchase-orders
# ──────────────────────────────────────────────────────────────────────────


def test_list_purchase_orders_returns_envelope(monkeypatch):
    """GET /purchase-orders → 200 com envelope items/count/data_available/summary."""
    client = _client(monkeypatch)

    fake_svc_result = {
        "items": [],
        "count": 0,
        "data_available": False,
        "source": "indisponivel",
        "last_synced_at": None,
        "unavailable_reason": "sem sync",
        "summary": {
            "open": 0,
            "overdue": 0,
            "received": 0,
            "cancelled": 0,
            "total_outstanding_qty": 0.0,
        },
    }
    with patch.object(supply_api, "PurchaseOrderService") as cls:
        cls.return_value.list_purchase_orders = AsyncMock(
            return_value=fake_svc_result
        )
        resp = client.get("/v1/supply/purchase-orders")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 0
    assert body["data_available"] is False
    assert body["source"] == "indisponivel"
    assert "summary" in body
    assert {"open", "overdue", "received", "cancelled", "total_outstanding_qty"} <= body[
        "summary"
    ].keys()


def test_list_purchase_orders_rejects_bad_limit(monkeypatch):
    """limit fora de [1, 1000] → 400."""
    client = _client(monkeypatch)
    resp = client.get("/v1/supply/purchase-orders", params={"limit": 9999})
    assert resp.status_code == 400


def test_list_purchase_orders_value_error_returns_400(monkeypatch):
    """ValueError do service → 400."""
    client = _client(monkeypatch)
    with patch.object(supply_api, "PurchaseOrderService") as cls:
        cls.return_value.list_purchase_orders = AsyncMock(
            side_effect=ValueError("status inválido")
        )
        resp = client.get(
            "/v1/supply/purchase-orders", params={"status_filter": "OPEN"}
        )
    assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────────────
# GET /materials/{sku_id}/stockout-forecast
# ──────────────────────────────────────────────────────────────────────────


def test_stockout_forecast_returns_shape(monkeypatch):
    """GET /materials/{sku_id}/stockout-forecast → 200 com sku_id/confidence/method."""
    client = _client(monkeypatch)

    with (
        patch.object(supply_api, "InventoryLedger") as ledger_cls,
        patch.object(supply_api, "StockoutPredictor") as pred_cls,
    ):
        ledger_cls.return_value.get_current_on_hand = AsyncMock(
            return_value=Decimal("100")
        )
        pred_cls.return_value.predict = AsyncMock(
            return_value={
                "sku_id": "MAT-001",
                "predicted_stockout_date": "2026-08-15",
                "confidence": "high",
                "avg_daily_consumption": 1.2,
                "history_days": 90,
                "total_consumed": 108.0,
                "window_days": 90,
                "days_to_stockout": 83.0,
                "reason": None,
                "method": "rolling_avg",
            }
        )
        resp = client.get("/v1/supply/materials/MAT-001/stockout-forecast")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sku_id"] == "MAT-001"
    assert body["confidence"] == "high"
    assert body["on_hand"] == 100.0
    assert body["method"] == "rolling_avg"


def test_stockout_forecast_rejects_bad_window(monkeypatch):
    """window_days < 7 → 400."""
    client = _client(monkeypatch)
    resp = client.get(
        "/v1/supply/materials/MAT-001/stockout-forecast",
        params={"window_days": 3},
    )
    assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────────────
# POST /materials
# ──────────────────────────────────────────────────────────────────────────


def test_create_material_returns_201(monkeypatch):
    """POST /materials → 201 com MaterialResponse."""
    client = _client(monkeypatch)

    with patch.object(supply_api, "MaterialService") as cls:
        cls.return_value.create_material = AsyncMock(
            return_value=_material_row("MAT-NEW")
        )
        resp = client.post(
            "/v1/supply/materials",
            json={"sku_id": "MAT-NEW", "name": "Resina nova"},
        )
    assert resp.status_code == 201, resp.text
    assert resp.json()["sku_id"] == "MAT-NEW"


def test_create_material_value_error_returns_400(monkeypatch):
    """POST /materials → 400 quando service levanta ValueError."""
    client = _client(monkeypatch)

    with patch.object(supply_api, "MaterialService") as cls:
        cls.return_value.create_material = AsyncMock(
            side_effect=ValueError("sku already exists")
        )
        resp = client.post(
            "/v1/supply/materials",
            json={"sku_id": "MAT-DUP", "name": "Dup"},
        )
    assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────────────
# GET /materials/{sku_id}/position
# ──────────────────────────────────────────────────────────────────────────


def test_get_material_position_returns_payload(monkeypatch):
    """GET /materials/{sku_id}/position → 200, payload livre."""
    client = _client(monkeypatch)

    fake_position = {
        "sku_id": "MAT-001",
        "on_hand": 50.0,
        "in_transit": 10.0,
        "min_stock_qty": 20.0,
        "horizon_days": 14,
    }
    with patch.object(supply_api, "MaterialService") as cls:
        cls.return_value.get_position = AsyncMock(return_value=fake_position)
        resp = client.get("/v1/supply/materials/MAT-001/position")
    assert resp.status_code == 200, resp.text
    assert resp.json() == fake_position


# ──────────────────────────────────────────────────────────────────────────
# PATCH /materials/{sku_id}/min-stock
# ──────────────────────────────────────────────────────────────────────────


def test_patch_min_stock_returns_material(monkeypatch):
    """PATCH /materials/{sku_id}/min-stock → 200 com MaterialResponse."""
    client = _client(monkeypatch)

    with patch.object(supply_api, "MaterialService") as cls:
        cls.return_value.update_min_stock = AsyncMock(
            return_value=_material_row("MAT-001")
        )
        resp = client.patch(
            "/v1/supply/materials/MAT-001/min-stock",
            json={"min_stock_qty": 25.0},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sku_id"] == "MAT-001"


def test_patch_min_stock_not_found_returns_404(monkeypatch):
    """PATCH /materials/{sku_id}/min-stock → 404 quando material nao existe."""
    client = _client(monkeypatch)

    with patch.object(supply_api, "MaterialService") as cls:
        cls.return_value.update_min_stock = AsyncMock(
            side_effect=MaterialNotFoundError("MAT-XXX")
        )
        resp = client.patch(
            "/v1/supply/materials/MAT-XXX/min-stock",
            json={"min_stock_qty": 25.0},
        )
    assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────
# POST /materials/{sku_id}/adjust
# ──────────────────────────────────────────────────────────────────────────


def test_adjust_stock_returns_shape(monkeypatch):
    """POST /materials/{sku_id}/adjust → 200 com qty_delta/qty_opening/qty_closing."""
    client = _client(monkeypatch)

    with patch.object(supply_api, "MaterialService") as cls:
        cls.return_value.adjust_stock = AsyncMock(
            return_value={
                "sku_id": "MAT-001",
                "on_hand_after": Decimal("12"),
                "qty_opening": Decimal("10"),
                "qty_closing": Decimal("12"),
                "qty_delta": 2.0,
                "reason": "contagem manual",
            }
        )
        resp = client.post(
            "/v1/supply/materials/MAT-001/adjust",
            json={"qty_delta": 2.0, "reason": "contagem manual"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sku_id"] == "MAT-001"
    assert body["qty_delta"] == 2.0
    assert body["reason"] == "contagem manual"


def test_adjust_stock_negative_blocked_returns_422(monkeypatch):
    """POST /materials/{sku_id}/adjust → 422 com payload estruturado quando NegativeStockBlocked."""
    client = _client(monkeypatch)

    with patch.object(supply_api, "MaterialService") as cls:
        cls.return_value.adjust_stock = AsyncMock(
            side_effect=NegativeStockBlockedError(
                "MAT-001", Decimal("5"), Decimal("-10")
            )
        )
        resp = client.post(
            "/v1/supply/materials/MAT-001/adjust",
            json={"qty_delta": -10.0, "reason": "consumo"},
        )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error"] == "NEGATIVE_STOCK_BLOCKED"
    assert detail["sku_id"] == "MAT-001"
    assert detail["current_qty"] == 5.0
    assert detail["requested_delta"] == -10.0


# ──────────────────────────────────────────────────────────────────────────
# GET /materials/{sku_id}/movements
# ──────────────────────────────────────────────────────────────────────────


def test_get_movements_returns_payload(monkeypatch):
    """GET /materials/{sku_id}/movements → 200, payload livre."""
    client = _client(monkeypatch)

    fake = [{"date": "2026-05-01", "qty_in": 10.0, "qty_out": 0.0}]
    with patch.object(supply_api, "MaterialService") as cls:
        cls.return_value.get_movements = AsyncMock(return_value=fake)
        resp = client.get("/v1/supply/materials/MAT-001/movements")
    assert resp.status_code == 200, resp.text
    assert resp.json() == fake


def test_get_movements_rejects_bad_limit(monkeypatch):
    """limit fora de [1, 1000] → 400."""
    client = _client(monkeypatch)
    resp = client.get(
        "/v1/supply/materials/MAT-001/movements", params={"limit": 9999}
    )
    assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────────────
# POST /reconciliation (create)
# ──────────────────────────────────────────────────────────────────────────


def test_create_reconciliation_returns_201(monkeypatch):
    """POST /reconciliation → 201 com ReconciliationResponse."""
    client = _client(monkeypatch)

    with patch.object(supply_api, "MaterialService") as cls:
        cls.return_value.create_reconciliation = AsyncMock(
            return_value=_reconciliation_row("MAT-001")
        )
        resp = client.post(
            "/v1/supply/reconciliation",
            params={"sku_id": "MAT-001"},
            json={"physical_qty": 95.0},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["sku_id"] == "MAT-001"
    assert body["physical_qty"] == 95.0
    assert body["resolved"] is False


# ──────────────────────────────────────────────────────────────────────────
# GET /reconciliation (list)
# ──────────────────────────────────────────────────────────────────────────


def test_list_reconciliations_returns_list(monkeypatch):
    """GET /reconciliation → 200 com lista."""
    client = _client(monkeypatch)

    with patch.object(supply_api, "MaterialService") as cls:
        cls.return_value.list_reconciliations = AsyncMock(
            return_value=[_reconciliation_row("MAT-001")]
        )
        resp = client.get("/v1/supply/reconciliation")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["sku_id"] == "MAT-001"


def test_list_reconciliations_rejects_bad_limit(monkeypatch):
    """limit fora de [1, 1000] → 400."""
    client = _client(monkeypatch)
    resp = client.get("/v1/supply/reconciliation", params={"limit": 0})
    assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────────────
# POST /reconciliation/{id}/resolve
# ──────────────────────────────────────────────────────────────────────────


def test_resolve_reconciliation_returns_200(monkeypatch):
    """POST /reconciliation/{id}/resolve → 200 com ReconciliationResponse."""
    client = _client(monkeypatch)
    rec_id = uuid4()
    resolved_row = _reconciliation_row("MAT-001")
    resolved_row.resolved = True
    resolved_row.resolved_at = datetime(2026, 5, 2, tzinfo=timezone.utc)
    resolved_row.resolved_by = "alice"

    with patch.object(supply_api, "MaterialService") as cls:
        cls.return_value.resolve_reconciliation = AsyncMock(
            return_value=resolved_row
        )
        resp = client.post(
            f"/v1/supply/reconciliation/{rec_id}/resolve",
            params={"resolved_by": "alice"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["resolved"] is True
    assert body["resolved_by"] == "alice"


def test_resolve_reconciliation_not_found_returns_404(monkeypatch):
    """POST /reconciliation/{id}/resolve → 404 quando service levanta ValueError."""
    client = _client(monkeypatch)
    rec_id = uuid4()

    with patch.object(supply_api, "MaterialService") as cls:
        cls.return_value.resolve_reconciliation = AsyncMock(
            side_effect=ValueError("not found")
        )
        resp = client.post(f"/v1/supply/reconciliation/{rec_id}/resolve")
    assert resp.status_code == 404
