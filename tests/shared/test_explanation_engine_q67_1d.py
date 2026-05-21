"""Q.67.1.D - pin do comportamento actual de `_analyze_root_causes`.

O TODO original em `src/shared/explanation_engine.py:174` propunha enriquecer
a categorizacao de causas com dados de machine breakdown e material lot
tracking. Essas fontes nao existem no ERP nem nas tabelas internas:

- nao ha tabela `machine_breakdown` / `equipment_failure` / `machine_failure`
  (`__tablename__` ausente em todo o `src/`);
- `material_lot_id` existe apenas como FK em `ReworkEntry`; nao ha tabela
  `material_lot` / `lot_tracking` para enriquecer com fornecedor, recepcao,
  COA, etc.

Logo o TODO foi convertido em bloqueio documentado (issue Q.68.D). Estes
testes pin o comportamento actual para que, quando a ingestao chegar, o
contrato fique visivel no diff:

1. `machine_id IS NULL`  -> conta para "Machine Issues";
2. `machine_id IS NOT NULL` -> conta para "Capacity Constraints";
3. "Setup Delays" e "Material Shortages" ficam a zero (sem fonte de dados);
4. As quatro chaves canonicas continuam a existir no dict de saida.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.profit.explanation_engine import ExplanationEngine


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _row(machine_id: UUID | None) -> SimpleNamespace:
    """Build a row that quacks like the SELECT in explain_otd."""
    return SimpleNamespace(
        order_id=uuid4(),
        scheduled_end_date=None,
        actual_end=None,
        status=None,
        machine_id=machine_id,
    )


@pytest.fixture
def engine() -> ExplanationEngine:
    return ExplanationEngine(session=AsyncMock(), tenant_id=TENANT)


@pytest.mark.asyncio
async def test_analyze_root_causes_returns_canonical_four_keys(engine):
    """Pin: as 4 chaves canonicas sao sempre devolvidas, mesmo sem dados."""
    causes = await engine._analyze_root_causes([])
    assert set(causes.keys()) == {
        "Machine Issues",
        "Setup Delays",
        "Material Shortages",
        "Capacity Constraints",
    }
    for cause in causes.values():
        assert cause["count"] == 0
        assert cause["total_delay"] == 0


@pytest.mark.asyncio
async def test_analyze_root_causes_unassigned_goes_to_machine_issues(engine):
    """Pin: schedule.machine_id IS NULL -> Machine Issues."""
    late = [_row(None), _row(None), _row(None)]

    causes = await engine._analyze_root_causes(late)

    assert causes["Machine Issues"]["count"] == 3
    assert causes["Capacity Constraints"]["count"] == 0


@pytest.mark.asyncio
async def test_analyze_root_causes_assigned_goes_to_capacity(engine):
    """Pin: schedule.machine_id IS NOT NULL -> Capacity Constraints."""
    machine_a = UUID("11111111-1111-1111-1111-111111111111")
    machine_b = UUID("22222222-2222-2222-2222-222222222222")
    late = [_row(machine_a), _row(machine_a), _row(machine_b)]

    causes = await engine._analyze_root_causes(late)

    assert causes["Machine Issues"]["count"] == 0
    assert causes["Capacity Constraints"]["count"] == 3


@pytest.mark.asyncio
async def test_analyze_root_causes_setup_and_material_remain_zero(engine):
    """Pin do bloqueio Q.68.D: sem ingestao de machine_breakdown nem
    material_lot tracking, estas duas categorias ficam SEMPRE a zero,
    independentemente do mix de schedules atrasados.
    """
    machine_a = UUID("11111111-1111-1111-1111-111111111111")
    late = [
        _row(None),
        _row(machine_a),
        _row(None),
        _row(machine_a),
        _row(machine_a),
    ]

    causes = await engine._analyze_root_causes(late)

    # Ate haver fontes reais (issue Q.68.D), estas duas nao sao mexidas.
    assert causes["Setup Delays"]["count"] == 0
    assert causes["Material Shortages"]["count"] == 0
    # As outras duas absorvem tudo: 2 unassigned + 3 assigned = 5 total.
    assert causes["Machine Issues"]["count"] == 2
    assert causes["Capacity Constraints"]["count"] == 3
    assert (
        causes["Machine Issues"]["count"]
        + causes["Capacity Constraints"]["count"]
        == len(late)
    )


@pytest.mark.asyncio
async def test_analyze_root_causes_even_split_50_50(engine):
    """Pin: split paritario entre unassigned e assigned -> 50/50 entre as
    duas unicas categorias activas hoje.
    """
    machine_a = UUID("11111111-1111-1111-1111-111111111111")
    late = [_row(None), _row(machine_a)]

    causes = await engine._analyze_root_causes(late)

    assert causes["Machine Issues"]["count"] == 1
    assert causes["Capacity Constraints"]["count"] == 1
