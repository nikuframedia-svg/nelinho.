"""Q.45.C — readers ERP de energia (sensores IoT) e KPI.

`IOT_SENSOR_DATA` (~3.6 M linhas) dá a potência trifásica para o custo
de energia; `KPI` (~115) e `KPI_OBJECTIVO` (~267) dão as definições e
objectivos de KPI já na ERP. As queries correm contra o SQL Server da
NELO (não testável sem o ERP); aqui verifica-se o contrato dos schemas
+ que o SQL aponta às tabelas/colunas certas. `_fetch_all` é
substituído por um fake — igual ao padrão de `test_q36_readers.py`.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from src.adapters.nelo import services
from src.adapters.nelo.schemas import (
    IotSensorDataRow,
    KpiObjectiveRow,
    KpiRow,
)


def test_iot_sensor_data_row_from_erp_mapping():
    """Uma linha de `IOT_SENSOR_DATA` constrói a IotSensorDataRow."""
    row = IotSensorDataRow(
        sample_id=99, sensor_id=4, sampled_at=datetime(2026, 5, 1, 8, 0),
        power_1=1200, power_2=1180, power_3=1210,
        current_1=5.4, current_2=5.3, current_3=5.5,
        temperature=22.0, humidity=48.0, pressure=1013.0,
    )
    assert row.power_1 == 1200
    assert row.current_3 == 5.5
    assert row.sensor_id == 4


def test_kpi_row_from_erp_mapping():
    """Uma linha de `KPI` (column→value) constrói a KpiRow."""
    row = KpiRow(
        kpi_id=1, kpi_date=date(2025, 2, 11), name="OEE",
        description="Eficiência global", parent_kpi_id=None,
        display_order=1, is_automatic=True, role=None,
    )
    assert row.name == "OEE"
    assert row.is_automatic is True


def test_kpi_objective_row_from_erp_mapping():
    """Uma linha de `KPI_OBJECTIVO` constrói a KpiObjectiveRow."""
    row = KpiObjectiveRow(
        objective_id=5, kpi_id=1, objective_date_logged=date(2025, 2, 11),
        value=0.72, objective=0.80, objective_date=date(2025, 3, 1),
    )
    assert row.value == 0.72
    assert row.objective == 0.80


def test_iot_sensor_data_view_targets_real_erp_table():
    sql = services._VW_IOT_SENSOR_DATA_SQL
    assert "dbo.IOT_SENSOR_DATA" in sql
    assert "SD_ID" in sql
    assert "SD_SENSOR_ID" in sql
    assert "SD_DATE" in sql
    assert "SD_POWER_1" in sql
    assert "SD_CURRENT_3" in sql


def test_kpi_views_target_real_erp_tables():
    kpi_sql = services._VW_KPI_SQL
    assert "dbo.KPI" in kpi_sql
    assert "KPI_NOME" in kpi_sql
    assert "KPI_AUTOMATICO" in kpi_sql

    obj_sql = services._VW_KPI_OBJECTIVES_SQL
    assert "dbo.KPI_OBJECTIVO" in obj_sql
    assert "KPIO_VALOR" in obj_sql
    assert "KPIO_OBJECTIVO" in obj_sql


@pytest.mark.asyncio
async def test_list_iot_sensor_data_requires_date_window(monkeypatch):
    """`IOT_SENSOR_DATA` é enorme — o reader filtra por `sampled_at`."""
    captured = {}

    async def fake(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr(services, "_fetch_all", fake)
    await services.list_iot_sensor_data(
        date_from=date(2026, 5, 1), date_to=date(2026, 5, 17),
    )
    assert "v.sampled_at >= :date_from" in captured["sql"]
    assert "v.sampled_at <  :date_to_plus_one" in captured["sql"]
    assert "date_to_plus_one" in captured["params"]


@pytest.mark.asyncio
async def test_list_kpi_definitions_orders_by_display_order(monkeypatch):
    captured = {}

    async def fake(sql, params=None):
        captured["sql"] = sql
        return [{
            "kpi_id": 1, "kpi_date": date(2025, 2, 11), "name": "OEE",
            "description": None, "parent_kpi_id": None, "display_order": 1,
            "is_automatic": True, "role": None,
        }]

    monkeypatch.setattr(services, "_fetch_all", fake)
    rows = await services.list_kpi_definitions()
    assert "ORDER BY v.display_order" in captured["sql"]
    assert isinstance(rows[0], KpiRow)


@pytest.mark.asyncio
async def test_list_kpi_objectives_builds_rows(monkeypatch):
    async def fake(sql, params=None):
        return [{
            "objective_id": 5, "kpi_id": 1,
            "objective_date_logged": date(2025, 2, 11), "value": 0.72,
            "objective": 0.80, "objective_date": None,
        }]

    monkeypatch.setattr(services, "_fetch_all", fake)
    rows = await services.list_kpi_objectives()
    assert rows[0].objective == 0.80


def test_q45c_readers_are_exported():
    for name in (
        "list_iot_sensor_data",
        "list_kpi_definitions",
        "list_kpi_objectives",
    ):
        assert name in services.__all__
