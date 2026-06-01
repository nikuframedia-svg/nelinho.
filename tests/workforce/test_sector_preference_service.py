"""Q.140.B — SectorPreferenceService: nível por sector + ranking inverso.

Testa a agregação pura (`build_sector_levels`) e o ranking por sector
(monkeypatch dos fetch helpers — sem DB). Garante:
* nível INDEPENDENTE por sector (a mesma pessoa difere entre grupos);
* precedência override > derivado > semente ERP > nada;
* ranking só inclui APTOS ao sector (axioma 5 — nunca alarga);
* ordenação determinística e estável.
DAMP > DRY — cada teste lê como spec.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.workforce.levels import AREA_GROUPS, LEVEL_STEPS
from src.workforce.sector_preference_service import (
    SectorPreferenceService,
    _laplace_level,
    _PhaseStat,
    build_sector_levels,
)

_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _stat(fase_id, fase_nome, ops, defects, *, last_fim=None):
    return _PhaseStat(
        fase_id=fase_id,
        fase_nome=fase_nome,
        ops=ops,
        defects=defects,
        last_fim=last_fim or datetime(2026, 5, 1),
    )


def _by_area(levels):
    return {lvl.area_group: lvl for lvl in levels}


# ─────────────────────────────────────────────────────────────────────────
# _laplace_level
# ─────────────────────────────────────────────────────────────────────────

def test_laplace_level_none_without_ops():
    assert _laplace_level(0, 0) is None


def test_laplace_level_in_steps_and_monotonic():
    clean = _laplace_level(200, 0)
    dirty = _laplace_level(200, 80)
    assert clean in LEVEL_STEPS
    assert dirty in LEVEL_STEPS
    assert clean >= dirty  # menos defeitos → nível >=


# ─────────────────────────────────────────────────────────────────────────
# build_sector_levels — independência por sector + precedência
# ─────────────────────────────────────────────────────────────────────────

def test_always_returns_seven_groups():
    levels = build_sector_levels([])
    assert {lvl.area_group for lvl in levels} == set(AREA_GROUPS)
    assert all(not lvl.apt for lvl in levels)
    assert all(lvl.derived_level is None for lvl in levels)


def test_level_is_independent_per_sector():
    # Muitas ops limpas na Pintura, muitos defeitos na Laminagem → níveis
    # DIFERENTES para a mesma pessoa.
    stats = [
        _stat("5", "Pintura Acabamento", ops=300, defects=0),
        _stat("1", "Laminagem", ops=300, defects=120),
    ]
    by = _by_area(build_sector_levels(stats))
    assert by["Pintura"].apt and by["Laminagem"].apt
    assert by["Pintura"].derived_level > by["Laminagem"].derived_level
    assert by["Montagem"].apt is False  # sector sem histórico


def test_override_takes_precedence_over_derived():
    stats = [_stat("5", "Pintura Acabamento", ops=300, defects=0)]
    by = _by_area(build_sector_levels(stats, overrides={"Pintura": 1.5}))
    assert by["Pintura"].override_level == 1.5
    assert by["Pintura"].effective_level == 1.5
    assert by["Pintura"].source == "override"


def test_override_clamped_to_half_step():
    by = _by_area(build_sector_levels([], overrides={"Montagem": 2.7}))
    assert by["Montagem"].override_level == 2.5
    assert by["Montagem"].effective_level == 2.5


def test_derived_beats_erp_seed_when_present():
    stats = [_stat("5", "Pintura Acabamento", ops=300, defects=0)]
    by = _by_area(build_sector_levels(stats, erp_level=2.0))
    assert by["Pintura"].source == "derived"
    assert by["Pintura"].effective_level == by["Pintura"].derived_level


def test_erp_seed_used_only_without_history_or_override():
    by = _by_area(build_sector_levels([], erp_level=2.0))
    # Sem histórico em nenhum grupo → semente ERP em todos.
    assert by["Pintura"].source == "erp_seed"
    assert by["Pintura"].effective_level == 2.0
    assert by["Pintura"].derived_level is None


def test_no_signal_at_all_is_none():
    by = _by_area(build_sector_levels([]))
    assert by["Pintura"].effective_level is None
    assert by["Pintura"].source == "none"


# ─────────────────────────────────────────────────────────────────────────
# sector_ranking — vista inversa
# ─────────────────────────────────────────────────────────────────────────

def _service_with(history, dim, *, erp=None, overrides=None):
    svc = SectorPreferenceService(session=None, tenant_id=_TENANT)  # type: ignore[arg-type]

    async def _hist(employee_code=None):
        if employee_code is None:
            return history
        return {employee_code: history.get(employee_code, [])}

    async def _erp():
        return erp or {}

    async def _ov():
        return overrides or {}

    async def _dim(codes=None):
        return dim

    svc._fetch_phase_history = _hist          # type: ignore[assignment]
    svc._fetch_erp_levels = _erp              # type: ignore[assignment]
    svc._fetch_overrides = _ov                # type: ignore[assignment]
    svc._fetch_employee_dim = _dim            # type: ignore[assignment]
    return svc


_UID_A = uuid4()
_UID_B = uuid4()
_UID_C = uuid4()


@pytest.mark.asyncio
async def test_ranking_only_includes_apt_workers():
    history = {
        "A": [_stat("5", "Pintura Acabamento", ops=100, defects=2)],
        "B": [_stat("1", "Laminagem", ops=100, defects=2)],  # não é Pintura
    }
    dim = {"A": (_UID_A, "Ana"), "B": (_UID_B, "Bruno")}
    svc = _service_with(history, dim)

    res = await svc.sector_ranking("Pintura")

    codes = [r["employee_code"] for r in res["ranking"]]
    assert codes == ["A"]            # B não trabalhou Pintura → fora (axioma 5)
    assert res["total"] == 1


@pytest.mark.asyncio
async def test_ranking_ordered_by_effective_level_then_ops():
    history = {
        "A": [_stat("5", "Pintura Acabamento", ops=50, defects=20)],   # nível baixo
        "B": [_stat("5", "Pintura Acabamento", ops=300, defects=0)],   # nível alto
        "C": [_stat("5", "Pintura Acabamento", ops=300, defects=0)],   # = B, mais ops? igual
    }
    dim = {"A": (_UID_A, "Ana"), "B": (_UID_B, "Bruno"), "C": (_UID_C, "Carla")}
    svc = _service_with(history, dim)

    res = await svc.sector_ranking("Pintura")
    codes = [r["employee_code"] for r in res["ranking"]]

    # B e C têm nível alto (vêm antes de A). A é último (nível baixo).
    assert codes[-1] == "A"
    assert set(codes[:2]) == {"B", "C"}
    assert res["ranking"][0]["rank"] == 1


@pytest.mark.asyncio
async def test_ranking_excludes_workers_without_employee_row():
    history = {"A": [_stat("5", "Pintura Acabamento", ops=100, defects=2)]}
    dim = {}  # A não tem linha em core.employees → sem UUID → fora
    svc = _service_with(history, dim)

    res = await svc.sector_ranking("Pintura")
    assert res["ranking"] == []
    assert res["total"] == 0


@pytest.mark.asyncio
async def test_ranking_override_lifts_a_low_history_worker():
    history = {
        "A": [_stat("5", "Pintura Acabamento", ops=50, defects=30)],   # derivado baixo
        "B": [_stat("5", "Pintura Acabamento", ops=300, defects=45)],  # derivado 2.5
    }
    dim = {"A": (_UID_A, "Ana"), "B": (_UID_B, "Bruno")}
    overrides = {(str(_UID_A), "Pintura"): 3.0}  # override manual eleva A ao topo (3.0 > 2.5)
    svc = _service_with(history, dim, overrides=overrides)

    res = await svc.sector_ranking("Pintura")
    assert res["ranking"][0]["employee_code"] == "A"
    assert res["ranking"][0]["source"] == "override"


@pytest.mark.asyncio
async def test_ranking_is_deterministic_across_runs():
    history = {
        "A": [_stat("5", "Pintura Acabamento", ops=100, defects=0)],
        "B": [_stat("5", "Pintura Acabamento", ops=100, defects=0)],
    }
    dim = {"A": (_UID_A, "Ana"), "B": (_UID_B, "Bruno")}
    svc = _service_with(history, dim)

    r1 = await svc.sector_ranking("Pintura")
    r2 = await svc.sector_ranking("Pintura")
    assert [r["employee_id"] for r in r1["ranking"]] == [
        r["employee_id"] for r in r2["ranking"]
    ]
