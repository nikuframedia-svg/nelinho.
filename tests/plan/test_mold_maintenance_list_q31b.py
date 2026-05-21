"""Q.31.B — GET /v1/plan/molds/{id}/maintenance.

Lista os eventos de manutenção de um molde (planeado / em curso / feito)
para a UF de manutenção poder mostrar o estado e oferecer iniciar/concluir.
"""

from __future__ import annotations

from datetime import date
from typing import Any, List
from uuid import UUID, uuid4

import pytest

from src.plan.api.mold import list_mold_maintenance
from src.plan.models.mold import MoldMaintenanceEvent
from tests.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")


# Q.68.3.4 — _FakeSession previously held a 15-line execute() that
# wrapped a fixed rows list. Replaced by the canónico ``FakeSession``
# with a single ``queue_scalars(events)`` call per test.
def _session_with(events: List[MoldMaintenanceEvent]) -> FakeSession:
    session = FakeSession()
    session.queue_scalars(events)
    return session


def _event(mold_id: UUID, **kw: Any) -> MoldMaintenanceEvent:
    return MoldMaintenanceEvent(
        id=uuid4(),
        tenant_id=TENANT,
        mold_id=mold_id,
        maintenance_type=kw.get("maintenance_type", "preventive"),
        planned_date=kw.get("planned_date", date(2026, 5, 20)),
        status=kw.get("status", "planned"),
    )


@pytest.mark.asyncio
async def test_list_maintenance_returns_event_dicts():
    mid = uuid4()
    session = _session_with([
        _event(mid, status="planned"),
        _event(mid, status="completed", maintenance_type="corrective"),
    ])
    out = await list_mold_maintenance(
        mold_id=mid, tenant_id=TENANT, session=session,  # type: ignore[arg-type]
    )
    assert isinstance(out, list)
    assert len(out) == 2
    assert {e["status"] for e in out} == {"planned", "completed"}
    assert out[0]["mold_id"] == str(mid)
    assert "maintenance_type" in out[0]


@pytest.mark.asyncio
async def test_list_maintenance_empty_is_empty_list():
    out = await list_mold_maintenance(
        mold_id=uuid4(), tenant_id=TENANT, session=_session_with([]),  # type: ignore[arg-type]
    )
    assert out == []
