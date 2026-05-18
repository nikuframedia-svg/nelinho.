"""Q.36.A — readers do adaptador ERP para o pipeline causal.

`OF_CHECKLIST` (≈3 M linhas) é a fonte real de retrabalho; `OFFP_EQ`
(≈1.4 M) liga operador↔operação. As queries correm contra o SQL Server
da NELO (não testável sem o ERP); aqui verifica-se o contrato dos
schemas + que o SQL das views aponta às tabelas certas.
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest

from src.adapters.nelo import services
from src.adapters.nelo.schemas import (
    ChecklistRow,
    MoldMovementRow,
    OperationCrewRow,
    OperationRow,
)


def test_checklist_row_from_erp_mapping():
    """Uma linha de `OF_CHECKLIST` (column→value) constrói a ChecklistRow."""
    row = {
        "checklist_id": 1, "work_order_id": 5000, "operation_id": 88,
        "phase_id": 18, "phase_name": "Pintura Acabamento",
        "description": "Interior enrugado", "description_en": None,
        "severity": 3, "mold_repair": True, "blame_chefe": False,
        "blame_operation_id": 70, "resolved": False, "state": 1,
        "verified_at": None, "updated_at": None, "detected_at": None,
        "operation_mold_id": 777,
    }
    chk = ChecklistRow(**row)
    assert chk.description == "Interior enrugado"
    assert chk.mold_repair is True
    assert chk.operation_mold_id == 777


def test_operation_crew_row_from_erp_mapping():
    """Uma linha de `OF_FP × OFFP_EQ` constrói a OperationCrewRow."""
    crew = OperationCrewRow(
        operation_id=88, work_order_id=5000, phase_id=18,
        operator_id=42, is_chefe=True,
    )
    assert crew.operator_id == 42
    assert crew.is_chefe is True


def test_operation_row_carries_operation_mold():
    """Q.36.A — o molde por-operação (`OFFP_OF_ID_MLD`) é distinto do
    molde a nível de ordem (`mold_work_order_id`)."""
    op = OperationRow(
        operation_id=1, work_order_id=5, phase_id=18, phase_name="Laminagem",
        standard_time_hours=1.0, temperature=20.0, humidity=50.0,
        is_return=False, severe_return=False, product_id=9,
        operation_mold_id=777, mold_work_order_id=900,
    )
    assert op.operation_mold_id == 777
    assert op.mold_work_order_id == 900


def test_checklist_view_targets_real_erp_tables():
    """O SQL da checklist lê `OF_CHECKLIST` + junta `OF_FP` (molde) — NÃO
    as colunas `OFFP_PROBS_*` vazias que o mirror antigo lia."""
    sql = services._VW_CHECKLIST_SQL
    assert "dbo.OF_CHECKLIST" in sql
    assert "OFCH_DESCR" in sql
    assert "OFCH_MOLDE_REPARAR" in sql
    assert "OFFP_OF_ID_MLD" in sql  # molde por operação
    assert "OFFP_PROBS_" not in sql  # a fonte errada/vazia


def test_operation_crew_view_joins_offp_eq():
    sql = services._VW_OPERATION_CREW_SQL
    assert "dbo.OFFP_EQ" in sql
    assert "OFFPEQ_E_ID" in sql
    assert "OFFPEQ_OFFP_ID" in sql


def test_q36_readers_are_exported():
    assert "list_checklist_incidents" in services.__all__
    assert "list_operation_crew" in services.__all__


@pytest.mark.asyncio
async def test_list_operations_default_excludes_open_wip(monkeypatch):
    """Sem `include_open` a janela filtra só por `end_at` — o contrato
    histórico que o time_mining/oee dependem (operações concluídas)."""
    captured = {}

    async def fake(sql, params=None):
        captured["sql"] = sql
        return []

    monkeypatch.setattr(services, "_fetch_all", fake)
    await services.list_operations(
        date_from=date(2026, 4, 1), date_to=date(2026, 5, 1),
    )
    assert "v.end_at IS NULL" not in captured["sql"]
    assert "v.end_at >= :date_from" in captured["sql"]


@pytest.mark.asyncio
async def test_list_operations_include_open_brings_wip(monkeypatch):
    """`include_open=True` acrescenta as operações em curso (`end_at`
    NULL, `start_at` na janela) — o WIP que o OverloadDetector precisa."""
    captured = {}

    async def fake(sql, params=None):
        captured["sql"] = sql
        return []

    monkeypatch.setattr(services, "_fetch_all", fake)
    await services.list_operations(
        date_from=date(2026, 4, 1), date_to=date(2026, 5, 1),
        include_open=True,
    )
    sql = captured["sql"]
    assert "v.end_at IS NULL" in sql
    assert "v.start_at >= :date_from" in sql


# ─── Q.38.A — MOLDES_MOV reader ────────────────────────────────────────


def test_mold_movement_row_from_erp_mapping():
    """Uma linha de `MOLDES_MOV` (column→value) constrói a MoldMovementRow."""
    row = {
        "mold_movement_id": 12,
        "moved_at": datetime(2024, 3, 1, 9, 30),
        "movement_type_id": 2,
        "mold_id": 70004,
        "entity_id": 815,
    }
    mov = MoldMovementRow(**row)
    assert mov.mold_movement_id == 12
    assert mov.mold_id == 70004
    assert mov.entity_id == 815
    assert mov.moved_at == datetime(2024, 3, 1, 9, 30)


def test_mold_movement_view_targets_real_erp_table():
    """O SQL aponta a `MOLDES_MOV` e usa os nomes de coluna `MLDU_*`
    verificados no schema discovery — sem nomes inventados."""
    sql = services._VW_MOLD_MOVEMENTS_SQL
    assert "dbo.MOLDES_MOV" in sql
    assert "MLDU_ID" in sql
    assert "MLDU_DATA" in sql
    assert "MLDU_TP_ID" in sql
    assert "MLDU_MLD_ID" in sql  # FK → MOLDES.MLD_ID
    assert "MLDU_E_ID" in sql


def test_list_mold_movements_is_exported():
    assert "list_mold_movements" in services.__all__


@pytest.mark.asyncio
async def test_list_mold_movements_orders_recent_first(monkeypatch):
    """O reader ordena por `moved_at` DESC — movimento mais recente
    primeiro — e constrói schemas frozen a partir das row mappings."""
    captured = {}

    async def fake(sql, params=None):
        captured["sql"] = sql
        return [
            {
                "mold_movement_id": 1,
                "moved_at": datetime(2024, 1, 5, 8, 0),
                "movement_type_id": 1,
                "mold_id": 70004,
                "entity_id": 815,
            },
        ]

    monkeypatch.setattr(services, "_fetch_all", fake)
    rows = await services.list_mold_movements()

    assert "ORDER BY v.moved_at DESC" in captured["sql"]
    assert len(rows) == 1
    assert isinstance(rows[0], MoldMovementRow)
    assert rows[0].mold_id == 70004
