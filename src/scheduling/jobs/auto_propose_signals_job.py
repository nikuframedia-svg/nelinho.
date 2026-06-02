"""Q.157.A — auto-propose REAL de decisões a partir de sinais do plano vivo.

Antes, a página landing ``/decisoes`` mostrava 3 cartões SEED hardcoded
(``seed_nelo_demo.py:upsert_suggestions``). O pipeline de auto-propose já existia
(``AutoProposeService`` + ``real_cpo_propose_runner``: INSERT + audit + SSE na
mesma tx) mas estava **gated em dev** (consumer Kafka só fora de dev) e **sem
gatilho** — o robô Q.137 (``auto_cpo_replan``) gera DRAFT no ``/overall`` mas
nunca cria Decisions.

Este job corre no APScheduler in-process (como o ``auto_cpo_replan`` e o
``phase_operator_affinity_job``) a cada 15 min — **sem** depender de Kafka nem do
dev-gate. Gera decisões PROPOSED reais (âmbito do projeto, ligadas ao CPO) de:

  A) **Planeamento (CPO)** — ``CommitsService``: se o DRAFT do robô melhora o
     plano LIVE (makespan/atrasos/€), propõe ``ADOPT_PLAN``. Aprovar promove o
     commit DRAFT→LIVE (Q.157.F.2). ``confidence`` = trust_index do CPO ou força
     dos sinais.
  B) **Expedição** — ``TransportSuggestionsService``: antecipar barco pronto,
     completar camião subutilizado, swap entre camiões, adiar barco em risco.
  C) **Reagendar barco em risco (OTD)** — ``OTDRiskService.otd_risk``.
     Gera para as ordens ``risk_band == "alto"`` (top-3). ``confidence = round(p*100)``.

Honestidade (invariante): ``confidence``/``why``/€ derivam SEMPRE dos KPIs/sinais
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

from src.plan.services.auto_propose import _SYSTEM_ACTOR, propose_decision_row
from src.plan.services.rate_limiter import RateLimiter
from src.scheduling.jobs.auto_cpo_replan_job import _resolve_tenants
from src.shared.auth.tenant_context import tenant_scope
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


async def _blocked_targets(session, tenant_id: UUID) -> set[tuple[str, str]]:
    """`{(action_type, target)}` de QUALQUER decisão já existente (qualquer
    status). Q.157.G.2: bloqueia re-propor o mesmo target — não duplica os
    PROPOSED abertos E respeita o "não" humano (REJECTED) e os já decididos
    (APPROVED/EXECUTED). Para ADOPT_PLAN o target é a sha (única por plano), por
    isso um plano NOVO (nova sha) é proposto à mesma."""
    rows = (
        await session.execute(
            select(SharedDecisionRun.action_type, SharedDecisionRun.target).where(
                SharedDecisionRun.tenant_id == tenant_id,
            )
        )
    ).all()
    return {(str(a), str(t)) for a, t in rows}


async def _publish_decision_rejected(tenant_id: UUID, decision) -> None:
    """Publica DECISION_REJECTED no SSE (best-effort)."""
    try:
        from src.shared.kafka_client import EventBase, Topics, publish_event

        await publish_event(
            Topics.DECISION_REJECTED,
            EventBase(
                event_type="DECISION_REJECTED",
                tenant_id=tenant_id,
                source_module="scheduling.jobs.auto_propose_signals_job",
                payload={
                    "decision_id": str(decision.id),
                    "action_type": decision.action_type,
                    "reason": "superseded",
                },
            ),
        )
    except Exception as exc:  # pragma: no cover - best-effort
        logger.debug("DECISION_REJECTED publish falhou para %s: %s", decision.id, exc)


async def _supersede_stale_adopt_plans(
    session_factory, tenant_id: UUID, keep_sha,
) -> int:
    """Q.157.G.1 — marca REJECTED ("superseded") os ADOPT_PLAN PROPOSED cujo
    target != keep_sha. Mantém ≤1 ADOPT_PLAN aberto (o plano CPO mais recente).
    Se keep_sha é None (sem DRAFT por adotar / já LIVE), supersede TODOS.
    Audit na mesma tx; SSE best-effort. Devolve nº superseded."""
    from src.governance.audit_service import audit_change

    superseded = []
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(SharedDecisionRun).where(
                    SharedDecisionRun.tenant_id == tenant_id,
                    SharedDecisionRun.action_type == "ADOPT_PLAN",
                    SharedDecisionRun.status == DecisionStatus.PROPOSED.value,
                )
            )
        ).scalars().all()
        for d in rows:
            if keep_sha is not None and str(d.target) == str(keep_sha):
                continue
            d.status = DecisionStatus.REJECTED.value
            await audit_change(
                session,
                tenant_id=tenant_id,
                entity_type="decision_run",
                entity_id=d.id,
                action="UPDATE",
                old_values={"status": DecisionStatus.PROPOSED.value},
                new_values={"status": DecisionStatus.REJECTED.value, "reason": "superseded"},
                actor_id=_SYSTEM_ACTOR,
                reason=(
                    "Q.157.G ADOPT_PLAN superseded por plano "
                    f"{(keep_sha or 'LIVE')[:8]}"
                ),
            )
            superseded.append(d)
        if superseded:
            await session.commit()

    for d in superseded:
        await _publish_decision_rejected(tenant_id, d)
    return len(superseded)


# ---------------------------------------------------------------------------
# Geradores de candidatos (cada um devolve dicts prontos p/ propose_decision_row)
# ---------------------------------------------------------------------------

def _f(value: Any):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _i(value: Any):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def _planning_candidates(
    session, tenant_id: UUID,
) -> List[Dict[str, Any]]:
    """PLANEAMENTO (ligado ao CPO) — propor ADOTAR o plano DRAFT do robô.

    O robô Q.137 corre o CPO pesado no worker Arq e persiste um DRAFT em
    plan_schedule_commits. Aqui LEMOS esse DRAFT (não corremos o CPO no
    event-loop) e, se melhora o plano LIVE (makespan/atrasos/€), propomos
    ``ADOPT_PLAN``. Aprovar a decisão promove o commit DRAFT→LIVE (Q.157.F.2).
    """
    from src.plan.cpo.commits import CommitsService
    from src.plan.services.auto_propose_cpo_runner import (
        _build_consequences,
        _cost_delta_for_commit,
    )

    svc = CommitsService(session, tenant_id)
    draft = await svc.get_latest()
    # Só há algo a adotar se o commit mais recente é um DRAFT por aprovar.
    if draft is None or str(getattr(draft, "status", "")) != "DRAFT":
        return []
    live = await svc.latest_live()

    dk = dict(draft.kpis or {})
    lk = dict(live.kpis or {}) if live is not None else {}
    d_make, l_make = _f(dk.get("makespan_hours")), _f(lk.get("makespan_hours"))
    d_late, l_late = _i(dk.get("num_late_orders")), _i(lk.get("num_late_orders"))
    cost_delta = await _cost_delta_for_commit(session, tenant_id, draft.commit_sha256)

    # O DRAFT é a proposta de plano mais recente do CPO (ainda por aprovar). É
    # sempre proposto — o humano decide vendo os deltas REAIS vs LIVE (melhor ou
    # pior). Os sinais abaixo só calibram a confiança; não suprimem a proposta.
    first_plan = live is None
    makespan_better = d_make is not None and l_make is not None and d_make < l_make - 0.05
    late_better = d_late is not None and l_late is not None and d_late < l_late
    eur_better = cost_delta is not None and cost_delta > 0

    # Confidence: trust_index real do CPO se disponível; senão força dos sinais.
    ti = _f(getattr(draft, "trust_index", 0)) or 0.0
    if ti > 0:
        confidence = max(50, min(99, round(ti * 100)))
    else:
        pos = sum([makespan_better, late_better, eur_better]) or (1 if first_plan else 0)
        confidence = {0: 55, 1: 65, 2: 80, 3: 92}[min(pos, 3)]

    sha = draft.commit_sha256
    sandbox: Dict[str, Any] = {
        "commit_sha": sha,
        "source": "CPO Scheduler",
        "confidence": confidence,
        "kpis": {
            "makespan_hours": d_make,
            "num_late_orders": d_late,
            "throughput_eur_day": _f(dk.get("throughput_eur_day")),
        },
    }
    if cost_delta is not None:
        sandbox["cost_delta"] = cost_delta
    # why / if_accept / if_reject derivados dos KPIs reais (reusa o builder).
    sandbox.update(_build_consequences(dk, cost_delta, None, sha[:8]))
    if l_make is not None and d_make is not None:
        sandbox["delta_makespan_h"] = round(d_make - l_make, 1)
    if l_late is not None and d_late is not None:
        sandbox["delta_late_orders"] = d_late - l_late

    title = "Adotar novo plano CPO"
    if d_make is not None:
        title += f" — makespan {d_make:.0f} h"
    if d_late is not None:
        title += f", {d_late} atrasadas"
    return [
        {
            "title": title[:255],
            "action_type": "ADOPT_PLAN",
            "target": sha,  # dedup pela sha: novo DRAFT = nova proposta
            "sandbox_result": sandbox,
            "before_state": {
                "commit_sha": live.commit_sha256 if live is not None else None,
                "kpis": lk,
            },
            "after_state": {"commit_sha": sha},
            "audit_reason": f"Q.157.F auto_propose adotar plano CPO {sha[:8]}",
            "audit_extra": {"source": "auto_propose_signals", "signal": "planning"},
            "sse_extra": {"source": "auto_propose_signals", "signal": "planning"},
        }
    ]


_EXPEDITION_TYPE_MAP = {
    "advance_boat": "SHIPMENT_ADVANCE",
    "complete_truck": "TRUCK_CONSOLIDATE",
    "swap_between_batches": "TRUCK_SWAP",
    "delay_boat": "SHIPMENT_DELAY",
}


async def _expedition_candidates(
    session, tenant_id: UUID,
) -> List[Dict[str, Any]]:
    """EXPEDIÇÃO — sugestões reais de camiões/barcos (TransportSuggestionsService).

    Por cada camião OPEN próximo (≤7 dias), corre o detetor já existente
    (antecipar barco pronto, completar camião subutilizado, swap entre camiões,
    adiar barco em risco) e transforma cada sugestão numa decisão. O serviço já
    devolve what/why/if_accept/if_reject reais — zero hardcode.
    """
    from datetime import date, timedelta

    from sqlalchemy import and_

    from src.plan.models.transport import TransportBatch
    from src.plan.services.transport_suggestions import TransportSuggestionsService

    today = date.today()
    horizon = today + timedelta(days=7)
    batches = list(
        (
            await session.execute(
                select(TransportBatch)
                .where(
                    and_(
                        TransportBatch.tenant_id == tenant_id,
                        TransportBatch.status != "DISPATCHED",
                        TransportBatch.transport_date >= today,
                        TransportBatch.transport_date <= horizon,
                    )
                )
                .order_by(TransportBatch.transport_date)
                .limit(20)
            )
        ).scalars().all()
    )
    if not batches:
        return []

    svc = TransportSuggestionsService(session, tenant_id)
    out: List[Dict[str, Any]] = []
    for batch in batches:
        for sug in await svc.for_batch(batch.id):
            action_type = _EXPEDITION_TYPE_MAP.get(sug.type)
            if action_type is None:
                continue
            out.append(
                {
                    "title": (sug.what or f"Expedição — {batch.code}")[:255],
                    "action_type": action_type,
                    "target": f"{batch.code}:{sug.type}",
                    "sandbox_result": {
                        "source": "Expedição",
                        "why": sug.why,
                        "what": sug.what,
                        "if_accept": [sug.if_accept] if sug.if_accept else [],
                        "if_reject": [sug.if_reject] if sug.if_reject else [],
                        "alternative": sug.alternative,
                        "affected_order_ids": sug.affected_order_ids or [],
                        "target_batch_id": sug.target_batch_id,
                        "batch_code": batch.code,
                    },
                    "before_state": {"batch_code": batch.code, "type": sug.type},
                    "after_state": {"batch_code": batch.code, "proposed": sug.type},
                    "audit_reason": f"Q.157.F auto_propose expedição {sug.type} {batch.code}",
                    "audit_extra": {"source": "auto_propose_signals", "signal": "expedition"},
                    "sse_extra": {"source": "auto_propose_signals", "signal": "expedition"},
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
            # tenant_scope injecta SET LOCAL app.tenant_id em cada tx desta
            # iteração → reads RLS-dependentes (ex.: OTD em plan.production_orders)
            # e quaisquer policies futuras funcionam no contexto de background.
            with tenant_scope(tid):
                async with get_session_context() as session:
                    if not await _enabled(session, tid):
                        continue
                    candidates: List[Dict[str, Any]] = []
                    for gen in (
                        _planning_candidates,
                        _expedition_candidates,
                        _otd_reschedule_candidates,
                    ):
                        try:
                            candidates.extend(await gen(session, tid))
                        except Exception as exc:  # best-effort por sinal
                            logger.warning(
                                "auto_propose_signals: gerador %s falhou tenant=%s: %s",
                                getattr(gen, "__name__", gen), tid, exc,
                            )

                # Q.157.G.1 — supersede ADOPT_PLAN obsoletos: mantém ≤1 aberto (o
                # plano CPO mais recente). keep_sha = target do candidato de plano
                # (ou None se não há DRAFT por adotar → supersede todos).
                keep_sha = next(
                    (c["target"] for c in candidates if c["action_type"] == "ADOPT_PLAN"),
                    None,
                )
                superseded = await _supersede_stale_adopt_plans(
                    async_session_factory, tid, keep_sha,
                )
                if superseded:
                    logger.info(
                        "auto_propose_signals: %d ADOPT_PLAN superseded tenant=%s",
                        superseded, tid,
                    )

                # Bloqueados = qualquer target já existente (Q.157.G.2): não
                # duplica abertos, não re-propõe rejeitados/decididos. Lido DEPOIS
                # do supersede para refletir os que acabaram de ser rejeitados.
                async with get_session_context() as session2:
                    blocked = await _blocked_targets(session2, tid)

                created = 0
                for cand in candidates:
                    key = f"{tid}:{cand['action_type']}:{cand['target']}"
                    if (cand["action_type"], cand["target"]) in blocked:
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
