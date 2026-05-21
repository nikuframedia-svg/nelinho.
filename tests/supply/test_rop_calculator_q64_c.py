"""Q.64.C — Tests for `recompute_rop_configs`.

Service le `MaterialMaster` (active=True) + soma `qty_out` no
`InventoryLedgerEntry` nos ultimos N dias, e faz upsert em `ROPConfig`.

Aqui mockamos `session.execute` em call-order (modelo do Q.62.C.1
`test_team_defect_rate_q62_c.py`): cada master gera 2 queries (sum_qty_out
+ existing ROPConfig); a primeira execucao geral lista masters.
"""

from __future__ import annotations

import math
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from src.supply.models import MaterialMaster, ROPConfig
from src.supply.services.rop_calculator import (
    _Z_SCORE_BY_SERVICE_LEVEL,
    _z_score_for,
    recompute_rop_configs,
)


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ---------------------------------------------------------------------------
# Helpers — call-order mock para session.execute.
# ---------------------------------------------------------------------------


def _result_with_scalars(items):
    """Mock de Result com `.scalars().all() -> items`."""
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=list(items))
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars)
    return result


def _result_with_scalar(value):
    """Mock de Result com `.scalar() -> value` E `.scalar_one_or_none() -> value`."""
    result = MagicMock()
    result.scalar = MagicMock(return_value=value)
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


def _make_session(execute_returns: list):
    """Cria AsyncMock session cujo `.execute()` devolve a sequencia dada."""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=execute_returns)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _material(sku_id: str, *, lead_time_days: int = 7) -> MaterialMaster:
    return MaterialMaster(
        id=uuid4(),
        tenant_id=_TENANT,
        sku_id=sku_id,
        name=f"Mat {sku_id}",
        unit_of_measure="UN",
        lead_time_days=lead_time_days,
        min_stock_qty=Decimal("0"),
        reorder_qty=Decimal("0"),
        safety_stock_days=0,
        critical_flag=False,
        active=True,
    )


def _rop_row(sku_id: str) -> ROPConfig:
    """Linha ROP existente para o caso "update path"."""
    return ROPConfig(
        id=uuid4(),
        tenant_id=_TENANT,
        sku_id=sku_id,
        avg_daily_demand=Decimal("1"),
        lead_time_days=1,
        lead_time_std_dev=0.0,
        service_level=0.95,
        rop=Decimal("1"),
        base_rop=Decimal("1"),
        safety_stock=Decimal("0"),
        z_score=1.645,
    )


# ---------------------------------------------------------------------------
# Z-score table
# ---------------------------------------------------------------------------


def test_z_score_for_default_service_level():
    """0.95 default → 1.645 da tabela hardcoded."""
    assert _z_score_for(0.95) == 1.645


def test_z_score_for_all_known_levels():
    """Cada chave da tabela devolve o seu valor exacto."""
    for level, z in _Z_SCORE_BY_SERVICE_LEVEL.items():
        assert _z_score_for(level) == z


def test_z_score_for_falls_back_to_closest():
    """0.96 cai no mais proximo entre 0.95 e 0.97. 0.95 esta mais perto."""
    assert _z_score_for(0.96) == 1.645  # |0.95-0.96|=0.01 < |0.97-0.96|=0.01 mas min escolhe primeiro
    # 0.98 cai em 0.97 (|0.97-0.98|=0.01 < |0.99-0.98|=0.01 — tie quebra pelo dict order)
    assert _z_score_for(0.98) in {1.881, 2.326}


# ---------------------------------------------------------------------------
# recompute_rop_configs — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recompute_empty_master_returns_zero():
    """Zero SKUs activos → tudo a zero, nada se adiciona."""
    session = _make_session([_result_with_scalars([])])  # masters query

    result = await recompute_rop_configs(session, _TENANT)

    assert result == {
        "rows_processed": 0,
        "rows_upserted": 0,
        "rows_skipped": 0,
    }
    session.add.assert_not_called()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_recompute_skips_skus_with_no_demand():
    """qty_out=0 → SKU saltado, nem se procura ROP existente."""
    master = _material("SKU-DRY")
    session = _make_session([
        _result_with_scalars([master]),  # masters
        _result_with_scalar(0),          # sum qty_out = 0
        # Nao deve haver mais queries — skip cedo.
    ])

    result = await recompute_rop_configs(
        session, _TENANT, lookback_days=90,
    )

    assert result["rows_processed"] == 1
    assert result["rows_upserted"] == 0
    assert result["rows_skipped"] == 1
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_recompute_creates_rop_for_active_sku():
    """Demanda real → upsert cria row, valores > 0."""
    master = _material("SKU-WET", lead_time_days=10)
    # 900 unidades em 90d = 10/dia, base_rop = 10*10 = 100.
    session = _make_session([
        _result_with_scalars([master]),  # masters
        _result_with_scalar(900),         # sum qty_out = 900
        _result_with_scalar(None),        # existing ROPConfig = None
    ])

    result = await recompute_rop_configs(
        session, _TENANT, lookback_days=90,
    )

    assert result["rows_processed"] == 1
    assert result["rows_upserted"] == 1
    assert result["rows_skipped"] == 0
    session.add.assert_called_once()

    # Inspecciona a row criada.
    added = session.add.call_args.args[0]
    assert isinstance(added, ROPConfig)
    assert added.sku_id == "SKU-WET"
    assert added.tenant_id == _TENANT
    assert added.lead_time_days == 10
    assert added.service_level == 0.95
    assert added.z_score == 1.645
    assert added.avg_daily_demand == Decimal("10")
    assert added.base_rop == Decimal("100")
    assert added.rop > added.base_rop  # safety > 0


