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
    data_rutura, saldo_minimo = _project_stock(
        stock_atual=500.0,
        reservas=0.0,
        entradas=[],
        consumos=[],
        min_stock=10.0,
        horizonte_dias=30,
        hoje=HOJE,
    )
    assert data_rutura is None
    assert saldo_minimo == 500.0


def test_project_stock_ja_em_rutura_hoje():
    """Stock abaixo do mínimo → rutura reportada em HOJE."""
    data_rutura, saldo_minimo = _project_stock(
        stock_atual=5.0,
        reservas=0.0,
        entradas=[],
        consumos=[],
        min_stock=10.0,
        horizonte_dias=30,
        hoje=HOJE,
    )
    assert data_rutura == HOJE
    # Q.173.AO — défice real = min_stock − saldo_minimo = 10 − 5 = 5
    assert saldo_minimo == 5.0


def test_project_stock_rutura_por_consumo():
    """Stock suficiente hoje mas consumo previsto esgota no dia 5."""
    consumos = [(HOJE + timedelta(days=i), 20.0) for i in range(1, 10)]
    data_rutura, saldo_minimo = _project_stock(
        stock_atual=90.0,
        reservas=0.0,
        entradas=[],
        consumos=consumos,
        min_stock=0.0,
        horizonte_dias=30,
        hoje=HOJE,
    )
    # 90 - 5×20 = -10 → rutura no dia 5
    assert data_rutura == HOJE + timedelta(days=5)
    # ponto mais fundo = fim dos 9 dias de consumo: 90 − 180 = −90
    assert saldo_minimo == -90.0


def test_project_stock_entradas_evitam_rutura():
    """PO chega antes do esgotamento → sem rutura."""
    consumos = [(HOJE + timedelta(days=i), 20.0) for i in range(1, 10)]
    eta = HOJE + timedelta(days=3)
    entradas = [(eta, 200.0, False)]  # (date, qty, eta_estimada)
    data_rutura, _ = _project_stock(
        stock_atual=50.0,
        reservas=0.0,
        entradas=entradas,
        consumos=consumos,
        min_stock=0.0,
        horizonte_dias=30,
        hoje=HOJE,
    )
    assert data_rutura is None


def test_project_stock_reservas_deduzem_imediatamente():
    """Reservas abertas deduzem do saldo inicial — picking pendente."""
    data_rutura, _ = _project_stock(
        stock_atual=100.0,
        reservas=95.0,  # deixa só 5
        entradas=[],
        consumos=[(HOJE + timedelta(days=1), 10.0)],
        min_stock=0.0,
        horizonte_dias=30,
        hoje=HOJE,
    )
    # saldo = 100 - 95 = 5; dia1: 5 - 10 = -5 → rutura dia 1
    assert data_rutura == HOJE + timedelta(days=1)


def test_project_stock_negativo_erp_ainda_compara_com_min():
    """Stock negativo (dado real ERP) → rutura em HOJE se abaixo do min."""
    data_rutura, saldo_minimo = _project_stock(
        stock_atual=-50.0,
        reservas=0.0,
        entradas=[],
        consumos=[],
        min_stock=0.0,
        horizonte_dias=30,
        hoje=HOJE,
    )
    assert data_rutura == HOJE
    assert saldo_minimo == -50.0


def test_project_stock_fora_do_horizonte_nao_conta():
    """Consumo após horizonte não afecta a projeção."""
    consumos = [(HOJE + timedelta(days=100), 1000.0)]  # fora dos 30 dias
    data_rutura, _ = _project_stock(
        stock_atual=10.0,
        reservas=0.0,
        entradas=[],
        consumos=consumos,
        min_stock=0.0,
        horizonte_dias=30,
        hoje=HOJE,
    )
    assert data_rutura is None


