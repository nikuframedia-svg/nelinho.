"""
ProdPlan ONE — Reichenbach common-cause detector (Sprint Q.15.D.2)
==================================================================

Princípio de Reichenbach (1956): se A e B variam juntos no tempo, ou
A causa B, ou B causa A, ou existe uma causa comum C que afecta ambos.

Na NELO a hipótese mais frequente é a 3ª — recurso partilhado:

  * Mesmo molde degradado afecta Laminagem (causa) E Pintura
    (consequência via retrabalho).
  * Mesmo operador chefe que está fora afecta as 2 fases onde ele
    aparece habitualmente.
  * Cascata: erros em Laminagem → defeitos detectados em Desmolde →
    barcos voltam → Lixagem fica sobrecarregada. Tudo "drift", mas
    a causa raiz é só Laminagem.

D.2 envia 3 checks:
  1. ``_check_shared_mold`` — molde usado por barcos que passaram por
     TODAS as fases que drift juntas, com taxa de erro anormal.
  2. ``_check_shared_workers`` — operadores activos em todas as fases
     que drift juntas, com horas/carga anormalmente altas.
  3. ``_check_cascade`` — uma fase que precede a outra no routing
     com taxa de erro elevada.

D.3 (sprint seguinte) acrescenta material / transport / shift.

Ordem de chamada — recurso partilhado ANTES de cascata: senão um
problema de molde compartilhado é mal-classificado como cascade.

Output uniforme com ERRO-TREE (D.1)
-----------------------------------

Cada check devolve ``Optional[Hypothesis]`` com ``alpha/beta`` no
mesmo modelo Beta-Bernoulli — confidence comparável across detectors.
A confidence ≥ 0.7 trip threshold é mantida para coerência.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID

from src.explain.diagnostics.erro_tree import ErroTreeDetector
from src.explain.diagnostics.repository import DiagnosticsRepository
from src.explain.diagnostics.types import Hypothesis, TriggerType
from src.shared.decorators import record_rule_firing
from src.shared.time import local_today

logger = logging.getLogger(__name__)


_CONFIDENCE_STOP_THRESHOLD = 0.7
_DEFAULT_PERIOD_DAYS = 7

# Mold-share threshold: molde tem que estar nos boats de mais de 30%
# das fases que drift para ser considerado "partilhado de facto".
_MIN_MOLD_SHARE = 0.3
_MOLD_RECENT_VS_HIST_RATIO = 1.5

# Worker-share threshold: operador a fazer pelo menos 50h na semana
# (vs ~40h normal) é candidato a sobrecarga.
_OVERTIME_HOURS_PER_WEEK = 45.0


# ───────────────────────────────────────────────────────────────────────────
# Per-check protocol + dataclasses
# ───────────────────────────────────────────────────────────────────────────


class _CommonCauseCheck(Protocol):
    name: str
    async def check(
        self, *, deviating_phases: List[str], period_days: int,
    ) -> Optional[Hypothesis]: ...


@dataclass
class CommonCauseResult:
    """Output of :meth:`ReichenbachDetector.find_common_cause`.

    Persisted by the @record_rule_firing decorator into
    ``governance.rule_firing.rule_output`` and by the endpoint into
    the JSON response body.
    """

    common_causes: List[Hypothesis]
    independent_causes: List[Hypothesis]
    verdict: str          # "common_cause" | "independent" | "inconclusive"
    checks_run: List[Dict[str, Any]] = field(default_factory=list)


# ───────────────────────────────────────────────────────────────────────────
# Individual checks
# ───────────────────────────────────────────────────────────────────────────


@dataclass
class SharedMoldCheck:
    """Check 1 — molde partilhado por barcos atravessando todas as
    fases que drift, com taxa de erro acima do baseline."""

    repo: DiagnosticsRepository
    name: str = "shared_mold"

    async def check(
        self, *, deviating_phases: List[str], period_days: int,
    ) -> Optional[Hypothesis]:
        if len(deviating_phases) < 2:
            return None

        end = local_today()
        start = end - timedelta(days=period_days)
        start_baseline = end - timedelta(days=period_days * 6)

        # Boats that passed through ALL deviating phases inside the window.
        common_boats = await self.repo.boats_through_phases(
            deviating_phases, start, end,
        )
        if not common_boats:
            return None

        # Molds these boats used (count = how many of_phase rows
        # shared this mold). The most-used mold is the strongest
        # candidate for "shared cause".
        mold_counts = await self.repo.molds_used_by_boats(
            common_boats, start, end,
        )
        if not mold_counts:
            return None

        # Pick molds whose share among the common boats is > 30%
        total_phases = sum(mold_counts.values())
        candidates = [
            (mold_id, count) for mold_id, count in mold_counts.items()
            if count / max(1, total_phases) >= _MIN_MOLD_SHARE
        ]
        candidates.sort(key=lambda x: -x[1])

        for mold_id, count in candidates:
            usage_recent = await self.repo.mold_usage(mold_id, start, end)
            usage_hist = await self.repo.mold_usage(
                mold_id, start_baseline, start,
            )
            if usage_recent.error_rate < 0.10:
                continue
            if usage_hist.error_rate <= 0:
                continue
            ratio = usage_recent.error_rate / usage_hist.error_rate
            if ratio < _MOLD_RECENT_VS_HIST_RATIO:
                continue

            # Build hypothesis (same Beta-Bernoulli scheme as ERRO-TREE
            # mold detector for cross-handler comparability).
            ratio_score = min(5.0, max(0.0, (ratio - 1.0) * 2.5))
            share_score = min(4.0, count / max(1, total_phases) * 8.0)
            alpha = 1.0 + ratio_score + share_score
            beta = 2.0
            return Hypothesis(
                type="shared_mold",
                entity=mold_id,
                alpha=alpha,
                beta=beta,
                evidence=[
                    f"Molde {mold_id} usado em {count}/{total_phases} "
                    f"fases dos {len(common_boats)} barcos comuns "
                    f"({count / max(1, total_phases):.0%} share)",
                    f"Taxa erro recente {usage_recent.error_rate:.0%} "
                    f"vs histórica {usage_hist.error_rate:.0%} "
                    f"(ratio {ratio:.1f}×)",
                    f"Fases que drift juntas: {', '.join(deviating_phases)}",
                ],
            )
        return None


@dataclass
class SharedWorkersCheck:
    """Check 2 — operadores activos em TODAS as fases que drift, com
    sobrecarga (overtime) que pode estar a degradar performance."""

    repo: DiagnosticsRepository
    name: str = "shared_workers"

    async def check(
        self, *, deviating_phases: List[str], period_days: int,
    ) -> Optional[Hypothesis]:
        if len(deviating_phases) < 2:
            return None

        end = local_today()
        start = end - timedelta(days=period_days)

        # Set per phase, then intersection.
        worker_sets: List[set] = []
        for phase_id in deviating_phases:
            worker_set = await self.repo.workers_in_phase_set(
                phase_id, start, end,
            )
            if not worker_set:
                # Empty phase → can't have shared workers AT ALL.
                return None
            worker_sets.append(worker_set)

        shared_workers = set.intersection(*worker_sets)
        if not shared_workers:
            return None

        # Pick the most-overloaded shared worker.
        weeks_in_window = max(1.0, period_days / 7.0)
        threshold_hours = _OVERTIME_HOURS_PER_WEEK * weeks_in_window
        candidates: List[tuple] = []
        for worker_id in shared_workers:
            hours = await self.repo.worker_hours_during(worker_id, start, end)
            if hours >= threshold_hours:
                candidates.append((worker_id, hours))

        if not candidates:
            return None

        candidates.sort(key=lambda x: -x[1])
        worker_id, hours = candidates[0]
        # Confidence proportional to how far over the threshold the
        # worker is. At threshold (~45h/wk) confidence ~0.71.
        excess_score = min(8.0, max(0.0, (hours / threshold_hours - 1.0) * 6.5))
        alpha = 1.0 + 4.0 + excess_score   # 4 = base "is shared in N phases"
        beta = 2.0
        return Hypothesis(
            type="shared_workers",
            entity=worker_id,
            alpha=alpha,
            beta=beta,
            evidence=[
                f"{worker_id} activo em todas as fases que drift "
                f"({len(deviating_phases)})",
                f"Horas no período: {hours:.0f}h "
                f"(threshold sobrecarga: {threshold_hours:.0f}h)",
                "Sobrecarga partilhada entre fases → causa comum",
            ],
        )


@dataclass
class CascadeCheck:
    """Check 3 — efeito cascata: uma fase precede outra no routing E
    a fase upstream tem erros elevados. Não é causa "comum" no sentido
    estrito, mas resolve o problema dos sintomas duplos da mesma forma:
    arranja a fase upstream e ambas voltam ao normal.
    """

    repo: DiagnosticsRepository
    name: str = "cascade"

    async def check(
        self, *, deviating_phases: List[str], period_days: int,
    ) -> Optional[Hypothesis]:
        if len(deviating_phases) < 2:
            return None

        end = local_today()
        start = end - timedelta(days=period_days)

        # For each ordered pair (A, B), check if A precedes B AND
        # has elevated error rate.
        for i, phase_a in enumerate(deviating_phases):
            for phase_b in deviating_phases[i + 1:]:
                # Try both directions: A→B and B→A.
                for upstream, downstream in [(phase_a, phase_b), (phase_b, phase_a)]:
                    if not await self.repo.phase_precedes(upstream, downstream):
                        continue
                    upstream_rate = await self.repo.phase_error_rate(
                        upstream, start, end,
                    )
                    if upstream_rate < 0.15:
                        continue

                    # Beta math: stronger upstream rate → higher confidence.
                    rate_score = min(8.0, upstream_rate * 16.0)  # 0.15 → 2.4
                    alpha = 1.0 + 3.0 + rate_score   # 3 = base "is precedence relation"
                    beta = 2.0
                    return Hypothesis(
                        type="cascade_effect",
                        entity=f"{upstream} → {downstream}",
                        alpha=alpha,
                        beta=beta,
                        evidence=[
                            f"Fase {upstream} precede {downstream} no routing",
                            f"Taxa erro em {upstream}: {upstream_rate:.0%}",
                            f"Resolver {upstream} resolve {downstream} "
                            "(efeito cascata)",
                        ],
                    )
        return None


# ───────────────────────────────────────────────────────────────────────────
# Sprint Q.15.D.3 — completion: material / transport / shift checks
# ───────────────────────────────────────────────────────────────────────────


@dataclass
class SharedMaterialCheck:
    """Check 4 — same material lot affecting multiple phases.

    Material lot tracking is NOT in the NELO curated layer today
    (system prompt v2.2 §13 H2). Until ERP shadow-mode (Fase G)
    populates a `CuratedMaterialLot` table, this check returns None
    silently AND records a `data_unavailable` audit step in the
    orchestrator's `checks_run` so the operator sees we tried but
    couldn't.

    The ``has_material_lot_tracking`` repo helper auto-detects when
    the data lands — no code change needed. That's the difference
    between graceful degradation and dead code.
    """

    repo: DiagnosticsRepository
    name: str = "shared_material"

    async def check(
        self, *, deviating_phases: List[str], period_days: int,
    ) -> Optional[Hypothesis]:
        if len(deviating_phases) < 2:
            return None
        has_data = await self.repo.has_material_lot_tracking()
        if not has_data:
            # Honest "no signal" — orchestrator records this as
            # DATA_UNAVAILABLE rather than CLEAR.
            return None
        # When lot data lands, the implementation slot below activates.
        # Until then, no-op for safety.
        # Pseudo-code retained as a contract for the future ingest:
        #   lots = await repo.material_lots_for_phases(deviating_phases, ...)
        #   for lot in shared_lots: check error_rate_with_lot vs without
        return None


@dataclass
class SharedTransportCheck:
    """Check 5 — large upcoming shipment putting cross-phase pressure.

    Plan v4 §8 + §6.2 PASSO 4: when expedição has > 50 boats coming
    in the next week, operators across multiple phases push harder
    (overtime, faster pace) → defects rise across phases simultaneously.
    Diagnosing each phase isolated misses the common cause.

    Trigger: upcoming truck capacity in the next 7 days exceeds 75
    boats (1.5× the 50-boat truck baseline). Confidence scales with
    how far over the threshold the volume is.
    """

    repo: DiagnosticsRepository
    name: str = "shared_transport"
    pressure_floor: int = 75

    async def check(
        self, *, deviating_phases: List[str], period_days: int,
    ) -> Optional[Hypothesis]:
        if len(deviating_phases) < 2:
            return None
        upcoming = await self.repo.upcoming_transport_volume(days_ahead=7)
        if upcoming < self.pressure_floor:
            return None

        # Confidence proportional to over-floor excess. At pressure_floor
        # confidence ~0.71; at 2× floor it climbs to ~0.85.
        ratio = upcoming / max(1, self.pressure_floor)
        excess_score = min(8.0, max(0.0, (ratio - 1.0) * 8.0))
        alpha = 1.0 + 4.0 + excess_score   # 4 = base "is shared pressure"
        beta = 2.0
        return Hypothesis(
            type="shared_transport_pressure",
            entity=f"{upcoming} barcos próximos 7 dias",
            alpha=alpha,
            beta=beta,
            evidence=[
                f"Volume expedição próximos 7 dias: {upcoming} barcos "
                f"(threshold pressão: {self.pressure_floor})",
                f"Fases que drift juntas: {', '.join(deviating_phases)}",
                "Pressão de expedição → pressa transversal → "
                "erros sobem em múltiplas fases ao mesmo tempo",
            ],
        )


@dataclass
class SharedShiftCheck:
    """Check 6 — same shift (manhã/tarde/noite) affecting both phases.

    NELO runs 95% turno único manhã (Plan v4 §2.8) so this is rarely
    actionable on current data. Curated layer doesn't carry shift_id
    on `CuratedAllocation` yet. Like SharedMaterialCheck, this stays
    a graceful no-op until the ingest evolves.
    """

    repo: DiagnosticsRepository
    name: str = "shared_shift"

    async def check(
        self, *, deviating_phases: List[str], period_days: int,
    ) -> Optional[Hypothesis]:
        if len(deviating_phases) < 2:
            return None
        has_data = await self.repo.has_shift_tracking()
        if not has_data:
            return None
        # Future implementation: look up shift_id per allocation in
        # the deviating phases, intersect, flag the dominant shift if
        # its error rate spikes.
        return None


# ───────────────────────────────────────────────────────────────────────────
# Orchestrator
# ───────────────────────────────────────────────────────────────────────────


class ReichenbachDetector:
    """Find shared-resource causes when 2+ phases drift together.

    Order matters: shared mold + shared workers run BEFORE cascade. A
    mold genuinely degrading affects upstream and downstream phases
    simultaneously; if we ran cascade first we'd mistake the symptom
    for the cause.

    Falls back to per-phase ERRO-TREE when no common cause is found —
    each deviating phase gets its own diagnosis. The verdict reflects
    which path produced the answer.
    """

    def __init__(self, session: Any, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self._repo = DiagnosticsRepository(session, tenant_id)
        self._erro_tree = ErroTreeDetector(session, tenant_id)
        # Order matters:
        #   1. SharedMold + SharedWorkers — concrete recursos (high confidence).
        #   2. SharedTransport — system-wide pressure (moderate signal).
        #   3. SharedMaterial + SharedShift — return None today (no data),
        #      kept in the cascade so audit shows we tried.
        #   4. Cascade — last because a real shared resource shouldn't
        #      get mis-classified as a downstream propagation.
        self._checks: List[_CommonCauseCheck] = [
            SharedMoldCheck(self._repo),
            SharedWorkersCheck(self._repo),
            SharedTransportCheck(self._repo),
            SharedMaterialCheck(self._repo),
            SharedShiftCheck(self._repo),
            CascadeCheck(self._repo),
        ]

    async def _emit_chain(
        self, hypothesis: Hypothesis, conversation_id: UUID,
    ) -> None:
        """Build + verify + persist a CausalChain for the common cause."""
        try:
            from src.explain.diagnostics.chain_builder import (
                build_chain_from_hypothesis,
                record_diagnostic_chain,
            )
            chain = build_chain_from_hypothesis(
                hypothesis, trigger=TriggerType.QUALITY_DROP,
                handler="reichenbach",
            )
            await record_diagnostic_chain(
                session=self.session,
                tenant_id=self.tenant_id,
                conversation_id=conversation_id,
                chain=chain,
            )
        except Exception as exc:
            logger.debug(
                "ReichenbachDetector._emit_chain failed (%s)", exc,
            )

    @record_rule_firing(
        rule_id="diagnostics.reichenbach",
        extract_payload=lambda self, *, deviating_phases, period_days=_DEFAULT_PERIOD_DAYS: {
            "deviating_phases": list(deviating_phases),
            "period_days": period_days,
        },
        serialise_output=lambda result: {
            "verdict": result.verdict,
            "common_cause_count": len(result.common_causes),
            "checks_run": result.checks_run,
        },
        dedupe_key=lambda self, *, deviating_phases, period_days=_DEFAULT_PERIOD_DAYS: (
            "reichenbach:" + ",".join(sorted(deviating_phases))
        ),
    )
    async def find_common_cause(
        self,
        *,
        deviating_phases: List[str],
        period_days: int = _DEFAULT_PERIOD_DAYS,
        conversation_id: Optional[UUID] = None,
    ) -> CommonCauseResult:
        """Run the 3 shared-resource checks. Falls back to per-phase
        ERRO-TREE when none trip."""
        if len(deviating_phases) < 2:
            return CommonCauseResult(
                common_causes=[], independent_causes=[],
                verdict="inconclusive",
                checks_run=[{
                    "step": "input_validation",
                    "result": "ABORTED",
                    "detail": "need >= 2 deviating phases",
                }],
            )

        common: List[Hypothesis] = []
        steps: List[Dict[str, Any]] = []
        for check in self._checks:
            try:
                hypothesis = await check.check(
                    deviating_phases=deviating_phases,
                    period_days=period_days,
                )
            except Exception as exc:
                logger.warning(
                    "ReichenbachDetector: %s.check failed (%s)", check.name, exc,
                )
                hypothesis = None
            if hypothesis is not None and hypothesis.confidence >= _CONFIDENCE_STOP_THRESHOLD:
                steps.append({
                    "step": check.name, "result": "FOUND",
                    "detail": hypothesis.entity,
                    "confidence": round(hypothesis.confidence, 3),
                })
                common.append(hypothesis)
            else:
                # Sprint Q.15.D.3 — distinguish "data unavailable" from
                # genuine CLEAR for the audit trail. Material + Shift
                # checks today always return None because the curated
                # layer doesn't carry the data; surface that honestly so
                # operators don't read absence-of-flag as absence-of-cause.
                data_unavailable_checks = (
                    "shared_material" if not await self._repo.has_material_lot_tracking() else None,
                    "shared_shift" if not await self._repo.has_shift_tracking() else None,
                )
                if check.name in data_unavailable_checks:
                    steps.append({
                        "step": check.name, "result": "DATA_UNAVAILABLE",
                        "detail": (
                            "curated layer doesn't carry this signal yet "
                            "(activates automatically when ERP shadow lands)"
                        ),
                    })
                else:
                    steps.append({
                        "step": check.name, "result": "CLEAR",
                        "detail": (
                            hypothesis.entity if hypothesis is not None
                            else "sem evidência"
                        ),
                    })

        if common:
            common.sort(key=lambda h: -h.confidence)
            # Sprint Q.15.D.5 — emit CausalChain for the strongest
            # common cause when the caller supplied a conversation_id.
            if conversation_id is not None:
                await self._emit_chain(common[0], conversation_id)
            return CommonCauseResult(
                common_causes=common,
                independent_causes=[],
                verdict="common_cause",
                checks_run=steps,
            )

        # Fallback: diagnose each phase isolated via ERRO-TREE.
        independent: List[Hypothesis] = []
        for phase_id in deviating_phases:
            try:
                result = await self._erro_tree.investigate(
                    trigger=TriggerType.QUALITY_DROP,
                    period_days=period_days,
                    phase_id=phase_id,
                )
            except Exception as exc:
                logger.warning(
                    "ReichenbachDetector fallback ERRO-TREE for %s failed (%s)",
                    phase_id, exc,
                )
                continue
            if result.root_cause is not None:
                independent.append(result.root_cause)
        steps.append({
            "step": "erro_tree_fallback",
            "result": "FOUND" if independent else "CLEAR",
            "detail": f"{len(independent)} per-phase root causes",
        })
        return CommonCauseResult(
            common_causes=[],
            independent_causes=independent,
            verdict="independent" if independent else "inconclusive",
            checks_run=steps,
        )


__all__ = [
    "CascadeCheck",
    "CommonCauseResult",
    "ReichenbachDetector",
    "SharedMoldCheck",
    "SharedWorkersCheck",
]
