"""Q.173.A + Q.174.F0.1 — transport_date do mirror de production_orders é honesta.

A auditoria 2026-06-11 encontrou transport_date fabricada: o COALESCE caía
em OF_DATA (data de CRIAÇÃO da OF) quando não havia promessa de transporte,
dando "data de expedição" a 100% das 9.607 ordens (violação do invariante #8
— dados honestos). Q.173.A removeu o fallback.

Q.174.F0.1 — a reconciliação live (2026-06-12) provou que a coluna
OF_TR_DATA_PREVISTA está morta desde 2009 e que a promessa REAL vive em
TRANSP_OF→TRANSPORTE.TR_DATA (93k links; 72.753 OFs com transporte agendado
eram invisíveis). A hierarquia honesta passa a ser: transporte FUTURO
canónico → coluna legacy → NULL. OF_DATA continua banida. Reparações:
SÓ o transporte futuro real (a promessa da venda original NUNCA).
"""
from __future__ import annotations

import re

from scripts.q131_setup_production_orders_mirror import (
    _UPSERT_SQL,
    _WIP_CTE,
    _wip_cte,
)


def _transport_expr(cte: str) -> str:
    """Isola a expressão que alimenta transport_date no ramo principal."""
    match = re.search(r"(?P<expr>[^\n]*(?:\n[^\n]*)*?)AS transport_date", cte)
    assert match is not None, "CTE deixou de definir transport_date"
    raw = match.group("expr").split("AS created_date")[-1]
    return "\n".join(
        line for line in raw.splitlines() if not line.strip().startswith("--")
    )


def test_transport_date_sem_fallback_para_of_data() -> None:
    expr = _transport_expr(_WIP_CTE)
    assert "tr_data_futura" in expr, (
        "transport_date tem de começar no transporte FUTURO canónico "
        "(TRANSP_OF→TRANSPORTE.TR_DATA, Q.174.F0.1)"
    )
    assert "OF_TR_DATA_PREVISTA" in expr, (
        "fallback legacy OF_TR_DATA_PREVISTA mantém-se (única coluna OF_* aceite)"
    )
    cleaned = expr.replace("OF_TR_DATA_PREVISTA", "").replace("tr_data_futura", "")
    assert "OF_DATA" not in cleaned, (
        "transport_date NÃO pode cair em OF_DATA (data de criação) — "
        "isso fabrica datas de expedição (invariante #8, auditoria 2026-06-11)"
    )


def test_transport_date_coalesce_so_com_fontes_reais() -> None:
    """O COALESCE só pode conter as 2 fontes sancionadas (camião futuro +
    coluna legacy). Qualquer fonte nova precisa de prova canónica e revisão."""
    expr = _transport_expr(_WIP_CTE)
    inside = expr[expr.upper().find("COALESCE"):]
    assert "tr_data_futura" in inside and "OF_TR_DATA_PREVISTA" in inside
    proibidas = ("OF_PLANO_DATA_PREVISTA", "OF_DATAENTREGA", "OF_DATATRANSPORTE")
    for col in proibidas:
        assert col not in inside, (
            f"{col} não é fonte de transport_date (previsão interna/coluna "
            "morta — reconciliação 2026-06-12)"
        )


def test_fallback_sem_transp_of_e_fonte_unica_legacy() -> None:
    """BD dev sem o mirror transp_of → fonte única legacy (sem COALESCE),
    exactamente o contrato Q.173.A original."""
    expr = _transport_expr(_wip_cte(False))
    assert "COALESCE" not in expr.upper()
    assert "OF_TR_DATA_PREVISTA" in expr
    assert "tr_data_futura" not in expr


def test_upsert_continua_a_propagar_transport_date() -> None:
    # O UPDATE do upsert tem de continuar a refrescar transport_date para que
    # promessas novas/alteradas no ERP cheguem ao espelho (e NULLs honestos
    # substituam datas fabricadas antigas).
    assert "transport_date     = EXCLUDED.transport_date" in _UPSERT_SQL


def test_q173v_reparacoes_reentradas_no_espelho() -> None:
    """Q.173.V — reparações re-entradas (OF_DATAFIM preenchido, op aberta
    na fase de reparação) entram no espelho via UNION com o critério
    canónico v_of_em_producao. Q.174.F0.1: a promessa de uma reparação é
    SÓ o transporte futuro real (tr_data_futura, NULL se não houver) —
    a promessa da venda ORIGINAL (colunas OF_*) nunca entra."""
    assert "UNION" in _WIP_CTE
    repair_branch = _WIP_CTE.split("UNION", 1)[1]
    assert "v.is_reparacao = true" in repair_branch
    assert 'NULLIF(ofb."OF_DATAFIM", \'\') IS NOT NULL' in repair_branch
    assert "tr.tr_data_futura" in repair_branch, (
        "reparação com transporte futuro real ganha a promessa NOVA (honesta)"
    )
    assert "OF_TR_DATA_PREVISTA" not in repair_branch, (
        "a promessa da venda original NUNCA é usada numa reparação (invariante #8)"
    )


def test_q173v_reparacao_sem_transp_of_fica_null() -> None:
    """Fallback (sem mirror transp_of): reparação volta a NULL — nunca a
    coluna legacy da venda original."""
    repair_branch = _wip_cte(False).split("UNION", 1)[1]
    assert "NULL::date" in repair_branch
    assert "OF_TR_DATA_PREVISTA" not in repair_branch
