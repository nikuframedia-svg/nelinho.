"""Sprint C 1.1 — product_pricing wire to CPO endpoint.

Before this fix the decoder was ready to compute throughput €/day but
nothing ever passed `product_price_eur` — the CEO's €30-35K/day target
could not move the GA's needle.

Covers:
* `_load_product_prices` returns `{product_id: price}` for the latest
  valid row per product (rows ordered DESC by valid_from → take first)
* Empty `product_pricing` table → empty dict (not an exception)
* Expired rows (`valid_to` in the past) are excluded
* `active=False` rows excluded
* The engine's `schedule(...)` now accepts + propagates `product_price_eur`
  kwarg to every internal `decode(...)`
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, List
from uuid import uuid4

import pytest

from src.plan.api.cpo import _load_product_prices
from tests.conftest import FakeSession


TENANT_A = uuid4()


# ---------------------------------------------------------------------------
# Fake session that returns seeded rows
# ---------------------------------------------------------------------------


def _session_with_rows(rows: List[tuple]) -> FakeSession:
    """Q.68.3.3 — Canonical FakeSession with ``rows`` queued for one ``execute().all()`` call."""
    session = FakeSession()
    session.queue_scalars(list(rows))
    return session


# ---------------------------------------------------------------------------
# _load_product_prices
# ---------------------------------------------------------------------------


def test_load_product_prices_empty_table_returns_empty_dict():
    session = _session_with_rows([])
    prices = asyncio.run(_load_product_prices(session, TENANT_A))
    assert prices == {}


def test_load_product_prices_picks_first_row_per_product():
    """The query already orders DESC by valid_from — the helper keeps the
    first row it sees per product (i.e. the latest-valid)."""
    product_1 = uuid4()
    product_2 = uuid4()
    today = date.today()
    rows = [
        # Product 1 — two rows; the newer (2025) must win.
        (product_1, Decimal("2400.00"), today - timedelta(days=30)),
        (product_1, Decimal("2000.00"), today - timedelta(days=365)),
        # Product 2 — single row.
        (product_2, Decimal("1800.00"), today),
    ]
    session = _session_with_rows(rows)
    prices = asyncio.run(_load_product_prices(session, TENANT_A))
    assert prices[str(product_1)] == 2400.0  # latest
    assert prices[str(product_2)] == 1800.0


def test_load_product_prices_swallows_db_errors():
    """If the pricing table is absent / schema drifts, the CPO endpoint
    must keep working with throughput=0 rather than 500."""

    class _BoomSession:
        async def execute(self, *_a, **_kw):
            raise RuntimeError("profit.product_pricing does not exist")

    prices = asyncio.run(_load_product_prices(_BoomSession(), TENANT_A))
    assert prices == {}


# ---------------------------------------------------------------------------
# engine.schedule accepts + propagates product_price_eur
# ---------------------------------------------------------------------------


def test_engine_schedule_signature_accepts_product_price_eur():
    """Type-only check: the Sprint C wire added `product_price_eur` as an
    optional kwarg. Regression guard — any future refactor that drops
    the kwarg breaks the CPO → throughput pipeline silently.
    """
    import inspect

    from src.plan.cpo.engine import CPOv4Engine

    sig = inspect.signature(CPOv4Engine.schedule)
    assert "product_price_eur" in sig.parameters
    param = sig.parameters["product_price_eur"]
    assert param.kind == inspect.Parameter.KEYWORD_ONLY
    assert param.default is None


def test_decoder_signature_still_accepts_product_price_eur():
    """Decoder-side symmetry — the kwarg must exist so engine.schedule
    can forward it.
    """
    import inspect

    from src.plan.cpo.decoder import decode

    sig = inspect.signature(decode)
    assert "product_price_eur" in sig.parameters


# ---------------------------------------------------------------------------
# End-to-end smoke: decoder turns prices into throughput
# ---------------------------------------------------------------------------


def test_decode_produces_nonzero_throughput_when_prices_supplied():
    from src.plan.cpo.chromosome import Chromosome
    from src.plan.cpo.decoder import decode
    from src.plan.cpo.state import FactoryState
    from src.plan.engines.scheduling_adapter import (
        SchedulingMachine,
        SchedulingOperation,
    )

    ref = datetime(2026, 4, 22, 8, 0)
    op = SchedulingOperation(
        operation_id="O_FINAL",
        order_id="OF1",
        product_id="P1",
        sequence=1,
        operation_code="O_FINAL",
        duration_minutes=60,
        machine_id="M1",
        phase_id="PINTURA_ACABAMENTO",
    )
    state = FactoryState(tenant_id=uuid4())

    result = decode(
        Chromosome(permutation=[0]),
        [op],
        [SchedulingMachine(machine_id="M1", name="M1")],
        state,
        horizon_start=ref,
        horizon_end=ref + timedelta(days=2),
        product_price_eur={"P1": 2400.0},
    )
    assert result["throughput_eur_total"] == 2400.0
    assert result["throughput_eur_day"] == 1200.0  # 2400 / 2 horizon days


def test_decode_zero_throughput_when_prices_empty():
    """Backwards-compat path — legacy callers don't pass the kwarg and
    the output must still be a clean 0, not a crash or NaN.
    """
    from src.plan.cpo.chromosome import Chromosome
    from src.plan.cpo.decoder import decode
    from src.plan.cpo.state import FactoryState
    from src.plan.engines.scheduling_adapter import (
        SchedulingMachine,
        SchedulingOperation,
    )

    ref = datetime(2026, 4, 22, 8, 0)
    op = SchedulingOperation(
        operation_id="O1",
        order_id="OF1",
        product_id="P1",
        sequence=1,
        operation_code="O1",
        duration_minutes=60,
        machine_id="M1",
        phase_id="PHASE_A",
    )
    result = decode(
        Chromosome(permutation=[0]),
        [op],
        [SchedulingMachine(machine_id="M1", name="M1")],
        FactoryState(tenant_id=uuid4()),
        horizon_start=ref,
        horizon_end=ref + timedelta(days=1),
    )
    assert result["throughput_eur_day"] == 0.0
    assert result["throughput_eur_total"] == 0.0
