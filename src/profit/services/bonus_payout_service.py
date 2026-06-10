"""
ProdPlan ONE — Phase Bonus Payout Service (CX5)
================================================

Serves the monetary bonus (€) paid per (product × phase), sourced from
the ERP field `ProdutoFase_CoeficienteX`. Downstream callers:

  * CostService (CS01)  — adds direct labor bonus to the COGS breakdown.
  * Payroll aggregation — sums bonuses earned per worker in a period.
  * ThroughputService (CS05) — subtracts labor bonus from revenue for
    the €/day margin target.

The caller passes the list of operations already executed (worker_id,
product_id, phase_id, completed_at) and this service returns the total
€ paid.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, List, Optional, Sequence
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.profit.models.phase_bonus import PhaseBonusPayout
from src.shared.time import local_today, utc_now_naive


class BonusPayoutService:
    """Reads, writes and aggregates phase-level labor bonuses."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def get_bonus(
        self,
        product_id: UUID,
        phase_id: UUID,
        on_date: Optional[date] = None,
    ) -> Decimal:
        """Bonus € paid for this (product, phase) effective on `on_date`.

        Falls back to Decimal(0) if no row matches — caller decides
        whether to treat that as "no bonus configured yet" or as an
        error.
        """
        ref = on_date or local_today()
        stmt = (
            select(PhaseBonusPayout)
            .where(PhaseBonusPayout.tenant_id == self.tenant_id)
            .where(PhaseBonusPayout.product_id == product_id)
            .where(PhaseBonusPayout.phase_id == phase_id)
            .where(PhaseBonusPayout.valid_from <= ref)
            .where(
                or_(
                    PhaseBonusPayout.valid_to.is_(None),
                    PhaseBonusPayout.valid_to >= ref,
                )
            )
            .order_by(PhaseBonusPayout.valid_from.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return Decimal(str(row.bonus_eur)) if row else Decimal("0")

    async def calculate_order_labor_bonus(
        self,
        operations: Sequence[dict],
    ) -> Decimal:
        """Sum of bonuses for every operation of one OF.

        `operations` is a list of dicts with at least `product_id`,
        `phase_id`, optional `completed_at` (date or datetime).
        """
        total = Decimal("0")
        for op in operations:
            pid = op["product_id"]
            phid = op["phase_id"]
            ts = op.get("completed_at")
            on_date = (
                ts.date() if isinstance(ts, datetime) else (ts or local_today())
            )
            total += await self.get_bonus(pid, phid, on_date)
        return total

    async def calculate_worker_payroll_bonus(
        self,
        operations: Sequence[dict],
        worker_id: UUID,
        period_start: date,
        period_end: date,
    ) -> Decimal:
        """Sum of bonuses earned by one worker in a closed period.

        `operations` already scoped to the period by the caller; this
        method only filters by `worker_id` and looks up each bonus.
        """
        total = Decimal("0")
        for op in operations:
            if op.get("worker_id") != worker_id:
                continue
            ts = op.get("completed_at")
            on_date = ts.date() if isinstance(ts, datetime) else ts
            if on_date is None or on_date < period_start or on_date > period_end:
                continue
            total += await self.get_bonus(op["product_id"], op["phase_id"], on_date)
        return total

    async def bulk_upsert(
        self,
        rows: Iterable[dict],
    ) -> int:
        """Upsert from ERP ingest. Each row: product_id, phase_id,
        bonus_eur, valid_from, optional valid_to, source.

        Conflict key = (tenant_id, product_id, phase_id, valid_from).
        Returns number of rows processed.
        """
        payload = []
        now = utc_now_naive()
        for r in rows:
            payload.append({
                "id": uuid4(),
                "tenant_id": self.tenant_id,
                "product_id": r["product_id"],
                "phase_id": r["phase_id"],
                "bonus_eur": Decimal(str(r["bonus_eur"])),
                "currency_code": r.get("currency_code", "EUR"),
                "valid_from": r.get("valid_from") or local_today(),
                "valid_to": r.get("valid_to"),
                "source": r.get("source", "ERP_STANDARD"),
                "created_at": now,
                "updated_at": now,
            })

        if not payload:
            return 0

        stmt = pg_insert(PhaseBonusPayout.__table__).values(payload)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_phase_bonus_payout_validity",
            set_={
                "bonus_eur": stmt.excluded.bonus_eur,
                "currency_code": stmt.excluded.currency_code,
                "valid_to": stmt.excluded.valid_to,
                "source": stmt.excluded.source,
                "updated_at": now,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()
        return len(payload)
