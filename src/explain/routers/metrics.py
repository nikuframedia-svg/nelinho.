"""Q.66.D.4c — Metrics & commit sub-router (extracted from `src.explain.api`).

Hosts:

* ``GET  /v1/explain/metric/{metric_id}``
* ``GET  /v1/explain/catalog``
* ``GET  /v1/explain/blocked``
* ``POST /v1/explain/compute``
* ``GET  /v1/explain/commit/{commit_sha}``

The legacy in-file ``METRIC_CATALOG`` dict + the ``_resolve_metric_value``
helper + the ``_generate_explanation`` narrative live here so the rest of
the package (and the characterization tests) can keep importing them
from the aggregator unchanged.

Behaviour MUST be byte-identical to the pre-decomposition router —
shapes are pinned by ``tests/explain/test_api_characterization_q66_d.py``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.factory_data_product.config import (
    BLOCKED_METRICS,
    SEMANTIC_LABELS,
    TRUST_INDEX,
)
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

logger = logging.getLogger(__name__)

# Sprint Q.12 Onda 0.1: tenant header is mandatory on every metric/commit
# endpoint that reads tenant-scoped state.
get_tenant_id = require_tenant_header

router = APIRouter(prefix="/v1/explain", tags=["Explainability"])


# ============================================================================
# SCHEMAS
# ============================================================================

class Citation(BaseModel):
    """Citation/data source for a metric."""
    label: str
    ref: str
    confidence: Optional[float] = None


class Factor(BaseModel):
    """Contributing factor to a metric."""
    name: str
    impact: float  # -1 to 1, negative = decreases metric, positive = increases
    description: Optional[str] = None


class ImprovementSuggestion(BaseModel):
    """Suggestion for improving a metric."""
    id: str
    description: str
    estimated_impact: Optional[float] = None  # Expected improvement in %
    difficulty: Optional[str] = None  # "easy", "medium", "hard"
    action_type: Optional[str] = None


class ExplainedMetric(BaseModel):
    """Full explanation for a metric."""
    metric_id: str
    metric_name: str
    value: Optional[float] = None
    unit: str = "%"
    explanation: str
    factors: List[Factor] = []
    suggestions: List[ImprovementSuggestion] = []
    citations: List[Citation] = []
    computed_at: str
    trust_index: Optional[float] = None


class MetricCatalogEntry(BaseModel):
    """Entry in the metric catalog."""
    id: str
    name: str
    domain: str
    unit: str
    description: str
    formula: Optional[str] = None


class CommitExplanation(BaseModel):
    """What the decoder produced for this commit + why it matters.

    Surfaces the MAP-Elites alternatives + rejected signals so the
    Copilot drawer can narrate "here's what we picked and how it differs
    from the ones you declined".
    """
    commit_sha256: str
    short_sha: str
    kpis: Dict[str, Any]
    alternatives: List[Dict[str, Any]]
    rejected_alternatives: List[Dict[str, Any]]
    user_preference_signal: Dict[str, Any]
    trust_index: float
    scenarios_tested: int
    why_these_choices: str


# ============================================================================
# METRIC DEFINITIONS (could be loaded from DB/config)
# ============================================================================

METRIC_CATALOG: Dict[str, Dict[str, Any]] = {
    # =========================================================================
    # BLOCKED METRICS (no data available in Folha_IA_extra.xlsx)
    # =========================================================================
    "oee_global": {
        "name": "OEE Global",
        "domain": "profit",
        "unit": "%",
        "description": "Overall Equipment Effectiveness - measures manufacturing productivity",
        "formula": "Availability × Performance × Quality",
        "explanation": "OEE is calculated by multiplying three factors: Availability (uptime), Performance (speed), and Quality (first pass yield). A world-class OEE is typically 85% or higher.",
        "status": "BLOCKED",
        "blocked_reason": BLOCKED_METRICS["oee_real"]["reason"],
        "required_data": BLOCKED_METRICS["oee_real"]["required_data"],
        "factors": [],
        "suggestions": [
            {"id": "oee_data_1", "description": "Implementar recolha de dados de paragens de máquinas", "estimated_impact": None, "difficulty": "hard", "action_type": "data_improvement"},
            {"id": "oee_data_2", "description": "Instalar sensores IoT para monitorização de equipamentos", "estimated_impact": None, "difficulty": "hard", "action_type": "data_improvement"},
        ],
        "citations": [],
        "trust_index": 0,
    },
    "availability_pct": {
        "name": "Availability",
        "domain": "profit",
        "unit": "%",
        "description": "Percentage of scheduled time that equipment is available for production",
        "formula": "(Scheduled Time - Downtime) / Scheduled Time × 100",
        "explanation": "Availability measures the proportion of scheduled production time that the equipment is actually available and running.",
        "status": "BLOCKED",
        "blocked_reason": BLOCKED_METRICS["availability_oee"]["reason"],
        "required_data": ["machine_downtime", "planned_production_time"],
        "factors": [],
        "suggestions": [
            {"id": "avail_data_1", "description": "Registar paragens de máquinas no sistema", "estimated_impact": None, "difficulty": "medium", "action_type": "data_improvement"},
        ],
        "citations": [],
        "trust_index": 0,
    },
    "otd_pct": {
        "name": "On-Time Delivery",
        "domain": "supply",
        "unit": "%",
        "description": "Percentage of orders delivered on or before the promised date",
        "formula": "Orders Delivered On Time / Total Orders × 100",
        "explanation": "OTD measures delivery reliability. It tracks how often customer orders are fulfilled by the promised delivery date.",
        "status": "BLOCKED",
        "blocked_reason": BLOCKED_METRICS["otd_official"]["reason"],
        "required_data": BLOCKED_METRICS["otd_official"]["required_data"],
        "factors": [],
        "suggestions": [
            {"id": "otd_data_1", "description": "Adicionar campo de data prometida (due date) nas ordens de fabrico", "estimated_impact": None, "difficulty": "easy", "action_type": "data_improvement"},
        ],
        "citations": [],
        "trust_index": 0,
    },

    # =========================================================================
    # AVAILABLE METRICS (can be calculated from Folha_IA_extra.xlsx)
    # =========================================================================
    "wip_theoretical": {
        "name": "WIP Teórico",
        "domain": "factory",
        "unit": "orders",
        "description": "Work in Progress - ordens abertas (sem DataAcabamento)",
        "formula": "COUNT(OrdensFabrico WHERE DataAcabamento IS NULL)",
        "explanation": "WIP teórico conta as ordens de fabrico que ainda não foram concluídas. Baseado no campo DataAcabamento da tabela OrdensFabrico.",
        "status": "OK",
        "semantic_label": SEMANTIC_LABELS["wip"],
        "trust_index": TRUST_INDEX.get("FasesOrdemFabrico_structure", 80) / 100,
        "factors": [
            {"name": "Ordens sem DataAcabamento", "impact": 1.0, "description": "Ordens consideradas em aberto"},
        ],
        "suggestions": [
            {"id": "wip_1", "description": "Reduzir WIP através de políticas de limite (WIP caps)", "estimated_impact": 15, "difficulty": "medium"},
            {"id": "wip_2", "description": "Identificar ordens bloqueadas há mais de X dias", "estimated_impact": 10, "difficulty": "easy"},
        ],
        "citations": [
            {"label": "OrdensFabrico", "ref": "factory_data_product.curated.orders", "confidence": 0.82},
        ],
    },
    "backlog_horas_theoretical": {
        "name": "Backlog Teórico (Horas)",
        "domain": "factory",
        "unit": "hours",
        "description": "Soma de HorasPrevistas das fases abertas",
        "formula": "SUM(HorasPrevistas_Final WHERE FaseOf_Fim IS NULL)",
        "explanation": "Backlog teórico em horas. ATENÇÃO: HorasPrevistas tem apenas 43.4% de cobertura (56.6% são zeros). Valores podem estar subestimados.",
        "status": "WARNING",
        "semantic_label": SEMANTIC_LABELS["bottleneck"],
        "trust_index": TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58) / 100,
        "factors": [
            {"name": "Cobertura HorasPrevistas", "impact": -0.43, "description": "56.6% dos registos têm HorasPrevistas = 0"},
            {"name": "Ambiguidade zeros", "impact": -0.2, "description": "0 pode significar 'não definido' ou 'zero real'"},
        ],
        "suggestions": [
            {"id": "backlog_data_1", "description": "Preencher HorasPrevistas em falta usando standards por produto/fase", "estimated_impact": 40, "difficulty": "medium", "action_type": "data_improvement"},
            {"id": "backlog_1", "description": "Priorizar fases com maior backlog teórico", "estimated_impact": 10, "difficulty": "easy"},
        ],
        "citations": [
            {"label": "FasesOrdemFabrico", "ref": "factory_data_product.curated.order_phases", "confidence": 0.58},
            {"label": "FasesStandardModelos", "ref": "factory_data_product.curated.standards", "confidence": 0.60},
        ],
    },
    "lead_time_observed": {
        "name": "Lead Time Observado",
        "domain": "factory",
        "unit": "days",
        "description": "Tempo médio entre DataCriacao e DataAcabamento",
        "formula": "AVG(DataAcabamento - DataCriacao) WHERE DataAcabamento IS NOT NULL",
        "explanation": "Lead time observado para ordens concluídas. Baseado em datas reais, não em previsões.",
        "status": "OK",
        "semantic_label": SEMANTIC_LABELS["lead_time"],
        "trust_index": TRUST_INDEX.get("OrdensFabrico", 82) / 100,
        "factors": [
            {"name": "Ordens concluídas", "impact": 1.0, "description": "Apenas ordens com DataAcabamento preenchido"},
        ],
        "suggestions": [
            {"id": "lt_1", "description": "Identificar ordens com lead time > média + 2σ", "estimated_impact": 8, "difficulty": "easy"},
            {"id": "lt_2", "description": "Analisar fases que mais contribuem para lead time", "estimated_impact": 12, "difficulty": "medium"},
        ],
        "citations": [
            {"label": "OrdensFabrico", "ref": "factory_data_product.curated.orders", "confidence": 0.82},
        ],
    },
    "bottleneck_count": {
        "name": "Gargalos Identificados",
        "domain": "factory",
        "unit": "phases",
        "description": "Número de fases com backlog > 5 dias teóricos",
        "formula": "COUNT(Fases WHERE backlog_dias_teoricos > 5)",
        "explanation": "Fases identificadas como potenciais gargalos baseado no backlog teórico. ATENÇÃO: Baseado em HorasPrevistas (58% cobertura).",
        "status": "WARNING",
        "semantic_label": SEMANTIC_LABELS["bottleneck"],
        "trust_index": TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58) / 100,
        "factors": [
            {"name": "Threshold 5 dias", "impact": 0.0, "description": "Fases com backlog > 5 dias são consideradas críticas"},
        ],
        "suggestions": [
            {"id": "bn_1", "description": "Aumentar capacidade nas fases gargalo", "estimated_impact": 20, "difficulty": "hard"},
            {"id": "bn_2", "description": "Rebalancear carga entre fases", "estimated_impact": 15, "difficulty": "medium"},
        ],
        "citations": [
            {"label": "FasesOrdemFabrico", "ref": "factory_data_product.curated.order_phases", "confidence": 0.58},
            {"label": "Fases", "ref": "factory_data_product.curated.phases", "confidence": 0.85},
        ],
    },
    "skills_risk_count": {
        "name": "Fases em Risco de Competências",
        "domain": "factory",
        "unit": "phases",
        "description": "Fases com menos de 3 funcionários aptos activos",
        "formula": "COUNT(Fases WHERE capable_employees < 3)",
        "explanation": "Fases onde poucos funcionários estão qualificados, criando risco operacional.",
        "status": "WARNING",
        "semantic_label": SEMANTIC_LABELS["skills"],
        "trust_index": TRUST_INDEX.get("FuncionariosFaseOrdemFabrico", 55) / 100,
        "factors": [
            {"name": "Threshold 3 funcionários", "impact": 0.0, "description": "Fases com < 3 aptos são consideradas em risco"},
        ],
        "suggestions": [
            {"id": "skill_1", "description": "Implementar programa de cross-training", "estimated_impact": 25, "difficulty": "medium"},
            {"id": "skill_2", "description": "Priorizar formação nas fases críticas", "estimated_impact": 15, "difficulty": "easy"},
        ],
        "citations": [
            {"label": "FuncionariosFasesAptos", "ref": "factory_data_product.curated.skill_matrix", "confidence": 0.55},
            {"label": "Funcionarios", "ref": "factory_data_product.curated.employees", "confidence": 0.75},
        ],
    },
    "quality_errors_total": {
        "name": "Total de Erros de Qualidade",
        "domain": "factory",
        "unit": "errors",
        "description": "Número total de erros registados",
        "formula": "COUNT(OrdemFabricoErros)",
        "explanation": "Total de erros de qualidade registados. ATENÇÃO: 41.5% dos erros não têm fase culpada identificada.",
        "status": "WARNING",
        "semantic_label": SEMANTIC_LABELS["quality"],
        "trust_index": TRUST_INDEX.get("OrdemFabricoErros", 67) / 100,
        "factors": [
            {"name": "Cobertura FaseOfCulpada", "impact": -0.42, "description": "41.5% dos erros sem fase culpada"},
        ],
        "suggestions": [
            {"id": "qual_data_1", "description": "Melhorar registo de fase culpada nos erros", "estimated_impact": 30, "difficulty": "easy", "action_type": "data_improvement"},
            {"id": "qual_1", "description": "Análise Pareto dos tipos de erro mais frequentes", "estimated_impact": 15, "difficulty": "easy"},
        ],
        "citations": [
            {"label": "OrdemFabricoErros", "ref": "factory_data_product.curated.errors", "confidence": 0.67},
        ],
    },
}


# ============================================================================
# Helpers
# ============================================================================

async def _resolve_metric_value(
    metric_id: str,
    session: Optional[AsyncSession],
) -> Optional[float]:
    """Sprint Q.9 (2.5) — try to fetch the live value from SemanticQueries.

    Returns ``None`` when no data is available (no DB, no active
    ingestion, query raises). Callers fall back to the catalogue's
    placeholder value in that case.
    """
    if session is None:
        return None
    try:
        from src.factory_data_product.semantic.queries import SemanticQueries

        sq = SemanticQueries(db=session)
        if metric_id == "wip_theoretical":
            r = await sq.wip()
            return r["data"].get("open_orders")
        if metric_id == "backlog_horas_theoretical":
            r = await sq.backlog_by_phase(top_n=100)
            data = r.get("data") or []
            if isinstance(data, list):
                return float(sum(d.get("backlog_horas", 0) or 0 for d in data))
            return None
        if metric_id == "lead_time_observed":
            r = await sq.lead_time_analysis(days_back=90)
            return r["data"].get("avg_lead_time_days")
        if metric_id == "bottleneck_count":
            r = await sq.bottlenecks(top_n=100)
            data = r.get("data") or []
            return float(len(data) if isinstance(data, list) else 0)
        if metric_id == "skills_risk_count":
            r = await sq.skills_risk(min_capable=3)
            data = r.get("data") or []
            return float(len(data) if isinstance(data, list) else 0)
        if metric_id == "quality_errors_total":
            r = await sq.quality_analysis()
            return r["data"].get("total_errors")
    except Exception as exc:  # pragma: no cover — DB / ingestion path
        logger.debug(
            "explain._resolve_metric_value(%s) fell back to catalogue: %s",
            metric_id, exc,
        )
    return None


def _generate_explanation(kpis: Dict[str, Any]) -> str:
    """Deterministic narrative describing the trade-offs this commit
    accepted. Stays simple — 2-3 sentences citing the headline numbers
    so the frontend can show a summary without waiting for the LLM.
    """
    makespan = kpis.get("makespan_hours", 0) or 0
    tardiness = kpis.get("total_tardiness_hours", 0) or 0
    late_orders = kpis.get("num_late_orders", 0) or 0
    throughput = kpis.get("throughput_eur_day", 0) or 0
    setups = kpis.get("setups", 0) or 0

    parts = []
    parts.append(
        f"Makespan total {makespan:.1f}h com {setups} mudanças de setup"
    )
    if late_orders > 0:
        parts.append(
            f"; {late_orders} ordens com atraso acumulando {tardiness:.1f}h"
        )
    else:
        parts.append("; nenhuma ordem atrasada")
    if throughput > 0:
        parts.append(f"; throughput alvo €{throughput:,.0f}/dia")
    return "".join(parts) + "."


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/metric/{metric_id}", response_model=ExplainedMetric)
async def get_metric_explanation(
    metric_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Get detailed explanation for a specific metric.

    Returns:
    - Current value (if available, None if BLOCKED)
    - Human-readable explanation
    - Contributing factors with impact
    - Improvement suggestions (including data_improvement actions for BLOCKED)
    - Data source citations
    - Trust index and status
    """
    metric_def = METRIC_CATALOG.get(metric_id)

    if not metric_def:
        # Return a generic explanation for unknown metrics
        return ExplainedMetric(
            metric_id=metric_id,
            metric_name=metric_id.replace("_", " ").title(),
            value=None,
            unit="%",
            explanation=f"Métrica '{metric_id}' não está no catálogo. Contacte o administrador para adicionar.",
            factors=[],
            suggestions=[],
            citations=[],
            computed_at=datetime.utcnow().isoformat(),
            trust_index=0.0,
        )

    # Check if metric is BLOCKED
    status_ = metric_def.get("status", "OK")

    if status_ == "BLOCKED":
        # Return BLOCKED metric with reason and data improvement suggestions
        blocked_reason = metric_def.get("blocked_reason", "Dados insuficientes")
        required_data = metric_def.get("required_data", [])

        explanation = (
            f"⛔ MÉTRICA BLOQUEADA: {blocked_reason}\n\n"
            f"Dados necessários: {', '.join(required_data)}\n\n"
            f"{metric_def.get('explanation', '')}"
        )

        return ExplainedMetric(
            metric_id=metric_id,
            metric_name=metric_def["name"],
            value=None,  # BLOCKED metrics have no value
            unit=metric_def.get("unit", "%"),
            explanation=explanation,
            factors=[],  # No factors for BLOCKED metrics
            suggestions=[ImprovementSuggestion(**s) for s in metric_def.get("suggestions", [])],
            citations=[],  # No citations for BLOCKED metrics
            computed_at=datetime.utcnow().isoformat(),
            trust_index=0.0,
        )

    # Sprint Q.9 (2.5) — try the semantic layer first; fall back to the
    # catalogue's placeholder when there's no data (no ingestion, DB down,
    # query unsupported).
    fallback_values = {
        "wip_theoretical": 1523,
        "backlog_horas_theoretical": 12450.5,
        "lead_time_observed": 12.5,
        "bottleneck_count": 5,
        "skills_risk_count": 8,
        "quality_errors_total": 89836,
    }
    live_value = await _resolve_metric_value(metric_id, session)
    metric_value = live_value if live_value is not None else fallback_values.get(metric_id)

    # Add status indicator to explanation
    trust_index = metric_def.get("trust_index", 0.5)
    semantic_label = metric_def.get("semantic_label", "")

    explanation = metric_def.get("explanation", "")
    if status_ == "WARNING":
        explanation = f"⚠️ CONFIANÇA LIMITADA: {semantic_label}\n\n{explanation}"

    return ExplainedMetric(
        metric_id=metric_id,
        metric_name=metric_def["name"],
        value=metric_value,
        unit=metric_def.get("unit", "%"),
        explanation=explanation,
        factors=[Factor(**f) for f in metric_def.get("factors", [])],
        suggestions=[ImprovementSuggestion(**s) for s in metric_def.get("suggestions", [])],
        citations=[Citation(**c) for c in metric_def.get("citations", [])],
        computed_at=datetime.utcnow().isoformat(),
        trust_index=trust_index,
    )


