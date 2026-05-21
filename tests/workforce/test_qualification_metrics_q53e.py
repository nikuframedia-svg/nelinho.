"""Sprint Q.53.E — métricas de qualificação (recency/versatility/productivity).

A auditoria: as métricas de qualificação do operador usavam só 3 sinais
(quality-score, skill-match, defect-rate). Faltavam 3:

* `recency_days` — última vez na fase/área.
* `versatility` — nº de fases/áreas aptas.
* `productivity` — operações por dia.

`qualification_metrics()` deriva tudo da `skill_matrix` já existente
(que junta curated + histórico real ERP). Estes testes injectam uma
skill_matrix sintética via monkeypatch — não tocam DB. ZERO MOCKS no
frontend; aqui é teste unitário, fakes de teste são permitidos.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from src.workforce.employee_extras_service import (
    EmployeeExtrasService,
    QualificationMetrics,
    SkillMatrixRow,
)

_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _row(phase_id, phase_name, can_do, ops_count, days_ago, nivel=None):
    """Constrói uma SkillMatrixRow com last_used_at = hoje - days_ago."""
    last = None if days_ago is None else datetime.now() - timedelta(days=days_ago)
    return SkillMatrixRow(
        phase_id=phase_id,
        phase_name=phase_name,
        can_do=can_do,
        nivel=nivel,
        ops_count=ops_count,
        last_used_at=last,
    )


def _service_with_skills(rows):
    """EmployeeExtrasService cujo skill_matrix devolve `rows`."""
    svc = EmployeeExtrasService(session=None, tenant_id=_TENANT)  # type: ignore[arg-type]

    async def _fake_skill_matrix(_employee_id):
        return rows

    svc.skill_matrix = _fake_skill_matrix  # type: ignore[assignment]
    return svc


# ─────────────────────────────────────────────────────────────────────────
# Shape do resultado
# ─────────────────────────────────────────────────────────────────────────

def test_qualification_metrics_to_dict_shape():
    m = QualificationMetrics(
        employee_id=uuid4(),
        recency_days=12,
        versatility=4,
        productivity=2.5,
        ops_total=100,
        scope=None,
    )
    d = m.to_dict()
    assert d["recency_days"] == 12
    assert d["versatility"] == 4
    assert d["productivity"] == 2.5
    assert d["ops_total"] == 100
    assert d["scope"] is None


def test_to_dict_rounds_productivity_and_keeps_none():
    m = QualificationMetrics(
        employee_id=uuid4(),
        recency_days=None,
        versatility=0,
        productivity=None,
        ops_total=0,
        scope="Laminagem",
    )
    d = m.to_dict()
    assert d["productivity"] is None
    assert d["recency_days"] is None
    assert d["scope"] == "Laminagem"


# ─────────────────────────────────────────────────────────────────────────
# Versatilidade — nº de fases aptas/trabalhadas
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_versatility_counts_apt_or_worked_phases():
    rows = [
        _row("LAM", "Laminagem", can_do=True, ops_count=50, days_ago=10),
        _row("PIN", "Pintura", can_do=True, ops_count=0, days_ago=None),
        _row("MON", "Montagem", can_do=False, ops_count=8, days_ago=30),
        _row("CUR", "Cura", can_do=False, ops_count=0, days_ago=None),
    ]
    svc = _service_with_skills(rows)
    m = await svc.qualification_metrics(uuid4())
    # LAM (apto), PIN (apto), MON (trabalhou) contam. CUR não.
    assert m.versatility == 3


@pytest.mark.asyncio
async def test_versatility_zero_when_no_skills():
    svc = _service_with_skills([])
    m = await svc.qualification_metrics(uuid4())
    assert m.versatility == 0
    assert m.recency_days is None
    assert m.productivity is None


# ─────────────────────────────────────────────────────────────────────────
# Recência — dias desde a última operação
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_recency_is_minimum_days_across_phases():
    rows = [
        _row("LAM", "Laminagem", can_do=True, ops_count=10, days_ago=40),
        _row("PIN", "Pintura", can_do=True, ops_count=5, days_ago=7),
    ]
    svc = _service_with_skills(rows)
    m = await svc.qualification_metrics(uuid4())
    # A operação mais recente foi há 7 dias.
    assert m.recency_days == 7


@pytest.mark.asyncio
async def test_recency_scoped_to_phase():
    rows = [
        _row("LAM", "Laminagem", can_do=True, ops_count=10, days_ago=40),
        _row("PIN", "Pintura", can_do=True, ops_count=5, days_ago=7),
    ]
    svc = _service_with_skills(rows)
    m = await svc.qualification_metrics(uuid4(), phase_id="LAM")
    assert m.recency_days == 40
    assert m.scope == "LAM"


@pytest.mark.asyncio
async def test_recency_scoped_to_area_group():
    rows = [
        _row("LAM", "Laminagem", can_do=True, ops_count=10, days_ago=40),
        _row("INF", "Laminagem Infusão", can_do=True, ops_count=5, days_ago=15),
        _row("PIN", "Pintura Acabamento", can_do=True, ops_count=5, days_ago=3),
    ]
    svc = _service_with_skills(rows)
    m = await svc.qualification_metrics(uuid4(), area_group="Laminagem")
    # Laminagem + Infusão estão ambas no grupo Laminagem; min(40,15)=15.
    assert m.recency_days == 15
    assert m.scope == "Laminagem"


@pytest.mark.asyncio
async def test_recency_none_when_no_history_in_scope():
    rows = [
        _row("PIN", "Pintura", can_do=True, ops_count=0, days_ago=None),
    ]
    svc = _service_with_skills(rows)
    m = await svc.qualification_metrics(uuid4())
    assert m.recency_days is None


# ─────────────────────────────────────────────────────────────────────────
# Produtividade — ops/dia
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_productivity_is_ops_per_day_over_span():
    rows = [
        _row("LAM", "Laminagem", can_do=True, ops_count=100, days_ago=100),
        _row("PIN", "Pintura", can_do=True, ops_count=0, days_ago=0),
    ]
    svc = _service_with_skills(rows)
    m = await svc.qualification_metrics(uuid4())
    # ops_total = 100, span = 100 dias → 1.0 ops/dia.
    assert m.ops_total == 100
    assert m.productivity == pytest.approx(1.0, abs=0.05)


@pytest.mark.asyncio
async def test_productivity_single_phase_does_not_divide_by_zero():
    rows = [
        _row("LAM", "Laminagem", can_do=True, ops_count=20, days_ago=5),
    ]
    svc = _service_with_skills(rows)
    m = await svc.qualification_metrics(uuid4())
    # Uma só fase → span 0 → assume 1 dia → 20 ops/dia. Sem ZeroDivision.
    assert m.productivity == 20.0


@pytest.mark.asyncio
async def test_productivity_none_when_no_ops():
    rows = [
        _row("PIN", "Pintura", can_do=True, ops_count=0, days_ago=None),
    ]
    svc = _service_with_skills(rows)
    m = await svc.qualification_metrics(uuid4())
    assert m.productivity is None
    assert m.ops_total == 0
