"""Q.173.L — config de tenant lida pelo planeador.

A auditoria 2026-06-11 encontrou duas regras só-mudáveis-em-código:
- ``use_queue_time`` (fila inter-fase mediana vs one-piece-flow) era um
  campo do CPOConfig que ``_build_cpo_config`` nunca lia da config;
- ``REPAIR_PHASE_IDS`` {14,76,77} era um frozenset hardcoded usado pelo
  loader (prioridade) e pelo CP-SAT global (exclusão).

Ambos passam a keys da categoria ``planning`` (``cpo.use_queue_time`` e
``repair.phase_ids``) com defaults idênticos ao comportamento anterior.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.plan.cpo import scheduler_run

_CFG_PATH = (
    "src.core.services.tenant_config_service.TenantConfigService.get_category"
)


def _req():
    return SimpleNamespace(
        population_size=scheduler_run._REQ_DEFAULT_POP_SIZE,
        generations=scheduler_run._REQ_DEFAULT_GENERATIONS,
        time_limit_sec=scheduler_run._REQ_DEFAULT_TIME_LIMIT_S,
    )


# ─── cpo.use_queue_time ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_use_queue_time_default_true(monkeypatch):
    async def fake(self, category):
        return {}

    monkeypatch.setattr(_CFG_PATH, fake)
    cfg = await scheduler_run._build_cpo_config(object(), uuid4(), _req())
    assert cfg.use_queue_time is True  # comportamento anterior intacto


@pytest.mark.asyncio
async def test_use_queue_time_one_piece_flow_via_config(monkeypatch):
    async def fake(self, category):
        return {"cpo.use_queue_time": False}

    monkeypatch.setattr(_CFG_PATH, fake)
    cfg = await scheduler_run._build_cpo_config(object(), uuid4(), _req())
    assert cfg.use_queue_time is False


# ─── repair.phase_ids ───────────────────────────────────────────────────────


def _op(phase_id: str):
    return SimpleNamespace(phase_id=phase_id, operation_id=f"op-{phase_id}")


def test_cpsat_global_exclui_reparacoes_default():
    """Sem config, o CP-SAT global exclui {14,76,77} — tudo reparação ⇒ None."""
    from src.plan.engines.cpsat_global import run_cpsat_global

    state = SimpleNamespace()  # sem repair_phase_ids → default
    out = run_cpsat_global(
        state, [_op("14"), _op("76"), _op("77")], [],
        datetime(2026, 6, 1), datetime(2026, 7, 1),
    )
    assert out is None  # main_ops vazio — devolve antes de tocar no solver


def test_cpsat_global_respeita_repair_ids_do_state(monkeypatch):
    """state.repair_phase_ids configurado governa a exclusão.

    Com repair_phase_ids={'40'}: a fase 40 é excluída e a 14 (default de
    reparação) passa a entrar no solver — provado por o solve_timing ser
    chamado com a op da fase 14.
    """
    from src.plan.engines import cpsat_global as cg

    seen: dict = {}

    class _FakeScheduler:
        def __init__(self, *_a, **_kw):
            pass

        def solve_timing(self, ops, *_a, **_kw):
            seen["ops"] = list(ops)
            return SimpleNamespace(available=False, reason="teste")

    monkeypatch.setattr(cg, "CPSATScheduler", _FakeScheduler)

    state = SimpleNamespace(repair_phase_ids=frozenset({"40"}))
    out = cg.run_cpsat_global(
        state, [_op("40"), _op("14")], [],
        datetime(2026, 6, 1), datetime(2026, 7, 1),
    )
    assert out is None  # timing indisponível → fallback
    assert [str(o.phase_id) for o in seen["ops"]] == ["14"], (
        "a fase 14 deve ENTRAR (já não é reparação) e a 40 deve ser excluída"
    )


# ─── seeds ──────────────────────────────────────────────────────────────────


def test_seeds_q173l_presentes():
    from src.core.services.default_configs import iter_seeds

    seeds = {(c, k): (v, t) for c, k, v, t, _n in iter_seeds()}
    assert seeds[("planning", "cpo.use_queue_time")] == (True, "bool")
    value, dtype = seeds[("planning", "repair.phase_ids")]
    assert dtype == "json"
    assert list(value) == [14, 76, 77]  # default = comportamento atual
