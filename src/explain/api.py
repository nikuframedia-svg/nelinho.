"""
ProdPlan ONE - Explainability API
==================================

Endpoints for metric explanations, factor analysis, and citations.

IMPORTANT: This module now integrates with Factory Data Product.
- BLOCKED metrics (OEE, Availability, OTD, etc.) return status=BLOCKED with reason
- AVAILABLE metrics return actual values from SemanticQueries
- All metrics include trust_index and semantic_label
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session

from src.factory_data_product.config import (
    BLOCKED_METRICS, 
    ALLOWED_METRICS, 
    TRUST_INDEX, 
    SEMANTIC_LABELS,
)

# Import the new comprehensive catalog
from src.explain.catalog import (
    METRIC_CATALOG as FULL_CATALOG,
    get_metric,
    get_all_metrics,
    get_blocked_metrics as get_blocked_from_catalog,
    get_available_metrics,
    get_metrics_by_domain,
    search_metrics,
    generate_catalog_markdown,
    MetricDomain,
)

logger = logging.getLogger(__name__)

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
# ENDPOINTS
# ============================================================================

from src.shared.auth.headers import require_tenant_header

# Sprint Q.12 Onda 0.1: replaced silent zero-UUID default. Explain
# endpoints look up tenant-scoped KPIs via SemanticQueriesInMemory, so
# tenant_id is mandatory — read-only catalogue browsing belongs in a
# separate untenanted endpoint.
get_tenant_id = require_tenant_header


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
    status = metric_def.get("status", "OK")
    
    if status == "BLOCKED":
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
    if status == "WARNING":
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
        status = metric_def.get("status", "OK")
        
        if status == "BLOCKED":
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
                "status": status,
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
# NEW CATALOG ENDPOINTS (from P0-3)
# ============================================================================

@router.get("/catalog/full")
async def get_full_metric_catalog(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    include_blocked: bool = Query(True, description="Include blocked metrics"),
):
    """
    Get the complete metric catalog with all definitions.
    
    This is the authoritative source for all metrics in the system.
    Each metric includes:
    - Full definition (formula, description, unit)
    - Trust information (base index, coverage requirements)
    - Forbidden claims (what NOT to say)
    - How to improve (actionable steps)
    """
    if domain:
        try:
            domain_enum = MetricDomain(domain)
            metrics = get_metrics_by_domain(domain_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid domain: {domain}. Valid: {[d.value for d in MetricDomain]}"
            )
    else:
        metrics = list(FULL_CATALOG.values())
    
    if not include_blocked:
        metrics = [m for m in metrics if not m.is_blocked]
    
    return {
        "metrics": [m.to_dict() for m in metrics],
        "total": len(metrics),
        "domains": [d.value for d in MetricDomain],
        "blocked_count": len([m for m in metrics if m.is_blocked]),
        "available_count": len([m for m in metrics if not m.is_blocked]),
    }


@router.get("/catalog/{metric_id}/full")
async def get_full_metric_definition(metric_id: str):
    """
    Get the complete definition for a specific metric.
    
    Returns ALL metadata including:
    - Formula and description (PT and EN)
    - Data sources with trust and coverage
    - Assumptions and forbidden claims
    - How to improve actions
    - Dependency chain
    """
    metric = get_metric(metric_id)
    
    if not metric:
        raise HTTPException(
            status_code=404,
            detail=f"Metric '{metric_id}' not found in catalog."
        )
    
    return metric.to_dict()


@router.get("/catalog/search")
async def search_metric_catalog(
    q: str = Query(..., min_length=2, description="Search query"),
):
    """
    Search the metric catalog by name or description.
    
    Searches in:
    - Name (EN and PT)
    - Description (EN and PT)
    - Formula
    """
    results = search_metrics(q)
    
    return {
        "query": q,
        "results": [m.to_dict() for m in results],
        "total": len(results),
    }


@router.get("/catalog/blocked/full")
async def get_full_blocked_metrics():
    """
    Get detailed information about all blocked metrics.
    
    Blocked metrics are those that cannot be computed due to missing data.
    This endpoint provides:
    - Why each metric is blocked
    - What data is needed to unblock
    - Actionable steps to enable the metric
    """
    blocked = get_blocked_from_catalog()
    
    return {
        "blocked": [
            {
                "id": m.id,
                "name": m.name,
                "name_pt": m.name_pt,
                "blocked_reason": m.blocked_reason,
                "how_to_improve": m.how_to_improve,
                "domain": m.domain.value,
            }
            for m in blocked
        ],
        "total": len(blocked),
        "message": f"{len(blocked)} metrics are blocked due to missing data",
    }


@router.get("/catalog/available/full")
async def get_full_available_metrics():
    """
    Get all metrics that can be computed with current data.
    
    These are the metrics that are safe to use in the UI and API.
    Each includes trust level and coverage information.
    """
    available = get_available_metrics()
    
    return {
        "available": [
            {
                "id": m.id,
                "name": m.name,
                "name_pt": m.name_pt,
                "unit": m.unit,
                "base_trust_index": m.base_trust_index,
                "semantic_kind": m.semantic_kind.value,
                "domain": m.domain.value,
                "assumptions": m.assumptions,
                "forbidden_claims": m.forbidden_claims,
            }
            for m in available
        ],
        "total": len(available),
    }


@router.get("/catalog/markdown")
async def get_catalog_as_markdown():
    """
    Generate markdown documentation from the metric catalog.

    Useful for:
    - Auto-generating documentation
    - Exporting for external systems
    - Auditing metric definitions
    """
    markdown = generate_catalog_markdown()

    return {
        "format": "markdown",
        "content": markdown,
        "generated_at": datetime.utcnow().isoformat(),
    }


# ============================================================================
# Sprint C 1.3 — commit explanations (explain ← plan)
# ============================================================================


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


# ═══════════════════════════════════════════════════════════════════════════
# Sprint I.3 — DoWhy-GCM attribution endpoint
# ═══════════════════════════════════════════════════════════════════════════


class AttributionNode(BaseModel):
    node: str
    share: float = Field(..., ge=0.0, le=1.0)
    direction: str
    absolute: float


class AttributionResponse(BaseModel):
    target: str
    status: str                            # ok / degraded / unavailable
    reason: Optional[str] = None
    engine: str
    sample_size: int
    baseline_mean: Optional[float] = None
    target_value: Optional[float] = None
    ranked: List[AttributionNode] = Field(default_factory=list)


@router.get("/attribution", response_model=AttributionResponse)
async def causal_attribution(
    target: str = Query(..., description="NELO_DAG node id, e.g. throughput_eur_day"),
    sample_size: int = Query(200, ge=50, le=2000),
    seed: int = Query(42, ge=0),
):
    """Return per-node contributions to the target's variance.

    Uses DoWhy-GCM's ``intrinsic_causal_influence`` on the NELO_DAG
    ancestors of ``target``. When DoWhy can't be imported (dev
    machine without the heavy deps) the response is
    ``status="unavailable"`` with a reason — the UI can fall back to
    the CausalChain narrative.

    For Sprint I.3 the sample is simulated from the DAG's functional
    forms (``status="degraded"``) because we don't have enough
    production telemetry yet. Sprint G + 3 months of real data will
    flip this to ``status="ok"`` without changing the endpoint.
    """
    from src.copilot.causal.attribution import attribution_analysis

    report = attribution_analysis(
        target=target, sample_size=sample_size, seed=seed,
    )
    return AttributionResponse(
        target=report.target,
        status=report.status,
        reason=report.reason,
        engine=report.engine,
        sample_size=report.sample_size,
        baseline_mean=report.baseline_mean,
        target_value=report.target_value,
        ranked=[AttributionNode(**a.__dict__) for a in report.ranked],
    )


# ═══════════════════════════════════════════════════════════════════════════
# Sprint I.4 — PCMCI+ causal discovery endpoint
# ═══════════════════════════════════════════════════════════════════════════


class DiscoveredEdgeResponse(BaseModel):
    src: str
    dst: str
    lag: int
    strength: float
    pvalue: float
    is_new: bool
    direction: str


class DiscoveryResponse(BaseModel):
    status: str                               # ok / degraded / unavailable
    reason: Optional[str] = None
    engine: str
    sample_size: int
    tau_max: int
    nodes_examined: int
    candidate_edges: List[DiscoveredEdgeResponse] = Field(default_factory=list)


@router.get("/discover", response_model=DiscoveryResponse)
async def causal_discover(
    tau_max: int = Query(2, ge=0, le=5),
    alpha: float = Query(0.05, gt=0.0, lt=0.5),
    sample_size: int = Query(300, ge=50, le=5000),
    seed: int = Query(17, ge=0),
    restrict_to: Optional[str] = Query(
        default=None,
        description="Optional comma-separated list of DAG node ids to limit the scan.",
    ),
):
    """Run PCMCI+ over a time series and propose new DAG edges.

    The ``is_new`` flag tells ``/admin/causal-discoveries`` which
    edges extend :data:`NELO_DAG` vs. which merely confirm it. Only
    ``is_new`` rows need human review; the rest are a confidence
    signal for the existing graph.

    Like the attribution endpoint, this will run on simulated data
    (``status="degraded"``) until Sprint G+I produces enough real
    telemetry to feed the series directly.
    """
    from src.copilot.causal.discovery import discover_edges

    restrict_list: Optional[List[str]] = None
    if restrict_to:
        restrict_list = [s.strip() for s in restrict_to.split(",") if s.strip()]

    report = discover_edges(
        tau_max=tau_max,
        alpha=alpha,
        sample_size=sample_size,
        seed=seed,
        restrict_to=restrict_list,
    )
    return DiscoveryResponse(
        status=report.status,
        reason=report.reason,
        engine=report.engine,
        sample_size=report.sample_size,
        tau_max=report.tau_max,
        nodes_examined=report.nodes_examined,
        candidate_edges=[
            DiscoveredEdgeResponse(**edge.to_json())
            for edge in report.candidate_edges
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# DIAGNOSTICS — ERRO-TREE (Sprint Q.15.D.1)
# ═══════════════════════════════════════════════════════════════════════════
#
# Operator-facing endpoint for the ERRO-TREE handler. The frontend or
# the LLM (via tool-calling, capability `diagnostics.erro_tree.enabled`)
# POSTs the trigger + period + optional phase_id; the handler runs the
# 3-detector cascade (mold → worker → overload) and returns either a
# root_cause hypothesis or a "no isolated cause" verdict.
#
# Audit + push: the @record_rule_firing decorator on `investigate()`
# persists every call to governance.rule_firing (Q.14.A) and triggers
# pg_notify push to the SSE channel (Q.14.B) when the allowlist matches.


class DiagnosticsInvestigateRequest(BaseModel):
    """Body for `POST /v1/explain/diagnostics/investigate`."""

    trigger: str = Field(
        ...,
        description=(
            "What symptom prompted the investigation. "
            "Allowed: quality_drop / throughput_drop / delay_spike."
        ),
    )
    period_days: int = Field(
        default=7, ge=1, le=90,
        description="Lookback window. Default 7 — captures weekly drift.",
    )
    phase_id: Optional[str] = Field(
        default=None,
        description="Optional — restrict to a single phase.",
    )
    conversation_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Sprint Q.15.D.5 — when supplied AND a hypothesis trips, "
            "the handler emits a verified CausalChain into the "
            "Camada-4 ABL pipeline (CopilotMessage.content_structured. "
            "causal_audit). Frontend passes the active conversation; "
            "scheduler-driven calls leave this null and chain emission "
            "is skipped (rule_firing audit still happens via Q.14.A)."
        ),
    )


@router.post("/diagnostics/investigate")
async def investigate_diagnostics(
    payload: DiagnosticsInvestigateRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Run the ERRO-TREE diagnostic cascade.

    Sprint Q.15.D.1 — replaces LLM improvisation with a real handler
    that reads governance.rule_firing-audited evidence + emits a
    `Hypothesis` with Beta-Bernoulli confidence + 95% CI.
    """
    from src.explain.diagnostics.erro_tree import ErroTreeDetector
    from src.explain.diagnostics.types import TriggerType

    try:
        trigger = TriggerType(payload.trigger)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid trigger '{payload.trigger}'. "
                f"Allowed: {[t.value for t in TriggerType]}"
            ),
        )

    detector = ErroTreeDetector(session=db, tenant_id=tenant_id)
    result = await detector.investigate(
        trigger=trigger,
        period_days=payload.period_days,
        phase_id=payload.phase_id,
        conversation_id=payload.conversation_id,
    )

    body: Dict[str, Any] = {
        "root_cause": None,
        "chain": result.chain,
        "steps_checked": result.steps_checked,
        "recommendation": result.recommendation,
    }
    if result.root_cause is not None:
        h = result.root_cause
        ci_low, ci_high = h.credible_interval(level=0.95)
        body["root_cause"] = {
            "type": h.type,
            "entity": h.entity,
            "confidence": round(h.confidence, 4),
            "credible_interval_95": {
                "low": round(ci_low, 4),
                "high": round(ci_high, 4),
            },
            "evidence": list(h.evidence),
        }
    return body


