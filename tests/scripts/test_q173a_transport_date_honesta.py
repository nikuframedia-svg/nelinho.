"""Q.173.A — transport_date do mirror de production_orders é honesta.

A auditoria 2026-06-11 encontrou transport_date fabricada: o COALESCE caía
em OF_DATA (data de CRIAÇÃO da OF) quando não havia promessa de transporte,
dando "data de expedição" a 100% das 9.607 ordens (violação do invariante #8
— dados honestos). Estes testes são o gate de regressão: a única fonte de
transport_date é OF_TR_DATA_PREVISTA; sem promessa → NULL.
"""
from __future__ import annotations

import re

from scripts.q131_setup_production_orders_mirror import _UPSERT_SQL, _WIP_CTE


def test_transport_date_sem_fallback_para_of_data() -> None:
    # Isola a expressão que alimenta transport_date no CTE.
    match = re.search(
        r"(?P<expr>[^\n]*(?:\n[^\n]*)*?)AS transport_date", _WIP_CTE
    )
    assert match is not None, "CTE deixou de definir transport_date"
    # Apanha só as linhas da expressão (depois da definição de created_date),
    # sem comentários SQL (que podem mencionar OF_DATA ao explicar o porquê).
    raw = match.group("expr").split("AS created_date")[-1]
    expr = "\n".join(
        line for line in raw.splitlines() if not line.strip().startswith("--")
    )
    assert "OF_TR_DATA_PREVISTA" in expr, (
        "transport_date tem de vir da promessa real OF_TR_DATA_PREVISTA"
    )
    assert "OF_DATA" not in expr.replace("OF_TR_DATA_PREVISTA", ""), (
        "transport_date NÃO pode cair em OF_DATA (data de criação) — "
        "isso fabrica datas de expedição (invariante #8, auditoria 2026-06-11)"
    )


def test_transport_date_sem_coalesce() -> None:
    expr = _WIP_CTE.split("AS created_date")[-1].split("AS transport_date")[0]
    assert "COALESCE" not in expr.upper(), (
        "transport_date é fonte única (OF_TR_DATA_PREVISTA ou NULL) — "
        "qualquer COALESCE novo precisa de fonte real e revisão"
    )


def test_upsert_continua_a_propagar_transport_date() -> None:
    # O UPDATE do upsert tem de continuar a refrescar transport_date para que
    # promessas novas/alteradas no ERP cheguem ao espelho (e NULLs honestos
    # substituam datas fabricadas antigas).
    assert "transport_date     = EXCLUDED.transport_date" in _UPSERT_SQL


def test_q173v_reparacoes_reentradas_no_espelho() -> None:
    """Q.173.V — reparações re-entradas (OF_DATAFIM preenchido, op aberta
    na fase de reparação) entram no espelho via UNION com o critério
    canónico v_of_em_producao; a promessa de transporte fica NULL (a do
    ERP é a da venda ORIGINAL — usá-la seria desonesto)."""
    assert "UNION" in _WIP_CTE
    repair_branch = _WIP_CTE.split("UNION", 1)[1]
    assert "v.is_reparacao = true" in repair_branch
    assert 'NULLIF(ofb."OF_DATAFIM", \'\') IS NOT NULL' in repair_branch
    assert "NULL::date" in repair_branch, (
        "reparação sem promessa real de transporte → NULL (invariante #8)"
    )
