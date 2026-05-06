"""Q.17.E — pre-approval safety mechanisms.

Two static (no-DB) checks every rule must pass before transitioning
``proposed → active``:

1. **Axiom check** (:class:`AxiomChecker`) — for each Spelke axiom the
   rule pledges to preserve in ``constraints.axioms_required``, verify
   that the rule's declared actions cannot logically violate it. This
   is a static analysis: it doesn't run the rule, only inspects its
   ``then[*]`` shape against an axiom-specific veto list.

2. **Conflict resolver** (:class:`ConflictResolver`) — find currently
   active rules that would collide with the new one at runtime. Two
   rules conflict when both:
   - target the same ``modify_fitness.weight_key`` with different
     multipliers,
   - emit ``block`` actions for the same ``scope``,
   - ``reassign_worker`` for the same ``phase_id``,
   - ``set_config`` on the same ``(category, key)`` with different
     ``value``s,
   - ``pause_writes`` on the same ``route_prefix``.

Sandbox dry-run (running 1 schedule with the rule injected and
comparing KPIs vs baseline) is deferred to Q.17.E.2 — it requires real
CPO integration which is out of scope here.

The :func:`run_safety_checks` orchestrator is called from
:meth:`RuleProposalService.approve` and raises
:class:`RuleSafetyError` if any errors are found.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable

from src.governance.yaml_policy.rule_schema import (
    ActionType,
    AxiomRequirement,
    Rule,
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SafetyViolation:
    """A single safety check finding."""

    rule_id: str
    check: str  # "axiom" | "conflict"
    severity: str  # "error" | "warning"
    code: str  # short machine-readable code (e.g. "axiom.skill_match.reassign_unguarded")
    detail: str
    context: dict[str, Any] = field(default_factory=dict)


class RuleSafetyError(RuntimeError):
    """Raised when one or more ``severity=error`` violations are found."""

    def __init__(self, violations: list[SafetyViolation]):
        self.violations = violations
        msg = "; ".join(f"[{v.code}] {v.detail}" for v in violations)
        super().__init__(f"safety check failed: {msg}")


# ---------------------------------------------------------------------------
# Axiom checks
# ---------------------------------------------------------------------------


class AxiomChecker:
    """Static safety check against the 7 Spelke axioms.

    Strategy: each axiom has a veto list of action shapes that, if
    present in the rule's ``then[*]``, would violate the axiom. The
    check returns one violation per (axiom × offending action) pair.

    The checks are deliberately conservative — better to refuse a safe
    rule and force the author to refine it than to admit a rule that
    silently breaks the kernel. The author can either fix the rule, or
    drop the axiom from ``constraints.axioms_required`` if they're sure.
    """

    def check(self, rule: Rule) -> list[SafetyViolation]:
        out: list[SafetyViolation] = []
        for axiom in rule.constraints.axioms_required:
            checker = self._handlers.get(axiom)
            if checker is None:
                _log.debug("no checker for axiom %s; skipping", axiom.value)
                continue
            out.extend(checker(self, rule))
        return out

    # --- per-axiom checks ------------------------------------------------
    # Each returns a list of violations for the given rule.

    def _check_capacity_non_negative(self, rule: Rule) -> list[SafetyViolation]:
        """Axiom 1 — capacity ≥ 0.

        Veto: ``set_config`` that sets a capacity-related key to a
        negative value (statically detectable).
        """
        out: list[SafetyViolation] = []
        for step in rule.then:
            if step.action is ActionType.SET_CONFIG:
                value = step.params.get("value")
                key = str(step.params.get("key", ""))
                cat = str(step.params.get("category", ""))
                if (cat, key) in {
                    ("planning", "capacity.boats_per_phase_per_day"),
                    ("transporte", "truck.capacity"),
                    ("transporte", "truck.capacity_moda"),
                } and isinstance(value, (int, float)) and value < 0:
                    out.append(SafetyViolation(
                        rule_id=rule.id, check="axiom", severity="error",
                        code="axiom.capacity_non_negative.negative_set_config",
                        detail=f"set_config {cat}.{key}={value} viola axiom 1 (capacity ≥ 0)",
                        context={"category": cat, "key": key, "value": value},
                    ))
        return out

    def _check_precedence_monotonic(self, rule: Rule) -> list[SafetyViolation]:
        """Axiom 2 — phase precedence cannot be inverted.

        Veto: ``set_config`` on routing.phases.* that could re-order
        phases. We don't know the dependency graph statically, so we
        warn (not error) on any routing edit.
        """
        out: list[SafetyViolation] = []
        for step in rule.then:
            if step.action is ActionType.SET_CONFIG:
                cat = str(step.params.get("category", ""))
                key = str(step.params.get("key", ""))
                if cat == "routing" and "phases" in key:
                    out.append(SafetyViolation(
                        rule_id=rule.id, check="axiom", severity="warning",
                        code="axiom.precedence_monotonic.routing_edit",
                        detail=f"set_config {cat}.{key} pode alterar precedência de fases — confirma manualmente",
                        context={"category": cat, "key": key},
                    ))
        return out

    def _check_mold_exclusive(self, rule: Rule) -> list[SafetyViolation]:
        """Axiom 3 — molde exclusivo (1 poço ≠ 2 barcos simultâneos).

        Veto: ``reassign_worker`` is fine; ``set_config`` on mold
        capacity > 1 is suspect. Only warn — most edits are legit.
        """
        out: list[SafetyViolation] = []
        for step in rule.then:
            if step.action is ActionType.SET_CONFIG:
                key = str(step.params.get("key", ""))
                if "mold.pocket_count" in key:
                    val = step.params.get("value")
                    if isinstance(val, int) and val > 7:
                        out.append(SafetyViolation(
                            rule_id=rule.id, check="axiom", severity="error",
                            code="axiom.mold_exclusive.pocket_count_excess",
                            detail=f"mold.pocket_count={val} excede observado em produção (max 7)",
                            context={"value": val},
                        ))
        return out

    def _check_dual_resource_laminagem(self, rule: Rule) -> list[SafetyViolation]:
        """Axiom 4 — Laminagem é par (88.5%).

        Veto: ``reassign_worker`` para fase Laminagem que substituí 2
        operadores por 1 (não detectável estaticamente sem schedule).
        Apenas warn em qualquer reassign de Laminagem.
        """
        out: list[SafetyViolation] = []
        for step in rule.then:
            if step.action is ActionType.REASSIGN_WORKER:
                phase = str(step.params.get("phase_id", "")).lower()
                if "laminagem" in phase:
                    out.append(SafetyViolation(
                        rule_id=rule.id, check="axiom", severity="warning",
                        code="axiom.dual_resource_laminagem.reassign",
                        detail=(
                            f"reassign_worker em fase {phase!r} requer par; "
                            "verifica que o operador substituto tem parceiro disponível"
                        ),
                        context={"phase_id": phase},
                    ))
        return out

    def _check_skill_match(self, rule: Rule) -> list[SafetyViolation]:
        """Axiom 5 — skill match (não-aptos rejeitados).

        Veto: ``reassign_worker`` sem indicar a skill alvo é arriscado.
        """
        out: list[SafetyViolation] = []
        for step in rule.then:
            if step.action is ActionType.REASSIGN_WORKER:
                # We can't statically check the worker has the skill;
                # but we can warn the author to verify.
                if not step.params.get("phase_id"):
                    out.append(SafetyViolation(
                        rule_id=rule.id, check="axiom", severity="error",
                        code="axiom.skill_match.no_phase_id",
                        detail="reassign_worker sem phase_id viola skill match — não há contexto para validar competência",
                    ))
        return out

    def _check_curing_gaps(self, rule: Rule) -> list[SafetyViolation]:
        """Axiom 6 — cura/secagem (16 transições min_gap_hours).

        Veto: ``set_config`` em ``planning.curing_gaps.*`` para 0 ou negativo.
        """
        out: list[SafetyViolation] = []
        for step in rule.then:
            if step.action is ActionType.SET_CONFIG:
                cat = str(step.params.get("category", ""))
                key = str(step.params.get("key", ""))
                val = step.params.get("value")
                if cat == "planning" and "curing" in key.lower():
                    if isinstance(val, (int, float)) and val <= 0:
                        out.append(SafetyViolation(
                            rule_id=rule.id, check="axiom", severity="error",
                            code="axiom.curing_gaps.non_positive",
                            detail=f"set_config {cat}.{key}={val} viola axiom 6 (curing gap > 0)",
                            context={"category": cat, "key": key, "value": val},
                        ))
        return out

    def _check_safety_net_baseline(self, rule: Rule) -> list[SafetyViolation]:
        """Axiom 7 — safety net (CPO ≥ baseline).

        Veto: ``modify_fitness`` com multiplicadores extremos que
        provavelmente fazem o solver convergir para soluções ruins.
        Schema já bound em ±50%, mas dois-passos com 1.5x cumulativo
        seriam suspect. Aqui apenas warn em multipliers >1.4 ou <0.6.
        """
        out: list[SafetyViolation] = []
        for step in rule.then:
            if step.action is ActionType.MODIFY_FITNESS:
                mult = float(step.params.get("multiplier", 1.0))
                if mult > 1.4 or mult < 0.6:
                    out.append(SafetyViolation(
                        rule_id=rule.id, check="axiom", severity="warning",
                        code="axiom.safety_net_baseline.aggressive_multiplier",
                        detail=(
                            f"modify_fitness multiplier={mult} é agressivo; "
                            "pode degradar baseline e accionar safety_net"
                        ),
                        context={"multiplier": mult},
                    ))
        return out

    @property
    def _handlers(self):
        return {
            AxiomRequirement.CAPACITY_NON_NEGATIVE: AxiomChecker._check_capacity_non_negative,
            AxiomRequirement.PRECEDENCE_MONOTONIC: AxiomChecker._check_precedence_monotonic,
            AxiomRequirement.MOLD_EXCLUSIVE: AxiomChecker._check_mold_exclusive,
            AxiomRequirement.DUAL_RESOURCE_LAMINAGEM: AxiomChecker._check_dual_resource_laminagem,
            AxiomRequirement.SKILL_MATCH: AxiomChecker._check_skill_match,
            AxiomRequirement.CURING_GAPS: AxiomChecker._check_curing_gaps,
            AxiomRequirement.SAFETY_NET_BASELINE: AxiomChecker._check_safety_net_baseline,
        }


# ---------------------------------------------------------------------------
# Conflict resolver
# ---------------------------------------------------------------------------


class ConflictResolver:
    """Detect rules that would collide at runtime with the new rule."""

    def find_conflicts(
        self,
        new_rule: Rule,
        active_rules: Iterable[Rule],
    ) -> list[SafetyViolation]:
        out: list[SafetyViolation] = []
        for other in active_rules:
            if other.id == new_rule.id:
                continue
            for step_new in new_rule.then:
                for step_old in other.then:
                    if step_new.action != step_old.action:
                        continue
                    conflict = self._conflict_for_action(
                        step_new.action, step_new.params, step_old.params,
                    )
                    if conflict is not None:
                        out.append(SafetyViolation(
                            rule_id=new_rule.id, check="conflict", severity="error",
                            code=f"conflict.{step_new.action.value}",
                            detail=(
                                f"colide com rule {other.id!r} ({step_new.action.value}): {conflict}"
                            ),
                            context={
                                "other_rule_id": other.id,
                                "action": step_new.action.value,
                            },
                        ))
        return out

    def _conflict_for_action(
        self,
        action: ActionType,
        new_params: dict[str, Any],
        old_params: dict[str, Any],
    ) -> str | None:
        if action is ActionType.MODIFY_FITNESS:
            if new_params.get("weight_key") == old_params.get("weight_key"):
                if new_params.get("multiplier") != old_params.get("multiplier"):
                    return (
                        f"ambas modificam fitness weight {new_params['weight_key']!r} "
                        f"com multiplicadores diferentes "
                        f"({new_params.get('multiplier')} vs {old_params.get('multiplier')})"
                    )
        elif action is ActionType.BLOCK:
            if new_params.get("scope") == old_params.get("scope"):
                return f"ambas bloqueiam scope {new_params['scope']!r} (redundante)"
        elif action is ActionType.REASSIGN_WORKER:
            if new_params.get("phase_id") == old_params.get("phase_id"):
                if new_params.get("replacement_worker_id") != old_params.get("replacement_worker_id"):
                    return (
                        f"ambas reatribuem fase {new_params['phase_id']!r} para "
                        f"operadores diferentes"
                    )
        elif action is ActionType.SET_CONFIG:
            if (
                new_params.get("category") == old_params.get("category")
                and new_params.get("key") == old_params.get("key")
            ):
                if new_params.get("value") != old_params.get("value"):
                    return (
                        f"ambas escrevem em {new_params['category']}.{new_params['key']} "
                        f"com valores diferentes"
                    )
        elif action is ActionType.PAUSE_WRITES:
            if new_params.get("route_prefix") == old_params.get("route_prefix"):
                return f"ambas pausam escritas em {new_params['route_prefix']!r}"
        return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_safety_checks(
    new_rule: Rule,
    *,
    active_rules: Iterable[Rule] = (),
) -> list[SafetyViolation]:
    """Run axiom + conflict checks. Returns ALL violations (errors + warnings).

    The caller is responsible for filtering by severity:

        violations = run_safety_checks(rule, active_rules=...)
        errors = [v for v in violations if v.severity == "error"]
        if errors:
            raise RuleSafetyError(errors)

    Warnings are surfaced to the UI but don't block approval — the
    operator can choose to proceed with eyes open.
    """
    out: list[SafetyViolation] = []
    out.extend(AxiomChecker().check(new_rule))
    out.extend(ConflictResolver().find_conflicts(new_rule, active_rules))
    return out
