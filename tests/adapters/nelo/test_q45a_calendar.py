"""Q.45.A — readers ERP do calendário de capacidade.

`DIAS_TRABALHO` (~15.6 k linhas) é o calendário de dias de trabalho;
`FERIAS` (~29) e `DIAS_FERIADOS_FERIAS` (~14) dão férias/feriados. As
queries correm contra o SQL Server da NELO (não testável sem o ERP);
aqui verifica-se o contrato dos schemas + que o SQL aponta às
tabelas/colunas certas. `_fetch_all` é substituído por um fake — igual
ao padrão de `test_q36_readers.py`.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.adapters.nelo import services
from src.adapters.nelo.schemas import (
    HolidayDefinitionRow,
    HolidayRow,
    WorkDayRow,
)


def test_work_day_row_from_erp_mapping():
    """Uma linha de `DIAS_TRABALHO` (column→value) constrói a WorkDayRow."""
    row = WorkDayRow(work_day_id=341, work_date=datetime(2016, 1, 4))
    assert row.work_day_id == 341
    assert row.work_date == datetime(2016, 1, 4)


def test_holiday_row_keeps_raw_kind():
    """`FERIAS.TIPO` é o valor cru ("Férias"/"Feriado") — sem enum inventado."""
    row = HolidayRow(holiday_date=datetime(2012, 2, 20), kind="Férias")
    assert row.kind == "Férias"


def test_holiday_definition_row_from_erp_mapping():
    """Uma linha de `DIAS_FERIADOS_FERIAS` constrói a HolidayDefinitionRow."""
    row = HolidayDefinitionRow(
        definition_id=1, month=1, day=1, is_fixed=True,
        is_vacation=False, is_holiday=True, description="Dia de Ano Novo",
    )
    assert row.month == 1 and row.day == 1
    assert row.is_holiday is True
    assert row.description == "Dia de Ano Novo"


def test_work_days_view_targets_real_erp_table():
    sql = services._VW_WORK_DAYS_SQL
    assert "dbo.DIAS_TRABALHO" in sql
    assert "DTRB_ID" in sql
    assert "DTRB_DATA" in sql


def test_holidays_view_targets_real_erp_table():
    sql = services._VW_HOLIDAYS_SQL
    assert "dbo.FERIAS" in sql
    assert "f.DATA" in sql
    assert "f.TIPO" in sql


def test_holiday_defs_view_targets_real_erp_table():
    sql = services._VW_HOLIDAY_DEFS_SQL
    assert "dbo.DIAS_FERIADOS_FERIAS" in sql
    assert "DFF_ID" in sql
    assert "DFF_MES" in sql
    assert "DFF_DIA" in sql
    assert "DFF_FERIADO" in sql


@pytest.mark.asyncio
async def test_list_work_days_orders_by_date(monkeypatch):
    captured = {}

    async def fake(sql, params=None):
        captured["sql"] = sql
        return [{"work_day_id": 341, "work_date": datetime(2016, 1, 4)}]

    monkeypatch.setattr(services, "_fetch_all", fake)
    rows = await services.list_work_days()
    assert "ORDER BY v.work_date" in captured["sql"]
    assert len(rows) == 1
    assert isinstance(rows[0], WorkDayRow)


@pytest.mark.asyncio
async def test_list_holidays_builds_rows(monkeypatch):
    async def fake(sql, params=None):
        return [{"holiday_date": datetime(2012, 2, 21), "kind": "Feriado"}]

    monkeypatch.setattr(services, "_fetch_all", fake)
    rows = await services.list_holidays()
    assert rows[0].kind == "Feriado"


@pytest.mark.asyncio
async def test_list_holiday_definitions_builds_rows(monkeypatch):
    async def fake(sql, params=None):
        return [{
            "definition_id": 2, "month": 3, "day": 30, "is_fixed": False,
            "is_vacation": False, "is_holiday": True,
            "description": "Sexta-feira Santa",
        }]

    monkeypatch.setattr(services, "_fetch_all", fake)
    rows = await services.list_holiday_definitions()
    assert rows[0].description == "Sexta-feira Santa"


def test_q45a_readers_are_exported():
    for name in (
        "list_work_days",
        "list_holidays",
        "list_holiday_definitions",
    ):
        assert name in services.__all__
