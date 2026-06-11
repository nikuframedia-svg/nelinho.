"""
ProdPlan ONE — ERRO-TREE Detector (Sprint Q.15.D.1)
====================================================

Cascade of 4 detectors (mold, worker, material, overload) that diagnose
why a quality / throughput / delay drop happened. Stops at the first
detector with confidence >= 0.7 — operator gets one root cause to act
on, not 4 hypotheses to triage.

Order matters
-------------

Empirically (NELO, 6 years, 89.836 errors): 35% of errors trace to
mold degradation, the rest split across workers + material + overload.
Mold first means the most-likely cause gets evaluated cheapest;
operator interrupts the cascade as soon as confidence trips.

Reuses
------

  * ``DiagnosticsRepository`` (D.0) for every query.
  * ``Hypothesis`` Beta-Bernoulli math (D.0 / Q.14.C).
  * ``@record_rule_firing`` (Q.14.A) on `investigate()` for audit +
    push reactivo via Q.14.B.
  * ``CausalChain`` Pydantic model (Q.13.D) for the verifiable output
    that feeds the Camada-4 ABL job.

What the cascade returns
------------------------

When a detector trips: ``DiagnosticResult`` with ``root_cause`` set,
the cascade stops, remaining steps marked SKIPPED. The hypothesis
carries (alpha, beta) so the audit dashboard renders confidence + CI
honestly.

When NO detector trips: ``root_cause=None``, ``chain`` carries the
"no isolated cause" narration; recommendation suggests manual review.
This is the right answer when the symptom is a combination of factors
none of which dominates statistically.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID

from src.explain.diagnostics.repository import DiagnosticsRepository
from src.explain.diagnostics.types import (
    DiagnosticResult,
    Hypothesis,
    TriggerType,
)
from src.shared.decorators import record_rule_firing
from src.shared.time import local_today

logger = logging.getLogger(__name__)


# Confidence threshold for stopping the cascade. 0.7 = 70% posterior
# mean. Tunable per-tenant in a future sprint via TenantConfig; today
# hard-coded for simplicity.
_CONFIDENCE_STOP_THRESHOLD = 0.7

# How far back to look for evidence by default. 7 days = a week,
# enough to capture a drift without the noise of a single bad day.
_DEFAULT_PERIOD_DAYS = 7

# Mold detector specifics
_MOLD_RECENT_VS_HISTORICAL_RATIO = 1.5     # recent rate / historical rate
_MOLD_MIN_RECENT_RATE = 0.15               # absolute floor — 15%
_MOLD_TYPED_ERROR_SHARE_THRESHOLD = 0.5    # > 50% of errors are mold-typed
# Phase IDs treated as the "mold-attributable" error families. Plan v4
# §7 — interior enrugado, molde baço, deformação são causados upstream
# pelo molde, não pelo operador da fase de detecção.
_MOLD_TYPED_ERROR_KEYWORDS = (
    "interior enrugado", "molde baço", "molde baco",
    "deformação", "deformacao", "bolha",
)

# Worker detector specifics
_WORKER_MIN_TENURE_MONTHS = 5
_WORKER_OUTLIER_RATIO = 2.0  # worker error rate / phase avg

# Overload detector specifics
_OVERLOAD_WIP_RATIO = 1.3  # current WIP / historical avg


# ───────────────────────────────────────────────────────────────────────────
# Detectors
# ───────────────────────────────────────────────────────────────────────────


class _Detector(Protocol):
    name: str
    async def check(
        self, *, trigger: TriggerType, period_days: int, phase_id: Optional[str],
    ) -> Optional[Hypothesis]: ...


@dataclass
class MoldDetector:
    """PASSO 1 — verifica se algum molde em uso recentemente tem taxa
    de erro anormal e tipos de erro tipicamente atribuíveis a moldes.

    Pluna v4 §7: 35% dos erros são "molde com deformações" + "molde
    baço". Quando o gestor reporta queda de qualidade, o causa raiz
    mais provável estatisticamente é um molde degradado.
    """
    repo: DiagnosticsRepository
    name: str = "moldes"

    async def check(
        self, *, trigger, period_days, phase_id,
    ) -> Optional[Hypothesis]:
        end = local_today()
        start_recent = end - timedelta(days=period_days)
        # Historical baseline: 6× the recent window (180d default), so
        # a real shift stands out from noise.
        start_historical = end - timedelta(days=period_days * 6)

        molds = await self.repo.molds_active_during(start_recent, end)
        if not molds:
            return None

        for mold_id in molds:
            recent_phases = await self.repo.mold_phase_count(
                mold_id, start_recent, end,
            )
            if recent_phases == 0:
                continue
            recent_errors = await self.repo.mold_error_count(
                mold_id, start_recent, end,
            )
            recent_rate = recent_errors / recent_phases

            historical_phases = await self.repo.mold_phase_count(
                mold_id, start_historical, start_recent,
            )
            if historical_phases == 0:
                # No baseline — refuse to flag (could be a brand new mold).
                continue
            historical_errors = await self.repo.mold_error_count(
                mold_id, start_historical, start_recent,
            )
            historical_rate = historical_errors / historical_phases

            # Two gates: recent rate is a real outlier AND mold-typed
            # errors dominate (otherwise it's likely upstream of the mold).
            if recent_rate < _MOLD_MIN_RECENT_RATE:
                continue
            if historical_rate > 0 and recent_rate < historical_rate * _MOLD_RECENT_VS_HISTORICAL_RATIO:
                continue

            error_types = await self.repo.mold_error_types(
                mold_id, start_recent, end,
            )
            if not error_types:
                continue
            typed = sum(
                count for tipo, count in error_types.items()
                if any(kw in (tipo or "").lower() for kw in _MOLD_TYPED_ERROR_KEYWORDS)
            )
            total = sum(error_types.values())
            if total == 0 or typed / total < _MOLD_TYPED_ERROR_SHARE_THRESHOLD:
                continue

            # All gates passed. Beta-Bernoulli confidence here is
            # "how confident am I that THIS mold is the root cause", not
            # "what's the error rate". So alpha counts pieces of
            # evidence supporting the hypothesis (gates passed × scaling
            # by ratio strength), beta is a small skepticism prior.
            ratio = recent_rate / historical_rate
            ratio_score = min(5.0, max(0.0, ratio - 1.0) * 2.5)
            typed_score = (typed / total) * 4.0
            alpha = 1.0 + ratio_score + typed_score   # range 1.0–10.0
            beta = 2.0                                # uniform skepticism
            return Hypothesis(
                type="mold_degradation",
                entity=mold_id,
                alpha=alpha,
                beta=beta,
                evidence=[
                    f"Taxa erro recente {recent_rate:.0%} "
                    f"vs histórica {historical_rate:.0%} (ratio {ratio:.1f}×)",
                    f"{typed}/{total} erros são tipicamente de molde "
                    f"(deformação / baço / interior enrugado)",
                    f"Molde {mold_id} usado em {recent_phases} fases "
                    f"nos últimos {period_days} dias",
                ],
            )
        return None


@dataclass
class WorkerDetector:
    """PASSO 2 — verifica se algum operador tem taxa de erro anormal
    numa fase crítica.

    Plan v4 §6.3: operadores com tier <5 meses ou com taxa erro >2× a
    média da fase são candidatos a causa raiz quando moldes estão OK.
    """
    repo: DiagnosticsRepository
    name: str = "operadores"

    async def check(
        self, *, trigger, period_days, phase_id,
    ) -> Optional[Hypothesis]:
        end = local_today()
        start = end - timedelta(days=period_days)

        # Without phase_id we'd have to scan every phase. To keep this
        # detector cheap, require a phase_id (the cascade caller passes
        # it when known). Without one, skip cleanly.
        if phase_id is None:
            return None

        phase_avg_rate = await self.repo.phase_error_rate(phase_id, start, end)
        if phase_avg_rate == 0.0:
            # No phase activity at all in the window — nothing to compare.
            return None

        workers = await self.repo.workers_active_in_phase(phase_id, start, end)
        if not workers:
            return None

        # Look at the most-active workers first (they had the most
        # opportunity to cause variance).
        workers.sort(key=lambda x: -x[1])

        for worker_id, _ in workers:
            stats = await self.repo.worker_phase_stats(
                worker_id, phase_id, start, end,
            )
            if stats.total_allocations < 3:
                # Tiny sample — could be tomorrow's apprentice. Skip.
                continue
            if stats.error_rate < phase_avg_rate * _WORKER_OUTLIER_RATIO:
                continue

            # Confidence proportional to the outlier ratio. At the
            # threshold (2× phase avg) confidence is ~0.71; at 4×
            # confidence climbs to ~0.85.
            ratio = stats.error_rate / max(phase_avg_rate, 1e-6)
            outlier_score = min(8.0, max(0.0, (ratio - 1.0) * 2.5))
            alpha = 1.0 + outlier_score        # range 1.0–9.0
            beta = 2.0
            return Hypothesis(
                type="worker_skill",
                entity=worker_id,
                alpha=alpha,
                beta=beta,
                evidence=[
                    f"Taxa erro do operador: {stats.error_rate:.0%} "
                    f"(média da fase: {phase_avg_rate:.0%}, ratio {ratio:.1f}×)",
                    f"Allocations no período: {stats.total_allocations} "
                    f"({stats.error_count} com erro)",
                    f"Fase: {phase_id}",
                ],
            )
        return None


@dataclass
class OverloadDetector:
    """PASSO 4 — verifica se a fábrica está sobrecarregada.

    Plan v4 §11: WIP normal está em 220-540 barcos; > 600 alarme. Quando
    sobrecarga, operadores fazem horas extra → pressa → erros sobem por
    cansaço, não por incompetência. Tratar a sobrecarga directamente
    (atrasar barcos não-urgentes) em vez de culpar um operador.
    """
    repo: DiagnosticsRepository
    name: str = "sobrecarga"

    async def check(
        self, *, trigger, period_days, phase_id,
    ) -> Optional[Hypothesis]:
        # phase_id is irrelevant for overload — it's a global signal.
        # We compare current WIP vs the 90-day rolling average.
        end = local_today()
        start = end - timedelta(days=period_days)
        start_baseline = end - timedelta(days=90)

        current_wip = await self.repo.current_wip()
        if current_wip == 0:
            return None
        avg_wip = await self.repo.avg_wip_during(start_baseline, start)
        if avg_wip == 0.0:
            return None

        ratio = current_wip / avg_wip
        if ratio < _OVERLOAD_WIP_RATIO:
            return None

        # Confidence proportional to over-WIP ratio. At the threshold
        # (1.3×) confidence is ~0.71; at 1.7×+ it climbs to ~0.83.
        excess_score = min(8.0, max(0.0, (ratio - 1.0) * 6.5))
        alpha = 1.0 + excess_score              # range 1.0–9.0
        beta = 2.0
        return Hypothesis(
            type="overload",
            entity="Fábrica sobrecarregada",
            alpha=alpha,
            beta=beta,
            evidence=[
                f"WIP actual: {current_wip} barcos "
                f"(média 90d: {avg_wip:.0f})",
                f"Ratio: {ratio:.2f}× normal",
                "Sobrecarga causa pressa → erros aumentam",
                "Sugestão: atrasar barcos não-urgentes",
            ],
        )


# ───────────────────────────────────────────────────────────────────────────
# Orchestrator
# ───────────────────────────────────────────────────────────────────────────


class ErroTreeDetector:
    """Run the cascade. Stop at the first hypothesis with confidence >= 0.7."""

    def __init__(self, session: Any, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self._repo = DiagnosticsRepository(session, tenant_id)
        # Order: most-prevalent cause first (mold). Worker before
        # overload because worker problems are easier to act on.
        # Q.67.3.E: Material detector bloqueado pendente ingestão de
        # material_lot data (issue Q.68.D — não há fonte ERP actual).
        # Ver Q.67.1.D explanation_engine para mesmo bloqueio. Quando
        # lot data estiver disponível, implementar detector que
        # correlaciona retrabalho com lot/batch ID.
        self._detectors: List[_Detector] = [
            MoldDetector(self._repo),
            WorkerDetector(self._repo),
            OverloadDetector(self._repo),
        ]

    async def _emit_chain(
        self,
        hypothesis: Hypothesis,
        trigger: TriggerType,
        conversation_id: UUID,
    ) -> None:
        """Build + verify + persist a CausalChain. Best-effort."""
        try:
            from src.explain.diagnostics.chain_builder import (
                build_chain_from_hypothesis,
                record_diagnostic_chain,
            )
            chain = build_chain_from_hypothesis(
                hypothesis, trigger=trigger, handler="erro_tree",
            )
            await record_diagnostic_chain(
                session=self.session,
                tenant_id=self.tenant_id,
                conversation_id=conversation_id,
                chain=chain,
            )
        except Exception as exc:
            logger.debug(
                "ErroTreeDetector._emit_chain failed (%s) — diagnosis "
                "still flows to operator", exc,
            )

    @record_rule_firing(
        rule_id="diagnostics.erro_tree",
        extract_payload=lambda self, *, trigger, period_days=_DEFAULT_PERIOD_DAYS,
        phase_id=None: {
            "trigger": trigger.value if hasattr(trigger, "value") else str(trigger),
            "period_days": period_days,
            "phase_id": phase_id,
        },
        serialise_output=lambda result: {
            "root_cause_type": result.root_cause.type if result.root_cause else None,
            "root_cause_entity": result.root_cause.entity if result.root_cause else None,
            "confidence": float(result.root_cause.confidence) if result.root_cause else None,
            "steps_checked": result.steps_checked,
        },
        dedupe_key=lambda self, *, trigger, period_days=_DEFAULT_PERIOD_DAYS,
        phase_id=None: (
            f"erro_tree:{trigger.value if hasattr(trigger, 'value') else trigger}"
            f":{phase_id or 'global'}"
        ),
    )
    async def investigate(
        self,
        *,
        trigger: TriggerType,
        period_days: int = _DEFAULT_PERIOD_DAYS,
        phase_id: Optional[str] = None,
        conversation_id: Optional[UUID] = None,
    ) -> DiagnosticResult:
        """Run the cascade. Returns a DiagnosticResult.

        Best-effort: if any detector raises, log + continue with the
        next. The cascade itself never raises — caller can rely on
        always getting a `DiagnosticResult`.

        Sprint Q.15.D.5 — when ``conversation_id`` is supplied AND a
        hypothesis trips, emit a verified ``CausalChain`` and persist
        it via ``record_causal_audit`` so the Camada-4 ABL job picks
        it up nightly. Best-effort: chain failures don't break the
        diagnosis; they just skip the audit.
        """
        steps: List[Dict[str, Any]] = []

        for detector in self._detectors:
            try:
                hypothesis = await detector.check(
                    trigger=trigger,
                    period_days=period_days,
                    phase_id=phase_id,
                )
            except Exception as exc:
                logger.warning(
                    "ErroTreeDetector: %s.check failed (%s) — treating as CLEAR",
                    detector.name, exc,
                )
                hypothesis = None

            if hypothesis is not None and hypothesis.confidence >= _CONFIDENCE_STOP_THRESHOLD:
                steps.append({
                    "step": detector.name,
                    "result": "FOUND",
                    "detail": hypothesis.entity,
                    "confidence": round(hypothesis.confidence, 3),
                })
                # Mark the rest as SKIPPED.
                for remaining in self._detectors[len(steps):]:
                    steps.append({
                        "step": remaining.name,
                        "result": "SKIPPED",
                        "detail": "causa já encontrada",
                    })
                # Sprint Q.15.D.5 — emit + persist CausalChain.
                if conversation_id is not None:
                    await self._emit_chain(hypothesis, trigger, conversation_id)
                return DiagnosticResult(
                    root_cause=hypothesis,
                    chain=_build_causal_chain(hypothesis, trigger),
                    steps_checked=steps,
                    recommendation=_recommend_action(hypothesis),
                )

            steps.append({
                "step": detector.name,
                "result": "CLEAR",
                "detail": (
                    hypothesis.entity if hypothesis is not None
                    else "sem anomalia detectada"
                ),
            })

        # No detector tripped — give the operator a clear "no isolated
        # cause" answer with the audit trail of what we DID check.
        return DiagnosticResult(
            root_cause=None,
            chain=[
                "Nenhuma causa isolada identificada com confiança ≥ 0.7",
                "Pode ser combinação de factores",
                "Sugestão: reunião com chefes de secção",
            ],
            steps_checked=steps,
            recommendation={
                "action": "Investigação manual",
                "detail": (
                    "Nenhum dos detectores automáticos encontrou causa "
                    f"com confiança ≥ {_CONFIDENCE_STOP_THRESHOLD:.0%}. "
                    "Pode haver combinação de factores."
                ),
            },
        )


# ───────────────────────────────────────────────────────────────────────────
# Hypothesis → narrative + recommendation
# ───────────────────────────────────────────────────────────────────────────


def _build_causal_chain(h: Hypothesis, trigger: TriggerType) -> List[str]:
    """Render the hypothesis into the 5-step NELO causal chain.

    For mold_degradation, follows the canonical chain from §10.1:
      Molde → Deformação Laminagem → Detection Desmolde → Lixagem
      sobrecarregada → Throughput cai
    """
    if h.type == "mold_degradation":
        return [
            f"Molde {h.entity} degradado (causa raiz)",
            "→ Deformações na Laminagem (defeitos upstream)",
            "→ Detectados no Desmolde (96.4% dos erros)",
            "→ Barcos voltam para Lixagem (retrabalho)",
            f"→ {trigger.value} observável (efeito final)",
        ]
    if h.type == "worker_skill":
        return [
            f"Operador {h.entity} com taxa erro acima da média",
            "→ Defeitos introduzidos durante a operação",
            f"→ {trigger.value} observável",
        ]
    if h.type == "overload":
        return [
            "Fábrica sobrecarregada (WIP > normal)",
            "→ Operadores em pressa, horas extra",
            "→ Erros aumentam por cansaço, não incompetência",
            f"→ {trigger.value} observável",
        ]
    return [f"Causa: {h.entity}", f"→ {trigger.value} observável"]


def _recommend_action(h: Hypothesis) -> Dict[str, Any]:
    """Map hypothesis type to a concrete operator action.

    Q.173.I — sem `cost_estimate_eur`/`downtime_hours` inventados
    (invariante #8): o sistema não tem dados reais de custo/paragem de
    manutenção de moldes; a recomendação é qualitativa e di-lo.
    """
    if h.type == "mold_degradation":
        return {
            "action": f"Manutenção do molde {h.entity}",
            "estimate": "sem estimativa — custo/paragem variam por molde; "
                        "pedir orçamento à manutenção",
            "alternative": (
                "Rerouting temporário para outro molde compatível "
                "(0 downtime, throughput inferior)"
            ),
        }
    if h.type == "worker_skill":
        return {
            "action": f"Substituir {h.entity} por operador mais experiente",
            "alternative": "Par com sénior para supervisão (formação)",
        }
    if h.type == "overload":
        return {
            "action": "Atrasar barcos não-urgentes para aliviar pressão",
            "alternative": "Turno extra (custo €/h × headcount)",
        }
    return {"action": "Revisão manual", "detail": "Tipo de hipótese desconhecido"}


__all__ = [
    "ErroTreeDetector",
    "MoldDetector",
    "OverloadDetector",
    "WorkerDetector",
]
