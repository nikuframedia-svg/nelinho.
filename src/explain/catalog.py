"""
Metric Catalog — Complete Definition of All System Metrics
===========================================================

Every metric in the system is defined here with:
- Stable ID (versioned)
- Human-readable name and description
- Formula (SQL-like or mathematical)
- Data sources and dependencies
- Trust index and coverage requirements
- Forbidden claims (what NOT to say about this metric)
- How to improve (actionable steps)

This catalog is:
- Auto-generated documentation source
- LLM tool guidance
- UI Inspector data source
- Validation reference
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class MetricDomain(str, Enum):
    """Domain/module that owns the metric."""
    FACTORY = "factory"
    PLANNING = "planning"
    QUALITY = "quality"
    COST = "cost"
    HR = "hr"
    MOLD = "mold"
    CAPACITY = "capacity"


class SemanticKind(str, Enum):
    """Type of value semantics."""
    THEORETICAL = "theoretical"
    OBSERVED = "observed"
    IMPUTED = "imputed"
    DERIVED = "derived"


class TrustLevel(str, Enum):
    """Trust level classification."""
    HIGH = "high"        # Trust >= 80
    MEDIUM = "medium"    # Trust 60-79
    LOW = "low"          # Trust 40-59
    BLOCKED = "blocked"  # Trust < 40


@dataclass
class DataSource:
    """Data source for a metric."""
    schema: str
    table: str
    fields: List[str]
    trust_index: int
    coverage_pct: float


@dataclass
class MetricDefinition:
    """
    Complete definition of a metric.
    
    This is the contract for any metric in the system.
    """
    
    # Identity
    id: str  # Stable, versioned identifier (e.g., "wip_theoretical_v1")
    name: str  # Human-readable name
    name_pt: str  # Portuguese name
    description: str
    description_pt: str
    
    # Classification
    domain: MetricDomain
    semantic_kind: SemanticKind
    unit: str  # hours, count, percentage, EUR, days
    
    # Formula
    formula: str  # SQL-like or mathematical formula
    formula_human: str  # Human-readable explanation
    
    # Data sources
    sources: List[DataSource] = field(default_factory=list)
    
    # Trust and quality
    base_trust_index: int = 50  # 0-100
    min_coverage_required: float = 30.0  # Minimum data coverage to compute
    
    # Constraints
    assumptions: List[str] = field(default_factory=list)
    forbidden_claims: List[str] = field(default_factory=list)
    how_to_improve: List[str] = field(default_factory=list)
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # Other metric IDs
    
    # Metadata
    version: str = "1.0.0"
    owner: str = "factory"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Flags
    is_blocked: bool = False
    blocked_reason: Optional[str] = None
    requires_pii: bool = False
    is_sensitive: bool = False
    
    def get_trust_level(self, actual_trust: int) -> TrustLevel:
        """Get trust level classification."""
        if actual_trust >= 80:
            return TrustLevel.HIGH
        elif actual_trust >= 60:
            return TrustLevel.MEDIUM
        elif actual_trust >= 40:
            return TrustLevel.LOW
        else:
            return TrustLevel.BLOCKED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "name_pt": self.name_pt,
            "description": self.description,
            "description_pt": self.description_pt,
            "domain": self.domain.value,
            "semantic_kind": self.semantic_kind.value,
            "unit": self.unit,
            "formula": self.formula,
            "formula_human": self.formula_human,
            "sources": [
                {
                    "schema": s.schema,
                    "table": s.table,
                    "fields": s.fields,
                    "trust_index": s.trust_index,
                    "coverage_pct": s.coverage_pct,
                }
                for s in self.sources
            ],
            "base_trust_index": self.base_trust_index,
            "min_coverage_required": self.min_coverage_required,
            "assumptions": self.assumptions,
            "forbidden_claims": self.forbidden_claims,
            "how_to_improve": self.how_to_improve,
            "depends_on": self.depends_on,
            "version": self.version,
            "owner": self.owner,
            "is_blocked": self.is_blocked,
            "blocked_reason": self.blocked_reason,
            "requires_pii": self.requires_pii,
            "is_sensitive": self.is_sensitive,
        }


# ============================================================================
# METRIC CATALOG
# ============================================================================

METRIC_CATALOG: Dict[str, MetricDefinition] = {
    
    # =========================================================================
    # FACTORY DOMAIN - WIP & Orders
    # =========================================================================
    
    "wip_theoretical": MetricDefinition(
        id="wip_theoretical",
        name="WIP (Theoretical)",
        name_pt="WIP Teórico",
        description="Count of open manufacturing orders (no completion date)",
        description_pt="Contagem de ordens de fabrico abertas (sem data de conclusão)",
        domain=MetricDomain.FACTORY,
        semantic_kind=SemanticKind.THEORETICAL,
        unit="count",
        formula="COUNT(OrdensFabrico WHERE DataAcabamento IS NULL)",
        formula_human="Count of orders where completion date is null",
        sources=[
            DataSource(
                schema="factory_curated",
                table="order",
                fields=["of_id", "data_conclusao"],
                trust_index=82,
                coverage_pct=100.0,
            ),
        ],
        base_trust_index=82,
        assumptions=[
            "DataAcabamento NULL means order is still open",
            "Does not account for paused/blocked orders",
        ],
        forbidden_claims=[
            "This is NOT physical WIP count",
            "Does NOT account for orders blocked in quality hold",
            "Does NOT represent actual shop floor inventory",
        ],
        how_to_improve=[
            "Add order status field to distinguish paused vs active",
            "Integrate with MES for real-time WIP tracking",
        ],
        version="1.0.0",
    ),
    
    "open_phases_count": MetricDefinition(
        id="open_phases_count",
        name="Open Phases Count",
        name_pt="Fases Abertas",
        description="Count of order phases without completion time",
        description_pt="Contagem de fases de ordens sem tempo de conclusão",
        domain=MetricDomain.FACTORY,
        semantic_kind=SemanticKind.THEORETICAL,
        unit="count",
        formula="COUNT(FasesOrdemFabrico WHERE FaseOf_Fim IS NULL)",
        formula_human="Count of phases where end time is null",
        sources=[
            DataSource(
                schema="factory_curated",
                table="order_phase",
                fields=["fase_of_id", "data_fim"],
                trust_index=80,
                coverage_pct=100.0,
            ),
        ],
        base_trust_index=80,
        assumptions=[
            "FaseOf_Fim NULL means phase is still in progress",
        ],
        forbidden_claims=[
            "Does NOT represent current physical location",
        ],
        how_to_improve=[
            "Track phase start/end times more accurately",
        ],
        version="1.0.0",
    ),
    
    # =========================================================================
    # CAPACITY DOMAIN - Backlog & Bottlenecks
    # =========================================================================
    
    "backlog_hours": MetricDefinition(
        id="backlog_hours",
        name="Backlog (Hours)",
        name_pt="Backlog Teórico (Horas)",
        description="Sum of predicted hours for open phases",
        description_pt="Soma de horas previstas para fases abertas",
        domain=MetricDomain.CAPACITY,
        semantic_kind=SemanticKind.THEORETICAL,
        unit="hours",
        formula="SUM(HorasPrevistas_Final WHERE is_phase_open = TRUE)",
        formula_human="Sum of HorasPrevistas_Final for all open phases",
        sources=[
            DataSource(
                schema="factory_curated",
                table="order_phase",
                fields=["horas_previstas", "horas_finais", "is_phase_open"],
                trust_index=58,
                coverage_pct=43.4,
            ),
        ],
        base_trust_index=58,
        min_coverage_required=30.0,
        assumptions=[
            "HorasPrevistas_Final is correctly derived",
            "56.6% of phases have HorasPrevistas=0 (unknown)",
            "Standards may be outdated",
        ],
        forbidden_claims=[
            "This is NOT actual work remaining",
            "Does NOT account for efficiency variations",
            "Does NOT account for setup times",
            "Cannot be used for precise scheduling",
        ],
        how_to_improve=[
            "Improve HorasPrevistas coverage (currently 43.4%)",
            "Review and update standards in FasesStandardModelos",
            "Add actual time tracking per phase",
        ],
        version="1.0.0",
    ),
    
    "backlog_days": MetricDefinition(
        id="backlog_days",
        name="Backlog (Days)",
        name_pt="Backlog Teórico (Dias)",
        description="Theoretical days of work based on capacity",
        description_pt="Dias teóricos de trabalho baseado na capacidade",
        domain=MetricDomain.CAPACITY,
        semantic_kind=SemanticKind.DERIVED,
        unit="days",
        formula="backlog_hours / capacidade_horas_dia",
        formula_human="Backlog hours divided by daily capacity (8h default)",
        sources=[
            DataSource(
                schema="factory_curated",
                table="order_phase",
                fields=["horas_finais"],
                trust_index=58,
                coverage_pct=43.4,
            ),
            DataSource(
                schema="factory_curated",
                table="phase_capacity",
                fields=["capacidade_horas"],
                trust_index=85,
                coverage_pct=80.0,
            ),
        ],
        base_trust_index=55,
        depends_on=["backlog_hours"],
        assumptions=[
            "8 hours per day default capacity",
            "No shift/overtime variations",
            "100% efficiency assumed",
        ],
        forbidden_claims=[
            "This is NOT a delivery promise",
            "Does NOT account for weekends/holidays",
            "Cannot be used for customer commitments",
        ],
        how_to_improve=[
            "Add shift calendar for accurate capacity",
            "Track actual capacity utilization",
        ],
        version="1.0.0",
    ),
    
    "bottleneck_score": MetricDefinition(
        id="bottleneck_score",
        name="Bottleneck Score",
        name_pt="Score de Gargalo",
        description="Relative bottleneck severity by phase",
        description_pt="Severidade relativa de gargalo por fase",
        domain=MetricDomain.CAPACITY,
        semantic_kind=SemanticKind.DERIVED,
        unit="score",
        formula="backlog_dias_fase / MAX(backlog_dias_todas_fases)",
        formula_human="Phase backlog days normalized to max",
        sources=[
            DataSource(
                schema="factory_curated",
                table="order_phase",
                fields=["fase_id", "horas_finais"],
                trust_index=58,
                coverage_pct=43.4,
            ),
        ],
        base_trust_index=50,
        depends_on=["backlog_days"],
        assumptions=[
            "TOC-like analysis with available data",
            "Assumes sequential flow",
        ],
        forbidden_claims=[
            "This is a PROBABLE bottleneck, not confirmed",
            "Does NOT account for parallel processing",
            "Does NOT account for resource sharing",
        ],
        how_to_improve=[
            "Add routing/flow data for accurate analysis",
            "Track actual throughput per phase",
        ],
        version="1.0.0",
    ),
    
    # =========================================================================
    # QUALITY DOMAIN
    # =========================================================================
    
    "error_count": MetricDefinition(
        id="error_count",
        name="Error Count",
        name_pt="Contagem de Erros",
        description="Total quality errors/defects recorded",
        description_pt="Total de erros/defeitos de qualidade registados",
        domain=MetricDomain.QUALITY,
        semantic_kind=SemanticKind.OBSERVED,
        unit="count",
        formula="COUNT(OrdemFabricoErros)",
        formula_human="Count of all error records",
        sources=[
            DataSource(
                schema="factory_curated",
                table="quality_event",
                fields=["id", "erro_tipo", "quantidade"],
                trust_index=67,
                coverage_pct=100.0,
            ),
        ],
        base_trust_index=67,
        assumptions=[
            "41.5% missing FaseOfCulpada (culprit phase)",
            "Severity classification may be inconsistent",
        ],
        forbidden_claims=[
            "Does NOT represent all quality issues",
            "Does NOT include unrecorded defects",
        ],
        how_to_improve=[
            "Improve FaseOfCulpada attribution (currently 58.5%)",
            "Standardize error severity classification",
        ],
        version="1.0.0",
    ),
    
    "error_rate_by_phase": MetricDefinition(
        id="error_rate_by_phase",
        name="Error Rate by Phase",
        name_pt="Taxa de Erros por Fase",
        description="Error count normalized by phase volume",
        description_pt="Contagem de erros normalizada pelo volume da fase",
        domain=MetricDomain.QUALITY,
        semantic_kind=SemanticKind.DERIVED,
        unit="percentage",
        formula="(errors_fase / total_ordens_fase) * 100",
        formula_human="Errors in phase divided by orders through phase",
        sources=[
            DataSource(
                schema="factory_curated",
                table="quality_event",
                fields=["fase_id", "quantidade"],
                trust_index=67,
                coverage_pct=58.5,
            ),
        ],
        base_trust_index=55,
        depends_on=["error_count"],
        assumptions=[
            "Only errors with FaseOfCulpada are attributed",
        ],
        forbidden_claims=[
            "41.5% of errors cannot be attributed to phase",
        ],
        how_to_improve=[
            "Improve error attribution to phases",
        ],
        version="1.0.0",
    ),
    
    # =========================================================================
    # MOLD DOMAIN
    # =========================================================================
    
    "mold_conflict_potential": MetricDefinition(
        id="mold_conflict_potential",
        name="Potential Mold Conflicts",
        name_pt="Conflitos Potenciais de Molde",
        description="Overlapping mold usage based on predicted dates",
        description_pt="Sobreposição de uso de molde baseada em datas previstas",
        domain=MetricDomain.MOLD,
        semantic_kind=SemanticKind.THEORETICAL,
        unit="count",
        formula="COUNT(mold_overlaps WHERE occupancy_hours > 12)",
        formula_human="Count of mold assignments with overlapping dates",
        sources=[
            DataSource(
                schema="factory_curated",
                table="order_phase",
                fields=["molde_id", "data_prevista"],
                trust_index=35,
                coverage_pct=4.8,
            ),
        ],
        base_trust_index=35,
        min_coverage_required=10.0,
        assumptions=[
            "12 hour mold occupancy assumption",
            "Only 4.8% of phases have DataPrevista",
        ],
        forbidden_claims=[
            "This is POTENTIAL conflict only, NOT confirmed",
            "95% of phases lack scheduling data",
            "Cannot confirm actual conflicts",
        ],
        how_to_improve=[
            "Improve DataPrevista coverage (currently 4.8%)",
            "Add real mold scheduling system",
        ],
        is_blocked=False,  # Low trust but computable
        version="1.0.0",
    ),
    
    # =========================================================================
    # HR/SKILLS DOMAIN
    # =========================================================================
    
    "skills_risk_score": MetricDefinition(
        id="skills_risk_score",
        name="Skills Risk Score",
        name_pt="Score de Risco de Competências",
        description="Risk of understaffing by phase based on capable employees",
        description_pt="Risco de subdimensionamento por fase baseado em funcionários aptos",
        domain=MetricDomain.HR,
        semantic_kind=SemanticKind.DERIVED,
        unit="score",
        formula="(min_required - capable_active) / min_required",
        formula_human="Gap between required and available capable employees",
        sources=[
            DataSource(
                schema="factory_curated",
                table="skill_matrix",
                fields=["funcionario_id", "fase_id", "apto"],
                trust_index=55,
                coverage_pct=70.0,
            ),
        ],
        base_trust_index=55,
        requires_pii=True,
        assumptions=[
            "Skill matrix is up to date",
            "Does not account for absence/vacation",
        ],
        forbidden_claims=[
            "Does NOT predict actual staffing issues",
            "Does NOT account for cross-training flexibility",
        ],
        how_to_improve=[
            "Keep skill matrix updated",
            "Add attendance/availability tracking",
        ],
        version="1.0.0",
    ),
    
    # =========================================================================
    # COST DOMAIN
    # =========================================================================
    
    "cost_theoretical": MetricDefinition(
        id="cost_theoretical",
        name="Theoretical Cost",
        name_pt="Custo Teórico Estimado",
        description="Estimated cost based on standard hours and rates",
        description_pt="Custo estimado baseado em horas standard e valores hora",
        domain=MetricDomain.COST,
        semantic_kind=SemanticKind.THEORETICAL,
        unit="EUR",
        formula="SUM(horas_previstas_final * valor_hora_mediano)",
        formula_human="Sum of predicted hours times median hourly rate",
        sources=[
            DataSource(
                schema="factory_curated",
                table="order_phase",
                fields=["horas_finais"],
                trust_index=58,
                coverage_pct=43.4,
            ),
            DataSource(
                schema="factory_curated",
                table="cost_reference",
                fields=["valor_hora_eur"],
                trust_index=75,
                coverage_pct=85.0,
            ),
        ],
        base_trust_index=52,
        is_sensitive=True,
        assumptions=[
            "Uses median ValorHora to avoid outliers",
            "Does not include material costs",
            "Does not include overhead",
        ],
        forbidden_claims=[
            "This is NOT actual cost",
            "This is NOT financial reporting data",
            "Does NOT include all cost components",
            "Cannot be used for customer pricing",
        ],
        how_to_improve=[
            "Track actual labor hours per order",
            "Add material cost tracking",
            "Integrate with financial system",
        ],
        version="1.0.0",
    ),
    
    # =========================================================================
    # LEAD TIME DOMAIN
    # =========================================================================
    
    "lead_time_observed": MetricDefinition(
        id="lead_time_observed",
        name="Lead Time (Observed)",
        name_pt="Lead Time Observado",
        description="Historical lead time from order creation to completion",
        description_pt="Lead time histórico desde criação até conclusão da ordem",
        domain=MetricDomain.FACTORY,
        semantic_kind=SemanticKind.OBSERVED,
        unit="days",
        formula="AVG(DataAcabamento - DataCriacao) WHERE both NOT NULL",
        formula_human="Average days from creation to completion",
        sources=[
            DataSource(
                schema="factory_curated",
                table="order",
                fields=["data_entrada", "data_conclusao"],
                trust_index=82,
                coverage_pct=100.0,
            ),
        ],
        base_trust_index=78,
        assumptions=[
            "Only completed orders included",
            "No distinction by product complexity",
        ],
        forbidden_claims=[
            "Does NOT predict future lead times",
            "Does NOT account for order complexity",
        ],
        how_to_improve=[
            "Segment by product/complexity",
            "Add planned vs actual comparison",
        ],
        version="1.0.0",
    ),
    
    # =========================================================================
    # BLOCKED METRICS (Cannot be computed with current data)
    # =========================================================================
    
    "oee_real": MetricDefinition(
        id="oee_real",
        name="OEE (Real)",
        name_pt="OEE Real",
        description="Overall Equipment Effectiveness",
        description_pt="Eficiência Global do Equipamento",
        domain=MetricDomain.FACTORY,
        semantic_kind=SemanticKind.OBSERVED,
        unit="percentage",
        formula="Availability × Performance × Quality",
        formula_human="Product of availability, performance, and quality rates",
        sources=[],  # No data sources available
        base_trust_index=0,
        is_blocked=True,
        blocked_reason="Não existem dados de paragens/máquinas para calcular Availability",
        forbidden_claims=[
            "Cannot claim any OEE value",
            "Cannot claim machine efficiency",
        ],
        how_to_improve=[
            "Add machine downtime tracking",
            "Add planned production time",
            "Integrate with MES/SCADA",
        ],
        version="1.0.0",
    ),
    
    "otd_official": MetricDefinition(
        id="otd_official",
        name="OTD (Official)",
        name_pt="OTD Oficial",
        description="On-Time Delivery rate",
        description_pt="Taxa de entregas atempadas",
        domain=MetricDomain.FACTORY,
        semantic_kind=SemanticKind.OBSERVED,
        unit="percentage",
        formula="(orders_delivered_on_time / total_orders) × 100",
        formula_human="Percentage of orders delivered by promised date",
        sources=[],  # No due date data available
        base_trust_index=0,
        is_blocked=True,
        blocked_reason="Não existe promessa comercial inequívoca (due date) nos dados",
        forbidden_claims=[
            "Cannot claim OTD rate",
            "Cannot claim delivery performance",
        ],
        how_to_improve=[
            "Add customer promised delivery dates",
            "Track delivery confirmations",
        ],
        version="1.0.0",
    ),
    
    "productivity_individual": MetricDefinition(
        id="productivity_individual",
        name="Individual Productivity",
        name_pt="Produtividade Individual",
        description="Output per employee",
        description_pt="Output por funcionário",
        domain=MetricDomain.HR,
        semantic_kind=SemanticKind.OBSERVED,
        unit="hours/person",
        formula="actual_hours / employee_count",
        formula_human="Actual hours worked per employee",
        sources=[],
        base_trust_index=0,
        is_blocked=True,
        blocked_reason="Não existem horas reais por funcionário nos dados",
        requires_pii=True,
        forbidden_claims=[
            "Cannot claim individual productivity",
            "Cannot compare employee performance",
        ],
        how_to_improve=[
            "Add actual labor hours tracking per employee",
            "Integrate with time & attendance system",
        ],
        version="1.0.0",
    ),
    
    "cost_real_per_order": MetricDefinition(
        id="cost_real_per_order",
        name="Real Cost per Order",
        name_pt="Custo Real por Ordem",
        description="Actual cost per manufacturing order",
        description_pt="Custo real por ordem de fabrico",
        domain=MetricDomain.COST,
        semantic_kind=SemanticKind.OBSERVED,
        unit="EUR",
        formula="SUM(actual_hours × actual_rate) per order",
        formula_human="Sum of actual labor cost per order",
        sources=[],
        base_trust_index=0,
        is_blocked=True,
        blocked_reason="Não existem horas reais por funcionário para calcular custo real",
        is_sensitive=True,
        forbidden_claims=[
            "Cannot claim actual cost",
            "Cannot use for financial reporting",
        ],
        how_to_improve=[
            "Track actual hours per order",
            "Integrate with payroll/finance",
        ],
        version="1.0.0",
    ),
    
    "capacity_real_per_day": MetricDefinition(
        id="capacity_real_per_day",
        name="Real Daily Capacity",
        name_pt="Capacidade Real Diária",
        description="Actual production capacity per day",
        description_pt="Capacidade de produção real por dia",
        domain=MetricDomain.CAPACITY,
        semantic_kind=SemanticKind.OBSERVED,
        unit="hours",
        formula="SUM(actual_available_hours) per day",
        formula_human="Sum of actual available hours per day",
        sources=[],
        base_trust_index=0,
        is_blocked=True,
        blocked_reason="Não existem dados de turnos/paragens para calcular capacidade real",
        forbidden_claims=[
            "Cannot claim actual capacity",
            "Cannot use for precise scheduling",
        ],
        how_to_improve=[
            "Add shift calendar",
            "Track machine downtime",
            "Integrate with scheduling system",
        ],
        version="1.0.0",
    ),
}


# ============================================================================
# CATALOG ACCESS FUNCTIONS
# ============================================================================

def get_metric(metric_id: str) -> Optional[MetricDefinition]:
    """Get metric definition by ID."""
    return METRIC_CATALOG.get(metric_id)


def get_all_metrics() -> Dict[str, MetricDefinition]:
    """Get all metric definitions."""
    return METRIC_CATALOG


def get_metrics_by_domain(domain: MetricDomain) -> List[MetricDefinition]:
    """Get all metrics for a domain."""
    return [m for m in METRIC_CATALOG.values() if m.domain == domain]


def get_blocked_metrics() -> List[MetricDefinition]:
    """Get all blocked metrics."""
    return [m for m in METRIC_CATALOG.values() if m.is_blocked]


def get_available_metrics() -> List[MetricDefinition]:
    """Get all available (non-blocked) metrics."""
    return [m for m in METRIC_CATALOG.values() if not m.is_blocked]


def get_metric_ids() -> List[str]:
    """Get list of all metric IDs."""
    return list(METRIC_CATALOG.keys())


def search_metrics(query: str) -> List[MetricDefinition]:
    """Search metrics by name or description."""
    query_lower = query.lower()
    return [
        m for m in METRIC_CATALOG.values()
        if query_lower in m.name.lower()
        or query_lower in m.name_pt.lower()
        or query_lower in m.description.lower()
        or query_lower in m.description_pt.lower()
    ]


def generate_catalog_markdown() -> str:
    """Generate markdown documentation from catalog."""
    lines = [
        "# ProdPlan ONE — Metric Catalog",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Total metrics: {len(METRIC_CATALOG)}",
        f"- Available: {len(get_available_metrics())}",
        f"- Blocked: {len(get_blocked_metrics())}",
        "",
        "---",
        "",
    ]
    
    # Group by domain
    for domain in MetricDomain:
        domain_metrics = get_metrics_by_domain(domain)
        if not domain_metrics:
            continue
        
        lines.append(f"## {domain.value.upper()}")
        lines.append("")
        
        for m in domain_metrics:
            status = "🔴 BLOCKED" if m.is_blocked else "✅ Available"
            lines.append(f"### {m.name} ({m.name_pt})")
            lines.append("")
            lines.append(f"**ID:** `{m.id}`")
            lines.append(f"**Status:** {status}")
            lines.append(f"**Unit:** {m.unit}")
            lines.append(f"**Trust:** {m.base_trust_index}/100")
            lines.append("")
            lines.append(f"**Description:** {m.description}")
            lines.append("")
            lines.append(f"**Formula:** `{m.formula}`")
            lines.append("")
            
            if m.forbidden_claims:
                lines.append("**⛔ Forbidden Claims:**")
                for claim in m.forbidden_claims:
                    lines.append(f"- {claim}")
                lines.append("")
            
            if m.how_to_improve:
                lines.append("**💡 How to Improve:**")
                for action in m.how_to_improve:
                    lines.append(f"- {action}")
                lines.append("")
            
            lines.append("---")
            lines.append("")
    
    return "\n".join(lines)