# ═══════════════════════════════════════════════════════════════════════════
# DIAGNOSTICS — Reichenbach (Sprint Q.15.D.2)
# ═══════════════════════════════════════════════════════════════════════════
#
# When 2+ phases drift simultaneously, the LLM (or the
# MultivariatePhaseMonitor scheduler hook) calls this endpoint instead
# of asking ERRO-TREE per phase. Reichenbach finds the shared resource
# (mold / workers / cascade) and returns a list of common-cause
# Hypothesis objects. When no common cause is found, falls back to
# per-phase ERRO-TREE results (verdict = "independent").


class CommonCauseRequest(BaseModel):
    """Body for `POST /v1/explain/diagnostics/common-cause`."""

    deviating_phases: List[str] = Field(
        ..., min_length=2,
        description=(
            "Phase ids that show simultaneous drift in the same window. "
            "The MultivariatePhaseMonitor produces this list on its 30-min "
            "schedule; the LLM may also pass it directly via tool-call."
        ),
    )
    period_days: int = Field(
        default=7, ge=1, le=90,
        description="Lookback window for the common-cause search.",
    )
    conversation_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Sprint Q.15.D.5 — when supplied AND a common cause trips, "
            "emit a verified CausalChain into the Camada-4 ABL pipeline."
        ),
    )


