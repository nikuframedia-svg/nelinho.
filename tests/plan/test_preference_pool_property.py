"""Q.140.H — property tests: preferência por sector só REORDENA, nunca alarga.

Axioma Spelke 5 (skill match): por mais alta que seja a preferência de um
worker FORA do pool apto, o `_pick_workers` nunca o escolhe. A preferência só
muda a ORDEM dentro do pool já filtrado por `workers_for`. Property-based
(hypothesis) porque é um invariante, não um exemplo.

Fronteira anti-dupla-contagem (documentada, não testada aqui):
* decoder `_pick_workers` / Hungarian — ESCOLHEM dentro do pool por nível de
  sector (afinidade-derivada do job ML + override manual). Fonte: histórico
  real + override.
* `preference_adapter.compute_preference_penalty` (fitness) — premeia
  `PreferenceRule(type=operator_affinity)` CONFIRMADAS por humano. Fonte
  distinta (regra confirmada, não nível). Logo não há dupla contagem: uma vive
  na escolha do pool, a outra na função de fitness.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from hypothesis import given, settings, strategies as st

from src.plan.cpo.decoder_resources import _pick_workers
from src.plan.cpo.state import FactoryState

_REF = datetime(2026, 5, 1, 8, 0, 0)
_FASE = "PHASE_X"
_POOL_IDS = [f"w{i}" for i in range(12)]
_GHOST_IDS = [f"ghost{i}" for i in range(4)]  # NUNCA no pool


def _state(pool: set[str], prefs: dict) -> FactoryState:
    st_ = FactoryState(tenant_id=uuid4())
    st_.skill_matrix = {_FASE: set(pool)}
    st_.sector_preferences = prefs
    return st_


_pools = st.sets(st.sampled_from(_POOL_IDS), min_size=1, max_size=10)
_team = st.integers(min_value=1, max_value=6)
_scores = st.floats(min_value=0.0, max_value=1.0)


@given(pool=_pools, team_size=_team, data=st.data())
@settings(max_examples=200, deadline=None)
def test_preference_never_introduces_out_of_pool_worker(pool, team_size, data):
    # Preferência ALTA (1.0) para fantasmas FORA do pool + scores aleatórios
    # para o pool. O fantasma nunca pode ser escolhido (axioma 5).
    prefs = {(w, _FASE): data.draw(_scores) for w in pool}
    for g in _GHOST_IDS:
        prefs[(g, _FASE)] = 1.0  # máximo — tenta "puxar" o fantasma
    state = _state(pool, prefs)
    free_at = {w: _REF + timedelta(hours=data.draw(st.integers(0, 10))) for w in pool}

    picked = _pick_workers(
        pool, team_size=team_size, worker_free_at=free_at, earliest=_REF,
        state=state, quality_weight=1.0, fase_id=_FASE,
    )

    assert set(picked).issubset(pool)              # nunca alarga o pool
    assert not (set(picked) & set(_GHOST_IDS))     # nenhum fantasma
    assert len(picked) == min(team_size, len(pool))  # cardinalidade certa
    assert len(set(picked)) == len(picked)         # sem duplicados


@given(pool=_pools, team_size=_team, data=st.data())
@settings(max_examples=100, deadline=None)
def test_pick_is_deterministic_across_runs(pool, team_size, data):
    prefs = {(w, _FASE): data.draw(_scores) for w in pool}
    state = _state(pool, prefs)
    free_at = {w: _REF + timedelta(hours=data.draw(st.integers(0, 10))) for w in pool}

    a = _pick_workers(pool, team_size, free_at, _REF, state=state,
                      quality_weight=1.0, fase_id=_FASE)
    b = _pick_workers(pool, team_size, free_at, _REF, state=state,
                      quality_weight=1.0, fase_id=_FASE)
    assert a == b  # mesmo input → mesma ordem (determinismo)


@given(pool=_pools, team_size=_team)
@settings(max_examples=100, deadline=None)
def test_empty_preferences_still_subset_of_pool(pool, team_size):
    # Sem preferências (back-compat): continua subconjunto do pool.
    state = _state(pool, {})
    free_at = {w: _REF for w in pool}
    picked = _pick_workers(pool, team_size, free_at, _REF, state=state,
                           quality_weight=0.3, fase_id=_FASE)
    assert set(picked).issubset(pool)
    assert len(picked) == min(team_size, len(pool))
