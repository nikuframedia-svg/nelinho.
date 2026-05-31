"""Q.132.B/B2 — a página de Configurações controla o fitness do CPO.

Antes, o scheduler corria em modo legacy (`use_v2_weights=False`) e
`from_tenant_config` só carregava adaptive weights → os sliders
`planning.fitness.weight.*` e o revenue target eram código morto. Agora
`from_tenant_config` activa v2, carrega os sliders nos pesos v2 e o revenue
target diário (activa o `revenue_alignment`).
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.plan.cpo.fitness import FitnessConfig

_CFG_PATH = "src.core.services.tenant_config_service.TenantConfigService.get_category"


class _FakeResult:
    def __init__(self, val):
        self._val = val

    def scalar_one_or_none(self):
        return self._val


class _FakeSession:
    """Só serve a query do revenue target (get_category é monkeypatched)."""

    def __init__(self, target=None):
        self._target = target

    async def execute(self, *_a, **_k):
        return _FakeResult(self._target)


@pytest.mark.asyncio
async def test_sliders_drive_v2_weights(monkeypatch):
    planning = {
        "fitness.weight.makespan": 0.40,
        "fitness.weight.tardiness_transport": 0.30,
        "fitness.weight.quality_risk": 0.05,
    }

    async def fake(self, category):
        return planning if category == "planning" else {}

    monkeypatch.setattr(_CFG_PATH, fake)
    cfg = await FitnessConfig.from_tenant_config(_FakeSession(), uuid4())

    assert cfg.use_v2_weights is True            # modo Blueprint v2.0 activo
    assert cfg.w_v2_makespan == pytest.approx(0.40)
    assert cfg.w_v2_tardiness_transport == pytest.approx(0.30)
    assert cfg.w_v2_quality_risk == pytest.approx(0.05)
    # peso não-configurado mantém o default v2
    assert cfg.w_v2_idle_operators == pytest.approx(0.15)


@pytest.mark.asyncio
async def test_revenue_target_loaded_activates_alignment(monkeypatch):
    async def fake(self, category):
        return {}

    monkeypatch.setattr(_CFG_PATH, fake)
    cfg = await FitnessConfig.from_tenant_config(_FakeSession(target=32000.0), uuid4())

    assert cfg.daily_revenue_target_eur == pytest.approx(32000.0)  # era None (neutro)


@pytest.mark.asyncio
async def test_use_v2_can_be_turned_off_by_config(monkeypatch):
    async def fake(self, category):
        return {"fitness.use_v2_weights": False} if category == "planning" else {}

    monkeypatch.setattr(_CFG_PATH, fake)
    cfg = await FitnessConfig.from_tenant_config(_FakeSession(), uuid4())
    assert cfg.use_v2_weights is False           # config pode reverter para legacy


@pytest.mark.asyncio
async def test_explicit_override_wins(monkeypatch):
    async def fake(self, category):
        return {"fitness.weight.makespan": 0.40}

    monkeypatch.setattr(_CFG_PATH, fake)
    cfg = await FitnessConfig.from_tenant_config(
        _FakeSession(), uuid4(), use_v2_weights=False, w_v2_makespan=0.99,
    )
    assert cfg.use_v2_weights is False           # override explícito ganha
    assert cfg.w_v2_makespan == pytest.approx(0.99)
