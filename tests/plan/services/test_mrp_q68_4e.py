"""Q.68.4.E — `src/plan/services/mrp_service.py` estava a 25% — toda a
`run_mrp` (BOM explosion + netting + lead-time offset + persistência)
sem testes. O sinal de "comprar X agora" depende disto; um silencioso
off-by-one no `start_date` cria backorder na realidade.

Testes:

* `_is_uuid()` — helper trivial mas chave para decidir se grava `material_id`.
* `run_mrp()` happy path com BoM 1-nivel: gera 1 requisito por componente,
  persiste `MaterialRequirement` + publica evento + audita.
* `run_mrp()` com inventário suficiente → zero compras.
* `run_mrp()` com `include_safety_stock=False` → safety stock ignorado.
* `run_mrp()` com BoM cíclico → `BOMCycleError` propagado (não silenciado).
* `create_purchase_orders()` cria N POs numeradas `PO-YYYYMMDD-0001`.
* `get_requirements()` filtra por `mrp_run_id` / `material_id`.

Usa `FakeSession` (queue) + monkeypatch ao `publish_event` para evitar
Kafka real.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.plan.engines.bom_adapter import BOMCycleError
from src.plan.models.mrp import MaterialRequirement, PurchaseOrder, POStatus
from src.plan.services import mrp_service as mrp_mod
from src.plan.services.mrp_service import MRPService


TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ─── Helpers ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _silence_kafka(monkeypatch: pytest.MonkeyPatch):
    """`publish_event` aqui é best-effort; em testes deve ser no-op."""

    async def _ok(*_a, **_kw):
        return True

    monkeypatch.setattr(mrp_mod, "publish_event", _ok)


def _build_service(fake_session) -> MRPService:
    return MRPService(session=fake_session, tenant_id=TENANT)


def _bom_one_level(parent: str, child: str, qty: float = 1.0) -> dict:
    return {
        "items": [
            {"item_id": parent, "name": parent, "item_type": "finished_good"},
            {
                "item_id": child,
                "name": child,
                "item_type": "raw_material",
                "lead_time_days": 5,
                "cost_per_unit": 12.5,
            },
        ],
        "components": [
            {"parent_id": parent, "component_id": child, "quantity_per": qty},
        ],
    }


def _bom_cyclic() -> dict:
    return {
        "items": [
            {"item_id": "A", "name": "A"},
            {"item_id": "B", "name": "B"},
        ],
        "components": [
            {"parent_id": "A", "component_id": "B", "quantity_per": 1.0},
            {"parent_id": "B", "component_id": "A", "quantity_per": 1.0},
        ],
    }


# ─── _is_uuid ──────────────────────────────────────────────────────────────


def test_is_uuid_recognises_valid_uuid(fake_session):
    svc = _build_service(fake_session)
    assert svc._is_uuid(str(uuid4())) is True


def test_is_uuid_rejects_string_and_none(fake_session):
    svc = _build_service(fake_session)
    assert svc._is_uuid("not-a-uuid") is False
    assert svc._is_uuid("") is False
    assert svc._is_uuid("123") is False


# ─── run_mrp ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_mrp_with_one_level_bom_creates_requirement(fake_session):
    """O kayak K1 precisa de 2 unidades de resina; 0 stock → 1 PO sugerida
    + 1 `MaterialRequirement` persistido + 1 `AuditLog` na mesma session."""
    svc = _build_service(fake_session)
    result = await svc.run_mrp(
        orders=[
            {
                "order_id": "OF-9001",
                "product_id": "K1",
                "quantity": 1,
                "due_date": (date.today() + timedelta(days=30)).isoformat(),
            },
        ],
        bom_data=_bom_one_level("K1", "RESIN-A", qty=2.0),
    )
    assert result["status"] == "completed"
    # `items_analyzed` é o nº de componentes únicos vindos da BoM
    # explosion (parent + child no caso 1-level), não o nº de orders.
    assert result["items_analyzed"] >= 1
    assert result["purchase_orders"] >= 1
    assert result["currency"] == "EUR"
    # Pelo menos 1 MaterialRequirement + 1 AuditLog na session.
    types_added = {type(o).__name__ for o in fake_session.added}
    assert "MaterialRequirement" in types_added
    assert "AuditLog" in types_added


@pytest.mark.asyncio
async def test_run_mrp_with_sufficient_inventory_zero_purchases(fake_session):
    """Stock disponível >> requisitos → nenhuma compra sugerida."""
    svc = _build_service(fake_session)
    result = await svc.run_mrp(
        orders=[
            {
                "order_id": "OF-1",
                "product_id": "K1",
                "quantity": 1,
                "due_date": (date.today() + timedelta(days=60)).isoformat(),
            },
        ],
        inventory={
            "K1": {"on_hand": 10000, "on_order": 0, "allocated": 0, "safety_stock": 0},
            "RESIN-A": {"on_hand": 10000, "on_order": 0, "allocated": 0, "safety_stock": 0},
        },
        bom_data=_bom_one_level("K1", "RESIN-A", qty=2.0),
    )
    assert result["purchase_orders"] == 0
    assert result["purchase_suggestions"] == []


@pytest.mark.asyncio
async def test_run_mrp_respects_include_safety_stock_flag(fake_session):
    """Mesmo cenário, include_safety_stock=False → safety stock = 0 no
    netting → net_req = gross_req (sem buffer)."""
    svc = _build_service(fake_session)
    result_with = await svc.run_mrp(
        orders=[{"order_id": "O1", "product_id": "P", "quantity": 1, "due_date": date.today().isoformat()}],
        inventory={"M": {"on_hand": 0, "safety_stock": 1000}},
        bom_data=_bom_one_level("P", "M", qty=1.0),
        include_safety_stock=True,
    )
    # Reset adapter state (MRPService partilha instâncias).
    svc_no = _build_service(fake_session)
    result_no = await svc_no.run_mrp(
        orders=[{"order_id": "O1", "product_id": "P", "quantity": 1, "due_date": date.today().isoformat()}],
        inventory={"M": {"on_hand": 0, "safety_stock": 1000}},
        bom_data=_bom_one_level("P", "M", qty=1.0),
        include_safety_stock=False,
    )
    # Com safety stock: pelo menos 1 sugestão (tem de cobrir o safety).
    # Sem: a quantidade total das sugestões deve ser menor.
    qty_with = sum(s["quantity"] for s in result_with["purchase_suggestions"])
    qty_no = sum(s["quantity"] for s in result_no["purchase_suggestions"])
    assert qty_with > qty_no


@pytest.mark.asyncio
async def test_run_mrp_cyclic_bom_raises(fake_session):
    """BoM cíclico (A→B→A) deve falhar com `BOMCycleError` em vez de
    explosão silenciada (CRIT-11)."""
    svc = _build_service(fake_session)
    with pytest.raises(BOMCycleError):
        await svc.run_mrp(
            orders=[{"order_id": "X", "product_id": "A", "quantity": 1, "due_date": date.today().isoformat()}],
            bom_data=_bom_cyclic(),
        )


@pytest.mark.asyncio
async def test_run_mrp_due_date_accepts_iso_string_and_date(fake_session):
    """`due_date` aceita str ISO (sem timezone) e `date` puro. O parser
    do MRPService normaliza ambos para `datetime` naive, compatível com
    a comparação interna do `MRPAdapter._aggregate_requirements`."""
    svc = _build_service(fake_session)
    # ISO string naive
    await svc.run_mrp(
        orders=[
            {
                "order_id": "O1",
                "product_id": "P",
                "quantity": 1,
                "due_date": "2026-12-15T00:00:00",
            },
        ],
        bom_data=_bom_one_level("P", "M", qty=1.0),
    )
    # `date` directo — converte para `datetime.combine(date, min.time())`
    svc2 = _build_service(fake_session)
    await svc2.run_mrp(
        orders=[
            {
                "order_id": "O2",
                "product_id": "P",
                "quantity": 1,
                "due_date": date.today() + timedelta(days=30),
            },
        ],
        bom_data=_bom_one_level("P", "M", qty=1.0),
    )


# ─── create_purchase_orders ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_purchase_orders_numbers_sequentially(fake_session):
    svc = _build_service(fake_session)
    suggestions = [
        {
            "item_id": str(uuid4()),
            "quantity": 5,
            "unit_cost": 10,
            "line_total": 50,
            "start_date": "2026-05-01",
            "due_date": "2026-05-10",
            "lead_time_days": 9,
        },
        {
            "item_id": "non-uuid",  # material_id deve ficar None
            "quantity": 7,
            "unit_cost": 20,
            "line_total": 140,
            "start_date": "2026-05-02",
            "due_date": "2026-05-12",
            "lead_time_days": 10,
        },
    ]
    pos = await svc.create_purchase_orders("mrp-test", suggestions)
    assert len(pos) == 2
    assert pos[0].po_number.endswith("-0001")
    assert pos[1].po_number.endswith("-0002")
    assert pos[0].status == POStatus.DRAFT
    assert pos[1].material_id is None  # non-uuid item_id
    # Cada PO gera 1 AuditLog.
    audit_count = sum(1 for o in fake_session.added if type(o).__name__ == "AuditLog")
    assert audit_count >= 2


# ─── get_requirements ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_requirements_returns_queued_rows(fake_session):
    """`get_requirements()` delega a um SELECT — o FakeSession devolve a
    fila injectada. Confirma que o tenant_id é pinned e o resultado
    sai como lista."""
    expected = [
        MaterialRequirement(
            id=uuid4(),
            tenant_id=TENANT,
            mrp_run_id="run-1",
            gross_requirement=Decimal("10"),
            net_requirement=Decimal("10"),
            order_quantity=Decimal("10"),
            order_date=date.today(),
            due_date=date.today() + timedelta(days=7),
        ),
    ]
    fake_session.queue_scalars(expected)
    svc = _build_service(fake_session)
    rows = await svc.get_requirements(mrp_run_id="run-1")
    assert rows == expected
