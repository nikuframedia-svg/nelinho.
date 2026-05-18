"""Q.45.B — readers ERP de qualidade (zona de defeito) e ambiente (cura).

`OFCH_LOCAL` (~58 k linhas) liga incidente de checklist à zona do casco;
`TH` (~586 k) dá leituras de temperatura/humidade. As queries correm
contra o SQL Server da NELO (não testável sem o ERP); aqui verifica-se
o contrato dos schemas + que o SQL aponta às tabelas/colunas certas.
`_fetch_all` é substituído por um fake — igual ao padrão de
`test_q36_readers.py`.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from src.adapters.nelo import services
from src.adapters.nelo.schemas import ChecklistLocationRow, TempHumidityRow


def test_checklist_location_row_from_erp_mapping():
    """Uma linha de `OFCH_LOCAL`×`PROBS_LOCAL` constrói a ChecklistLocationRow."""
    row = ChecklistLocationRow(
        checklist_id=1670295, location_id=6, location_description="Casco",
    )
    assert row.checklist_id == 1670295
    assert row.location_id == 6
    assert row.location_description == "Casco"


def test_temp_humidity_row_from_erp_mapping():
    """Uma linha de `TH` (column→value) constrói a TempHumidityRow."""
    row = TempHumidityRow(
        reading_id=10, measured_at=datetime(2024, 2, 1, 10, 0),
        temperature=21.5, humidity=55.0, phase_id=18, probe_id=3,
    )
    assert row.temperature == 21.5
    assert row.humidity == 55.0
    assert row.probe_id == 3


def test_checklist_locations_view_joins_probs_local():
    """O SQL liga `OFCH_LOCAL` a `PROBS_LOCAL` para a descrição da zona."""
    sql = services._VW_CHECKLIST_LOCATIONS_SQL
    assert "dbo.OFCH_LOCAL" in sql
    assert "dbo.PROBS_LOCAL" in sql
    assert "OFPROBS_OFCH_ID" in sql
    assert "OFPROBS_PROBSL_ID" in sql
    assert "PROBSL_DSCR" in sql


def test_temp_humidity_view_targets_real_erp_table():
    sql = services._VW_TEMP_HUMIDITY_SQL
    assert "dbo.TH" in sql
    assert "TH_ID" in sql
    assert "TH_DATA" in sql
    assert "TH_TEMP" in sql
    assert "TH_FASE" in sql
    assert "TH_SONDA" in sql


@pytest.mark.asyncio
async def test_list_checklist_locations_orders_by_id(monkeypatch):
    captured = {}

    async def fake(sql, params=None):
        captured["sql"] = sql
        return [{
            "checklist_id": 1670295, "location_id": 6,
            "location_description": "Casco",
        }]

    monkeypatch.setattr(services, "_fetch_all", fake)
    rows = await services.list_checklist_locations()
    assert "ORDER BY v.checklist_id" in captured["sql"]
    assert isinstance(rows[0], ChecklistLocationRow)


@pytest.mark.asyncio
async def test_list_temperature_humidity_requires_date_window(monkeypatch):
    """`TH` é grande — o reader filtra por `measured_at` na janela dada."""
    captured = {}

    async def fake(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr(services, "_fetch_all", fake)
    await services.list_temperature_humidity(
        date_from=date(2026, 4, 1), date_to=date(2026, 5, 1),
    )
    assert "v.measured_at >= :date_from" in captured["sql"]
    assert "v.measured_at <  :date_to_plus_one" in captured["sql"]
    assert "date_from" in captured["params"]
    assert "date_to_plus_one" in captured["params"]


def test_q45b_readers_are_exported():
    for name in ("list_checklist_locations", "list_temperature_humidity"):
        assert name in services.__all__