def test_project_stock_defice_vs_min_stock_q173ao():
    """Caso real Q.173.AO: saldo positivo mas abaixo do mínimo do ERP.

    O défice antigo media contra zero → 0.0 "rutura sem défice" na página
    /materiais. O défice real é min_stock − saldo_minimo.
    """
    data_rutura, saldo_minimo = _project_stock(
        stock_atual=1562.0,
        reservas=600.0,  # saldo = 962
        entradas=[],
        consumos=[],
        min_stock=1000.0,
        horizonte_dias=60,
        hoje=HOJE,
    )
    assert data_rutura == HOJE
    defice = max(0.0, 1000.0 - saldo_minimo)
    assert defice == 38.0  # 1000 − 962 — acionável, não 0.0


# ---------------------------------------------------------------------------
# _calcular_sugestao
# ---------------------------------------------------------------------------

def test_sugestao_sem_rutura():
    sugestao, detalhe, limite = _calcular_sugestao(
        data_rutura=None,
        hoje=HOJE,
        lead_time_days=7,
        defice=0.0,
    )
    assert sugestao == "ok"
    assert limite is None


def test_sugestao_transferencia_removida_q173ao():
    """Q.173.AO: 'transferencia' não existe mais — o saldo agrega todos os
    armazéns, mover stock entre eles nunca corrige o total (era dupla contagem).
    """
    import inspect

    src = inspect.getsource(_calcular_sugestao)
    assert '"transferencia"' not in src
    assert "total_outros" not in src


def test_sugestao_compra_quando_ha_tempo():
    rutura = HOJE + timedelta(days=20)
    sugestao, detalhe, limite = _calcular_sugestao(
        data_rutura=rutura,
        hoje=HOJE,
        lead_time_days=7,
        defice=50.0,
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
    )
    assert sugestao == "replaneamento"
    assert limite is not None
    assert (limite - HOJE).days < 0  # data no passado


def test_load_reservas_exclui_ofs_fechadas_q173ao():
    """Guard estático: o SQL das reservas exclui OFs já fechadas (lixo
    histórico — 10.268 reservas abertas de OFs com OF_DATAFIM preenchida).
    """
    import inspect

    from src.supply.services.shortage_forecast_service import ShortageForecastService

    src = inspect.getsource(ShortageForecastService._load_reservas)
    assert 'LEFT JOIN factory_raw.ordemfabrico' in src
    assert '"OF_DATAFIM" IS NULL' in src


def test_sugestao_producao_interna_cobre_defice_q174():
    """Q.174.F0.3 — défice coberto por pedido interno aberto à Fábrica
    (TPMOV=12 → e_id=19747): a sugestão é confirmar a produção interna,
    NUNCA comprar em duplicado."""
    sugestao, detalhe, data_limite = _calcular_sugestao(
        data_rutura=HOJE + timedelta(days=20),
        hoje=HOJE,
        lead_time_days=7,
        defice=100.0,
        producao_interna_aberta=250.0,
    )
    assert sugestao == "producao_interna"
    assert "250.0" in detalhe and "100.0" in detalhe
    assert data_limite == HOJE + timedelta(days=13)


def test_sugestao_producao_interna_parcial_mantem_compra_q174():
    """Produção interna aberta que NÃO cobre o défice → compra mantém-se,
    com a cobertura parcial mencionada (não esconder o que já está pedido)."""
    sugestao, detalhe, _ = _calcular_sugestao(
        data_rutura=HOJE + timedelta(days=20),
        hoje=HOJE,
        lead_time_days=7,
        defice=100.0,
        producao_interna_aberta=30.0,
    )
    assert sugestao == "compra"
    assert "30.0" in detalhe


def test_sugestao_sem_producao_interna_back_compat_q174():
    """Default producao_interna_aberta=0.0 → comportamento Q.173.Z exato."""
    com = _calcular_sugestao(
        data_rutura=HOJE + timedelta(days=20), hoje=HOJE,
        lead_time_days=7, defice=100.0, producao_interna_aberta=0.0,
    )
    sem = _calcular_sugestao(
        data_rutura=HOJE + timedelta(days=20), hoje=HOJE,
        lead_time_days=7, defice=100.0,
    )
    assert com == sem and com[0] == "compra"


