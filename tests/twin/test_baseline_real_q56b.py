"""Q.56.B — o baseline do Twin computa-se de tabelas reais.

Antes: `_create_baseline_state` dependia da camada semântica do Factory
Data Product. Em dev essa camada está indisponível → todos os 9 KPIs
vinham `null` → qualquer simulação mexia zero números.

Agora, quando a camada semântica falha, WIP / erros de qualidade /
backlog caem para métricas computadas de `production_orders`,
`rework_entry` e do commit CPO mais recente. Os KPIs sem fonte barata
(OEE/OTD) ficam `BLOCKED` — honesto, nunca inventado.
"""

from __future__ import annotations

import types
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.plan.cpo.commits import CommitsService
from src.twin.service import TwinService

TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture(autouse=True)
def _semantic_layer_down(monkeypatch):
    """Força a camada semântica a indisponível — o caso real em dev."""
    class _Unavailable:
        def __init__(self) -> None:
            raise RuntimeError("semantic layer down (test)")

    monkeypatch.setattr(
        "src.factory_data_product.services.semantic_queries_inmemory."
        "SemanticQueriesInMemory",
        _Unavailable,
    )


def _db(phases: list[str], rework_count: int):
    """db mock — serve as duas queries de `_governance_baseline_metrics`.

    A query de WIP usa `.scalars().all()`; a de retrabalho usa `.scalar()`.
    Um único `_Result` com os dois acessores serve ambas (cada query só
    chama o seu).
    """
    db = AsyncMock()

    class _Result:
        def scalars(self_):
            class _S:
                def all(_s):
                    return list(phases)
            return _S()

        def scalar(self_):
            return rework_count

    async def _execute(_stmt):
        return _Result()

    db.execute = _execute
    db.add = lambda obj: None
    db.commit = AsyncMock()
    return db


def _patch_commit(monkeypatch, kpis):
    """Faz `CommitsService.get_latest` devolver um commit com `kpis`."""
    commit = types.SimpleNamespace(kpis=kpis) if kpis is not None else None

    async def _get_latest(_self):
        return commit

    monkeypatch.setattr(CommitsService, "get_latest", _get_latest)


# ── _governance_baseline_metrics ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_governance_metrics_compute_wip_quality_backlog(monkeypatch):
    # 3 fases de chão de fábrica + 1 terminal → WIP conta só as 3.
    db = _db(["Laminagem", "Cura", "Montagem", "Entregue"], rework_count=42)
    _patch_commit(monkeypatch, {"makespan_hours": 613.38})

    svc = TwinService(db, TENANT)
    metrics = await svc._governance_baseline_metrics()

    assert metrics["wip"] == 3  # "Entregue" não conta
    assert metrics["quality_errors"] == 42
    assert metrics["backlog_hours"] == 613.38


@pytest.mark.asyncio
async def test_governance_backlog_none_without_commit(monkeypatch):
    db = _db(["Laminagem"], rework_count=0)
    _patch_commit(monkeypatch, None)  # sem commit CPO

    svc = TwinService(db, TENANT)
    metrics = await svc._governance_baseline_metrics()

    assert metrics["backlog_hours"] is None
    assert metrics["quality_errors"] == 0  # zero é um valor real, não None


# ── _create_baseline_state ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_baseline_fills_from_governance_when_semantic_down(monkeypatch):
    db = _db(["Laminagem", "Cura", "Pintura Acabamento"], rework_count=42)
    _patch_commit(monkeypatch, {"makespan_hours": 613.38})

    svc = TwinService(db, TENANT)
    state = await svc._create_baseline_state()

    assert state["wip_theoretical"]["value"] == 3
    assert state["wip_theoretical"]["status"] == "OK"
    assert state["wip_theoretical"]["source"] == "governance_tables"

    assert state["quality_errors_total"]["value"] == 42
    assert state["quality_errors_total"]["status"] == "WARNING"

    assert state["backlog_horas_theoretical"]["value"] == 613.4  # round(1)
    assert state["backlog_horas_theoretical"]["status"] == "WARNING"

    # KPIs sem fonte barata continuam honestamente bloqueados.
    assert state["oee"]["status"] == "BLOCKED"
    assert state["otd"]["status"] == "BLOCKED"

    assert state["_metadata"]["data_version"] == "governance_tables"


@pytest.mark.asyncio
async def test_baseline_backlog_no_data_without_commit(monkeypatch):
    db = _db(["Laminagem"], rework_count=5)
    _patch_commit(monkeypatch, None)

    svc = TwinService(db, TENANT)
    state = await svc._create_baseline_state()

    assert state["backlog_horas_theoretical"]["value"] is None
    assert state["backlog_horas_theoretical"]["status"] == "NO_DATA"
    # WIP e qualidade vieram das tabelas → data_version reflecte-o.
    assert state["wip_theoretical"]["value"] == 1
    assert state["_metadata"]["data_version"] == "governance_tables"


# ── um delta de crise mexe o baseline real ───────────────────────────────


@pytest.mark.asyncio
async def test_capacity_delta_moves_real_backlog(monkeypatch):
    """Com baseline real, um `capacity_adjustment` negativo cresce o backlog."""
    db = _db(["Laminagem"], rework_count=0)
    _patch_commit(monkeypatch, {"makespan_hours": 600.0})

    svc = TwinService(db, TENANT)
    state = await svc._create_baseline_state()

    # Crise "molde parte" → capacity_increase_pct -30 → backlog *= 1.30.
    after = svc._apply_delta_to_state(state, {
        "entity_type": "capacity_adjustment",
        "entity_key": "molde-k1-7ml-03",
        "patch": {"capacity_increase_pct": -30},
    })

    before_backlog = state["backlog_horas_theoretical"]["value"]
    after_backlog = after["backlog_horas_theoretical"]["value"]
    assert before_backlog == 600.0
    assert after_backlog == pytest.approx(780.0)  # 600 × 1.30
