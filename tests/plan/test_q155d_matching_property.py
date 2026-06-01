"""Q.155.D — property tests do matching "barco difícil ↔ melhores operadores".

Invariantes do `_pick_workers` com o boost de complexidade:
  1. Um operador CURADO (rank-1) e livre é escolhido nos barcos (preferência
     ganha quando competitiva) — "barco difícil → melhor operador".
  2. Preferência forte é SOFT: um curado OCUPADO perde para um livre quando a
     complexidade é 0 (não esfomeia — axioma capacidade/par seguro).
  3. Complexidade alta puxa o curado mesmo que esteja mais ocupado (o ganho real
     concentra-se nos barcos complexos).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from src.plan.cpo.decoder_resources import _pick_workers

_EARLIEST = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _StubState:
    """FactoryState mínimo p/ o _pick_workers (curado + skill, sem sector)."""

    def __init__(self, preferred=None, skill=None):
        self._preferred = preferred or {}
        self._skill = skill or {}

    def skill_count(self, w):
        return self._skill.get(w, 0)

    def preferred_rank_score(self, w, fase):
        ranked = self._preferred.get(fase)
        if not ranked:
            return None
        try:
            i = ranked.index(w)
        except ValueError:
            return None
        return max(0.5, 1.0 - 0.05 * i)

    def preference_score_for(self, w, fase):
        return None


@settings(max_examples=120)
@given(
    others=st.lists(
        st.text(alphabet="bcdefghij", min_size=2, max_size=4),
        min_size=1, max_size=8, unique=True,
    ),
    skills=st.lists(st.integers(min_value=0, max_value=10), max_size=8),
    complexity=st.floats(min_value=0.0, max_value=1.0),
)
def test_curated_rank1_free_is_picked(others, skills, complexity):
    """Curado rank-1 e livre → sempre escolhido (team_size=1), a qualquer
    complexidade. 'A' ordena primeiro p/ vencer empates a 1.0 (skill máximo)."""
    A = "0A"  # ordena antes de qualquer "b..j"; é o melhor POR CURADORIA
    pool = set(others) | {A}
    skill = {w: (skills[i] if i < len(skills) else 1) for i, w in enumerate(others)}
    skill[A] = 0  # de propósito sem skill alto: ganha só pela curadoria
    free = {w: _EARLIEST for w in pool}  # todos livres
    state = _StubState(preferred={"LAM": [A]}, skill=skill)
    picked = _pick_workers(
        pool, 1, free, _EARLIEST,
        state=state, quality_weight=0.3, fase_id="LAM", op_complexity=complexity,
    )
    assert picked == [A]


def test_soft_preference_does_not_starve():
    """Curado OCUPADO perde para um livre quando complexidade=0 (soft)."""
    A, B = "0A", "zz"
    pool = {A, B}
    state = _StubState(preferred={"LAM": [A]}, skill={A: 0, B: 0})
    free = {A: _EARLIEST + timedelta(hours=96), B: _EARLIEST}  # A ocupado 4 dias
    picked = _pick_workers(
        pool, 1, free, _EARLIEST,
        state=state, quality_weight=0.3, fase_id="LAM", op_complexity=0.0,
    )
    assert picked == [B]


def test_curated_dominates_max_skill_noncurated_when_complex():
    """Regressão (bug apanhado live): o curado tem de DOMINAR, não só empatar.

    'B' não-curado tem id menor (venceria empates) E skill máximo; 'A' curado
    tem id maior e skill 0. Com complexidade alta, o bónus do curado ganha."""
    A, B = "9aa", "0zz"  # B venceria o desempate por id
    pool = {A, B}
    state = _StubState(preferred={"LAM": [A]}, skill={A: 0, B: 10})
    free = {A: _EARLIEST, B: _EARLIEST}
    picked = _pick_workers(
        pool, 1, free, _EARLIEST,
        state=state, quality_weight=0.3, fase_id="LAM", op_complexity=1.0,
    )
    assert picked == [A]


def test_high_complexity_pulls_curated_even_if_busier():
    """Mesma cena, complexidade=1.0 → o curado ganha (barco difícil → melhor)."""
    A, B = "0A", "zz"
    pool = {A, B}
    state = _StubState(preferred={"LAM": [A]}, skill={A: 0, B: 0})
    free = {A: _EARLIEST + timedelta(hours=96), B: _EARLIEST}
    picked = _pick_workers(
        pool, 1, free, _EARLIEST,
        state=state, quality_weight=0.3, fase_id="LAM", op_complexity=1.0,
    )
    assert picked == [A]