def test_load_pedidos_internos_canonico_q174():
    """Q.174.F0.3 — guard estático: o SQL dos pedidos internos segue a fórmula
    canónica produto_Stock_Necessidades (corpo lido live 2026-06-12):
    procura = TPMOV=12 abertos com MOV_E_ID<>19747 e SEM OF; oferta interna
    = TPMOV=12 abertos com MOV_E_ID=19747 (Fábrica produz)."""
    import inspect

    from src.supply.services.shortage_forecast_service import ShortageForecastService

    src = inspect.getsource(ShortageForecastService._load_pedidos_internos)
    assert '"MOV_TPMOV_ID" = 12' in src
    assert '"MOV_SATISFEITO" = false' in src
    assert '"MOV_E_ID" <> 19747 AND m."MOV_OF_ID" IS NULL' in src
    assert '"MOV_E_ID" = 19747' in src


def test_load_reservas_filtros_canonicos_q174():
    """Q.174.F0.3 — as reservas contam SÓ OFs de barco de cliente
    (OF_ID < 10M, OF_E_ID_ENC <> 19747), como produto_Stock_Necessidades —
    reservas de OFs de peças entram pelo canal TPMOV=12 (evita dupla
    contagem) e o Cliente Fábrica não é procura."""
    import inspect

    from src.supply.services.shortage_forecast_service import ShortageForecastService

    src = inspect.getsource(ShortageForecastService._load_reservas)
    assert '"OF_ID" < 10000000' in src
    assert '"OF_E_ID_ENC" <> 19747' in src


def test_explode_multinivel_sem_stock_propaga_tudo_q174():
    """Sem cobertura da peça, a procura desce inteira aos filhos (qty×qty)."""
    from src.supply.services.shortage_forecast_service import (
        _explode_consumos_multinivel,
    )

    d = date(2026, 6, 20)
    out = _explode_consumos_multinivel(
        consumos={"100": [(d, 10.0)]},
        bom_children={"100": [("200", 2.0)], "200": [("300", 3.0)]},
        stock_map={},
        producao_interna={},
    )
    assert out["100"] == [(d, 10.0)]          # procura da peça mantém-se
    assert out["200"] == [(d, 20.0)]          # 10 × 2
    assert out["300"] == [(d, 60.0)]          # 20 × 3


def test_explode_multinivel_netting_total_q174():
    """Peça totalmente coberta por stock → filhos NÃO herdam nada (provado
    live OF 501298: explosão cega duplicaria — o ERP regista peça E
    subcomponentes contra a OF do barco)."""
    from src.supply.services.shortage_forecast_service import (
        _explode_consumos_multinivel,
    )

    d = date(2026, 6, 20)
    out = _explode_consumos_multinivel(
        consumos={"100": [(d, 10.0)]},
        bom_children={"100": [("200", 2.0)]},
        stock_map={"100": 10.0},
        producao_interna={},
    )
    assert "200" not in out


def test_explode_multinivel_netting_parcial_q174():
    """Cobertura parcial (stock 4 + produção interna 2 de 10) → filhos herdam
    só o remanescente (ratio 0.4)."""
    from src.supply.services.shortage_forecast_service import (
        _explode_consumos_multinivel,
    )

    d = date(2026, 6, 20)
    out = _explode_consumos_multinivel(
        consumos={"100": [(d, 10.0)]},
        bom_children={"100": [("200", 5.0)]},
        stock_map={"100": 4.0},
        producao_interna={"100": 2.0},
    )
    assert out["200"] == [(d, pytest.approx(20.0))]  # 10×0.4 × 5


