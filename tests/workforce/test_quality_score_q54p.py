"""Q.54.P — quality_score lê o histórico real do ERP.

Bug confirmado live: a página Fábrica mostrava TODOS os operadores com
"0 ops · 0.0% erro · Sem histórico de qualidade". Mas a base de dados tem
o histórico:

* ``factory_curated.allocation`` — 131 176 operações reais por operador;
* ``factory_curated.quality_event`` — 97 006 eventos de qualidade;
* ``plan.production_schedules`` — 159 linhas, **0** com operador atribuído.

O ``quality_score`` só contava ``production_schedules`` → 0 ops → sempre
``default_no_history``. Agora cai na camada curada quando o schedule está
vazio (mesmo fallback que o ``skill_matrix`` já fazia).

Estes testes injectam os contadores via monkeypatch — testam o branching,
não a SQL (essa foi verificada contra a BD real: Carlos Marujo Almeida
20363 → 221 ops, 8 defeitos).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.workforce.employee_extras_service import EmployeeExtrasService

_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _service() -> EmployeeExtrasService:
    return EmployeeExtrasService(session=None, tenant_id=_TENANT)  # type: ignore[arg-type]


def _async(value):
    """Função assíncrona que devolve sempre `value` (monkeypatch)."""

    async def _f(*_args, **_kwargs):
        return value

    return _f


def _fake_employee(code):
    """`_get_employee` falso — devolve um objecto só com employee_code."""
    emp = type("FakeEmployee", (), {"employee_code": code})()
    return _async(emp)


# ─────────────────────────────────────────────────────────────────────────
# Branching: governança vs camada curada
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_uses_curated_layer_when_production_schedule_empty():
    # O caso real: ProductionSchedule não cobre o operador → camada ERP.
    svc = _service()
    svc._get_employee = _fake_employee("20363")  # type: ignore[assignment]
    svc._count_ops = _async(0)  # type: ignore[assignment]
    svc._count_rework = _async(0)  # type: ignore[assignment]
    svc._count_curated_ops = _async(221)  # type: ignore[assignment]
    svc._count_curated_defects = _async(8)  # type: ignore[assignment]

    res = await svc.quality_score(uuid4())

    assert res.operations == 221
    assert res.defects == 8
    assert res.method == "laplace_smoothed"
    # rate = (8+1)/(221+10) ≈ 0.039 → score ≈ 9.6
    assert res.score == pytest.approx(9.61, abs=0.1)


@pytest.mark.asyncio
async def test_prefers_production_schedule_when_it_has_ops():
    # Quando o schedule tem operações, é a fonte autoritária — não vai à
    # camada curada.
    svc = _service()
    svc._get_employee = _fake_employee("20363")  # type: ignore[assignment]
    svc._count_ops = _async(50)  # type: ignore[assignment]
    svc._count_rework = _async(3)  # type: ignore[assignment]
    # Sentinelas que rebentam o teste se forem (erradamente) usadas.
    svc._count_curated_ops = _async(999)  # type: ignore[assignment]
    svc._count_curated_defects = _async(999)  # type: ignore[assignment]

    res = await svc.quality_score(uuid4())

    assert res.operations == 50
    assert res.defects == 3
    assert res.method == "laplace_smoothed"


@pytest.mark.asyncio
async def test_default_no_history_only_when_both_layers_empty():
    svc = _service()
    svc._get_employee = _fake_employee("99999")  # type: ignore[assignment]
    svc._count_ops = _async(0)  # type: ignore[assignment]
    svc._count_rework = _async(0)  # type: ignore[assignment]
    svc._count_curated_ops = _async(0)  # type: ignore[assignment]
    svc._count_curated_defects = _async(0)  # type: ignore[assignment]

    res = await svc.quality_score(uuid4())

    assert res.method == "default_no_history"
    assert res.operations == 0
    assert res.defects == 0


@pytest.mark.asyncio
async def test_curated_ops_with_zero_defects_is_real_history_not_default():
    # 221 operações limpas → histórico real, score alto — NÃO
    # "default_no_history" (o bug que estávamos a corrigir).
    svc = _service()
    svc._get_employee = _fake_employee("30342")  # type: ignore[assignment]
    svc._count_ops = _async(0)  # type: ignore[assignment]
    svc._count_rework = _async(0)  # type: ignore[assignment]
    svc._count_curated_ops = _async(221)  # type: ignore[assignment]
    svc._count_curated_defects = _async(0)  # type: ignore[assignment]

    res = await svc.quality_score(uuid4())

    assert res.method == "laplace_smoothed"
    assert res.operations == 221
    assert res.defects == 0
    assert res.score > 9.5


@pytest.mark.asyncio
async def test_high_defect_rate_drops_the_score():
    # João Azevedo Seixas: 132 ops, 21 defeitos → score baixo.
    svc = _service()
    svc._get_employee = _fake_employee("25050")  # type: ignore[assignment]
    svc._count_ops = _async(0)  # type: ignore[assignment]
    svc._count_rework = _async(0)  # type: ignore[assignment]
    svc._count_curated_ops = _async(132)  # type: ignore[assignment]
    svc._count_curated_defects = _async(21)  # type: ignore[assignment]

    res = await svc.quality_score(uuid4())

    # rate = (21+1)/(132+10) ≈ 0.155 → score ≈ 8.45
    assert res.score == pytest.approx(8.45, abs=0.1)
    assert res.defect_rate > 0.1


# ─────────────────────────────────────────────────────────────────────────
# Early-returns dos contadores curados — sem employee_code, sem DB
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_curated_counters_return_zero_without_employee_code():
    svc = _service()
    assert await svc._count_curated_ops(None) == 0
    assert await svc._count_curated_ops("") == 0
    assert await svc._count_curated_defects(None) == 0
    assert await svc._count_curated_defects("") == 0
