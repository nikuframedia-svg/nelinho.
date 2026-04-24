"""Sprint C 2.2 — Camada 1 aprendizagem (§50 do blueprint).

The detector mines `ScheduleCommit.rejected_alternatives` + `user_
preference_signal` (which the Sprint B CO1 work wired) and surfaces
recurring patterns as `PreferenceRule` rows awaiting operator
confirmation. This is the moat: every confirmed rule is a piece of
tacit factory knowledge that becomes part of the scheduler's behaviour.
"""

from .detector import PreferenceRuleDetector

__all__ = ["PreferenceRuleDetector"]