@router.get("/catalog", response_model=List[MetricCatalogEntry])
async def get_metric_catalog():
    """
    Get catalog of all available metrics with explanations.

    Returns list of metrics that can be explained.
    """
    return [
        MetricCatalogEntry(
            id=metric_id,
            name=metric_def["name"],
            domain=metric_def["domain"],
            unit=metric_def.get("unit", "%"),
            description=metric_def["description"],
            formula=metric_def.get("formula"),
        )
        for metric_id, metric_def in METRIC_CATALOG.items()
    ]


@router.get("/blocked")
async def get_blocked_metrics():
    """
    Get list of metrics that are blocked from computation.

    Blocked metrics are those missing required data sources.
    Returns both blocked and available metrics for comparison.
    """
    blocked = []
    available = []

    for metric_id, metric_def in METRIC_CATALOG.items():
        status_ = metric_def.get("status", "OK")

        if status_ == "BLOCKED":
            blocked.append({
                "metric_id": metric_id,
                "name": metric_def["name"],
                "reason": metric_def.get("blocked_reason", "Dados insuficientes"),
                "required_data": metric_def.get("required_data", []),
                "suggestions": [s for s in metric_def.get("suggestions", []) if s.get("action_type") == "data_improvement"],
            })
        else:
            available.append({
                "metric_id": metric_id,
                "name": metric_def["name"],
                "status": status_,
                "trust_index": metric_def.get("trust_index", 0.5),
                "semantic_label": metric_def.get("semantic_label", ""),
            })

    return {
        "blocked": blocked,
        "blocked_count": len(blocked),
        "available": available,
        "available_count": len(available),
        "summary": {
            "message": f"{len(blocked)} métricas bloqueadas, {len(available)} disponíveis",
            "blocked_reasons": list(set(b["reason"] for b in blocked)),
        },
    }


