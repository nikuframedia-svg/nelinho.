"""Q.42.A — alimentar os contadores de uso de molde com `MOLDES_MOV`.

O health model dos moldes já está completo; faltava-lhe uso REAL. Estes
testes cobrem:

* `aggregate_movement_cycles` — função pura que conta os movimentos da
  ERP por molde em (total, since_reset);
* `MoldService.sync_usage_from_erp_movements` — liga o reader read-only
  `list_mold_movements` aos `MoldUsageCounter`.

NOTA: o threshold de ciclos de manutenção continua a 0 (desactivado, CEO
2026-04-26) — esta fatia só alimenta os contadores, não muda a política.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, List, Optional
from uuid import UUID, uuid4

import pytest

from src.plan.models.mold import Mold, MoldUsageCounter
from src.plan.services.mold_service import (
    MoldService,
    MovementCycleCount,
    aggregate_movement_cycles,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _mov(mold_id: int, moved_at: Optional[datetime]) -> SimpleNamespace:
    """Imita um `MoldMovementRow` (só os campos que o agregador lê)."""
    return SimpleNamespace(mold_id=mold_id, moved_at=moved_at)


def _dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


# ─── função pura: aggregate_movement_cycles ───────────────────────────────


def test_aggregate_counts_total_per_mold():
    """Cada movimento é um ciclo de uso; total = nº de movimentos."""
    movements = [
        _mov(7, _dt(2026, 1, 5)),
        _mov(7, _dt(2026, 2, 5)),
        _mov(9, _dt(2026, 1, 8)),
    ]
    counts = aggregate_movement_cycles(movements, reset_at_by_mold={})
    assert counts[7].total == 2
    assert counts[9].total == 1


def test_aggregate_without_reset_since_reset_equals_total():
    """Molde nunca mantido (reset_at None) → since_reset == total."""
    movements = [_mov(7, _dt(2026, 1, 5)), _mov(7, _dt(2026, 3, 5))]
    counts = aggregate_movement_cycles(movements, reset_at_by_mold={7: None})
    assert counts[7].total == 2
    assert counts[7].since_reset == 2


def test_aggregate_reset_splits_since_reset_from_total():
    """Só movimentos depois da última manutenção contam para since_reset."""
    movements = [
        _mov(7, _dt(2026, 1, 5)),   # antes do reset
        _mov(7, _dt(2026, 2, 5)),   # antes do reset
        _mov(7, _dt(2026, 4, 5)),   # depois do reset
    ]
    counts = aggregate_movement_cycles(
        movements, reset_at_by_mold={7: _dt(2026, 3, 1)},
    )
    assert counts[7].total == 3
    assert counts[7].since_reset == 1


def test_aggregate_undated_movement_counts_total_not_since_reset():
    """Movimento sem data conta para total mas nunca para since_reset."""
    movements = [_mov(7, None), _mov(7, _dt(2026, 4, 5))]
    counts = aggregate_movement_cycles(
        movements, reset_at_by_mold={7: None},
    )
    assert counts[7].total == 2
    assert counts[7].since_reset == 1  # só o datado


def test_aggregate_naive_timestamps_treated_as_utc():
    """`moved_at`/`reset_at` sem tzinfo são tratados como UTC, sem crash."""
    movements = [_mov(7, datetime(2026, 4, 5))]  # naive
    counts = aggregate_movement_cycles(
        movements, reset_at_by_mold={7: datetime(2026, 3, 1)},  # naive
    )
    assert counts[7].since_reset == 1


def test_aggregate_skips_movement_without_mold_id():
    counts = aggregate_movement_cycles(
        [_mov(None, _dt(2026, 1, 5))], reset_at_by_mold={},  # type: ignore[arg-type]
    )
    assert counts == {}


# ─── MoldService.sync_usage_from_erp_movements ────────────────────────────


class _FakeSession:
    """AsyncSession mínima: serve molds e counters semeados, regista adds."""

    def __init__(
        self,
        molds: List[Mold],
        counters: List[MoldUsageCounter],
    ) -> None:
        self._molds = list(molds)
        self._counters = list(counters)
        self.added: list[Any] = []
        self.flushed = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if isinstance(obj, MoldUsageCounter):
            self._counters.append(obj)

    async def flush(self) -> None:
        self.flushed += 1

    async def execute(self, stmt):  # noqa: ANN001 — test stub
        # O modelo-alvo do SELECT distingue as duas queries do método.
        entity = stmt.column_descriptions[0]["entity"]
        if entity is Mold:
            rows: list[Any] = list(self._molds)
        else:
            rows = list(self._counters)

        class _Scalars:
            def __init__(self, items: list[Any]) -> None:
                self._items = items

            def all(self) -> list[Any]:
                return list(self._items)

        class _Result:
            def __init__(self, items: list[Any]) -> None:
                self._items = items

            def scalars(self) -> _Scalars:
                return _Scalars(self._items)

            def scalar_one_or_none(self) -> Any:
                return self._items[0] if self._items else None

        return _Result(rows)


def _mold(mold_code: str) -> Mold:
    return Mold(
        id=uuid4(),
        tenant_id=TENANT,
        mold_code=mold_code,
        model_id="",
        pocket_count=1,
        active=True,
        depreciated=False,
    )


def _counter(mold_id: UUID, *, reset_at: Optional[datetime] = None) -> MoldUsageCounter:
    return MoldUsageCounter(
        id=uuid4(),
        tenant_id=TENANT,
        mold_id=mold_id,
        shot_count_total=0,
        cycles_since_last_maint=0,
        last_updated_at=datetime.now(timezone.utc),
        last_reset_at=reset_at,
    )


@pytest.mark.asyncio
async def test_sync_writes_real_counts_onto_existing_counter(monkeypatch):
    """Q.42.A — o contador existente passa a reflectir o uso real."""
    mold = _mold("7")  # ERP MLD_ID 7
    counter = _counter(mold.id)
    session = _FakeSession([mold], [counter])

    async def _fake_list_mold_movements(limit: int = 50_000):
        return [_mov(7, _dt(2026, 1, 5)), _mov(7, _dt(2026, 2, 5))]

    monkeypatch.setattr(
        "src.adapters.nelo.services.list_mold_movements",
        _fake_list_mold_movements,
    )

    svc = MoldService(session, TENANT)  # type: ignore[arg-type]
    summary = await svc.sync_usage_from_erp_movements()

    assert summary == {
        "movements_read": 2,
        "molds_matched": 1,
        "counters_updated": 1,
    }
    assert counter.shot_count_total == 2
    assert counter.cycles_since_last_maint == 2


@pytest.mark.asyncio
async def test_sync_respects_last_reset_for_cycles_since_maint(monkeypatch):
    """Movimentos antes da última manutenção não contam para o ciclo."""
    mold = _mold("7")
    counter = _counter(mold.id, reset_at=_dt(2026, 3, 1))
    session = _FakeSession([mold], [counter])

    async def _fake_list_mold_movements(limit: int = 50_000):
        return [
            _mov(7, _dt(2026, 1, 5)),  # antes do reset
            _mov(7, _dt(2026, 4, 5)),  # depois do reset
        ]

    monkeypatch.setattr(
        "src.adapters.nelo.services.list_mold_movements",
        _fake_list_mold_movements,
    )

    svc = MoldService(session, TENANT)  # type: ignore[arg-type]
    await svc.sync_usage_from_erp_movements()

    assert counter.shot_count_total == 2
    assert counter.cycles_since_last_maint == 1


@pytest.mark.asyncio
async def test_sync_skips_excel_molds_with_non_int_code(monkeypatch):
    """Moldes só-Excel (code ~70000+ não-numérico aqui) não têm movimentos
    ERP — não rebentam e não são contados."""
    excel_mold = _mold("EXCEL-ABC")  # business key não-int
    session = _FakeSession([excel_mold], [_counter(excel_mold.id)])

    async def _fake_list_mold_movements(limit: int = 50_000):
        return [_mov(7, _dt(2026, 1, 5))]

    monkeypatch.setattr(
        "src.adapters.nelo.services.list_mold_movements",
        _fake_list_mold_movements,
    )

    svc = MoldService(session, TENANT)  # type: ignore[arg-type]
    summary = await svc.sync_usage_from_erp_movements()

    assert summary["molds_matched"] == 0
    assert summary["counters_updated"] == 0


@pytest.mark.asyncio
async def test_sync_creates_counter_when_missing(monkeypatch):
    """Molde sem contador (ex: criado fora do create_mold) ganha um."""
    mold = _mold("9")
    session = _FakeSession([mold], [])  # sem contador

    async def _fake_list_mold_movements(limit: int = 50_000):
        return [_mov(9, _dt(2026, 1, 5)), _mov(9, _dt(2026, 1, 6)), _mov(9, _dt(2026, 1, 7))]

    monkeypatch.setattr(
        "src.adapters.nelo.services.list_mold_movements",
        _fake_list_mold_movements,
    )

    svc = MoldService(session, TENANT)  # type: ignore[arg-type]
    summary = await svc.sync_usage_from_erp_movements()

    assert summary["counters_updated"] == 1
    created = [o for o in session.added if isinstance(o, MoldUsageCounter)]
    assert len(created) == 1
    assert created[0].shot_count_total == 3
    assert created[0].cycles_since_last_maint == 3


def test_movement_cycle_count_defaults_zero():
    c = MovementCycleCount()
    assert c.total == 0
    assert c.since_reset == 0
