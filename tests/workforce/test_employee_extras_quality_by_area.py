"""Q.140.A — quality_score escopado a um grupo de área (sector).

O Luis quer um nível DIFERENTE por sector para cada pessoa (uma pessoa
multi-funcional é boa na Pintura mas fraca na Laminagem). O primeiro
tijolo é poder calcular o quality_score Laplace SÓ com as ops/defeitos
das fases de um grupo de área.

`quality_score(employee_id, area_group=...)` reaproveita o mesmo caminho
Laplace, mas conta só as fases cujo `area_group_for_phase(...)` casa com
o sector pedido. `area_group=None` mantém o comportamento global (retro-
compatível). Estes testes injectam contadores/skill_matrix via monkey-
patch — testam o branching, não a SQL (DAMP > DRY, cada teste é spec).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.workforce.employee_extras_service import (
    DEFAULT_SCORE,
    EmployeeExtrasService,
    SkillMatrixRow,
)
from src.workforce.levels import LEVEL_STEPS, quality_to_level

_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _service() -> EmployeeExtrasService:
    return EmployeeExtrasService(session=None, tenant_id=_TENANT)  # type: ignore[arg-type]


def _async(value):
    async def _f(*_args, **_kwargs):
        return value

    return _f


def _fake_employee(code):
    emp = type("FakeEmployee", (), {"employee_code": code})()
    return _async(emp)


def _row(phase_id, phase_name, ops_count, *, can_do=True):
    return SkillMatrixRow(
        phase_id=phase_id,
        phase_name=phase_name,
        can_do=can_do,
        nivel=None,
        ops_count=ops_count,
        last_used_at=datetime(2026, 5, 1),
    )


def _with_skills(svc, rows, defects_by_phase):
    """Monkeypatch o caminho curado: employee + skill_matrix + defeitos/fase."""
    svc._get_employee = _fake_employee("20363")  # type: ignore[assignment]
    svc.skill_matrix = _async(rows)  # type: ignore[assignment]
    svc._curated_defects_by_phase = _async(defects_by_phase)  # type: ignore[assignment]
    return svc


# Corpus comum: 2 fases de Pintura, 1 de Laminagem.
_PINTURA_A = _row("10", "Pintura Acabamento", ops_count=120)
_PINTURA_B = _row("11", "Lixagem água", ops_count=80)   # Lixagem → Pintura
_LAMINAGEM = _row("20", "Laminagem", ops_count=200)


# ─────────────────────────────────────────────────────────────────────────
# Escopo por área
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_quality_score_by_area_counts_only_that_area():
    svc = _with_skills(
        _service(),
        [_PINTURA_A, _PINTURA_B, _LAMINAGEM],
        {"10": 5, "11": 0, "20": 60},  # defeitos por fase_id
    )

    res = await svc.quality_score(uuid4(), area_group="Pintura")

    # Pintura: ops 120+80=200, defeitos 5+0=5 (a Laminagem com 60 NÃO conta).
    assert res.operations == 200
    assert res.defects == 5
    assert res.area_group == "Pintura"
    assert res.method == "laplace_smoothed"


@pytest.mark.asyncio
async def test_area_with_no_ops_is_default_no_history():
    svc = _with_skills(_service(), [_LAMINAGEM], {"20": 0})

    # Pintura não tem nenhuma fase nas rows → sem histórico nesse sector.
    res = await svc.quality_score(uuid4(), area_group="Pintura")

    assert res.method == "default_no_history"
    assert res.operations == 0
    assert res.defects == 0
    assert res.score == DEFAULT_SCORE
    assert res.area_group == "Pintura"


@pytest.mark.asyncio
async def test_high_defect_area_scores_below_clean_area():
    rows = [_PINTURA_A, _LAMINAGEM]
    svc = _with_skills(_service(), rows, {"10": 0, "20": 90})

    pintura = await svc.quality_score(uuid4(), area_group="Pintura")   # 0 defeitos
    laminagem = await svc.quality_score(uuid4(), area_group="Laminagem")  # 90 defeitos

    assert pintura.score > laminagem.score
    assert laminagem.defect_rate > pintura.defect_rate


@pytest.mark.asyncio
async def test_sum_of_area_ops_equals_total_skill_matrix_ops():
    rows = [_PINTURA_A, _PINTURA_B, _LAMINAGEM]
    svc = _with_skills(_service(), rows, {})

    pintura = await svc.quality_score(uuid4(), area_group="Pintura")
    laminagem = await svc.quality_score(uuid4(), area_group="Laminagem")

    total_rows_ops = sum(r.ops_count for r in rows)
    assert pintura.operations + laminagem.operations == total_rows_ops


@pytest.mark.asyncio
async def test_derived_level_for_area_is_a_valid_half_step():
    svc = _with_skills(_service(), [_PINTURA_A], {"10": 3})

    res = await svc.quality_score(uuid4(), area_group="Pintura")

    assert quality_to_level(res.score) in LEVEL_STEPS


# ─────────────────────────────────────────────────────────────────────────
# Retrocompatibilidade: area_group=None == comportamento global anterior
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_area_group_none_keeps_global_curated_path():
    # O caminho global continua a usar os contadores escalares (Q.54.P),
    # NÃO o skill_matrix — sentinela rebenta se a área path for usada.
    svc = _service()
    svc._get_employee = _fake_employee("20363")  # type: ignore[assignment]
    svc._count_ops = _async(0)  # type: ignore[assignment]
    svc._count_rework = _async(0)  # type: ignore[assignment]
    svc._count_curated_ops = _async(221)  # type: ignore[assignment]
    svc._count_curated_defects = _async(8)  # type: ignore[assignment]

    res = await svc.quality_score(uuid4())

    assert res.operations == 221
    assert res.defects == 8
    assert res.area_group is None
    assert res.method == "laplace_smoothed"
