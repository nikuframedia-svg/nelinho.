"""Q.173.U — testes do OrderMaterialsService.

Padrão: _CaptureSession captura SQL text gerado (sem BD real);
asserts sobre o SQL e sobre a lógica de agregação.

Cobertura:
  - movimento_types: constantes correctas
  - _reservas_abertas: SQL tem TPMOV=4 + MOV_SATISFEITO=false
  - _consumos: SQL tem TPMOV=11
  - materiais_restantes: agregação + stock_suficiente tri-state
  - OF sem movimentos → items=[] + fonte honesta
  - stock_suficiente=None quando sem snapshot
  - stock_suficiente=False quando stock < qty_res
  - stock_suficiente=True quando stock >= qty_res
"""
from __future__ import annotations

from typing import Any, List
from uuid import UUID

import pytest

from src.supply.movement_types import (
    TPMOV_CONSUMO_OF,
    TPMOV_RESERVA,
    TPMOV_CONSUMO_TIPOS,
    TPMOV_RESERVA_TIPOS,
)
from src.plan.services.order_materials_service import (
    OrderMaterialsService,
    OrdemMaterialsResult,
)

TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ---------------------------------------------------------------------------
# Constantes TPMOV

def test_tpmov_reserva_e_4():
    assert TPMOV_RESERVA == 4


def test_tpmov_consumo_of_e_11():
    assert TPMOV_CONSUMO_OF == 11


def test_tpmov_sets_corretos():
    assert TPMOV_RESERVA in TPMOV_RESERVA_TIPOS
    assert TPMOV_CONSUMO_OF in TPMOV_CONSUMO_TIPOS
    assert TPMOV_RESERVA not in TPMOV_CONSUMO_TIPOS
    assert TPMOV_CONSUMO_OF not in TPMOV_RESERVA_TIPOS


# ---------------------------------------------------------------------------
# _CaptureSession — captura SQL sem BD

class _FakeResult:
    def __init__(self, rows: List[tuple]) -> None:
        self._rows = rows

    def all(self) -> List[tuple]:
        return self._rows


class _CaptureSession:
    """Sessão fake que captura as queries SQL executadas."""

    def __init__(self, stock_rows: List[tuple] | None = None) -> None:
        self.sql_calls: List[str] = []
        self.params_calls: List[dict] = []
        self._stock_rows = stock_rows or []
        # reservas e consumos simulados (product_id, qty)
        self._reserva_rows: List[tuple] = []
        self._consumo_rows: List[tuple] = []

    def set_reservas(self, rows: List[tuple]) -> None:
        self._reserva_rows = rows

    def set_consumos(self, rows: List[tuple]) -> None:
        self._consumo_rows = rows

    async def execute(self, stmt: Any, params: dict | None = None) -> _FakeResult:
        sql_str = str(stmt)
        self.sql_calls.append(sql_str)
        self.params_calls.append(params or {})

        # Devolve linhas conforme o tipo de query (heurística no SQL)
        if "MOV_SATISFEITO" in sql_str:
            return _FakeResult(self._reserva_rows)
        if "TPMOV" in sql_str and "SATISFEITO" not in sql_str and "factory_raw.movimento" in sql_str:
            return _FakeResult(self._consumo_rows)
        if "warehouse_stock" in sql_str:
            return _FakeResult(self._stock_rows)
        if "factory_raw.produto" in sql_str:
            return _FakeResult([])
        return _FakeResult([])


# ---------------------------------------------------------------------------
# SQL gerado por _reservas_abertas

@pytest.mark.asyncio
async def test_reservas_abertas_sql_tem_tpmov_4():
    sess = _CaptureSession()
    svc = OrderMaterialsService(sess, TENANT)
    await svc._reservas_abertas(902252)

    sql = sess.sql_calls[0]
    assert '"MOV_TPMOV_ID" = :tpmov' in sql
    assert "MOV_SATISFEITO" in sql
    assert "factory_raw.movimento" in sql
    assert sess.params_calls[0]["tpmov"] == 4
    assert sess.params_calls[0]["of_id"] == 902252


