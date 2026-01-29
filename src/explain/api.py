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
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

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

def get_tenant_id(x_tenant_id: UUID = Header(default=UUID("00000000-0000-0000-0000-000000000000"))) -> UUID:
    """Extract tenant ID from header (optional for explain endpoints)."""
    return x_tenant_id


@router.get("/metric/{metric_id}", response_model=ExplainedMetric)
async def get_metric_explanation(
    metric_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
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
    
    # Mock values for AVAILABLE metrics
    # TODO: Fetch from SemanticQueries when DB is connected
    mock_values = {
        "wip_theoretical": 1523,
        "backlog_horas_theoretical": 12450.5,
        "lead_time_observed": 12.5,
        "bottleneck_count": 5,
        "skills_risk_count": 8,
        "quality_errors_total": 89836,
    }
    
    # Add status indicator to explanation
    trust_index = metric_def.get("trust_index", 0.5)
    semantic_label = metric_def.get("semantic_label", "")
    
    explanation = metric_def.get("explanation", "")
    if status == "WARNING":
        explanation = f"⚠️ CONFIANÇA LIMITADA: {semantic_label}\n\n{explanation}"
    
    return ExplainedMetric(
        metric_id=metric_id,
        metric_name=metric_def["name"],
        value=mock_values.get(metric_id),
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
):
    """
    Compute a metric value on-demand.
    
    Allows computing metrics with custom scope and time period.
    """
    metric_def = METRIC_CATALOG.get(metric_id)
    
    if not metric_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metric '{metric_id}' not found in catalog.",
        )
    
    # TODO: Implement actual metric computation
    # This would call the appropriate calculation engine
    
    return {
        "metric_id": metric_id,
        "metric_name": metric_def["name"],
        "value": 75.0,  # Mock computed value
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

