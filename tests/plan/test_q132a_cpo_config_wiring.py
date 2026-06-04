"""Q.132.A — o CPOConfig passa a ser controlado pela página de Configurações.

Antes, `generations`/`total_budget_s` eram hardcoded / vinham só do request
(default 50/60). Agora `scheduler_run._build_cpo_config` lê a categoria
`planning` de `tenant_configuration` (cpo.gen_count / cpo.total_budget_s /
cpo.pop_size + sub-budgets), com o request a sobrepor só quando difere do
default do schema. Sem config → defaults canónicos do CPOConfig.

Q.138.D — actualizados defaults: gens=200 (era 50, Blueprint §5.5),
time_limit=120 (era 30, insuficiente para 200 ordens), total_budget=150 (era 60).
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.plan.cpo import scheduler_run
from src.plan.cpo.engine import CPOConfig
from src.plan.cpo import scheduler_run as _sr

_CFG_PATH = "src.core.services.tenant_config_service.TenantConfigService.get_category"

# Q.138.D — alinhados com _REQ_DEFAULT_* do scheduler_run (Blueprint v2.0).
_DEF_GENS = _sr._REQ_DEFAULT_GENERATIONS      # 200
_DEF_TLIM = _sr._REQ_DEFAULT_TIME_LIMIT_S     # 120.0
_DEF_POP = _sr._REQ_DEFAULT_POP_SIZE          # 100


def _req(pop=_DEF_POP, gens=_DEF_GENS, tlim=_DEF_TLIM):
    # Defaults do schema CPOScheduleRequest (Q.138.D: pop=100, gens=200, tlim=120).
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

    assert cfg.generations == 120        # da Config, não o default 200 do request
    assert cfg.total_budget_s == 90.0
    assert cfg.population_size == 80
    assert cfg.time_limit_sec == 45.0    # cai em cpo.ga_budget_s


@pytest.mark.asyncio
async def test_explicit_request_override_wins_over_config(monkeypatch):
    async def fake(self, category):
        return {"cpo.gen_count": 120}

    monkeypatch.setattr(_CFG_PATH, fake)
    # generations=300 != default 200 -> caller explícito ganha
    cfg = await scheduler_run._build_cpo_config(object(), uuid4(), _req(gens=300))
    assert cfg.generations == 300


@pytest.mark.asyncio
async def test_robot_time_limit_bumps_ga_and_total_budget(monkeypatch):
    """Q.161.B — um caller (robô de fundo) que pede `time_limit_sec` maior que o
    `ga_budget` alarga ga_budget E total_budget para o acomodar. Senão o
    `CPOConfig.__post_init__` cortava o time_limit de volta para o ga_budget
    (120s) e o robô nunca usaria os 600s pedidos para planear os ~1200 barcos."""
    async def fake(self, category):
        return {}  # sem overrides → ga_budget=120, total=150 (defaults Blueprint)

    monkeypatch.setattr(_CFG_PATH, fake)
    cfg = await scheduler_run._build_cpo_config(
        object(), uuid4(), _req(tlim=600.0),
    )
    assert cfg.time_limit_sec == 600.0                 # NÃO foi cortado para 120
    assert cfg.ga_budget_s == 600.0                    # alargado para caber
    assert cfg.total_budget_s == 150.0 + (600.0 - 120.0)  # 630 (delta somado)


@pytest.mark.asyncio
async def test_interactive_default_does_not_bump_budget(monkeypatch):
    """Q.161.B — o caso interativo (tlim=default) NÃO alarga nada: fica nos
    budgets da config/defaults (back-compat exacto com o botão Replanear)."""
    async def fake(self, category):
        return {"cpo.ga_budget_s": 120.0, "cpo.total_budget_s": 150.0}

    monkeypatch.setattr(_CFG_PATH, fake)
    cfg = await scheduler_run._build_cpo_config(object(), uuid4(), _req())
    assert cfg.ga_budget_s == 120.0
    assert cfg.total_budget_s == 150.0


@pytest.mark.asyncio
async def test_falls_back_to_canonical_defaults_without_config(monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    async def boom(self, category):
        raise SQLAlchemyError("sem BD de config")

    monkeypatch.setattr(_CFG_PATH, boom)
    cfg = await scheduler_run._build_cpo_config(object(), uuid4(), _req())

    # Defaults Blueprint v2.0 — nunca degradar quando a config falta.
    # Q.138.D: gens=200 (era 50), total_budget=150 (era 60).
    canonical = CPOConfig()
    assert cfg.generations == canonical.generations   # 200
    assert cfg.total_budget_s == canonical.total_budget_s  # 150
    assert cfg.population_size == _DEF_POP             # 100
