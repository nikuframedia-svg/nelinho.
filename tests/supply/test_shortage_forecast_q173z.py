"""Testes unitários ao motor de previsão de ruturas (Q.173.Z).

Foco: algoritmo de projeção puro (_project_stock, _calcular_sugestao,
_compute_consumos, _ordens_afetadas_para) — sem BD.

Padrão: dados sintéticos, sem mocks de BD (funções puras).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import pytest

from src.supply.services.shortage_forecast_service import (
    OrdemAfetada,
    _calcular_sugestao,
    _compute_consumos,
    _ordens_afetadas_para,
    _project_stock,
)

# ---------------------------------------------------------------------------
# _project_stock
# ---------------------------------------------------------------------------

HOJE = date(2026, 6, 11)


def test_project_stock_sem_consumo_sem_rutura():
    """Stock alto, sem consumo previsto → sem rutura."""
    resultado = _project_stock(
        stock_atual=500.0,
        reservas=0.0,
        entradas=[],
        consumos=[],
        min_stock=10.0,
        horizonte_dias=30,
        hoje=HOJE,
    )
    assert resultado is None


def test_project_stock_ja_em_rutura_hoje():
    """Stock abaixo do mínimo → rutura reportada em HOJE."""
    resultado = _project_stock(
        stock_atual=5.0,
        reservas=0.0,
        entradas=[],
        consumos=[],
        min_stock=10.0,
        horizonte_dias=30,
        hoje=HOJE,
    )
    assert resultado == HOJE


def test_project_stock_rutura_por_consumo():
    """Stock suficiente hoje mas consumo previsto esgota no dia 5."""
    consumos = [(HOJE + timedelta(days=i), 20.0) for i in range(1, 10)]
    resultado = _project_stock(
        stock_atual=90.0,
        reservas=0.0,
        entradas=[],
        consumos=consumos,
        min_stock=0.0,
        horizonte_dias=30,
        hoje=HOJE,
    )
    # 90 - 5×20 = -10 → rutura no dia 5
    assert resultado == HOJE + timedelta(days=5)


def test_project_stock_entradas_evitam_rutura():
    """PO chega antes do esgotamento → sem rutura."""
    consumos = [(HOJE + timedelta(days=i), 20.0) for i in range(1, 10)]
    eta = HOJE + timedelta(days=3)
    entradas = [(eta, 200.0, False)]  # (date, qty, eta_estimada)
    resultado = _project_stock(
        stock_atual=50.0,
        reservas=0.0,
        entradas=entradas,
        consumos=consumos,
        min_stock=0.0,
        horizonte_dias=30,
        hoje=HOJE,
    )
    assert resultado is None


def test_project_stock_reservas_deduzem_imediatamente():
    """Reservas abertas deduzem do saldo inicial — picking pendente."""
    resultado = _project_stock(
        stock_atual=100.0,
        reservas=95.0,  # deixa só 5
        entradas=[],
        consumos=[(HOJE + timedelta(days=1), 10.0)],
        min_stock=0.0,
        horizonte_dias=30,
        hoje=HOJE,
    )
    # saldo = 100 - 95 = 5; dia1: 5 - 10 = -5 → rutura dia 1
    assert resultado == HOJE + timedelta(days=1)


def test_project_stock_negativo_erp_ainda_compara_com_min():
    """Stock negativo (dado real ERP) → rutura em HOJE se abaixo do min."""
    resultado = _project_stock(
        stock_atual=-50.0,
        reservas=0.0,
        entradas=[],
        consumos=[],
        min_stock=0.0,
        horizonte_dias=30,
        hoje=HOJE,
    )
    assert resultado == HOJE


def test_project_stock_fora_do_horizonte_nao_conta():
    """Consumo após horizonte não afecta a projeção."""
    consumos = [(HOJE + timedelta(days=100), 1000.0)]  # fora dos 30 dias
    resultado = _project_stock(
        stock_atual=10.0,
        reservas=0.0,
        entradas=[],
        consumos=consumos,
        min_stock=0.0,
        horizonte_dias=30,
        hoje=HOJE,
    )
    assert resultado is None


# ---------------------------------------------------------------------------
# _calcular_sugestao
# ---------------------------------------------------------------------------

def test_sugestao_sem_rutura():
    sugestao, detalhe, limite = _calcular_sugestao(
        data_rutura=None,
        hoje=HOJE,
        lead_time_days=7,
        defice=0.0,
        outros_armazens=[],
        total_outros=0.0,
    )
    assert sugestao == "ok"
    assert limite is None


def test_sugestao_transferencia_quando_outro_armazem_tem_suficiente():
    sugestao, detalhe, limite = _calcular_sugestao(
        data_rutura=HOJE + timedelta(days=10),
        hoje=HOJE,
        lead_time_days=7,
        defice=50.0,
        outros_armazens=[{"warehouse_name": "Armazém B", "stock": 100.0}],
        total_outros=100.0,
    )
    assert sugestao == "transferencia"
    assert limite is None


def test_sugestao_compra_quando_ha_tempo():
    rutura = HOJE + timedelta(days=20)
    sugestao, detalhe, limite = _calcular_sugestao(
        data_rutura=rutura,
        hoje=HOJE,
        lead_time_days=7,
        defice=50.0,
        outros_armazens=[],
        total_outros=0.0,
    )
    assert sugestao == "compra"
    assert limite == rutura - timedelta(days=7)
    assert "Encomendar 50.0" in detalhe


def test_sugestao_replaneamento_quando_lead_time_nao_chega():
    rutura = HOJE + timedelta(days=3)
    sugestao, detalhe, limite = _calcular_sugestao(
        data_rutura=rutura,
        hoje=HOJE,
        lead_time_days=7,
        defice=50.0,
        outros_armazens=[],
        total_outros=0.0,
    )
    assert sugestao == "replaneamento"
    assert limite is not None
    assert (limite - HOJE).days < 0  # data no passado


# ---------------------------------------------------------------------------
# _compute_consumos
# ---------------------------------------------------------------------------

def _make_op(
    model_id: int,
    phase_id: int,
    start_day: date,
) -> dict:
    """Op sintética com order_id único por modelo (para testes unitários)."""
    return {
        "order_id": f"ord_{model_id}",
        "phase_id": phase_id,
        "start_time": datetime.combine(start_day, datetime.min.time()),
    }


def _order_map(*model_ids: int) -> dict:
    """Gera order_model_map sintético para testes: order_id=ord_N → model_id=N."""
    return {f"ord_{mid}": mid for mid in model_ids}


def test_compute_consumos_basico():
    """Duas ops do mesmo (model, phase) com BOM de 2 materiais."""
    ops = [
        _make_op(100, 10, HOJE + timedelta(days=5)),
        _make_op(100, 10, HOJE + timedelta(days=10)),
    ]
    bom_map = {
        (100, 10): [
            ("mat_A", 2.0, True),
            ("mat_B", 1.5, True),
        ]
    }
    consumos = _compute_consumos(ops, bom_map, _order_map(100), HOJE, horizonte_dias=60)
    assert "mat_A" in consumos
    assert "mat_B" in consumos
    # 2 ops × 2.0 = 4.0 total para mat_A
    total_A = sum(qty for _, qty in consumos["mat_A"])
    assert abs(total_A - 4.0) < 1e-9


def test_compute_consumos_sem_fase_usa_primeira_op():
    """Componente sem fase atribui à primeira op do modelo."""
    ops = [
        _make_op(200, 5, HOJE + timedelta(days=2)),  # primeira
        _make_op(200, 10, HOJE + timedelta(days=8)),
    ]
    bom_map = {
        (200, 5): [("mat_C", 3.0, False)],  # sem fase → atribuída à fase 5 (primeira)
    }
    consumos = _compute_consumos(ops, bom_map, _order_map(200), HOJE, horizonte_dias=60)
    assert "mat_C" in consumos


def test_compute_consumos_exclui_ops_fora_horizonte():
    """Ops fora do horizonte não geram consumo."""
    ops = [
        _make_op(300, 1, HOJE + timedelta(days=90)),  # fora
    ]
    bom_map = {(300, 1): [("mat_D", 5.0, True)]}
    consumos = _compute_consumos(ops, bom_map, _order_map(300), HOJE, horizonte_dias=60)
    assert "mat_D" not in consumos


def test_compute_consumos_agrega_por_dia():
    """Múltiplas ops no mesmo dia agregam em vez de duplicar."""
    ops = [
        _make_op(400, 2, HOJE + timedelta(days=3)),
        _make_op(400, 2, HOJE + timedelta(days=3)),
        _make_op(400, 2, HOJE + timedelta(days=3)),
    ]
    bom_map = {(400, 2): [("mat_E", 1.0, True)]}
    consumos = _compute_consumos(ops, bom_map, _order_map(400), HOJE, horizonte_dias=30)
    # 3 ops × 1.0 = 3.0 num único dia
    assert len(consumos["mat_E"]) == 1
    assert abs(consumos["mat_E"][0][1] - 3.0) < 1e-9


# ---------------------------------------------------------------------------
# _ordens_afetadas_para
# ---------------------------------------------------------------------------

def test_ordens_afetadas_filtra_por_data_rutura():
    """Só ops até à data de rutura incluídas."""
    rutura = HOJE + timedelta(days=5)
    ops = [
        _make_op(500, 1, HOJE + timedelta(days=2)),   # dentro
        _make_op(500, 1, HOJE + timedelta(days=8)),   # fora
    ]
    bom_map = {(500, 1): [("mat_F", 1.0, True)]}
    ordens = _ordens_afetadas_para("mat_F", ops, bom_map, rutura, HOJE, _order_map(500))
    assert len(ordens) == 1
    assert ordens[0].order_id == "ord_500"


def test_ordens_afetadas_limite_5():
    """Máximo de 5 ordens mesmo que haja mais."""
    rutura = HOJE + timedelta(days=30)
    ops = [
        {
            "order_id": f"ord_{600 + i}",
            "phase_id": 1,
            "start_time": datetime.combine(HOJE + timedelta(days=i + 1), datetime.min.time()),
        }
        for i in range(10)
    ]
    bom_map = {(600 + i, 1): [("mat_G", 1.0, True)] for i in range(10)}
    om = {f"ord_{600 + i}": 600 + i for i in range(10)}
    ordens = _ordens_afetadas_para("mat_G", ops, bom_map, rutura, HOJE, om)
    assert len(ordens) <= 5


def test_ordens_afetadas_dedup_por_order_id():
    """Várias ops da mesma ordem contam como uma única ordem afetada."""
    rutura = HOJE + timedelta(days=20)
    ops = [
        {"order_id": "ord_700", "phase_id": 1, "start_time": datetime.combine(HOJE + timedelta(days=2), datetime.min.time())},
        {"order_id": "ord_700", "phase_id": 2, "start_time": datetime.combine(HOJE + timedelta(days=4), datetime.min.time())},
    ]
    bom_map = {
        (700, 1): [("mat_H", 1.0, True)],
        (700, 2): [("mat_H", 1.0, True)],
    }
    ordens = _ordens_afetadas_para("mat_H", ops, bom_map, rutura, HOJE, {"ord_700": 700})
    assert len(ordens) == 1
    assert ordens[0].order_id == "ord_700"
