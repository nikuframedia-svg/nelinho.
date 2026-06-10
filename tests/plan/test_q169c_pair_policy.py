"""Q.169.C — política de pares: match EXATO do código canónico de fase.

`team_size_for` usava substring ("LAMINAGEM" in "LAMINAGEM_INFUSAO" →
True) e pedia equipa de 2 à Infusão, enquanto `pair_assignment.
prefers_pair` (match exato) dizia False — inconsistência que podia tornar
ops de Infusão infeasible (team_size=2 sem direito a downgrade soft),
contra o histórico (58% solo, "never required at all" — state.py:348).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from src.plan.cpo.schedule_validator import validate_schedule
from src.plan.cpo.state import FactoryState

_T0 = datetime(2026, 6, 15, 8, 0, 0)


def _state() -> FactoryState:
    return FactoryState(tenant_id=uuid4())


class TestTeamSizeExactMatch:
    def test_laminagem_standard_is_pair(self):
        assert _state().team_size_for("40", "Laminagem") == 2

    def test_laminagem_infusao_is_solo(self):
        """Infusão NÃO é par-preferida (58% solo histórico) — o substring
        match antigo dava-lhe team_size=2."""
        assert _state().team_size_for("41", "Laminagem Infusão") == 1

    def test_accents_and_case_normalized(self):
        assert _state().team_size_for("40", "LAMINAGEM") == 2
        assert _state().team_size_for("40", "laminagem") == 2

    def test_override_respects_pair_minimum(self):
        state = _state()
        state.phase_config = {"40": {"team_size_override": 1}}
        # override nunca abaixo do mínimo da fase par-preferida
        assert state.team_size_for("40", "Laminagem") == 2

    def test_override_applies_to_solo_phase(self):
        state = _state()
        state.phase_config = {"41": {"team_size_override": 3}}
        assert state.team_size_for("41", "Laminagem Infusão") == 3


class TestValidatorPairExactMatch:
    def test_infusao_solo_does_not_warn(self):
        """O validador (Q.169.B) também usa match exato — Infusão solo é
        o estado normal, não um warning."""
        state = _state()
        state.phase_catalog = [
            {"fase_id": "41", "fase_nome": "Laminagem Infusão", "sequence": 1},
        ]
        rep = validate_schedule({"operations": [{
            "operation_id": "a", "order_id": "OF-1", "phase_id": "41",
            "machine_id": None, "workers": ["W1"], "mold_id": None,
            "mold_batch_id": None,
            "start_time": _T0.isoformat(),
            "end_time": (_T0 + timedelta(hours=4)).isoformat(),
        }]}, state=state)
        assert rep.ok
        assert not any("par-preferida" in w for w in rep.warnings)

    def test_laminagem_solo_still_warns(self):
        state = _state()
        state.phase_catalog = [
            {"fase_id": "40", "fase_nome": "Laminagem", "sequence": 1},
        ]
        rep = validate_schedule({"operations": [{
            "operation_id": "a", "order_id": "OF-1", "phase_id": "40",
            "machine_id": None, "workers": ["W1"], "mold_id": None,
            "mold_batch_id": None,
            "start_time": _T0.isoformat(),
            "end_time": (_T0 + timedelta(hours=4)).isoformat(),
        }]}, state=state)
        assert rep.ok
        assert any("par-preferida" in w for w in rep.warnings)
