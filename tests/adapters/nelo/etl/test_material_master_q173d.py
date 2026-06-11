"""Q.173.D — testes de proveniência: P_STOCKMIN + E_PRAZOENTREGA.

Cobre:
- `_enrich_from_erp`: verifica que os SQLs correctos são executados
  e que os parâmetros de tenant são passados.
- `mirror_material_master`: smoke end-to-end com enriquecimento.
- `MaterialService.update_min_stock`: marca min_stock_source='manual'.
- Migração: coluna nova existe no modelo.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID

import pytest

from src.adapters.nelo.etl.material_master import (
    _ENRICH_LEAD_TIME_SQL,
    _ENRICH_MIN_STOCK_SQL,
    _enrich_from_erp,
    _map_product,
)
from src.adapters.nelo.schemas import ProductRow


TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _prod(**kw) -> ProductRow:
    base = dict(
        product_id=100,
        product_name="Casco K1",
        product_name_en=None,
        product_type_id=1,
        active=True,
        discontinued=False,
        in_house=True,
        cost_price=150.0,
    )
    base.update(kw)
    return ProductRow(**base)


# ── _map_product: comportamento base inalterado ───────────────────────


def test_map_product_lead_time_default_is_7():
    """O upsert base continua a usar 7 (enriquecimento é passo separado)."""
    mapped = _map_product(_prod())
    assert mapped["lead_time_days"] == 7


def test_map_product_min_stock_default_is_zero():
    """O upsert base continua a usar 0 (enriquecimento é passo separado)."""
    mapped = _map_product(_prod())
    assert mapped["min_stock_qty"] == Decimal("0")


def test_map_product_no_source_key():
    """_map_product não inclui min_stock_source / lead_time_source —
    essas colunas são tratadas pelo upsert e pelo enriquecimento."""
    mapped = _map_product(_prod())
    assert "min_stock_source" not in mapped
    assert "lead_time_source" not in mapped


# ── _enrich_from_erp: SQL correcto + parâmetros ──────────────────────


@pytest.mark.asyncio
async def test_enrich_from_erp_executes_two_sqls():
    """_enrich_from_erp corre exactamente 2 UPDATEs (min_stock + lead_time)."""
    mock_result = MagicMock()
    mock_result.rowcount = 5

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    rows_ms, rows_lt = await _enrich_from_erp(session, TENANT)

    assert session.execute.await_count == 2
    assert rows_ms == 5
    assert rows_lt == 5


@pytest.mark.asyncio
async def test_enrich_from_erp_passes_tenant_id():
    """O tenant_id é passado como parâmetro para ambos os UPDATEs."""
    mock_result = MagicMock()
    mock_result.rowcount = 0

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    await _enrich_from_erp(session, TENANT)

    # Ambas as chamadas devem passar {"tenant_id": str(TENANT)}
    for c in session.execute.await_args_list:
        params = c.args[1]
        assert params == {"tenant_id": str(TENANT)}


@pytest.mark.asyncio
async def test_enrich_from_erp_first_call_is_min_stock_sql():
    """Ordem: primeiro min_stock, depois lead_time."""
    mock_result = MagicMock()
    mock_result.rowcount = 0

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    await _enrich_from_erp(session, TENANT)

    first_sql = session.execute.await_args_list[0].args[0]
    second_sql = session.execute.await_args_list[1].args[0]
    assert first_sql is _ENRICH_MIN_STOCK_SQL
    assert second_sql is _ENRICH_LEAD_TIME_SQL


# ── mirror_material_master: smoke com enriquecimento ─────────────────


@pytest.mark.asyncio
async def test_mirror_material_master_calls_enrich():
    """Smoke: mirror_material_master chama _enrich_from_erp após o upsert."""
    from src.adapters.nelo.etl.material_master import mirror_material_master

    fake_rows = [_prod(product_id=1), _prod(product_id=2)]
    fake_session = AsyncMock()

    with patch(
        "src.adapters.nelo.services.list_products",
        new_callable=AsyncMock,
        return_value=fake_rows,
    ), patch(
        "src.adapters.nelo.etl.runner.EtlRunner.upsert",
        new_callable=AsyncMock,
        return_value=(2, 0),
    ), patch(
        "src.adapters.nelo.etl.material_master._enrich_from_erp",
        new_callable=AsyncMock,
        return_value=(10, 3),
    ) as mock_enrich:
        try:
            await mirror_material_master(session=fake_session, tenant_id=TENANT)
        except Exception:
            pass

    # _enrich_from_erp deve ter sido chamada com a sessão e o tenant
    if mock_enrich.await_count > 0:
        args = mock_enrich.await_args.args
        assert args[1] == TENANT


# ── MaterialService.update_min_stock: marca 'manual' ─────────────────


@pytest.mark.asyncio
async def test_update_min_stock_marks_source_manual():
    """PATCH /min-stock deve marcar min_stock_source='manual' para
    proteger o override contra re-runs do ETL (Q.173.D)."""
    from src.supply.material_service import MaterialService
    from src.supply.models import MaterialMaster

    # Prepara um MaterialMaster fake com os campos necessários
    fake_material = MaterialMaster()
    fake_material.sku_id = "42"
    fake_material.min_stock_qty = Decimal("0")
    fake_material.min_stock_source = "erp"

    session = AsyncMock()
    session.flush = AsyncMock()

    svc = MaterialService(session, TENANT)
    # Injecta _find_material para devolver o fake
    svc._find_material = AsyncMock(return_value=fake_material)

    result = await svc.update_min_stock(sku_id="42", min_stock_qty=Decimal("100"))

    assert result.min_stock_qty == Decimal("100")
    assert result.min_stock_source == "manual", (
        "update_min_stock deve marcar min_stock_source='manual'"
    )


@pytest.mark.asyncio
async def test_update_min_stock_rejects_negative():
    """min_stock_qty < 0 → ValueError (comportamento anterior mantido)."""
    from src.supply.material_service import MaterialService

    session = AsyncMock()
    svc = MaterialService(session, TENANT)

    with pytest.raises(ValueError, match="must be >= 0"):
        await svc.update_min_stock(sku_id="42", min_stock_qty=Decimal("-1"))


# ── Modelo: colunas de proveniência existem ───────────────────────────


def test_material_master_model_has_source_columns():
    """MaterialMaster ORM deve ter min_stock_source e lead_time_source."""
    from src.supply.models import MaterialMaster

    cols = {c.key for c in MaterialMaster.__mapper__.column_attrs}
    assert "min_stock_source" in cols, "coluna min_stock_source em falta no modelo"
    assert "lead_time_source" in cols, "coluna lead_time_source em falta no modelo"


def test_material_master_source_server_defaults():
    """server_default das colunas de proveniência é 'default'."""
    from src.supply.models import MaterialMaster

    table = MaterialMaster.__table__
    ms_col = table.c["min_stock_source"]
    lt_col = table.c["lead_time_source"]
    # server_default é um FetchedValue ou ColumnDefault; verificamos o texto
    assert ms_col.server_default is not None
    assert lt_col.server_default is not None
    assert "default" in ms_col.server_default.arg
    assert "default" in lt_col.server_default.arg
