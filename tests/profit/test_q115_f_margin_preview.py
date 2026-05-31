"""Q.115.F — MarginPreview endpoint + service tests.

6 cenários:
 1. Happy path: 50 ops + DurationModel activo + target definido → confidence=low (sample<100)
 2. Commit não existe → ValueError("commit_not_found")
 3. Sem target definido → baseline_margin_eur=None, delta_eur=None, predicted populado
 4. Sem DurationModel activo → fallback p50, confidence=low
 5. Sample >= 100 → confidence=medium (sem fallback)
 6. 50 OFs demo_orders style → confidence=low, predicted_margin_eur consistente
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, List, Optional
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from src.profit.services.margin_preview import (
    MarginPreview,
    _confidence,
    compute_margin_preview,
)
from tests.conftest import TEST_TENANT_ID

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TENANT = TEST_TENANT_ID


def _make_op(
    *,
    product_id: Optional[str] = None,
    phase_id: Optional[str] = None,
    duration_h: float = 2.0,
    modelo_id: str = "M01",
) -> dict:
    return {
        "operation_id": str(uuid4()),
        "product_id": product_id or str(uuid4()),
        "phase_id": phase_id or str(uuid4()),
        "duration_h": duration_h,
        "modelo_id": modelo_id,
        "team_size": 2,
        "mold_pocket_count": 1,
        "is_rework": 0,
        "queue_depth": 5,
    }


def _make_commit(ops: list, commit_id: Optional[UUID] = None) -> SimpleNamespace:
    cid = commit_id or uuid4()
    c = SimpleNamespace()
    c.id = cid
    c.tenant_id = _TENANT
    c.commit_sha256 = "abc1234" + "0" * 57
    c.operations = ops
    return c


def _make_bonus_row(*, bonus_eur: Decimal = Decimal("5.50")) -> SimpleNamespace:
    r = SimpleNamespace()
    r.bonus_eur = bonus_eur
    r.valid_to = None
    return r


def _make_target(*, target_eur: float = 35000.0) -> SimpleNamespace:
    t = SimpleNamespace()
    t.target_eur = target_eur
    t.effective_from = date.today()
    return t


def _make_template_phase(p50_h: float) -> float:
    return p50_h


class _FakeSession:
    """Session stub que devolve o que lhe for configurado via queue_scalar/scalars."""

    def __init__(self) -> None:
        self._scalar_queue: list = []
        self._scalars_queue: list = []
        self._get_result: Any = None

    def set_get(self, obj: Any) -> None:
        self._get_result = obj

    def queue_scalar(self, v: Any) -> None:
        self._scalar_queue.append(v)

    def queue_scalars(self, vs: list) -> None:
        self._scalars_queue.append(list(vs))

    async def get(self, model_cls: Any, pk: Any) -> Any:
        return self._get_result

    async def execute(self, stmt: Any) -> "_FR":
        scalar = self._scalar_queue.pop(0) if self._scalar_queue else None
        scalars = self._scalars_queue.pop(0) if self._scalars_queue else []
        return _FR(scalar, scalars)


class _FR:
    def __init__(self, scalar: Any, scalars: list) -> None:
        self._s = scalar
        self._ss = scalars

    def scalar_one_or_none(self) -> Any:
        return self._s

    def scalars(self) -> "_FS":
        return _FS(self._ss)

    def all(self) -> list:
        return list(self._ss)


class _FS:
    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return list(self._items)


def _make_duration_model(p50_h: float = 1.5) -> Any:
    """Stub DurationModel que devolve p50 fixo."""
    m = MagicMock()
    m.predict.return_value = {"p50_hours": p50_h, "p90_hours": p50_h + 0.5}
    return m


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_50_ops_confidence_low():
    """50 operações + DurationModel activo + target → confidence=low (sample<100)."""
    ops = [_make_op() for _ in range(50)]
    commit = _make_commit(ops)
    session = _FakeSession()
    session.set_get(commit)

    # Por cada operação: 1 scalar para bonus + 0 para template_p50 (ML ok)
    # + 1 scalar para daily_target no final
    for _ in ops:
        session.queue_scalar(_make_bonus_row(bonus_eur=Decimal("5.00")))

    session.queue_scalar(_make_target(target_eur=35000.0))

    dm = _make_duration_model(p50_h=2.0)

    result = await compute_margin_preview(
        session, _TENANT, str(commit.id), duration_model=dm
    )

    assert result.confidence == "low"
    assert result.sample_size == 50
    assert result.predicted_margin_eur is not None
    # 50 ops × (5.00 - 2.0 × 12.00) = 50 × (5 - 24) = 50 × -19 = -950
    assert result.predicted_margin_eur == Decimal("-950.0000")
    assert result.baseline_margin_eur is not None
    assert result.delta_eur is not None


@pytest.mark.asyncio
async def test_commit_not_found_raises():
    """Commit inexistente → ValueError commit_not_found."""
    session = _FakeSession()
    session.set_get(None)
    # sha prefix também devolve vazio
    session.queue_scalars([])

    with pytest.raises(ValueError, match="commit_not_found"):
        await compute_margin_preview(session, _TENANT, "aaabbbccc")


@pytest.mark.asyncio
async def test_no_target_baseline_null():
    """Sem daily_revenue_target → baseline=None, delta=None, predicted populado."""
    ops = [_make_op(duration_h=1.0) for _ in range(5)]
    commit = _make_commit(ops)
    session = _FakeSession()
    session.set_get(commit)

    for _ in ops:
        session.queue_scalar(_make_bonus_row(bonus_eur=Decimal("10.00")))

    # target query → None
    session.queue_scalar(None)

    dm = _make_duration_model(p50_h=1.0)

    result = await compute_margin_preview(
        session, _TENANT, str(commit.id), duration_model=dm
    )

    assert result.baseline_margin_eur is None
    assert result.delta_eur is None
    assert result.predicted_margin_eur is not None
    assert result.confidence == "low"


@pytest.mark.asyncio
async def test_no_duration_model_fallback_p50():
    """Sem DurationModel → usa duration_h da operação como fallback → confidence=low."""
    ops = [_make_op(duration_h=3.0) for _ in range(10)]
    commit = _make_commit(ops)
    session = _FakeSession()
    session.set_get(commit)

    for _ in ops:
        session.queue_scalar(_make_bonus_row(bonus_eur=Decimal("8.00")))

    session.queue_scalar(_make_target(target_eur=30000.0))

    result = await compute_margin_preview(
        session, _TENANT, str(commit.id), duration_model=None
    )

    assert result.confidence == "low"
    assert result.predicted_margin_eur is not None
    # 10 × (8 - 3 × 12) = 10 × (8 - 36) = 10 × -28 = -280
    assert result.predicted_margin_eur == Decimal("-280.0000")


@pytest.mark.asyncio
async def test_sample_gte_100_medium_confidence():
    """100 < sample <= 500 → confidence=medium (sem fallback, ML activo)."""
    ops = [_make_op() for _ in range(200)]
    commit = _make_commit(ops)
    session = _FakeSession()
    session.set_get(commit)

    for _ in ops:
        session.queue_scalar(_make_bonus_row(bonus_eur=Decimal("5.00")))

    session.queue_scalar(_make_target())

    dm = _make_duration_model(p50_h=1.0)

    result = await compute_margin_preview(
        session, _TENANT, str(commit.id), duration_model=dm
    )

    assert result.confidence == "medium"
    assert result.sample_size == 200


@pytest.mark.asyncio
async def test_confidence_helper_unit():
    """_confidence é determinístico e respeita as regras de negócio."""
    assert _confidence(50, False) == "low"    # sample < 100
    assert _confidence(50, True) == "low"     # fallback sempre low
    assert _confidence(100, False) == "medium"
    assert _confidence(500, False) == "medium"
    assert _confidence(501, False) == "high"
    assert _confidence(501, True) == "low"    # fallback sobrepõe-se


@pytest.mark.asyncio
async def test_demo_orders_50_of_consistent():
    """50 OFs estilo demo_orders → confidence=low e predicted consistente entre runs."""
    # Simula 50 ordens com operações variadas
    ops = []
    for i in range(50):
        ops.append({
            "operation_id": str(uuid4()),
            "product_id": str(uuid4()),
            "phase_id": str(uuid4()),
            "duration_h": 1.5 + (i % 5) * 0.5,
            "modelo_id": f"M{i % 10:02d}",
            "team_size": 2,
        })

    commit = _make_commit(ops)
    session = _FakeSession()
    session.set_get(commit)

    bonus_val = Decimal("6.00")
    for _ in ops:
        session.queue_scalar(_make_bonus_row(bonus_eur=bonus_val))
    session.queue_scalar(_make_target(target_eur=35000.0))

    dm = _make_duration_model(p50_h=2.0)

    result = await compute_margin_preview(
        session, _TENANT, str(commit.id), duration_model=dm
    )

    # Segunda run com session fresca — resultado tem de ser idêntico
    session2 = _FakeSession()
    session2.set_get(commit)
    for _ in ops:
        session2.queue_scalar(_make_bonus_row(bonus_eur=bonus_val))
    session2.queue_scalar(_make_target(target_eur=35000.0))

    dm2 = _make_duration_model(p50_h=2.0)
    result2 = await compute_margin_preview(
        session2, _TENANT, str(commit.id), duration_model=dm2
    )

    assert result.confidence == "low"
    assert result.sample_size == 50
    assert result.predicted_margin_eur == result2.predicted_margin_eur
    assert result.predicted_margin_eur is not None
