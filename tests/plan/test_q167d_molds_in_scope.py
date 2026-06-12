"""Q.167.D — moldes no scope do CPO (opt-in via scope="boats_and_molds").

Decisão do Luís: moldes entram no scope. Implementação input-only (axioma
Spelke 5 — só muda o pool de entrada): um ramo UNION ALL adiciona os moldes
em reparação (P_TP_ID=82 via v_of_is_mold, fase {13,14} com op aberta) ao
`_load_open_orders_db`, com `is_mold=true`. O ramo dos barcos fica idêntico
ao `boats_only` → zero regressão.

SQL coberto com FakeSession que regista o statement (sem BD real). DAMP > DRY.
A verificação LIVE (boats_only 1205 inalterado; boats_and_molds +23 moldes)
corre fora do pytest.
"""
from __future__ import annotations

from uuid import UUID

import pytest

from src.plan.cpo.state_loaders import _load_open_orders_db

_TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _MapResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)


class _RecSession:
    """FakeSession: devolve as rows e regista os statements executados."""

    def __init__(self, rows):
        self._rows = rows
        self.statements: list = []

    async def execute(self, stmt, *_a, **_k):
        self.statements.append(stmt)
        return _MapResult(self._rows)


def _row(of_id, fase, is_mold):
    return {
        "of_id": of_id, "modelo_id": "900", "current_fase_id": fase,
        "data_entrega_prevista": None, "due_source": None, "is_mold": is_mold, "done_fase_ids": [],
    }


@pytest.mark.asyncio
async def test_boats_and_molds_sql_has_mold_union():
    """scope=boats_and_molds → o SQL inclui o ramo UNION dos moldes."""
    s = _RecSession([])
    await _load_open_orders_db(s, _TENANT, scope="boats_and_molds", plan_cap=0)
    sql = str(s.statements[-1])  # Q.174.F0.1: [0] é o probe de transp_of; o SQL principal é o último
    assert "v_of_is_mold" in sql
    assert "UNION ALL" in sql
    assert 'IN (13, 14)' in sql  # fases de reparação de molde
    assert "true AS is_mold" in sql


@pytest.mark.asyncio
async def test_boats_only_sql_has_no_mold_branch():
    """scope=boats_only → SEM ramo de moldes (zero regressão no scheduler)."""
    s = _RecSession([])
    await _load_open_orders_db(s, _TENANT, scope="boats_only", plan_cap=0)
    sql = str(s.statements[-1])  # Q.174.F0.1: [0] é o probe de transp_of; o SQL principal é o último
    assert "v_of_is_mold" not in sql
    assert "UNION ALL" not in sql
    # o ramo dos barcos passa a expor is_mold=false (coluna aditiva, mesmas rows).
    assert "false AS is_mold" in sql
    assert "v_of_is_boat" in sql  # critério de barco mantém-se


@pytest.mark.asyncio
async def test_all_scope_has_neither_view():
    """scope=all → back-compat: sem join de barco nem de molde."""
    s = _RecSession([])
    await _load_open_orders_db(s, _TENANT, scope="all", plan_cap=0)
    sql = str(s.statements[-1])  # Q.174.F0.1: [0] é o probe de transp_of; o SQL principal é o último
    assert "v_of_is_mold" not in sql
    assert "v_of_is_boat" not in sql


@pytest.mark.asyncio
async def test_is_mold_flag_maps_per_row():
    """A flag is_mold viaja por ordem; um molde em fase 14 é reparação."""
    s = _RecSession([_row("70449", "14", True), _row("5000", "1", False)])
    out = await _load_open_orders_db(s, _TENANT, scope="boats_and_molds", plan_cap=0)
    by_id = {o["of_id"]: o for o in out}
    assert by_id["70449"]["is_mold"] is True
    assert by_id["70449"]["is_reparacao"] is True   # fase 14 ∈ REPAIR_PHASE_IDS
    assert by_id["5000"]["is_mold"] is False
    assert by_id["5000"]["is_reparacao"] is False    # fase 1 (Laminagem)
