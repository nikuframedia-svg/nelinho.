"""Q.157.A — auto-propose REAL de decisões a partir de sinais do plano vivo.

Antes, a página landing ``/decisoes`` mostrava 3 cartões SEED hardcoded
(``seed_nelo_demo.py:upsert_suggestions``). O pipeline de auto-propose já existia
(``AutoProposeService`` + ``real_cpo_propose_runner``: INSERT + audit + SSE na
mesma tx) mas estava **gated em dev** (consumer Kafka só fora de dev) e **sem
gatilho** — o robô Q.137 (``auto_cpo_replan``) gera DRAFT no ``/overall`` mas
nunca cria Decisions.

Este job corre no APScheduler in-process (como o ``auto_cpo_replan`` e o
``phase_operator_affinity_job``) a cada 15 min — **sem** depender de Kafka nem do
dev-gate. Gera decisões PROPOSED reais a partir de dois sinais já calculados no
sistema:

  A) **Manutenção de molde** — ``MoldService.latest_health`` / ``MoldHealthCalculator``.
     Gera quando ``risk_category in {red, yellow}``. ``confidence = 100 - score``.
  B) **Reagendar barco em risco (OTD)** — ``OTDRiskService.otd_risk``.
     Gera para as ordens ``risk_band == "alto"`` (top-3). ``confidence = round(p*100)``.

Honestidade (invariante): ``confidence`` e o ``why`` derivam SEMPRE dos sinais
reais; nenhum número é literal. Sem sinal → nenhuma decisão (vazio honesto).

Anti-spam: ``RateLimiter`` in-memory (5 min) + **dedup durável** (não cria 2ª
PROPOSED para o mesmo ``(action_type, target)`` ainda aberto). Q.17: as decisões
nascem ``PROPOSED`` (``proposed_by=_SYSTEM_ACTOR``) e nunca executam. Best-effort:
uma falha num tenant/sinal é registada e não crasha o scheduler.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from src.plan.services.auto_propose import propose_decision_row
from src.plan.services.rate_limiter import RateLimiter
from src.scheduling.jobs.auto_cpo_replan_job import _resolve_tenants
from src.shared.models.governance import DecisionStatus, SharedDecisionRun

logger = logging.getLogger(__name__)

# Rate-limit in-memory partilhado entre ticks: max 1 decisão por (tenant,
# action_type, target) por 5 min. Sobrevive ao tick mas não ao restart (igual
# ao _last_run do auto_cpo_replan — aceitável).
_rate_limiter = RateLimiter()

# Limite de decisões OTD por tenant por tick (as de maior risco primeiro), para
# o ledger não inundar quando há muitos barcos em risco.
_OTD_MAX_PER_TICK = 3


async def _enabled(session, tenant_id: UUID) -> bool:
    """`planning.auto_propose_enabled` (default True); best-effort."""
    try:
        from src.core.services.tenant_config_service import TenantConfigService

        planning = await TenantConfigService(session, tenant_id).get_category("planning")
        return str(planning.get("auto_propose_enabled", "true")).lower() not in (
            "false", "0", "no",
        )
    except (SQLAlchemyError, ImportError, AttributeError, TypeError):
        return True


async def _existing_proposed_targets(session, tenant_id: UUID) -> set[tuple[str, str]]:
    """`{(action_type, target)}` das decisões já PROPOSED (dedup durável)."""
    rows = (
        await session.execute(
            select(SharedDecisionRun.action_type, SharedDecisionRun.target).where(
                SharedDecisionRun.tenant_id == tenant_id,
                SharedDecisionRun.status == DecisionStatus.PROPOSED.value,
            )
        )
    ).all()
    return {(str(a), str(t)) for a, t in rows}


# ---------------------------------------------------------------------------
# Geradores de candidatos (cada um devolve dicts prontos p/ propose_decision_row)
# ---------------------------------------------------------------------------

def _pct(value: Any) -> int:
    try:
        return round(max(0.0, min(1.0, float(value))) * 100)
    except (TypeError, ValueError):
        return 0


async def _mold_maintenance_candidates(
    session, tenant_id: UUID,
) -> List[Dict[str, Any]]:
    """A) Manutenção preventiva de molde a partir da saúde real (R.6.2)."""
    from src.plan.services.mold_health_calculator import MoldHealthCalculator
    from src.plan.services.mold_service import MoldService

    svc = MoldService(session, tenant_id)
    molds = await svc.list_molds()
    out: List[Dict[str, Any]] = []
    for mold in molds:
        health = await svc.latest_health(mold.id)
        if health is not None:
            score = int(health.score_0_100)
            risk = str(health.risk_category)
            components = dict(health.components or {})
        else:
            # Sem snapshot persistido (o scan diário ainda não correu) → computa
            # read-only, sem persistir nem auditar (HealthResult, não MoldHealth).
            res = await MoldHealthCalculator(session, tenant_id).compute(mold)
            score = res.score_0_100
            risk = res.risk_category
            components = res.components.as_dict()

        if risk not in ("red", "yellow"):
            continue

        confidence = max(0, min(100, 100 - score))
        code = mold.mold_code
        why = (
            f"Saúde do molde {code}: {score}/100 ({risk}). Fatores — "
            f"ciclos {_pct(components.get('cycles_pct'))}%, "
            f"manutenção {_pct(components.get('maint_age_pct'))}%, "
            f"defeitos {_pct(components.get('defect_penalty'))}%, "
            f"retrabalho {_pct(components.get('rework_rate'))}%."
        )
        out.append(
            {
                "title": f"Manutenção preventiva — molde {code}",
                "action_type": "MOLD_MAINTENANCE",
                "target": str(code),
                "sandbox_result": {
                    "confidence": confidence,
                    "source": "Saúde de molde (R.6.2)",
                    "why": why,
                    "if_accept": [
                        f"Manutenção do molde {code} agendada",
                        f"Saúde atual {score}/100 ({risk}) deve recuperar após manutenção",
                    ],
                    "if_reject": [
                        f"Molde {code} mantém-se {risk} ({score}/100)",
                        "Risco acrescido de defeito/retrabalho até ser mantido",
                    ],
                    "components": components,
                    "risk_category": risk,
                    "score_0_100": score,
                },
                "before_state": {
                    "score_0_100": score,
                    "risk_category": risk,
                    "components": components,
                },
                "after_state": {
                    "proposed_action": "schedule_maintenance",
                    "mold_code": str(code),
                },
                "audit_reason": f"Q.157.A auto_propose saúde de molde {code}",
                "audit_extra": {"source": "auto_propose_signals", "signal": "mold_health"},
                "sse_extra": {"source": "auto_propose_signals", "signal": "mold_health"},
            }
        )
    return out


async def _otd_reschedule_candidates(
    session, tenant_id: UUID,
) -> List[Dict[str, Any]]:
    """B) Reagendar barcos em risco de atraso a partir do modelo OTD (Q.54.F)."""
    from src.plan.services.otd_risk_service import OTDRiskService

    result = await OTDRiskService(session, tenant_id).otd_risk(top_n=50)
    if not result.get("model_available"):
        return []  # sem modelo → vazio honesto, nunca probabilidade inventada

    out: List[Dict[str, Any]] = []
    for order in result.get("orders", []):
        if order.get("risk_band") != "alto":
            continue
        of_id = str(order.get("of_id") or "")
        if not of_id:
            continue
        p = float(order.get("late_probability") or 0.0)
        confidence = max(0, min(100, round(p * 100)))
        transport = order.get("transport_date")
        slack = (order.get("features") or {}).get("slack_days")
        why_bits = [f"risco de atraso {confidence}% (banda alta)"]
        if transport:
            why_bits.append(f"entrega prevista {transport}")
        if slack is not None:
            why_bits.append(f"folga {slack} dias")
        out.append(
            {
                "title": f"Barco {of_id} em risco de atraso",
                "action_type": "OTD_RESCHEDULE",
                "target": of_id,
                "sandbox_result": {
                    "confidence": confidence,
                    "source": "Modelo OTD-risk (Q.54.F)",
                    "why": "Barco " + of_id + ": " + ", ".join(why_bits) + ".",
                    "if_accept": [
                        f"Rever o plano do barco {of_id}"
                        + (f" (entrega {transport})" if transport else ""),
                        "Priorizar as fases em falta para recuperar folga",
                    ],
                    "if_reject": [
                        f"Mantém o plano atual — risco de atraso {confidence}% por resolver",
                    ],
                    "late_probability": round(p, 4),
                    "transport_date": transport,
                    "slack_days": slack,
                    "current_phase_name": order.get("current_phase_name"),
                },
                "before_state": {
                    "late_probability": round(p, 4),
                    "transport_date": transport,
                    "slack_days": slack,
                },
                "after_state": {"proposed_action": "review_schedule", "of_id": of_id},
                "audit_reason": f"Q.157.A auto_propose OTD-risk barco {of_id}",
                "audit_extra": {"source": "auto_propose_signals", "signal": "otd_risk"},
                "sse_extra": {"source": "auto_propose_signals", "signal": "otd_risk"},
            }
        )
        if len(out) >= _OTD_MAX_PER_TICK:
            break
    return out


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------

async def _auto_propose_signals_job(tenant_ids: List[UUID]) -> None:
    """Por tenant: gera decisões PROPOSED reais de sinais do plano (molde + OTD).

    Registado no scheduler core a cada 15 min. Best-effort por tenant/sinal."""
    from src.shared.database import async_session_factory, get_session_context

    tenants = await _resolve_tenants(tenant_ids)
    for tid in tenants:
        try:
            async with get_session_context() as session:
                if not await _enabled(session, tid):
                    continue
                candidates: List[Dict[str, Any]] = []
                for gen in (_mold_maintenance_candidates, _otd_reschedule_candidates):
                    try:
                        candidates.extend(await gen(session, tid))
                    except Exception as exc:  # best-effort por sinal
                        logger.warning(
                            "auto_propose_signals: gerador %s falhou tenant=%s: %s",
                            getattr(gen, "__name__", gen), tid, exc,
                        )
                existing = await _existing_proposed_targets(session, tid)

            created = 0
            for cand in candidates:
                key = f"{tid}:{cand['action_type']}:{cand['target']}"
                # Dedup durável: já existe uma PROPOSED igual ainda aberta.
                if (cand["action_type"], cand["target"]) in existing:
                    continue
                # Rate-limit in-memory (5 min) para não repetir entre ticks.
                if not _rate_limiter.is_allowed(key):
                    continue
                await propose_decision_row(async_session_factory, tenant_id=tid, **cand)
                _rate_limiter.record(key)
                created += 1

            if created:
                logger.info(
                    "auto_propose_signals: %d decisão(ões) PROPOSED criada(s) tenant=%s",
                    created, tid,
                )
        except (SQLAlchemyError, OSError, RuntimeError, ValueError, ImportError) as exc:
            logger.error(
                "auto_propose_signals tenant=%s falhou: %s", tid, exc, exc_info=True,
            )