def test_explode_multinivel_cobertura_nao_reusada_q174():
    """O mesmo stock não cobre procura em ramos/níveis diferentes — a
    cobertura é consumida uma vez (cobertura_usada)."""
    from src.supply.services.shortage_forecast_service import (
        _explode_consumos_multinivel,
    )

    d1, d2 = date(2026, 6, 20), date(2026, 6, 25)
    # "200" recebe procura de dois pais (nível-1 direto e via "100").
    out = _explode_consumos_multinivel(
        consumos={"100": [(d1, 10.0)], "200": [(d2, 6.0)]},
        bom_children={"100": [("200", 1.0)], "200": [("300", 1.0)]},
        stock_map={"200": 6.0},
        producao_interna={},
    )
    # Nível 1: "200" tem procura própria 6 → coberta pelo stock 6 (usada).
    # Nível 2: "200" recebe 10 via "100" → stock já gasto → desce aos filhos.
    total_300 = sum(q for _, q in out.get("300", []))
    assert total_300 == pytest.approx(10.0)


def test_explode_multinivel_ciclo_limitado_q174():
    """Ciclo a→b→a (dados sujos) termina pelo cap de profundidade."""
    from src.supply.services.shortage_forecast_service import (
        _explode_consumos_multinivel,
    )

    d = date(2026, 6, 20)
    out = _explode_consumos_multinivel(
        consumos={"a": [(d, 1.0)]},
        bom_children={"a": [("b", 1.0)], "b": [("a", 1.0)]},
        stock_map={},
        producao_interna={},
        max_depth=4,
    )
    # Termina; "a" e "b" acumulam procura limitada pelo cap, sem loop infinito.
    assert sum(q for _, q in out["b"]) <= 2.0


def test_explode_multinivel_sem_bom_e_identidade_q174():
    """bom_children vazio → output É o input (caminho fallback intacto)."""
    from src.supply.services.shortage_forecast_service import (
        _explode_consumos_multinivel,
    )

    consumos = {"100": [(date(2026, 6, 20), 10.0)]}
    assert _explode_consumos_multinivel(consumos, {}, {}, {}) == consumos


def test_filtro_armazem_coerente_q174():
    """Q.174.F0.4 — quando `supply.production_warehouses` está definido, o
    filtro de armazém aplica-se COERENTEMENTE: stock (warehouse_id), reservas
    e pedidos internos (MOV_ARM_ID). Default vazio = todos (canónico —
    produto_Stock_Necessidades agrega global, corpo lido live 2026-06-12)."""
    import inspect

    from src.supply.services.shortage_forecast_service import ShortageForecastService

    src_stock = inspect.getsource(ShortageForecastService._load_stock)
    assert "arm_filter is None or wh_id in arm_filter" in src_stock
    assert '"conta"' in src_stock  # breakdown transparente

    for fn in (ShortageForecastService._load_reservas,
               ShortageForecastService._load_pedidos_internos):
        src = inspect.getsource(fn)
        assert '"MOV_ARM_ID" = ANY(:arms)' in src, (
            f"{fn.__name__} tem de honrar o mesmo filtro de armazém do stock"
        )
        assert "if arm_filter" in src  # opt-in: vazio = canónico


def test_load_bom_direcao_canonica_q174():
    """Q.174.F0.2 — guard estático: a BOM filtra pelo PAI (``COMP_P_ID`` =
    modelo do plano) e devolve o FILHO (``COMP_P_P_ID`` = componente).

    Provado live 2026-06-12 nos 5 modelos com mais WIP: um barco real só
    aparece como ``COMP_P_ID`` (ex. Ocean Ski 510 Pl → 20 filhos; 0 linhas
    como ``COMP_P_P_ID``). A direção trocada devolvia 0 linhas para TODOS os
    barcos e o forecast caía em silêncio no consumo histórico (E2 da
    reconciliação canónica).
    """
    import inspect

    from src.supply.services.shortage_forecast_service import ShortageForecastService

    src = inspect.getsource(ShortageForecastService._load_bom)
    assert '"COMP_P_ID" = ANY(:model_ids)' in src, (
        "o filtro da BOM tem de ser pelo PAI (COMP_P_ID = modelo)"
    )
    assert 'AS model_id' in src.split('"COMP_P_ID"::text', 1)[1].splitlines()[0]
    assert 'AS comp_id' in src.split('"COMP_P_P_ID"::text', 1)[1].splitlines()[0]


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