@pytest.mark.asyncio
async def test_recompute_updates_existing_rop_idempotent():
    """Segunda call → update da row existente, NAO duplicate."""
    master = _material("SKU-IDEMP")
    existing = _rop_row("SKU-IDEMP")
    session = _make_session([
        _result_with_scalars([master]),
        _result_with_scalar(450),         # 450/90 = 5/dia
        _result_with_scalar(existing),    # ROPConfig existente
    ])

    result = await recompute_rop_configs(session, _TENANT)

    assert result["rows_upserted"] == 1
    # NAO foi adicionada nova row — apenas mutacao in-place.
    session.add.assert_not_called()
    # Existing row foi mutada.
    assert existing.avg_daily_demand == Decimal("5")
    assert existing.lead_time_days == 7
    assert existing.base_rop == Decimal("35")  # 5 * 7
    assert existing.rop > existing.base_rop


# ---------------------------------------------------------------------------
# Formula correctness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rop_formula_base_plus_safety_stock():
    """base_rop = demand × lead_time;
    safety = z × sqrt(lead) × demand × variability;
    rop = base + safety.
    """
    master = _material("SKU-MATH", lead_time_days=16)  # sqrt(16) = 4 exacto
    # 900 / 90 = 10/dia.
    session = _make_session([
        _result_with_scalars([master]),
        _result_with_scalar(900),
        _result_with_scalar(None),
    ])

    await recompute_rop_configs(
        session, _TENANT,
        lookback_days=90,
        service_level=0.95,
        variability_factor=0.3,
    )

    added = session.add.call_args.args[0]
    # Manual: avg_daily=10, lead=16, sqrt(16)=4, z=1.645, var=0.3
    # base = 10 * 16 = 160
    # safety = 1.645 * 4 * 10 * 0.3 = 19.74
    # rop = 179.74
    assert added.base_rop == Decimal("160")
    expected_safety = Decimal("1.645") * Decimal("4") * Decimal("10") * Decimal("0.3")
    assert added.safety_stock == expected_safety
    assert added.rop == added.base_rop + added.safety_stock
    # lead_time_std_dev = sqrt(16) * 0.3 = 1.2.
    assert math.isclose(added.lead_time_std_dev, 1.2, abs_tol=1e-9)


@pytest.mark.asyncio
async def test_recompute_lookback_window_changes_demand():
    """lookback=30d → mesma soma dividida por 30, nao por 90."""
    master = _material("SKU-WINDOW", lead_time_days=5)
    # 600 unidades em 30d = 20/dia.
    session = _make_session([
        _result_with_scalars([master]),
        _result_with_scalar(600),
        _result_with_scalar(None),
    ])

    await recompute_rop_configs(
        session, _TENANT,
        lookback_days=30,
    )

    added = session.add.call_args.args[0]
    assert added.avg_daily_demand == Decimal("20")
    assert added.base_rop == Decimal("100")  # 20 * 5


@pytest.mark.asyncio
async def test_recompute_higher_service_level_higher_z_score():
    """0.99 → z=2.326 > 0.95 → z=1.645 ; safety maior."""
    master = _material("SKU-SL", lead_time_days=9)  # sqrt=3
    session_a = _make_session([
        _result_with_scalars([master]),
        _result_with_scalar(900),  # 10/dia
        _result_with_scalar(None),
    ])
    session_b = _make_session([
        _result_with_scalars([master]),
        _result_with_scalar(900),
        _result_with_scalar(None),
    ])

    await recompute_rop_configs(
        session_a, _TENANT, service_level=0.95,
    )
    await recompute_rop_configs(
        session_b, _TENANT, service_level=0.99,
    )

    a = session_a.add.call_args.args[0]
    b = session_b.add.call_args.args[0]
    assert b.z_score > a.z_score
    assert b.safety_stock > a.safety_stock
    assert b.rop > a.rop


@pytest.mark.asyncio
async def test_recompute_lead_time_falsy_defaults_to_seven():
    """lead_time_days=0 (falsy) ou None → fallback 7d.

    Spec: `master.lead_time_days or 7` em `recompute_rop_configs`. O `max(.., 1)`
    e um floor contra negativos. SKUs sem lead_time configurado usam 7d (default
    razoavel para forwecaster nao explodir).
    """
    master = _material("SKU-FLOOR", lead_time_days=0)
    session = _make_session([
        _result_with_scalars([master]),
        _result_with_scalar(900),  # 10/dia
        _result_with_scalar(None),
    ])

    await recompute_rop_configs(session, _TENANT)

    added = session.add.call_args.args[0]
    assert added.lead_time_days == 7
    assert added.base_rop == Decimal("70")  # 10/dia * 7d