@pytest.mark.asyncio
async def test_consumos_sql_tem_tpmov_11():
    sess = _CaptureSession()
    svc = OrderMaterialsService(sess, TENANT)
    await svc._consumos(902252)

    # A query de consumos é a segunda call (após a de reservas ser invocada
    # directamente aqui, é a primeira)
    sql = sess.sql_calls[0]
    assert '"MOV_TPMOV_ID" = :tpmov' in sql
    assert "factory_raw.movimento" in sql
    assert sess.params_calls[0]["tpmov"] == 11


# ---------------------------------------------------------------------------
# materiais_restantes — lógica de agregação

@pytest.mark.asyncio
async def test_of_sem_movimentos_devolve_lista_vazia():
    """OF sem reservas nem consumos → items=[], fonte honesta."""
    sess = _CaptureSession()
    svc = OrderMaterialsService(sess, TENANT)
    result = await svc.materiais_restantes(999999)

    assert isinstance(result, OrdemMaterialsResult)
    assert result.items == []
    assert result.fonte == "movimento(tpmov=4,11)"
    assert result.of_legacy_id == 999999


@pytest.mark.asyncio
async def test_stock_suficiente_none_quando_sem_snapshot():
    """Sem warehouse_stock → stock_suficiente=None (nunca bloqueia em ausência)."""
    sess = _CaptureSession(stock_rows=[])
    sess.set_reservas([(22394, 42.72)])
    svc = OrderMaterialsService(sess, TENANT)
    result = await svc.materiais_restantes(902252)

    assert len(result.items) == 1
    item = result.items[0]
    assert item.produto_id == 22394
    assert item.qty_reservada_aberta == 42.72
    assert item.stock_disponivel is None
    assert item.stock_suficiente is None
    assert result.stock_snapshot_disponivel is False


@pytest.mark.asyncio
async def test_stock_suficiente_false_quando_stock_insuficiente():
    """stock < qty_res → stock_suficiente=False (shortage detectado)."""
    # stock_rows: (product_id_int, total_stock)
    sess = _CaptureSession(stock_rows=[(22394, 10.0)])
    sess.set_reservas([(22394, 42.72)])
    svc = OrderMaterialsService(sess, TENANT)
    result = await svc.materiais_restantes(902252)

    item = result.items[0]
    assert item.stock_disponivel == 10.0
    assert item.stock_suficiente is False
    assert result.stock_snapshot_disponivel is True


@pytest.mark.asyncio
async def test_stock_suficiente_true_quando_stock_cobre():
    """stock >= qty_res → stock_suficiente=True."""
    sess = _CaptureSession(stock_rows=[(22394, 100.0)])
    sess.set_reservas([(22394, 42.72)])
    svc = OrderMaterialsService(sess, TENANT)
    result = await svc.materiais_restantes(902252)

    item = result.items[0]
    assert item.stock_suficiente is True


@pytest.mark.asyncio
async def test_consumo_aparece_sem_reserva():
    """Material só com consumos (TPMOV=11, sem reserva aberta) → qty_reservada_aberta=0."""
    sess = _CaptureSession(stock_rows=[])
    sess.set_consumos([(41902, 11.0)])
    svc = OrderMaterialsService(sess, TENANT)
    result = await svc.materiais_restantes(902252)

    assert len(result.items) == 1
    item = result.items[0]
    assert item.produto_id == 41902
    assert item.qty_reservada_aberta == 0.0
    assert item.qty_consumida == 11.0


@pytest.mark.asyncio
async def test_reserva_e_consumo_combinados():
    """Produto com reserva aberta E consumo → ambos somados correctamente."""
    sess = _CaptureSession(stock_rows=[(22394, 50.0)])
    sess.set_reservas([(22394, 30.0)])
    sess.set_consumos([(22394, 10.0)])
    svc = OrderMaterialsService(sess, TENANT)
    result = await svc.materiais_restantes(902252)

    assert len(result.items) == 1
    item = result.items[0]
    assert item.qty_reservada_aberta == 30.0
    assert item.qty_consumida == 10.0
    assert item.stock_disponivel == 50.0
    assert item.stock_suficiente is True  # 50 >= 30