@router.post("/compute")
async def compute_metric_value(
    metric_id: str = Query(...),
    scope: Optional[Dict[str, Any]] = None,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Compute a metric value on-demand.

    Allows computing metrics with custom scope and time period.

    Sprint Q.9 (2.5) — pulls live values via the semantic layer when
    available (same path as ``/metric/{id}``); falls back to a static
    placeholder for catalogue entries the semantic layer doesn't yet
    cover so the endpoint always answers.
    """
    metric_def = METRIC_CATALOG.get(metric_id)

    if not metric_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metric '{metric_id}' not found in catalog.",
        )

    live_value = await _resolve_metric_value(metric_id, session)
    metric_value = live_value if live_value is not None else 75.0
    source = "semantic_queries" if live_value is not None else "catalogue_fallback"

    return {
        "metric_id": metric_id,
        "metric_name": metric_def["name"],
        "value": metric_value,
        "source": source,
        "unit": metric_def.get("unit", "%"),
        "computed_at": datetime.utcnow().isoformat(),
        "scope": scope,
        "period": {
            "start": period_start,
            "end": period_end,
        },
    }


# ============================================================================
# Sprint C 1.3 — commit explanations (explain ← plan)
# ============================================================================

@router.get("/commit/{commit_sha}", response_model=CommitExplanation)
async def explain_commit(
    commit_sha: str,
    tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
):
    """Return the KPIs, alternatives and rejection signals for one commit.

    Supports full SHA-256 and short (≥7 char) prefixes — the same
    lookup semantics the CPO commit endpoints already use.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.plan.cpo.commits import CommitsService
    from src.shared.database import get_session_context

    async with get_session_context() as session:  # type: AsyncSession
        service = CommitsService(session, tenant_id)
        commit = await service.get_by_sha(commit_sha)
        if commit is None and len(commit_sha) >= 7:
            commit = await service.get_by_sha_prefix(commit_sha)
        if commit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"commit not found: {commit_sha}",
            )

        kpis = dict(commit.kpis or {})
        return CommitExplanation(
            commit_sha256=commit.commit_sha256,
            short_sha=commit.commit_sha256[:12],
            kpis=kpis,
            alternatives=list(commit.alternatives or []),
            rejected_alternatives=list(commit.rejected_alternatives or []),
            user_preference_signal=dict(commit.user_preference_signal or {}),
            trust_index=float(commit.trust_index or 0.0),
            scenarios_tested=int(commit.scenarios_tested or 0),
            why_these_choices=_generate_explanation(kpis),
        )
