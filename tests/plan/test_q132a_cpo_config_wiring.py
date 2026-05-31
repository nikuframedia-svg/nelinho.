"""Q.132.A — o CPOConfig passa a ser controlado pela página de Configurações.

Antes, `generations`/`total_budget_s` eram hardcoded / vinham só do request
(default 50/60). Agora `scheduler_run._build_cpo_config` lê a categoria
`planning` de `tenant_configuration` (cpo.gen_count / cpo.total_budget_s /
cpo.pop_size + sub-budgets), com o request a sobrepor só quando difere do
default do schema. Sem config → defaults canónicos do CPOConfig.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.plan.cpo import scheduler_run

_CFG_PATH = "src.core.services.tenant_config_service.TenantConfigService.get_category"


def _req(pop=100, gens=50, tlim=30.0):
    # Defaults do schema CPOScheduleRequest (pop=100, gens=50, tlim=30.0).
    return SimpleNamespace(population_size=pop, generations=gens, time_limit_sec=tlim)


@pytest.mark.asyncio
async def test_config_drives_engine_when_request_is_default(monkeypatch):
    planning = {
        "cpo.gen_count": 120, "cpo.total_budget_s": 90.0, "cpo.pop_size": 80,
        "cpo.ga_budget_s": 45.0,
    }

    async def fake(self, category):
        return planning if category == "planning" else {}

    monkeypatch.setattr(_CFG_PATH, fake)
    cfg = await scheduler_run._build_cpo_config(object(), uuid4(), _req())

    assert cfg.generations == 120        # da Config, não o default 50 do request
    assert cfg.total_budget_s == 90.0
    assert cfg.population_size == 80
    assert cfg.time_limit_sec == 45.0    # cai em cpo.ga_budget_s


@pytest.mark.asyncio
async def test_explicit_request_override_wins_over_config(monkeypatch):
    async def fake(self, category):
        return {"cpo.gen_count": 120}

    monkeypatch.setattr(_CFG_PATH, fake)
    # generations=300 != default 50 -> caller explícito ganha
    cfg = await scheduler_run._build_cpo_config(object(), uuid4(), _req(gens=300))
    assert cfg.generations == 300


@pytest.mark.asyncio
async def test_falls_back_to_canonical_defaults_without_config(monkeypatch):
    async def boom(self, category):
        raise RuntimeError("sem BD de config")

    monkeypatch.setattr(_CFG_PATH, boom)
    cfg = await scheduler_run._build_cpo_config(object(), uuid4(), _req())

    # Defaults Blueprint v2.0 — nunca degradar quando a config falta.
    assert cfg.generations == 200
    assert cfg.total_budget_s == 60.0
    assert cfg.population_size == 100
