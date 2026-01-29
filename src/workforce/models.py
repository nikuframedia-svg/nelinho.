"""
Workforce Models for API
========================

Pydantic models for the Workforce Operations System API.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class DeltaType(str, Enum):
    """Types of workforce changes that can be simulated."""
    ADD_TRAINING = "add_training"
    REMOVE_EMPLOYEE = "remove_employee"
    ADD_EMPLOYEE = "add_employee"
    MODIFY_CAPACITY = "modify_capacity"


class RiskLevel(str, Enum):
    """Risk levels for phases/employees."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OK = "ok"


class WorkforceDelta(BaseModel):
    """A single workforce change to simulate."""
    type: DeltaType
    employee_id: Optional[str] = None
    phase_id: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    description: str


class GraphNode(BaseModel):
    """A node in the dependency graph."""
    id: str
    type: str  # 'phase', 'employee', 'order'
    label: str
    risk_level: Optional[RiskLevel] = None
    size: Optional[int] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """An edge in the dependency graph."""
    id: str
    source: str
    target: str
    type: str  # 'aptitude', 'assignment', 'dependency'
    weight: Optional[float] = None


class DependencyGraphResponse(BaseModel):
    """Response containing the dependency graph."""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    metadata: Dict[str, Any]
    trust_index: float
    semantic_label: str


class CascadeLevelItem(BaseModel):
    """An item within a cascade level."""
    label: str
    value: Any
    severity: Optional[RiskLevel] = None


class CascadeLevel(BaseModel):
    """A level in the cascade impact analysis."""
    level: int
    type: str  # 'workforce', 'production', 'downstream', 'economic'
    title: str
    items: List[CascadeLevelItem]


class CascadeImpactResponse(BaseModel):
    """Response containing cascade impact analysis."""
    source_phase: str
    source_phase_name: str
    trigger_employee: Optional[str] = None
    trigger_employee_name: Optional[str] = None
    levels: List[CascadeLevel]
    total_orders_affected: int
    total_backlog_affected: float
    estimated_daily_cost: float
    trust_index: float
    warnings: List[str] = Field(default_factory=list)


class SimulationMetrics(BaseModel):
    """Metrics for a simulation scenario."""
    spof_count: int
    avg_risk_score: float
    total_backlog_at_risk: float
    phases_at_risk: int


class SimulationResultResponse(BaseModel):
    """Response containing simulation results."""
    scenario_id: str
    scenario_name: str
    baseline: SimulationMetrics
    simulated: SimulationMetrics
    deltas: List[WorkforceDelta]
    impact: Dict[str, float]
    estimated_cost: Optional[Dict[str, float]] = None
    recommendations: List[str]
    trust_index: float


class TrainingRecommendationResponse(BaseModel):
    """A training recommendation."""
    id: str
    priority: RiskLevel
    employee_id: str
    employee_name: str
    employee_current_phases: List[str]
    target_phase_id: str
    target_phase_name: str
    reasoning: List[str]
    expected_impact: Dict[str, Any]
    estimated_cost: Dict[str, float]
    trust_index: float


class ScenarioMetrics(BaseModel):
    """Metrics for a comparison scenario."""
    spof_count: int
    avg_risk_score: float
    backlog_at_risk: float
    estimated_cost: float
    payback_days: Optional[float] = None


class ScenarioComparisonItem(BaseModel):
    """A single scenario in a comparison."""
    id: str
    name: str
    type: str  # 'baseline', 'training', 'hiring', 'custom'
    metrics: ScenarioMetrics
    is_recommended: bool
    recommendation_reason: Optional[str] = None


class ScenarioComparisonResponse(BaseModel):
    """Response containing scenario comparison."""
    scenarios: List[ScenarioComparisonItem]
    trust_index: float

