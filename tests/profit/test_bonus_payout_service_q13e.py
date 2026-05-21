"""Sprint Q.13.E E.4 — `BonusPayoutService` test coverage (CX5).

Plan v4 §54 H1: ProdutoFase_CoeficienteX is a monetary bonus (€), NOT a
time coefficient. The fix is in place since Q.7-Q.8 but the service
that consumes the bonus had ZERO tests — it was production-grade dead
code as far as the regression suite was concerned.

These five scenarios cover:
  1. Single op, single bonus row that's currently valid.
  2. Bonus row whose validity has expired (valid_to < ref) → 0.
  3. Two overlapping rows; the most-recent-valid_from wins (versioning).
  4. Multi-op `calculate_order_labor_bonus` sums correctly.
  5. Worker-payroll filter: only this worker's ops, only inside period.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, List
from uuid import UUID, uuid4

import pytest

from src.profit.services.bonus_payout_service import BonusPayoutService
from tests.conftest import FakeSession


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _PhaseBonusRow:
    """Minimal `PhaseBonusPayout` stand-in — only the columns the
    service actually reads from the row need to exist."""

    def __init__(
        self,
        *,
        product_id: UUID,
        phase_id: UUID,
        bonus_eur: Decimal,
        valid_from: date,
        valid_to: date | None = None,
    ) -> None:
        self.tenant_id = _TENANT
        self.product_id = product_id
        self.phase_id = phase_id
        self.bonus_eur = bonus_eur
        self.valid_from = valid_from
        self.valid_to = valid_to


# Q.68.3.4 — _FakeSession era um stub de 50L com whereclause walking
# para extrair (product_id, phase_id, ref) e ordenação descendente por
# valid_from. Mantemos o helper SQL inline mas usamos o canónico como
# base — só o filtro é específico deste teste.
class _FakeSession(FakeSession):
    """Q.68.3.4 — subclasse local com WHERE-clause introspection.

    BonusPayoutService.get_bonus emite SELECT(PhaseBonusPayout) WHERE
    product_id == :p AND phase_id == :ph AND valid_from <= :ref AND
    (valid_to is None OR valid_to >= :ref) ORDER BY valid_from DESC
    LIMIT 1. Caminhamos a árvore de cláusulas em Python para recuperar
    (p, ph, ref) e devolvemos a row mais recente que casa.
    """

    def __init__(self, rows: List[_PhaseBonusRow]) -> None:
        super().__init__()
        self._rows = list(rows)

    async def execute(self, stmt):  # type: ignore[override]
        # Walk the WHERE clauses to recover (product_id, phase_id, ref).
        wanted_product = None
        wanted_phase = None
        ref = None
        try:
            clauses = list(stmt.whereclause.clauses) if stmt.whereclause is not None else []
        except AttributeError:
            clauses = []

        for clause in clauses:
            try:
                left_name = clause.left.name
            except AttributeError:
                continue
            try:
                right_value = clause.right.value
            except AttributeError:
                right_value = None
            if left_name == "product_id":
                wanted_product = right_value
            elif left_name == "phase_id":
                wanted_phase = right_value
            elif left_name == "valid_from":
                ref = right_value
            elif left_name == "valid_to":
                ref = ref or right_value

        ref = ref or date.today()
        matches = [
            r for r in self._rows
            if r.product_id == wanted_product
            and r.phase_id == wanted_phase
            and r.valid_from <= ref
            and (r.valid_to is None or r.valid_to >= ref)
        ]
        matches.sort(key=lambda r: r.valid_from, reverse=True)
        self.queue_scalar(matches[0] if matches else None)
        return await super().execute(stmt)


# ───────────────────────────────────────────────────────────────────────────
# Tests
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_bonus_returns_active_row():
    pid = uuid4()
    phid = uuid4()
    row = _PhaseBonusRow(
        product_id=pid, phase_id=phid,
        bonus_eur=Decimal("4.20"),
        valid_from=date(2026, 1, 1),
    )
    svc = BonusPayoutService(_FakeSession([row]), _TENANT)  # type: ignore[arg-type]

    bonus = await svc.get_bonus(pid, phid, on_date=date(2026, 5, 3))
    assert bonus == Decimal("4.20")


@pytest.mark.asyncio
async def test_get_bonus_returns_zero_when_validity_expired():
    pid = uuid4()
    phid = uuid4()
    expired = _PhaseBonusRow(
        product_id=pid, phase_id=phid,
        bonus_eur=Decimal("9.99"),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),  # expired before Q.13.E ref date
    )
    svc = BonusPayoutService(_FakeSession([expired]), _TENANT)  # type: ignore[arg-type]

    bonus = await svc.get_bonus(pid, phid, on_date=date(2026, 5, 3))
    assert bonus == Decimal("0")


@pytest.mark.asyncio
async def test_get_bonus_picks_most_recent_valid_from_when_multiple_active():
    """ERP versioning: when both rows are currently valid, the one
    with the most recent valid_from wins — that's the active bonus."""
    pid = uuid4()
    phid = uuid4()
    older = _PhaseBonusRow(
        product_id=pid, phase_id=phid,
        bonus_eur=Decimal("3.00"),
        valid_from=date(2025, 1, 1),
    )
    newer = _PhaseBonusRow(
        product_id=pid, phase_id=phid,
        bonus_eur=Decimal("4.50"),
        valid_from=date(2026, 1, 1),
    )
    svc = BonusPayoutService(_FakeSession([older, newer]), _TENANT)  # type: ignore[arg-type]

    bonus = await svc.get_bonus(pid, phid, on_date=date(2026, 5, 3))
    assert bonus == Decimal("4.50")


