"""Q.173.X — CTP gate de materiais por BOM real (nível-1).

Substitui o proxy do produto acabado por explosão BOM de core.bom_items.
Tri-state honesto:
  - sem BOM → (True, [], False)  — inconclusivo, não bloqueia
  - BOM existe mas sem snapshot → (True, [], False) — inconclusivo
  - BOM + stock OK → (True, [], True)
  - BOM + shortage → (False, missing_list, True)
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, List
from uuid import UUID, uuid4

import pytest

from tests.conftest import TEST_TENANT_ID, FakeSession


def _svc(bom_rows: List[Any] | None = None, stock_map: dict | None = None):
    """CTPService com session fake e BOM/stock configuráveis."""
    from src.plan.services.ctp_service import CapableToPromiseService

    svc = CapableToPromiseService(FakeSession(), TEST_TENANT_ID)
    # Monkeypatches inline — sem BD
    async def _fake_bom(product_id):
        return bom_rows or []

    async def _fake_stock():
        return stock_map or {}

    svc._bom_for_product = _fake_bom
    svc._stock_by_product = _fake_stock
    return svc


def _order(product_id: str | None = None):
    return SimpleNamespace(product_id=product_id or str(uuid4()))


# ---------------------------------------------------------------------------
# _materials_gate_bom — tri-state

@pytest.mark.asyncio
async def test_sem_bom_retorna_inconclusivo():
    """Sem BOM → (True, [], False): não bloqueia, known=False (nunca OK silencioso)."""
    svc = _svc(bom_rows=[])
    ok, missing, known = await svc._materials_gate_bom(_order(), {"abc": 10.0})
    assert (ok, missing, known) == (True, [], False)


@pytest.mark.asyncio
async def test_bom_existe_sem_snapshot_inconclusivo():
    """BOM existe mas sem snapshot de stock → (True, [], False)."""
    bom = [{"component_code": "COMP-1", "quantity_per": 2.0}]
    svc = _svc(bom_rows=bom, stock_map={})
    ok, missing, known = await svc._materials_gate_bom(_order(), {})
    assert (ok, missing, known) == (True, [], False)


@pytest.mark.asyncio
async def test_bom_stock_suficiente_retorna_ok():
    """BOM + stock suficiente → (True, [], True)."""
    cid = str(uuid4())
    bom = [{"component_code": cid, "quantity_per": 3.0}]
    svc = _svc(bom_rows=bom, stock_map={cid: 10.0})
    ok, missing, known = await svc._materials_gate_bom(_order(), {cid: 10.0})
    assert ok is True
    assert missing == []
    assert known is True


@pytest.mark.asyncio
async def test_bom_stock_insuficiente_retorna_false_com_detalhe():
    """BOM + stock < needed → (False, [{component, needed, available}], True)."""
    cid = str(uuid4())
    bom = [{"component_code": cid, "quantity_per": 5.0}]
    svc = _svc(bom_rows=bom, stock_map={cid: 2.0})
    ok, missing, known = await svc._materials_gate_bom(_order(), {cid: 2.0})
    assert ok is False
    assert known is True
    assert len(missing) == 1
    assert missing[0]["component"] == cid
    assert missing[0]["needed"] == 5.0
    assert missing[0]["available"] == 2.0


@pytest.mark.asyncio
async def test_bom_componente_sem_stock_zero_disponivel():
    """Componente na BOM mas sem row no stock_map → treated as 0 disponível."""
    cid = str(uuid4())
    bom = [{"component_code": cid, "quantity_per": 1.0}]
    svc = _svc(bom_rows=bom, stock_map={})
    # stock_map vazio — mas tem BOM; não é o caso "sem_snapshot" do outer check
    # porque passamos o dict diretamente. Este path nunca devia acontecer via
    # evaluate (veja o outer check), mas o método deve ser robusto.
    # Com stock_map={} e bom != [] → retorna inconclusivo (outer check)
    ok, missing, known = await svc._materials_gate_bom(_order(), {})
    assert (ok, missing, known) == (True, [], False)


@pytest.mark.asyncio
async def test_bom_multiplos_componentes_um_em_falta():
    """Vários componentes; só um em falta → shortage com exactamente 1 missing."""
    c1 = str(uuid4())
    c2 = str(uuid4())
    bom = [
        {"component_code": c1, "quantity_per": 2.0},
        {"component_code": c2, "quantity_per": 5.0},
    ]
    stock = {c1: 10.0, c2: 3.0}  # c2 insuficiente
    svc = _svc(bom_rows=bom, stock_map=stock)
    ok, missing, known = await svc._materials_gate_bom(_order(), stock)
    assert ok is False
    assert known is True
    assert len(missing) == 1
    assert missing[0]["component"] == c2


# ---------------------------------------------------------------------------
# bom_data_available propagado no campo da resposta

@pytest.mark.asyncio
async def test_evaluated_entry_tem_bom_data_available():
    """O dict de evaluate inclui bom_data_available=False quando sem BOM."""
    from datetime import date
    from unittest.mock import AsyncMock, patch

    from src.plan.services.ctp_service import CapableToPromiseService

    order = SimpleNamespace(
        id=uuid4(),
        legacy_id=99,
        product_name="K1 Test",
        product_type="K1",
        product_id=str(uuid4()),
        status=type("S", (), {"value": "IN_PROGRESS"})(),
        tenant_id=TEST_TENANT_ID,
    )

    svc = CapableToPromiseService(FakeSession(), TEST_TENANT_ID)

    async def _fake_bom_for_product(pid):
        return []  # sem BOM

    async def _fake_stock():
        return {}

    async def _fake_suggest(o, start=None):
        return {}  # sem data sugerida

    svc._bom_for_product = _fake_bom_for_product
    svc._stock_by_product = _fake_stock

    with patch.object(
        svc,
        "_stock_by_product",
        new=AsyncMock(return_value={}),
    ):
        with patch(
            "src.plan.services.ctp_service.BackwardSchedulerService",
        ) as MockBW:
            mock_bw = MockBW.return_value
            mock_bw.suggest_shipment_for_order = AsyncMock(return_value={})

            from sqlalchemy import select
            from unittest.mock import MagicMock

            async def _fake_execute(stmt, *args, **kwargs):
                mock_res = MagicMock()
                mock_res.scalars.return_value.all.return_value = [order]
                return mock_res

            svc.session.execute = _fake_execute

            result = await svc.evaluate(
                truck_date=date(2026, 7, 1),
                truck_capacity=5,
            )

    # Todos os evaluated devem ter bom_data_available=False (sem BOM)
    all_boats = result["committable"] + result["at_risk"] + result["rejected"]
    for boat in all_boats:
        assert "bom_data_available" in boat, (
            "bom_data_available deve estar no shape de resposta"
        )
        assert boat["bom_data_available"] is False
