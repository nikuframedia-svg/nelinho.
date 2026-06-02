"""Q.158.B — property test: gate de polivalência DECLARADO (Entidade_Fase).

A frase do Nuno: "a polivalência está definida na Entidade_Fase e o histórico
na OF_FP". São duas camadas: ``Entidade_Fase`` = quem PODE (gate),
``OF_FP`` = quem faz MELHOR (ranking). Antes o CPO usava o histórico como gate
(conflação). ``_apply_qualification_gate`` corrige isto:

* onde há qualificações declaradas, o pool elegível É o conjunto qualificado;
* fases sem dados declarados mantêm o histórico (partial-safe);
* ``qualified`` vazio → histórico intacto (back-compat — inerte até o mirror
  Q.158.A preencher ``is_certified``).

Spelke axioma 5: o pool elegível nunca contém quem não está na competência
real declarada (para fases gated). Testa a função pura.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.plan.cpo.state import _apply_qualification_gate

# ─── strategies ─────────────────────────────────────────────────────────────

_fase = st.sampled_from([str(i) for i in range(1, 12)])
_worker = st.sampled_from([f"W{i}" for i in range(1, 16)])
_matrix = st.dictionaries(
    keys=_fase,
    values=st.sets(_worker, min_size=0, max_size=8),
    min_size=0,
    max_size=8,
)


# ─── property: gate declarado é respeitado ──────────────────────────────────

@settings(max_examples=300, deadline=None)
@given(history=_matrix, qualified=_matrix)
def test_gated_phase_pool_equals_declared(history, qualified):
    """Para qualquer fase com qualificações declaradas, o pool resultante É
    exactamente o conjunto qualificado (a Entidade_Fase é a verdade)."""
    merged = _apply_qualification_gate(history, qualified)
    for fase_id, pool in qualified.items():
        assert merged[fase_id] == pool


@settings(max_examples=300, deadline=None)
@given(history=_matrix, qualified=_matrix)
def test_no_unqualified_worker_in_gated_phase(history, qualified):
    """Spelke 5 — numa fase gated, ninguém fora do conjunto qualificado entra,
    mesmo que estivesse no histórico (o gate aperta, não alarga)."""
    merged = _apply_qualification_gate(history, qualified)
    for fase_id in qualified:
        assert merged[fase_id] <= qualified[fase_id]


@settings(max_examples=300, deadline=None)
@given(history=_matrix, qualified=_matrix)
def test_phases_without_declared_keep_history(history, qualified):
    """Fases sem dados declarados mantêm o histórico (partial-safe)."""
    merged = _apply_qualification_gate(history, qualified)
    for fase_id, pool in history.items():
        if fase_id not in qualified:
            assert merged[fase_id] == pool


@given(history=_matrix)
def test_empty_qualified_is_identity(history):
    """``qualified`` vazio → histórico intacto (back-compat exacto: inerte até
    o mirror Q.158.A preencher ``is_certified``)."""
    assert _apply_qualification_gate(history, {}) == history


def test_declared_can_add_qualified_not_in_history():
    """Um operador qualificado (declarado) entra mesmo sem histórico na fase —
    é competência real, não invenção."""
    history = {"1": {"W1"}}
    qualified = {"1": {"W1", "W2"}}  # W2 qualificado mas sem histórico
    merged = _apply_qualification_gate(history, qualified)
    assert merged["1"] == {"W1", "W2"}


def test_history_only_unqualified_removed():
    """Quem fez a fase no histórico mas NÃO está qualificado é removido."""
    history = {"1": {"W1", "W_NAO_QUALIFICADO"}}
    qualified = {"1": {"W1"}}
    merged = _apply_qualification_gate(history, qualified)
    assert merged["1"] == {"W1"}
    assert "W_NAO_QUALIFICADO" not in merged["1"]
