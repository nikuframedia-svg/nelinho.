"""Q.117.B — runner CPO real (propose-only) para o AutoProposeService.

Antes, o ``AutoProposeService`` usava ``_noop_cpo_runner`` — devolvia kpis
vazios e um sha fictício, por isso as decisões criadas a partir de eventos
Kafka (orders.created, quality.defect_logged, …) chegavam à página
/decisoes sem conteúdo accionável (sem commit real, sem risco, sem €).

Este runner liga o pipeline canónico:

  1. ``run_cpo_schedule`` (o mesmo de ``POST /v1/plan/cpo/schedule``) corre o
     CPO em modo propose-only e cria um ScheduleCommit → commit_sha real +
     KPIs de scheduling (makespan, atrasos, utilização).
  2. ``cost_delta`` — delta € do commit vs baseline via
     ``compute_margin_preview`` (src/profit). É a fonte honesta do número €
     que o badge mostra; omitido se não computável.
  3. ``quality_risk`` — risk band (alto/medio/baixo) da ordem-alvo via
     ``DefectRiskService`` (Q.117.G). Omitido se não houver modelo/ordem.

Fronteiras: este módulo vive em ``src.plan.services`` (não em
``src.plan.cpo``), por isso pode importar ``src.profit`` e ``src.quality``
— o contrato import-linter só proíbe ``src.plan.cpo`` → ``src.profit``.
Delegar o cálculo de € ao profit é o padrão certo (CoeficienteX é €).

Contrato de robustez: **nunca levanta**. Qualquer falha (FactoryState não
carregado, sem ordens, yaml_policy block, erro do motor) cai num resultado
com a mesma forma do antigo noop, para o listener Kafka nunca morrer.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


def _fallback(reason: str) -> Dict[str, Any]:
    """Resultado com a forma do antigo noop — proposta sem schedule."""
    return {
        "commit_sha": "",
        "kpis": {},
        "operations": [],
        "propose_only": True,
        "fallback_reason": reason,
    }


async def _cost_delta_for_commit(
    session, tenant_id: UUID, commit_sha: str,
) -> Optional[float]:
    """Delta € do commit vs baseline (compute_margin_preview). None se n/d."""
    if not commit_sha:
        return None
    try:
        from src.profit.services.margin_preview import compute_margin_preview

        preview = await compute_margin_preview(session, tenant_id, commit_sha)
        if preview.delta_eur is None:
            return None
        return round(float(preview.delta_eur), 2)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("auto_propose: cost_delta enrichment falhou: %s", exc)
        return None


def _target_from_payload(payload: Dict[str, Any]) -> str:
    """Identificador da ordem-alvo do evento (of_id/order_id/boat_id)."""
    return str(
        payload.get("of_id")
        or payload.get("order_id")
        or payload.get("boat_id")
        or ""
    ).strip()


def _build_consequences(
    kpis: Dict[str, Any],
    cost_delta: Optional[float],
    quality_risk: Optional[str],
    target: str,
) -> Dict[str, Any]:
    """Deriva why/if_accept/if_reject SÓ de valores reais já computados.

    Q.131+ — a card "Consequências" da tab Simulações lê estas chaves; antes
    nenhum produtor de sandbox_result as escrevia e a card ficava sempre vazia.
    Aqui não se inventa nada: cada linha só entra se a sua fonte existir
    (KPIs do commit, cost_delta de src/profit, quality_risk de src/quality).
    Devolve só as chaves preenchidas — listas vazias são omitidas para a UI
    cair no empty-state honesto.
    """
    makespan = kpis.get("makespan_hours")
    late = kpis.get("num_late_orders")

    if_accept: list[str] = []
    if makespan is not None:
        line = f"Novo plano: makespan {float(makespan):.1f} h"
        if late is not None:
            line += f" · {int(late)} ordens atrasadas"
        if_accept.append(line)
    if cost_delta is not None:
        if_accept.append(f"Margem {cost_delta:+.0f} € vs plano atual")
    if quality_risk:
        if_accept.append(f"Risco de qualidade da ordem-alvo: {quality_risk}")

    # Só faz sentido falar do status quo quando há de facto um plano alternativo.
    if_reject: list[str] = []
    if if_accept:
        if_reject.append("Mantém o plano atual — sem replaneamento")
        if target:
            if_reject.append(f"A ordem {target} fica sem o replaneamento proposto")

    out: Dict[str, Any] = {}
    if if_accept:
        out["if_accept"] = if_accept
    if if_reject:
        out["if_reject"] = if_reject
        bits: list[str] = []
        if makespan is not None:
            bits.append(f"makespan {float(makespan):.1f} h")
        if late is not None:
            bits.append(f"{int(late)} atrasadas")
        if cost_delta is not None:
            bits.append(f"margem {cost_delta:+.0f} €")
        if quality_risk:
            bits.append(f"risco {quality_risk}")
        if bits:
            out["why"] = "Replaneamento proposto pelo CPO: " + ", ".join(bits) + "."
    return out


async def _quality_risk_for_target(
    session, tenant_id: UUID, payload: Dict[str, Any],
) -> Optional[str]:
    """Risk band (alto/medio/baixo) da ordem-alvo do evento. None se n/d."""
    target = _target_from_payload(payload)
    if not target:
        return None
    try:
        from src.quality.services.defect_risk_service import DefectRiskService

        svc = DefectRiskService(session, tenant_id)
        result = await svc.defect_risk(top_n=500)
        if not result.get("model_available"):
            return None
        for order in result.get("orders", []):
            if str(order.get("of_id")) == target:
                return order.get("risk_band")
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("auto_propose: quality_risk enrichment falhou: %s", exc)
    return None


async def real_cpo_propose_runner(
    *,
    tenant_id: UUID,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Corre o CPO propose-only e devolve o sandbox_result enriquecido."""
    from src.shared.database import async_session_factory

    try:
        from src.plan.api.cpo_routers.schedule import CPOScheduleRequest
        from src.plan.cpo.scheduler_run import run_cpo_schedule
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("auto_propose CPO runner: import falhou: %s", exc)
        return _fallback("import_error")

    try:
        async with async_session_factory() as session:
            # author/message identificam a origem no histórico de commits.
            # Defaults (generations=50, horizon_days=30) preservados — não
            # baixar generations (invariante Q.59).
            req = CPOScheduleRequest(
                author="auto_propose",
                message="Replaneamento automático (propose-only)",
            )
            try:
                result = await run_cpo_schedule(session, tenant_id, req)
            except Exception as exc:
                # HTTPException 503 (FactoryState), 400 (sem ordens), 409
                # (yaml_policy block) ou erro do motor → proposta sem schedule.
                detail = getattr(exc, "detail", None) or str(exc)
                logger.info(
                    "auto_propose CPO runner: sem schedule (%s) — fallback",
                    str(detail)[:160],
                )
                return _fallback(str(detail)[:160])

            await session.commit()

            commit_sha = result.get("commit_sha256") or ""
            out: Dict[str, Any] = {
                "commit_sha": commit_sha,
                "kpis": {
                    "makespan_hours": result.get("makespan_hours"),
                    "num_late_orders": result.get("num_late_orders"),
                    "avg_utilization": result.get("avg_utilization"),
                    "total_tardiness_hours": result.get("total_tardiness_hours"),
                },
                "operations": result.get("operations", []),
                "engine_used": result.get("engine_used"),
                "propose_only": True,
            }

            cost_delta = await _cost_delta_for_commit(session, tenant_id, commit_sha)
            if cost_delta is not None:
                out["cost_delta"] = cost_delta

            quality_risk = await _quality_risk_for_target(session, tenant_id, payload)
            if quality_risk is not None:
                out["quality_risk"] = quality_risk

            # Consequências (if_accept/if_reject/why) — derivadas dos valores
            # reais acima; alimenta a card "Consequências" da tab Simulações.
            out.update(
                _build_consequences(
                    out["kpis"], cost_delta, quality_risk,
                    _target_from_payload(payload),
                )
            )

            return out
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("auto_propose CPO runner falhou: %s", exc, exc_info=True)
        return _fallback("runner_error")
