"""Q.174.F8 — drift-guard do explain: a MESMA fórmula do `_pick_workers`.

`explain_pick_workers` reimplementa o scoring com breakdown (o hot-path
não deve pagar dicts por worker). Se alguém mexer na fórmula de um lado
e não do outro, este property test rebenta: a ORDEM dos dois tem de ser
idêntica em qualquer input (skill, curados, sector, carga, ausências,
quality_weight, ICB).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import hypothesis.strategies as st
from hypothesis import given, settings

from src.plan.cpo.decoder_resources import _pick_workers, explain_pick_workers

_REF = datetime(2026, 6, 15, 8, 0, 0)
_IDS = [f"w{i:02d}" for i in range(12)]


class _State:
    """Stub mínimo com os 4 acessores que o scoring consulta."""

    def __init__(self, skills, ranks, sector, absences):
        self._skills = skills
        self._ranks = ranks
        self._sector = sector
        self._absences = absences

    def skill_count(self, worker):
        return self._skills.get(worker, 0)

    def preferred_rank_score(self, worker, fase_id):
        return self._ranks.get(worker)

    def preference_score_for(self, worker, fase_id):
        return self._sector.get(worker)

    def absence_adjusted_start(self, worker, start, dur_h):
        return start + timedelta(hours=self._absences.get(worker, 0.0))


_HOURS = st.floats(min_value=0.0, max_value=200.0,
                   allow_nan=False, allow_infinity=False)
_UNIT = st.floats(min_value=0.0, max_value=1.0,
                  allow_nan=False, allow_infinity=False)


@st.composite
def _scenario(draw):
    ws = draw(st.lists(st.sampled_from(_IDS), min_size=1, max_size=12,
                       unique=True))

    def _sub(values):
        return {w: draw(values) for w in ws if draw(st.booleans())}

    return {
        "workers": ws,
        "free_h": _sub(_HOURS),
        "skills": {w: draw(st.integers(min_value=0, max_value=50)) for w in ws},
        "ranks": _sub(_UNIT),
        "sector": _sub(_UNIT),
        "load_h": _sub(_HOURS),
        "absences_h": _sub(_HOURS),
        "quality_weight": draw(_UNIT),
        "op_complexity": draw(st.floats(min_value=0.0, max_value=3.0,
                                        allow_nan=False)),
        "op_duration_h": draw(st.floats(min_value=0.0, max_value=12.0,
                                        allow_nan=False)),
        "team_size": draw(st.integers(min_value=1, max_value=12)),
    }


@settings(max_examples=200, deadline=None)
@given(s=_scenario())
def test_explain_ordena_exactamente_como_pick_workers(s):
    state = _State(s["skills"], s["ranks"], s["sector"], s["absences_h"])
    free_at = {w: _REF + timedelta(hours=h) for w, h in s["free_h"].items()}
    kwargs = dict(
        state=state,
        quality_weight=s["quality_weight"],
        fase_id="40",
        op_complexity=s["op_complexity"],
        worker_load_h=dict(s["load_h"]),
        op_duration_h=s["op_duration_h"],
    )

    picked = _pick_workers(
        set(s["workers"]), s["team_size"], dict(free_at), _REF, **kwargs,
    )
    explained = explain_pick_workers(
        set(s["workers"]), dict(free_at), _REF, **kwargs,
    )

    assert [c["worker_id"] for c in explained][: s["team_size"]] == picked


def test_explain_pool_vazio_devolve_vazio():
    assert explain_pick_workers(set(), {}, _REF) == []


def test_explain_marca_ausencia_e_carga():
    state = _State(
        skills={"w01": 10, "w02": 10},
        ranks={},
        sector={},
        absences={"w02": 8.0},  # w02 ausente 8h a partir do earliest
    )
    out = explain_pick_workers(
        {"w01", "w02"}, {}, _REF,
        state=state, quality_weight=0.3, fase_id="40",
        worker_load_h={"w01": 5.0, "w02": 20.0},
        op_duration_h=2.0,
    )
    by_id = {c["worker_id"]: c for c in out}
    assert by_id["w02"]["ausente_na_janela"] is True
    assert by_id["w02"]["horas_ate_livre"] == 8.0
    assert by_id["w01"]["ausente_na_janela"] is False
    assert by_id["w01"]["carga_plano_h"] == 5.0
    assert by_id["w02"]["carga_frac"] == 1.0  # mais carregado do pool
    assert out[0]["worker_id"] == "w01"  # livre + menos carregado ganha
