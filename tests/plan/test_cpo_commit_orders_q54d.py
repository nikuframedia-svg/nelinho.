"""Q.54.D — merge do plano optimizado do CPO com as ordens activas.

Cobre a lógica pura de :mod:`src.plan.services.cpo_commit_orders` e o
endpoint ``GET /v1/plan/cpo/commits/{sha}/orders``:

* uma ordem planeada ganha os campos optimizados (fase/operador/máquina/datas);
* uma ordem fora do plano fica com ``in_optimized_plan=False`` e campos a null;
* a operação escolhida é a que casa com a fase actual, senão a mais cedo;
* nome de operador não resolvido → null honesto (zero mocks);
* o endpoint aceita ``latest`` e devolve os KPIs do commit.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.plan.api.cpo import router as cpo_router
from src.plan.cpo.commits import ScheduleCommit
from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.services.cpo_commit_orders import (
    merge_commit_with_orders,
    pick_operation_for_order,
)
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session


TENANT = UUID("00000000-0000-0000-0000-000000000001")


# ─── Builders ─────────────────────────────────────────────────────────────


def _order(
    *,
    legacy_id: int,
    product_name: str = "K1 Vanquish",
    product_type: str = "K1",
    phase: str = "Laminagem",
    status: OrderStatus = OrderStatus.IN_PROGRESS,
) -> ProductionOrder:
    return ProductionOrder(
        id=uuid4(),
        tenant_id=TENANT,
        legacy_id=legacy_id,
        product_id=legacy_id,
        product_name=product_name,
        product_type=product_type,
        current_phase_id=None,
        current_phase_name=phase,
        created_date=date(2026, 4, 1),
        transport_date=date(2026, 6, 1),
        status=status,
    )


def _op(
    *,
    order_id: str,
    phase_id: str = "F-LAM",
    setup_family: str = "Laminagem",
    machine_id: str | None = "MOLDE-12",
    workers: list[str] | None = None,
    start: str | None = "2026-04-20T08:00:00",
    end: str | None = "2026-04-20T12:00:00",
) -> dict:
    return {
        "operation_id": f"{order_id}::{phase_id}",
        "order_id": order_id,
        "phase_id": phase_id,
        "setup_family": setup_family,
        "machine_id": machine_id,
        "workers": workers if workers is not None else ["EMP-7"],
        "mold_id": None,
        "start_time": start,
        "end_time": end,
        "duration_minutes": 240.0,
    }


# ─── pick_operation_for_order ─────────────────────────────────────────────


class TestPickOperationForOrder:
    def test_no_ops_returns_none(self):
        assert pick_operation_for_order(_order(legacy_id=1), []) is None

    def test_matches_current_phase(self):
        order = _order(legacy_id=10, phase="Montagem")
        ops = [
            _op(order_id="10", setup_family="Laminagem", start="2026-04-20T08:00:00"),
            _op(order_id="10", setup_family="Montagem", start="2026-04-25T08:00:00"),
        ]
        chosen = pick_operation_for_order(order, ops)
        assert chosen is not None
        assert chosen["setup_family"] == "Montagem"

    def test_falls_back_to_earliest_start(self):
        # Fase actual "Corte" não tem operação no commit.
        order = _order(legacy_id=20, phase="Corte")
        ops = [
            _op(order_id="20", setup_family="Montagem", start="2026-04-25T08:00:00"),
            _op(order_id="20", setup_family="Laminagem", start="2026-04-20T08:00:00"),
        ]
        chosen = pick_operation_for_order(order, ops)
        assert chosen["setup_family"] == "Laminagem"  # arranca mais cedo

    def test_falls_back_to_first_when_no_dates(self):
        order = _order(legacy_id=30, phase="Corte")
        ops = [
            _op(order_id="30", setup_family="Montagem", start=None),
            _op(order_id="30", setup_family="Laminagem", start=None),
        ]
        chosen = pick_operation_for_order(order, ops)
        assert chosen["setup_family"] == "Montagem"


# ─── merge_commit_with_orders ─────────────────────────────────────────────


class TestMergeCommitWithOrders:
    def test_planned_order_gets_optimized_fields(self):
        order = _order(legacy_id=100, phase="Laminagem")
        ops = [_op(order_id="100", workers=["EMP-7"], machine_id="MOLDE-3")]
        merged = merge_commit_with_orders(
            operations=ops,
            orders=[order],
            employee_names={"EMP-7": "Paulo Gomes"},
        )
        assert len(merged) == 1
        item = merged[0]
        # forma de /orders/active preservada
        assert item["id"] == str(order.id)
        assert item["hull"] == "100"
        assert item["product_name"] == "K1 Vanquish"
        assert item["phase"] == "Laminagem"
        assert item["status"] == "IN_PROGRESS"
        # campos optimizados
        assert item["in_optimized_plan"] is True
        assert item["optimized_phase"] == "Laminagem"
        assert item["assigned_employee_id"] == "EMP-7"
        assert item["assigned_employee_name"] == "Paulo Gomes"
        assert item["assigned_machine_id"] == "MOLDE-3"
        assert item["scheduled_start"] == "2026-04-20T08:00:00"
        assert item["scheduled_end"] == "2026-04-20T12:00:00"

    def test_order_outside_plan_marked_honestly(self):
        order = _order(legacy_id=200)
        merged = merge_commit_with_orders(
            operations=[],  # commit vazio
            orders=[order],
            employee_names={},
        )
        item = merged[0]
        assert item["in_optimized_plan"] is False
        assert item["optimized_phase"] is None
        assert item["assigned_employee_id"] is None
        assert item["assigned_employee_name"] is None
        assert item["assigned_machine_id"] is None
        assert item["scheduled_start"] is None
        assert item["scheduled_end"] is None
        # mas a forma /orders/active continua completa
        assert item["hull"] == "200"
        assert item["product_type"] == "K1"

    def test_unresolved_employee_name_is_null(self):
        order = _order(legacy_id=300)
        ops = [_op(order_id="300", workers=["EMP-DESCONHECIDO"])]
        merged = merge_commit_with_orders(
            operations=ops,
            orders=[order],
            employee_names={"EMP-7": "Paulo Gomes"},  # não tem EMP-DESCONHECIDO
        )
        item = merged[0]
        assert item["assigned_employee_id"] == "EMP-DESCONHECIDO"
        assert item["assigned_employee_name"] is None  # honesto, não inventa

    def test_op_without_workers_yields_null_employee(self):
        order = _order(legacy_id=400)
        ops = [_op(order_id="400", workers=[])]
        merged = merge_commit_with_orders(
            operations=ops, orders=[order], employee_names={},
        )
        assert merged[0]["assigned_employee_id"] is None
        assert merged[0]["in_optimized_plan"] is True  # planeada, mas manual

    def test_phase_id_used_when_no_setup_family(self):
        order = _order(legacy_id=500, phase="Corte")
        ops = [
            {
                "operation_id": "500::F-X",
                "order_id": "500",
                "phase_id": "F-X",
                "setup_family": "",
                "machine_id": None,
                "workers": [],
                "start_time": "2026-05-01T08:00:00",
                "end_time": "2026-05-01T10:00:00",
            }
        ]
        merged = merge_commit_with_orders(
            operations=ops, orders=[order], employee_names={},
        )
        assert merged[0]["optimized_phase"] == "F-X"

    def test_multiple_orders_only_matching_ops(self):
        o1 = _order(legacy_id=1, phase="Laminagem")
        o2 = _order(legacy_id=2, phase="Montagem")
        ops = [
            _op(order_id="1", setup_family="Laminagem"),
            _op(order_id="2", setup_family="Montagem", machine_id="BANCADA-1"),
        ]
        merged = merge_commit_with_orders(
            operations=ops, orders=[o1, o2], employee_names={},
        )
        by_hull = {m["hull"]: m for m in merged}
        assert by_hull["1"]["optimized_phase"] == "Laminagem"
        assert by_hull["2"]["assigned_machine_id"] == "BANCADA-1"


# ─── Endpoint GET /v1/plan/cpo/commits/{sha}/orders ───────────────────────


class _FakeResult:
    def __init__(self, scalar=None, scalars_list=None):
        self._scalar = scalar
        self._scalars_list = scalars_list

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        rows = self._scalars_list or []

        class _S:
            def all(_self):
                return list(rows)

        return _S()


class _FakeSession:
    """Sessão mínima: devolve o commit no primeiro execute, as ordens no
    segundo, os empregados no terceiro. A ordem segue o código do endpoint."""

    def __init__(self, *, commit, orders, employees):
        self._commit = commit
        self._orders = orders
        self._employees = employees
        self._calls = 0

    async def execute(self, stmt):  # noqa: ANN001
        self._calls += 1
        if self._calls == 1:
            # CommitsService.get_by_sha / get_latest
            return _FakeResult(scalar=self._commit)
        if self._calls == 2:
            return _FakeResult(scalars_list=self._orders)
        return _FakeResult(scalars_list=self._employees)


class _FakeEmployee:
    def __init__(self, code: str, name: str):
        self.employee_code = code
        self.employee_name = name


def _commit_with(operations, kpis=None) -> ScheduleCommit:
    return ScheduleCommit(
        id=uuid4(),
        tenant_id=TENANT,
        parent_id=None,
        commit_sha256="d" * 64,
        author="test",
        message="",
        kpis=kpis or {"makespan_hours": 12.5, "setups": 4,
                      "avg_utilization": 71.0, "num_late_orders": 1},
        operations=operations,
        delta={},
        alternatives=[],
        cpo_meta={},
        trust_index=0.0,
        operations_count=len(operations),
    )


def _client(session) -> TestClient:
    app = FastAPI()
    app.include_router(cpo_router)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[require_tenant_header] = lambda: TENANT
    return TestClient(app)


class TestCommitOrdersEndpoint:
    def test_latest_returns_merged_orders_and_kpis(self):
        order = _order(legacy_id=100, phase="Laminagem")
        commit = _commit_with([_op(order_id="100", workers=["EMP-7"])])
        session = _FakeSession(
            commit=commit,
            orders=[order],
            employees=[_FakeEmployee("EMP-7", "Paulo Gomes")],
        )
        resp = _client(session).get("/v1/plan/cpo/commits/latest/orders")
        assert resp.status_code == 200
        body = resp.json()
        assert body["commit_sha256"] == "d" * 64
        assert body["kpis"]["makespan_hours"] == 12.5
        assert body["kpis"]["num_late_orders"] == 1
        assert len(body["orders"]) == 1
        item = body["orders"][0]
        assert item["hull"] == "100"
        assert item["optimized_phase"] == "Laminagem"
        assert item["assigned_employee_name"] == "Paulo Gomes"
        assert item["in_optimized_plan"] is True

    def test_unknown_sha_returns_404(self):
        session = _FakeSession(commit=None, orders=[], employees=[])
        resp = _client(session).get("/v1/plan/cpo/commits/" + "f" * 64 + "/orders")
        assert resp.status_code == 404

    def test_no_commit_for_latest_returns_404(self):
        session = _FakeSession(commit=None, orders=[], employees=[])
        resp = _client(session).get("/v1/plan/cpo/commits/latest/orders")
        assert resp.status_code == 404
