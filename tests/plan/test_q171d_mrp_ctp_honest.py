"""Q.171.D — MRP lê stock REAL + CTP declara a base do gate de materiais.

A auditoria 2026-06-10 apanhou dois buracos de honestidade (invariante #8):

* ``MRPService.run_mrp`` corria SEMPRE com ``inventory={}`` quando o caller
  não fornecia (o endpoint `/v1/plan/mrp/run` envia ``{}`` por omissão) —
  netting cego: sugeria compras como se a fábrica não tivesse stock NENHUM,
  apesar do mirror ERP `supply.warehouse_stock` (Q.52.K) existir ao lado.
* ``CTPService._materials_gate`` devolvia "OK" em SILÊNCIO quando não havia
  snapshot de stock — o consumidor via verde sem saber que era "sem dados".

Estes testes travam o contrato novo: inventário do warehouse por omissão
(com ``inventory_source`` honesto no resultado) e ``materials_known`` /
``materials_basis`` explícitos no CTP.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.plan.services.mrp_service import MRPService
from tests.conftest import TEST_TENANT_ID, FakeSession


@pytest.fixture(autouse=True)
def _no_kafka(monkeypatch):
    """Sem broker nos testes — evita os retries de ligação (lentos)."""
    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        "src.plan.services.mrp_service.publish_event", AsyncMock(),
    )


def _stock_row(product_code: str, stock: float, warehouse_id: int = 1):
    """Row mínima com o shape de supply.WarehouseStock que o serviço lê."""
    return SimpleNamespace(
        product_code=product_code,
        warehouse_id=warehouse_id,
        stock=Decimal(str(stock)),
    )


_BOM = {
    "items": [
        {"item_id": "BARCO-510", "item_type": "finished_good", "lead_time_days": 0},
        {"item_id": "RESINA-EP", "item_type": "raw_material", "lead_time_days": 3},
    ],
    "components": [
        {"parent_id": "BARCO-510", "component_id": "RESINA-EP", "quantity_per": 2},
    ],
}

_ORDERS = [
    {
        "order_id": str(uuid4()),
        "product_id": "BARCO-510",
        "quantity": 5,
        # naïve como o adapter espera (períodos do MRPAdapter são naïve)
        "due_date": "2026-07-01T00:00:00",
    },
]


async def test_run_mrp_sem_inventory_le_warehouse_stock_e_faz_netting():
    """Sem inventário do caller, o MRP carrega supply.warehouse_stock
    (agregado por product_code entre armazéns) e o netting desconta o
    stock real: 10 un. de resina em stock cobrem a necessidade de 10
    (5 barcos × 2) → ZERO sugestões de compra."""
    session = FakeSession()
    # 2 armazéns com 6+4 da mesma resina — o agregado tem de somar 10.
    session.queue_scalars([_stock_row("RESINA-EP", 6, 1), _stock_row("RESINA-EP", 4, 2)])

    service = MRPService(session, TEST_TENANT_ID)
    result = await service.run_mrp(orders=_ORDERS, bom_data=_BOM)

    assert result["inventory_source"] == "warehouse_stock"
    # o explode inclui o item-raiz (BARCO-510); o netting em causa é o do
    # componente com stock no armazém.
    resina = [
        s for s in result["purchase_suggestions"] if s["item_id"] == "RESINA-EP"
    ]
    assert resina == [], (
        "stock real cobre a necessidade — sugerir compra seria netting cego"
    )


async def test_run_mrp_sem_snapshot_declara_vazio_e_sugere_compra():
    """Mirror vazio → inventário {} como dantes, MAS o resultado declara
    ``inventory_source='vazio_sem_snapshot'`` (honesto) e a compra é
    sugerida pela necessidade bruta."""
    session = FakeSession()
    session.queue_scalars([])  # warehouse_stock sem rows

    service = MRPService(session, TEST_TENANT_ID)
    result = await service.run_mrp(orders=_ORDERS, bom_data=_BOM)

    assert result["inventory_source"] == "vazio_sem_snapshot"
    qty = sum(
        float(s["quantity"])
        for s in result["purchase_suggestions"]
        if s["item_id"] == "RESINA-EP"
    )
    assert qty == pytest.approx(10.0)


async def test_run_mrp_inventory_do_caller_tem_precedencia():
    """Inventário explícito do caller NÃO é substituído pelo warehouse."""
    session = FakeSession()  # nada na queue — a query do warehouse nem corre

    service = MRPService(session, TEST_TENANT_ID)
    result = await service.run_mrp(
        orders=_ORDERS,
        inventory={"RESINA-EP": {"on_hand": 10}},
        bom_data=_BOM,
    )

    assert result["inventory_source"] == "caller"
    resina = [
        s for s in result["purchase_suggestions"] if s["item_id"] == "RESINA-EP"
    ]
    assert resina == []


# ──────────────────────────────────────────────────────────────────────────
# CTP — gate de materiais com base explícita
# ──────────────────────────────────────────────────────────────────────────


def _ctp_service():
    from src.plan.services.ctp_service import CapableToPromiseService

    return CapableToPromiseService(FakeSession(), TEST_TENANT_ID)


def _order(product_id: str = "510"):
    return SimpleNamespace(product_id=product_id)


def test_materials_gate_sem_snapshot_e_unknown_nao_verificado():
    """Sem snapshot: não bloqueia (ausência ≠ escassez) mas known=False —
    acabou o 'OK' silencioso."""
    ok, missing, known = _ctp_service()._materials_gate(_order(), {})
    assert (ok, missing, known) == (True, [], False)


def test_materials_gate_produto_sem_row_e_unknown():
    ok, missing, known = _ctp_service()._materials_gate(
        _order("510"), {"999": 4.0},
    )
    assert (ok, missing, known) == (True, [], False)


def test_materials_gate_stock_real_verifica():
    svc = _ctp_service()
    assert svc._materials_gate(_order("510"), {"510": 3.0}) == (True, [], True)
    assert svc._materials_gate(_order("510"), {"510": 0.0}) == (
        False, ["510"], True,
    )
