"""Q.157.H Slice B — property tests para o critério de barco.

Invariante: barco = raiz de PRODUTO_TIPO é Kayak (TP_ID 1) AND OF_ID < 10 000 000.

Quatro propriedades testadas com hypothesis:
  (a) raiz=Kayak AND OF_ID<10M → is_boat=True
  (b) raiz=Kayak AND OF_ID>=10M (pagaia) → is_boat=False
  (c) raiz≠Kayak → is_boat=False, independentemente do OF_ID
  (d) o critério NÃO usa P_QTDDECK nem P_QTDCASCO

O código testado é a função lógica pura `_is_boat_by_criterion`, que extrai
a decisão do SQL de forma testável sem BD real.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

# ---------------------------------------------------------------------------
# Função lógica pura (espelho do predicado SQL)
# ---------------------------------------------------------------------------

KAYAK_TP_ID = 1
OF_ID_MAX_BOAT = 10_000_000


def _is_boat_by_criterion(root_tp_id: int, of_id: int) -> bool:
    """Replica a lógica da view factory_raw.v_of_is_boat.

    is_boat = root_tp_id == KAYAK_TP_ID AND of_id < OF_ID_MAX_BOAT

    NÃO usa P_QTDDECK nem P_QTDCASCO — essa é a propriedade (d).
    """
    return root_tp_id == KAYAK_TP_ID and of_id < OF_ID_MAX_BOAT


# ---------------------------------------------------------------------------
# (a) raiz=Kayak AND OF_ID<10M → barco
# ---------------------------------------------------------------------------

@given(of_id=st.integers(min_value=1, max_value=OF_ID_MAX_BOAT - 1))
@settings(max_examples=200)
def test_kayak_low_ofid_is_boat(of_id: int) -> None:
    """Qualquer OF com raiz=Kayak e OF_ID abaixo de 10M é barco."""
    assert _is_boat_by_criterion(root_tp_id=KAYAK_TP_ID, of_id=of_id) is True


# ---------------------------------------------------------------------------
# (b) raiz=Kayak AND OF_ID>=10M (pagaia TP331) → NÃO é barco
# ---------------------------------------------------------------------------

@given(of_id=st.integers(min_value=OF_ID_MAX_BOAT, max_value=OF_ID_MAX_BOAT * 10))
@settings(max_examples=200)
def test_kayak_high_ofid_pagaia_not_boat(of_id: int) -> None:
    """OF com raiz=Kayak mas OF_ID>=10M (pagaias TP331) NÃO é barco."""
    assert _is_boat_by_criterion(root_tp_id=KAYAK_TP_ID, of_id=of_id) is False


# ---------------------------------------------------------------------------
# (c) raiz≠Kayak (Gola/Leme/acessório) → NÃO é barco
# ---------------------------------------------------------------------------

@given(
    root_tp_id=st.integers(min_value=2, max_value=9999),
    of_id=st.integers(min_value=1, max_value=OF_ID_MAX_BOAT * 10),
)
@settings(max_examples=200)
def test_non_kayak_root_not_boat(root_tp_id: int, of_id: int) -> None:
    """Produto com raiz que não é Kayak nunca é barco, qualquer que seja o OF_ID."""
    assert _is_boat_by_criterion(root_tp_id=root_tp_id, of_id=of_id) is False


# ---------------------------------------------------------------------------
# (d) o critério não usa P_QTDDECK nem P_QTDCASCO
# ---------------------------------------------------------------------------

def test_criterion_does_not_use_deck_casco_columns() -> None:
    """Confirma (via AST) que o predicado SQL em state.py e cpo_commit_orders.py
    não contém P_QTDDECK nem P_QTDCASCO após Q.157.H."""
    import ast
    import pathlib

    targets = [
        pathlib.Path("src/plan/cpo/state.py"),
        pathlib.Path("src/plan/services/cpo_commit_orders.py"),
    ]
    forbidden = {"P_QTDDECK", "P_QTDCASCO"}

    for path in targets:
        src = path.read_text(encoding="utf-8")
        # Procura literal de string que contenha as colunas proibidas
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for col in forbidden:
                    assert col not in node.value, (
                        f"{path}: ainda contém '{col}' numa string literal "
                        f"(linha {node.lineno}). Critério deck+casco deve estar "
                        "substituído por raiz=Kayak AND OF_ID<10M."
                    )
