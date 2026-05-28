"""Q.116.B — tests for `curing_gap_pairs()` helper em src/plan/cpo/state.py.

A funcao expoe os pares (from_phase, to_phase) declarados no seed para
o `verify_invariants.py` poder validar que cada par
(predecessor_alternativo, fase_flexivel) tem suporte fisico.

Cobertura:
  1. Retorna set com cardinalidade igual ao seed (16 pares hoje).
  2. Contem pares conhecidos do seed (sem hard-coding da estrutura).
  3. Mutar o set retornado nao afecta o seed (defensiva).
"""
from __future__ import annotations

from src.plan.cpo.state import NELO_CURING_GAPS_SEED, curing_gap_pairs


def test_curing_gap_pairs_matches_seed_cardinality():
    """O helper devolve um par por linha do seed (16 hoje, sem duplicados)."""
    pairs = curing_gap_pairs()
    # 16 linhas distintas — se o seed crescer, este numero acompanha.
    assert len(pairs) == len(NELO_CURING_GAPS_SEED)
    # Sem duplicados acidentais no seed.
    raw = [(row[0], row[1]) for row in NELO_CURING_GAPS_SEED]
    assert len(set(raw)) == len(raw), (
        "NELO_CURING_GAPS_SEED tem duplicados em (from, to) — verificar"
    )


def test_curing_gap_pairs_contains_known_pairs():
    """Spot-check de pares historicamente verdes (Q.116.A descobriu)."""
    pairs = curing_gap_pairs()
    assert ("LAMINAGEM", "CURA") in pairs
    assert ("LAMINAGEM_INFUSAO", "CURA") in pairs
    assert ("COLAGEM_PECAS", "PINTURA_ACABAMENTO") in pairs
    assert ("PINTURA_ACABAMENTO", "LIXAGEM_SECO") in pairs


def test_curing_gap_pairs_returns_isolated_set():
    """Mutar o set retornado nao deve afectar o seed nem chamadas seguintes."""
    pairs = curing_gap_pairs()
    n_before = len(pairs)
    pairs.add(("FAKE_FROM", "FAKE_TO"))
    pairs2 = curing_gap_pairs()
    # A nova chamada nao herda a mutacao.
    assert ("FAKE_FROM", "FAKE_TO") not in pairs2
    assert len(pairs2) == n_before


def test_curing_gap_pairs_pure_strings():
    """Todos os pares sao tuplos de duas strings nao-vazias."""
    pairs = curing_gap_pairs()
    for p in pairs:
        assert isinstance(p, tuple)
        assert len(p) == 2
        assert isinstance(p[0], str) and p[0]
        assert isinstance(p[1], str) and p[1]
