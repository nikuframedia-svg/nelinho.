"""
Q.37.D — testes dos action handlers reais (inventário + scheduling).

Só testes unitários (FakeSession / AsyncMock, sem Postgres) — regra do
worktree. Twin e CPO são substituídos por fakes; o que se verifica é o
contrato dos handlers e o registo.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.copilot.actions import (
    Action,
    ActionMode,
    _ACTION_HANDLERS,
    clear_action_handlers,
)
from src.copilot.action_handlers import register_all_action_handlers
from src.copilot.action_handlers.inventory import (
    InventoryAdjustmentRejected,
    adjust_inventory,
)
from src.copilot.action_handlers import scheduling

TENANT = UUID("00000000-0000-0000-0000-000000000001")
USER = UUID("00000000-0000-0000-0000-000000000001")


# ─────────────────────────────────────────────────────────────────────
# Fakes
# ─────────────────────────────────────────────────────────────────────

class _FakeResult:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class _FakeSession:
    """Sessão mínima: `execute` devolve um produto fixo, `flush` no-op."""

    def __init__(self, product=None):
        self._product = product
        self.flushed = False

    async def execute(self, _query):
        return _FakeResult(self._product)

    async def flush(self):
        self.flushed = True


class _FakeExecutor:
    def __init__(self, session, mode=None):
        self.session = session
        self.tenant_id = TENANT
        self.user_id = USER
        self.current_mode = mode


def _make_product(safety_stock="100"):
    return SimpleNamespace(
        id=uuid4(),
        product_code="K1-RACE",
        safety_stock=Decimal(safety_stock),
        lead_time_days=7,
    )


def _inventory_action(target, new_ss, baseline=None):
    payload = {"target": str(target), "new_safety_stock": new_ss}
    if baseline is not None:
        payload["baseline_safety_stock"] = baseline
    return Action(
        action_id=str(uuid4()),
        action_type="adjust_inventory",
        description="ajuste",
        modes=["execute"],
        estimated_impact={},
        payload=payload,
    )


# ─────────────────────────────────────────────────────────────────────
# register_all_action_handlers
# ─────────────────────────────────────────────────────────────────────

def test_register_all_action_handlers_regista_quatro():
    clear_action_handlers()
    n = register_all_action_handlers()
    assert n == 4
    for action_type in (
        "adjust_inventory",
        "reschedule_order",
        "optimize_capacity",
        "reduce_setup",
    ):
        assert action_type in _ACTION_HANDLERS
    clear_action_handlers()


def test_register_all_action_handlers_idempotente():
    clear_action_handlers()
    register_all_action_handlers()
    # Segunda chamada não rebenta com "already registered".
    register_all_action_handlers()
    assert len(_ACTION_HANDLERS) == 4
    clear_action_handlers()


# ─────────────────────────────────────────────────────────────────────
# inventory.adjust_inventory
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_adjust_inventory_sobe_safety_stock():
    product = _make_product("100")
    session = _FakeSession(product)
    executor = _FakeExecutor(session)
    action = _inventory_action(product.id, 150)

    result = await adjust_inventory(executor, action, None)

    assert product.safety_stock == Decimal("150")
    assert session.flushed is True
    assert result["products"][0]["safety_stock"] == 150.0
    assert result["adjustment"]["old_safety_stock"] == 100.0
    assert result["adjustment"]["new_safety_stock"] == 150.0


@pytest.mark.asyncio
async def test_adjust_inventory_recusa_abaixo_do_baseline_axioma_7():
    product = _make_product("100")
    session = _FakeSession(product)
    executor = _FakeExecutor(session)
    # Desce para 80 mas o baseline é 100 → recusado.
    action = _inventory_action(product.id, 80, baseline=100)

    with pytest.raises(InventoryAdjustmentRejected, match="axioma 7"):
        await adjust_inventory(executor, action, None)

    # O produto NÃO foi tocado.
    assert product.safety_stock == Decimal("100")


@pytest.mark.asyncio
async def test_adjust_inventory_recusa_negativo_sem_baseline():
    product = _make_product("50")
    session = _FakeSession(product)
    executor = _FakeExecutor(session)
    action = _inventory_action(product.id, -10)

    with pytest.raises(InventoryAdjustmentRejected):
        await adjust_inventory(executor, action, None)


@pytest.mark.asyncio
async def test_adjust_inventory_produto_inexistente_rejeita():
    session = _FakeSession(product=None)
    executor = _FakeExecutor(session)
    action = _inventory_action(uuid4(), 120)

    with pytest.raises(InventoryAdjustmentRejected, match="não encontrado"):
        await adjust_inventory(executor, action, None)


@pytest.mark.asyncio
async def test_adjust_inventory_sem_target_rejeita():
    executor = _FakeExecutor(_FakeSession())
    action = Action(
        action_id=str(uuid4()),
        action_type="adjust_inventory",
        description="x",
        modes=["execute"],
        estimated_impact={},
        payload={"new_safety_stock": 100},
    )
    with pytest.raises(InventoryAdjustmentRejected, match="target"):
        await adjust_inventory(executor, action, None)


# ─────────────────────────────────────────────────────────────────────
# scheduling — dispatcher SANDBOX vs EXECUTE
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scheduling_sandbox_usa_twin(monkeypatch):
    scenario = SimpleNamespace(id=uuid4(), scenario_hash="hash-sandbox")
    fake_twin = AsyncMock()
    fake_twin.create_scenario.return_value = scenario
    fake_twin.apply_delta.return_value = SimpleNamespace(id=uuid4())
    fake_twin.simulate.return_value = {
        "before": {"backlog_horas_theoretical": {"value": 200}},
        "after": {"backlog_horas_theoretical": {"value": 180}},
        "delta_summary": {"backlog_horas_theoretical_change": -20},
    }
    monkeypatch.setattr(
        "src.twin.service.TwinService", lambda db, tenant_id: fake_twin
    )

    executor = _FakeExecutor(_FakeSession(), mode=ActionMode.SANDBOX)
    action = Action(
        action_id=str(uuid4()),
        action_type="optimize_capacity",
        description="x",
        modes=["sandbox"],
        estimated_impact={},
        payload={"target": "fase-laminagem", "magnitude_pct": 10},
    )

    result = await scheduling.optimize_capacity(executor, action, None)

    assert result["mode"] == "sandbox_twin"
    assert result["scenario_hash"] == "hash-sandbox"
    assert result["delta_summary"]["backlog_horas_theoretical_change"] == -20
    fake_twin.simulate.assert_awaited_once()


@pytest.mark.asyncio
async def test_scheduling_execute_usa_cpo(monkeypatch):
    cpo_response = SimpleNamespace(
        model_dump=lambda: {
            "commit_sha256": "deadbeef",
            "engine_used": "cpo_v4",
            "status": "ok",
            "makespan_hours": 120.5,
            "num_late_orders": 2,
            "safety_net_triggered": False,
            "degraded": False,
        }
    )

    async def _fake_schedule_cpo(request, tenant_id, db):
        return cpo_response

    monkeypatch.setattr("src.plan.api.cpo.schedule_cpo", _fake_schedule_cpo)

    executor = _FakeExecutor(_FakeSession(), mode=ActionMode.EXECUTE)
    action = Action(
        action_id=str(uuid4()),
        action_type="reschedule_order",
        description="x",
        modes=["execute"],
        estimated_impact={},
        payload={"horizon_days": 14},
    )

    result = await scheduling.reschedule_order(executor, action, None)

    assert result["mode"] == "execute_cpo"
    assert result["commit_sha256"] == "deadbeef"
    assert result["num_late_orders"] == 2
    assert result["safety_net_triggered"] is False
