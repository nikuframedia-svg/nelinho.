"""Q.167.G — o gate de polivalência (Entidade_Fase) APERTA o pool real do CPO.

As property tests de `_apply_qualification_gate` (test_qualification_gate_q158.py)
provam a função pura. Este módulo liga-a ao CONSUMIDOR real — `FactoryState.
workers_for` — e ao loader `_load_qualified_db`, fechando o gap "ninguém
confirmou que o gate aperta com dados reais":

  * o loader constrói a matriz declarada a partir das linhas (parsing + CAST);
  * a composição gate → filtro-de-activos → `workers_for` remove quem o
    histórico tinha mas a Entidade_Fase NÃO declara (incl. quem expirou — a
    SQL `certification_expiry` exclui-o, logo não chega ao `qualified`);
  * graceful: sem matriz declarada o pool fica intacto (axioma 5, back-compat).

O filtro SQL de expiração (`certification_expiry >= CURRENT_DATE`) é server-side
→ verificado LIVE (Q.167.G.3, semeando uma linha expirada no Postgres dev).
Aqui simula-se o EFEITO: o `qualified` pós-SQL já não contém o operador expirado.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.plan.cpo.state import (
    FactoryState,
    _apply_active_operator_filter,
    _apply_qualification_gate,
    _load_qualified_db,
)

TENANT = UUID("22222222-2222-2222-2222-222222222222")


# ── loader: parsing + graceful (fake session) ────────────────────────────────


class _Res:
    def __init__(self, rows=None):
        self._rows = rows or []

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _Sess:
    def __init__(self, rows=None, raise_exc=False):
        self.rows = rows or []
        self.raise_exc = raise_exc

    async def execute(self, stmt, *args, **kwargs):
        if self.raise_exc:
            raise SQLAlchemyError("relation hr.employee_skills does not exist")
        return _Res(rows=self.rows)


@pytest.mark.asyncio
async def test_loader_builds_declared_matrix():
    """`_load_qualified_db` agrupa (fase_id → {employee_code}) a partir das linhas
    qualificadas+activas+não-expiradas que a SQL devolve."""
    rows = [
        {"fase_id": "40", "func_id": "101"},
        {"fase_id": "40", "func_id": "102"},
        {"fase_id": "5", "func_id": "101"},
    ]
    out = await _load_qualified_db(_Sess(rows=rows), TENANT)
    assert out == {"40": {"101", "102"}, "5": {"101"}}


@pytest.mark.asyncio
async def test_loader_swallows_db_error():
    """Tabela ausente / outage → {} (gate inerte, nunca rebenta o build)."""
    assert await _load_qualified_db(_Sess(raise_exc=True), TENANT) == {}


@pytest.mark.asyncio
async def test_loader_none_session():
    assert await _load_qualified_db(None, TENANT) == {}


# ── integração: o gate aperta o pool que o decoder vê ────────────────────────


def test_workers_for_excludes_unqualified_and_expired():
    """O histórico (of_fp) põe 3 operadores na fase 40; a Entidade_Fase só
    declara o W1 (W3 nunca foi qualificado; W2 expirou → a SQL não o devolve).
    Depois do gate, `workers_for('40')` — o que o decoder consome — devolve só W1."""
    history = {"40": {"W1", "W2_expirado", "W3_nao_qualificado"}}
    qualified = {"40": {"W1"}}  # pós-SQL: sem expirado, sem não-qualificado

    gated = _apply_qualification_gate(history, qualified)
    state = FactoryState(tenant_id=TENANT, skill_matrix=gated)

    assert state.workers_for("40") == {"W1"}
    assert "W2_expirado" not in state.workers_for("40")
    assert "W3_nao_qualificado" not in state.workers_for("40")


def test_gate_then_active_filter_compose_to_narrow():
    """Composição real do `_build_state` (gate Q.158 → filtro activos Q.159):
    o pool final nunca alarga além do declarado E do activo (axioma 5)."""
    history = {"40": {"W1", "W2", "W3"}}
    qualified = {"40": {"W1", "W2"}}          # Entidade_Fase declara W1, W2
    active = {"W1"}                            # só W1 trabalhou nos últimos 2 meses

    gated = _apply_qualification_gate(history, qualified)
    narrowed = _apply_active_operator_filter(gated, active)
    state = FactoryState(tenant_id=TENANT, skill_matrix=narrowed)

    assert state.workers_for("40") == {"W1"}  # interseção declarado ∩ activo


def test_phase_without_declaration_keeps_history():
    """Fase sem qualificação declarada mantém o histórico (partial-safe):
    o gate não esvazia o que a Entidade_Fase não cobre."""
    history = {"40": {"W1", "W2"}, "5": {"W9"}}
    qualified = {"40": {"W1"}}                 # fase 5 não declarada

    gated = _apply_qualification_gate(history, qualified)
    state = FactoryState(tenant_id=TENANT, skill_matrix=gated)

    assert state.workers_for("40") == {"W1"}   # gated
    assert state.workers_for("5") == {"W9"}    # histórico intacto


def test_empty_declaration_is_inert():
    """Sem matriz declarada (mirror nunca correu / tudo expirado) o pool fica
    exactamente o histórico — back-compat exacto (axioma 5: não inventa)."""
    history = {"40": {"W1", "W2"}}
    state = FactoryState(tenant_id=TENANT, skill_matrix=_apply_qualification_gate(history, {}))
    assert state.workers_for("40") == {"W1", "W2"}