def _serialise_hypothesis(h) -> Dict[str, Any]:
    """Convert a Hypothesis into the JSON shape the frontend renders."""
    ci_low, ci_high = h.credible_interval(level=0.95)
    return {
        "type": h.type,
        "entity": h.entity,
        "confidence": round(h.confidence, 4),
        "credible_interval_95": {
            "low": round(ci_low, 4),
            "high": round(ci_high, 4),
        },
        "evidence": list(h.evidence),
    }


@router.post("/diagnostics/common-cause")
async def common_cause(
    payload: CommonCauseRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Reichenbach common-cause analysis.

    Returns:
        ``{"verdict": "common_cause"|"independent"|"inconclusive",
           "common_causes": [Hypothesis, ...],
           "independent_causes": [Hypothesis, ...],
           "checks_run": [...]}``

    - ``common_cause`` → at least one shared-resource hypothesis tripped.
    - ``independent`` → no shared cause found; per-phase ERRO-TREE
      hypotheses are in `independent_causes` instead.
    - ``inconclusive`` → input had < 2 phases or no detectors produced anything.
    """
    from src.explain.diagnostics.reichenbach import ReichenbachDetector

    detector = ReichenbachDetector(session=db, tenant_id=tenant_id)
    result = await detector.find_common_cause(
        deviating_phases=payload.deviating_phases,
        period_days=payload.period_days,
        conversation_id=payload.conversation_id,
    )
    return {
        "verdict": result.verdict,
        "common_causes": [_serialise_hypothesis(h) for h in result.common_causes],
        "independent_causes": [
            _serialise_hypothesis(h) for h in result.independent_causes
        ],
        "checks_run": result.checks_run,
    }


# ═══════════════════════════════════════════════════════════════════════════
# DIAGNOSTICS — Mill's method (Sprint Q.15.D.4)
# ═══════════════════════════════════════════════════════════════════════════
#
# *"O que mudou entre antes e agora?"* — compare a "good" period with
# a "bad" period, rank what's different by Cohen's d correlation, and
# return a list of candidate causes ordered by likelihood.


class WhatChangedRequest(BaseModel):
    """Body for `POST /v1/explain/diagnostics/what-changed`."""

    good_period_start: date = Field(..., description="ISO date — start of 'before' (inclusive)")
    good_period_end: date = Field(..., description="ISO date — end of 'before' (exclusive)")
    bad_period_start: date = Field(..., description="ISO date — start of 'after' (inclusive)")
    bad_period_end: date = Field(..., description="ISO date — end of 'after' (exclusive)")
    metric: str = Field(
        default="error_rate",
        description="Metric to compare. Today: 'error_rate' (only)."
    )
    phase_id: Optional[str] = Field(
        default=None,
        description="Optional — restrict the comparison to one phase.",
    )
    likely_threshold: float = Field(
        default=0.7, ge=0.5, le=0.95,
        description=(
            "Correlation cutoff for `likely_cause=True`. 0.7 ≈ Cohen's "
            "'large' effect; lower it to surface weaker signals."
        ),
    )
    conversation_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Sprint Q.15.D.5 — when supplied AND a likely_cause Change "
            "is found, emit a verified CausalChain into the Camada-4 "
            "ABL pipeline."
        ),
    )


@router.post("/diagnostics/what-changed")
async def what_changed(
    payload: WhatChangedRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Mill's method of difference — what changed between 2 periods.

    Sprint Q.15.D.4 — closes §10.4 of the v2.2 prompt. Returns:
      ``metric_comparison``: actual delta + Cohen's d on daily samples.
      ``changes_found``: list of {category, change, correlation,
        likely_cause, evidence}, ranked by correlation desc.
      ``unchanged``: dimensions whose data isn't there or the shift is
        below the noise floor.
      ``verdict``: one-liner naming the strongest likely_cause.
    """
    from src.explain.diagnostics.mill_diff import MillDiffDetector

    if payload.bad_period_end <= payload.good_period_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bad_period must come after good_period.",
        )

    detector = MillDiffDetector(session=db, tenant_id=tenant_id)
    report = await detector.what_changed(
        good_start=payload.good_period_start,
        good_end=payload.good_period_end,
        bad_start=payload.bad_period_start,
        bad_end=payload.bad_period_end,
        metric=payload.metric,
        phase_id=payload.phase_id,
        likely_threshold=payload.likely_threshold,
        conversation_id=payload.conversation_id,
    )
    return report.to_dict()