@pytest.mark.asyncio
async def test_calculate_order_labor_bonus_sums_across_ops():
    pid_a = uuid4()
    pid_b = uuid4()
    ph_lam = uuid4()
    ph_pin = uuid4()
    rows = [
        _PhaseBonusRow(product_id=pid_a, phase_id=ph_lam,
                       bonus_eur=Decimal("4.20"),
                       valid_from=date(2026, 1, 1)),
        _PhaseBonusRow(product_id=pid_a, phase_id=ph_pin,
                       bonus_eur=Decimal("1.50"),
                       valid_from=date(2026, 1, 1)),
        _PhaseBonusRow(product_id=pid_b, phase_id=ph_lam,
                       bonus_eur=Decimal("5.10"),
                       valid_from=date(2026, 1, 1)),
    ]
    svc = BonusPayoutService(_FakeSession(rows), _TENANT)  # type: ignore[arg-type]

    operations = [
        {"product_id": pid_a, "phase_id": ph_lam,
         "completed_at": date(2026, 5, 3)},
        {"product_id": pid_a, "phase_id": ph_pin,
         "completed_at": date(2026, 5, 3)},
        {"product_id": pid_b, "phase_id": ph_lam,
         "completed_at": date(2026, 5, 3)},
    ]
    total = await svc.calculate_order_labor_bonus(operations)
    assert total == Decimal("10.80")  # 4.20 + 1.50 + 5.10


@pytest.mark.asyncio
async def test_worker_payroll_filters_by_worker_and_period():
    """Multi-worker, multi-month operations: only this worker's ops
    inside the closed period must contribute."""
    pid = uuid4()
    phid = uuid4()
    worker_a = uuid4()
    worker_b = uuid4()
    rows = [
        _PhaseBonusRow(product_id=pid, phase_id=phid,
                       bonus_eur=Decimal("2.00"),
                       valid_from=date(2026, 1, 1)),
    ]
    svc = BonusPayoutService(_FakeSession(rows), _TENANT)  # type: ignore[arg-type]

    operations = [
        {"product_id": pid, "phase_id": phid, "worker_id": worker_a,
         "completed_at": date(2026, 5, 5)},   # in-period worker A
        {"product_id": pid, "phase_id": phid, "worker_id": worker_a,
         "completed_at": date(2026, 5, 28)},  # in-period worker A
        {"product_id": pid, "phase_id": phid, "worker_id": worker_b,
         "completed_at": date(2026, 5, 5)},   # OTHER worker — skip
        {"product_id": pid, "phase_id": phid, "worker_id": worker_a,
         "completed_at": date(2026, 4, 30)},  # before period — skip
        {"product_id": pid, "phase_id": phid, "worker_id": worker_a,
         "completed_at": None},               # missing date — skip
    ]
    total = await svc.calculate_worker_payroll_bonus(
        operations,
        worker_id=worker_a,
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
    )
    # Only worker_a + in-period rows: 2× 2.00 EUR
    assert total == Decimal("4.00")
