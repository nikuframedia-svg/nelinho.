"""
Q.55.C.1 — `_build_quality_snapshot` lê `quality.rework_entry` em vez de uma
camada in-memory vazia.

Antes, a função chamava `SemanticQueriesInMemory().quality_analysis()` (classe
mal-instanciada, método inexistente) → excepção silenciada → zeros → o copiloto
respondia "não tenho dados" a "qual o erro mais comum / trabalhador com mais
erros", apesar de a BD ter 100k+ eventos de retrabalho.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.copilot.context_builder import _build_quality_snapshot

TENANT = UUID("00000000-0000-0000-0000-000000000001")
EMP_A = uuid4()
EMP_B = uuid4()


class _Result:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def all(self):
        return list(self._rows)

    def scalar(self):
        return self._scalar


class _Session:
    """Sessão falsa que devolve resultados por ordem de `execute()`.

    Ordem em `_build_quality_snapshot`: tipos de erro, total, ranking de
    trabalhadores (WorkerRankingService), nomes de erro, nomes de trabalhador.
    """

    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _stmt):
        return self._results.pop(0) if self._results else _Result()


@pytest.mark.asyncio
async def test_snapshot_traz_erro_mais_comum_e_trabalhadores():
    session = _Session([
        _Result(rows=[("E_LAM_01", 120), ("E_PINT_02", 80)]),     # tipos de erro
        _Result(scalar=230),                                       # total
        _Result(rows=[(EMP_A, 90), (EMP_B, 50)]),                  # WorkerRanking
        _Result(rows=[("E_LAM_01", "Delaminação"),                 # ErrorCatalog
                       ("E_PINT_02", "Escorrido de tinta")]),
        _Result(rows=[(EMP_A, "Ana Silva"), (EMP_B, "João Costa")]),  # employees
    ])

    snap = await _build_quality_snapshot(
        session, TENANT, datetime.now(timezone.utc) - timedelta(hours=6),
    )

    assert snap["has_data"] is True
    assert snap["total_errors"] == 230
    assert snap["most_common_error"]["name"] == "Delaminação"
    assert snap["most_common_error"]["events"] == 120
    assert snap["top_workers"][0]["name"] == "Ana Silva"
    assert snap["top_workers"][0]["error_count"] == 90
    assert len(snap["top_error_types"]) == 2
    assert snap["source"] == "quality.rework_entry"


@pytest.mark.asyncio
async def test_snapshot_bd_vazia_degrada_sem_rebentar():
    session = _Session([
        _Result(rows=[]),       # tipos de erro
        _Result(scalar=0),      # total
        _Result(rows=[]),       # WorkerRanking
    ])

    snap = await _build_quality_snapshot(
        session, TENANT, datetime.now(timezone.utc) - timedelta(hours=6),
    )

    assert snap["has_data"] is False
    assert snap["total_errors"] == 0
    assert snap["most_common_error"] is None
    assert snap["top_workers"] == []
    assert snap["top_error_types"] == []
