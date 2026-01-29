"""
ExplainedValue Model — Contrato 020
===================================

The central model for explainability. Every metric must be wrapped
in an ExplainedValue with full metadata.

REQUIRED FIELDS:
- metric_id: stable, versioned identifier
- value: the actual value (can be null)
- unit: measurement unit
- period: time context
- scope: entity context
- semantics: theoretical/observed/imputed
- trust: confidence level with warnings
- lineage: data provenance
- explain: human-readable explanation
"""

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, computed_field


# ============================================================================
# ENUMS
# ============================================================================

class PeriodType(str, Enum):
    """Type of time period."""
    AS_OF = "as_of"           # Point in time
    RANGE = "range"           # From/to range
    ROLLING = "rolling"       # Rolling window
    YTD = "ytd"               # Year to date
    MTD = "mtd"               # Month to date


class ScopeLevel(str, Enum):
    """Level of aggregation."""
    FACTORY = "factory"       # Entire factory
    LINE = "line"             # Production line
    PHASE = "phase"           # Production phase
    ORDER = "order"           # Single order
    PRODUCT = "product"       # Product type
    MODEL = "model"           # Model type
    MOLD = "mold"             # Mold
    EMPLOYEE = "employee"     # Employee (PII)


class SemanticKind(str, Enum):
    """Type of value semantics."""
    THEORETICAL = "theoretical"   # Based on standards/estimates
    OBSERVED = "observed"         # Based on actual measurements
    IMPUTED = "imputed"           # Derived/calculated
    UNKNOWN = "unknown"           # Cannot determine


class SemanticCompleteness(str, Enum):
    """Data completeness level."""
    COMPLETE = "complete"         # All data present
    PARTIAL = "partial"           # Some data missing
    INSUFFICIENT = "insufficient" # Not enough data


# ============================================================================
# SUB-MODELS
# ============================================================================

class TimePeriod(BaseModel):
    """Time context for a value."""
    
    model_config = ConfigDict(extra="forbid")
    
    type: PeriodType = PeriodType.AS_OF
    
    # For AS_OF
    timestamp: Optional[datetime] = None
    
    # For RANGE
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    
    # For ROLLING
    window_days: Optional[int] = None


class ValueScope(BaseModel):
    """Entity context for a value."""
    
    model_config = ConfigDict(extra="forbid")
    
    level: ScopeLevel
    
    # Entity identifiers (based on level)
    factory_id: Optional[str] = None
    line_id: Optional[str] = None
    phase_id: Optional[str] = None
    fase_nome: Optional[str] = None
    order_id: Optional[str] = None
    product_id: Optional[str] = None
    model_id: Optional[str] = None
    mold_id: Optional[str] = None
    employee_id: Optional[str] = None  # PII
    
    # Additional context
    filters: Dict[str, Any] = Field(default_factory=dict)


class SemanticInfo(BaseModel):
    """Semantic metadata for a value."""
    
    model_config = ConfigDict(extra="forbid")
    
    kind: SemanticKind = SemanticKind.UNKNOWN
    completeness: SemanticCompleteness = SemanticCompleteness.PARTIAL


class TrustInfo(BaseModel):
    """Trust/confidence metadata."""
    
    model_config = ConfigDict(extra="forbid")
    
    # Trust index (0-100)
    index_0_100: int = Field(ge=0, le=100)
    
    # Data coverage percentage
    coverage_pct: float = Field(ge=0, le=100)
    
    # Warnings (non-blocking issues)
    warnings: List[str] = Field(default_factory=list)
    
    # Blocking reasons (if any, value should not be used for automation)
    blocking_reasons: List[str] = Field(default_factory=list)
    
    @property
    def is_blocked(self) -> bool:
        """Check if value is blocked from automation."""
        return len(self.blocking_reasons) > 0 or self.index_0_100 < 40
    
    @property
    def is_low_confidence(self) -> bool:
        """Check if confidence is low."""
        return self.index_0_100 < 60


class LineageSource(BaseModel):
    """Source of data in lineage."""
    
    model_config = ConfigDict(extra="forbid")
    
    schema: str
    table_or_view: str
    fields: List[str] = Field(default_factory=list)


class LineageInfo(BaseModel):
    """Data provenance metadata."""
    
    model_config = ConfigDict(extra="forbid")
    
    # Active ingestion (from Factory Data Product)
    active_ingestion_id: Optional[str] = None
    
    # Data sources
    sources: List[LineageSource] = Field(default_factory=list)
    
    # Effective filters
    filters: Dict[str, Any] = Field(default_factory=dict)
    
    # When computed
    computed_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    
    # Query hash for audit/cache
    query_hash: Optional[str] = None
    
    def compute_query_hash(self, query_text: str) -> str:
        """Compute and store query hash."""
        self.query_hash = "sha256:" + hashlib.sha256(
            query_text.encode()
        ).hexdigest()[:16]
        return self.query_hash


class ExplainInfo(BaseModel):
    """Human-readable explanation."""
    
    model_config = ConfigDict(extra="forbid")
    
    # Short definition
    definition: str
    
    # Formula (text or pseudo-SQL)
    formula: str
    
    # Assumptions made
    assumptions: List[str] = Field(default_factory=list)
    
    # What NOT to claim (anti-claims)
    forbidden_claims: List[str] = Field(default_factory=list)
    
    # Plain language explanation
    what_it_means: str
    
    # Actions to improve trust
    how_to_improve: List[str] = Field(default_factory=list)


# ============================================================================
# MAIN MODEL
# ============================================================================

class ExplainedValue(BaseModel):
    """
    The central explainability model.
    
    EVERY metric in the system must be wrapped in an ExplainedValue.
    No number leaves the system without full metadata.
    """
    
    model_config = ConfigDict(extra="forbid")
    
    # -------------------------------------------------------------------------
    # REQUIRED: Identity
    # -------------------------------------------------------------------------
    
    metric_id: str = Field(
        ...,
        description="Stable, versioned metric identifier",
    )
    
    # -------------------------------------------------------------------------
    # REQUIRED: Value
    # -------------------------------------------------------------------------
    
    value: Optional[Union[int, float, Decimal, str]] = Field(
        default=None,
        description="The actual value (null if not computable)",
    )
    
    unit: str = Field(
        ...,
        description="Unit of measurement (hours, pct, EUR, count, etc.)",
    )
    
    # Optional display format
    display_value: Optional[str] = None
    
    # -------------------------------------------------------------------------
    # REQUIRED: Context
    # -------------------------------------------------------------------------
    
    period: TimePeriod = Field(
        ...,
        description="Time context for the value",
    )
    
    scope: ValueScope = Field(
        ...,
        description="Entity context for the value",
    )
    
    # -------------------------------------------------------------------------
    # REQUIRED: Semantics
    # -------------------------------------------------------------------------
    
    semantics: SemanticInfo = Field(
        default_factory=SemanticInfo,
        description="Semantic metadata (theoretical/observed, completeness)",
    )
    
    # -------------------------------------------------------------------------
    # REQUIRED: Trust
    # -------------------------------------------------------------------------
    
    trust: TrustInfo = Field(
        ...,
        description="Trust/confidence metadata",
    )
    
    # -------------------------------------------------------------------------
    # REQUIRED: Lineage
    # -------------------------------------------------------------------------
    
    lineage: LineageInfo = Field(
        default_factory=LineageInfo,
        description="Data provenance metadata",
    )
    
    # -------------------------------------------------------------------------
    # REQUIRED: Explain
    # -------------------------------------------------------------------------
    
    explain: ExplainInfo = Field(
        ...,
        description="Human-readable explanation",
    )
    
    # -------------------------------------------------------------------------
    # COMPUTED PROPERTIES
    # -------------------------------------------------------------------------
    
    @computed_field
    @property
    def is_blocked(self) -> bool:
        """Check if value is blocked from automation."""
        return self.trust.is_blocked
    
    @computed_field
    @property
    def is_usable(self) -> bool:
        """Check if value is usable (not insufficient)."""
        return (
            self.value is not None and
            self.semantics.completeness != SemanticCompleteness.INSUFFICIENT
        )
    
    @computed_field
    @property
    def status(self) -> str:
        """Get overall status."""
        if not self.is_usable:
            return "unavailable"
        elif self.is_blocked:
            return "blocked"
        elif self.trust.is_low_confidence:
            return "low_confidence"
        else:
            return "ok"


# ============================================================================
# BUILDER
# ============================================================================

class ExplainedValueBuilder:
    """
    Builder for creating ExplainedValue instances.
    
    Simplifies construction with sensible defaults.
    """
    
    def __init__(self, metric_id: str):
        self.metric_id = metric_id
        self._value: Optional[Any] = None
        self._unit: str = "count"
        self._period: Optional[TimePeriod] = None
        self._scope: Optional[ValueScope] = None
        self._semantics: Optional[SemanticInfo] = None
        self._trust: Optional[TrustInfo] = None
        self._lineage: Optional[LineageInfo] = None
        self._explain: Optional[ExplainInfo] = None
    
    def with_value(
        self,
        value: Optional[Any],
        unit: str = "count",
        display: Optional[str] = None,
    ) -> "ExplainedValueBuilder":
        """Set the value."""
        self._value = value
        self._unit = unit
        self._display = display
        return self
    
    def with_period_as_of(
        self,
        timestamp: Optional[datetime] = None,
    ) -> "ExplainedValueBuilder":
        """Set period as point-in-time."""
        self._period = TimePeriod(
            type=PeriodType.AS_OF,
            timestamp=timestamp or datetime.now(timezone.utc),
        )
        return self
    
    def with_period_range(
        self,
        from_date: datetime,
        to_date: datetime,
    ) -> "ExplainedValueBuilder":
        """Set period as range."""
        self._period = TimePeriod(
            type=PeriodType.RANGE,
            from_date=from_date,
            to_date=to_date,
        )
        return self
    
    def with_scope(
        self,
        level: ScopeLevel,
        **kwargs,
    ) -> "ExplainedValueBuilder":
        """Set scope."""
        self._scope = ValueScope(level=level, **kwargs)
        return self
    
    def with_semantics(
        self,
        kind: SemanticKind = SemanticKind.THEORETICAL,
        completeness: SemanticCompleteness = SemanticCompleteness.PARTIAL,
    ) -> "ExplainedValueBuilder":
        """Set semantics."""
        self._semantics = SemanticInfo(kind=kind, completeness=completeness)
        return self
    
    def with_trust(
        self,
        index: int,
        coverage: float = 100.0,
        warnings: Optional[List[str]] = None,
        blocking_reasons: Optional[List[str]] = None,
    ) -> "ExplainedValueBuilder":
        """Set trust."""
        self._trust = TrustInfo(
            index_0_100=index,
            coverage_pct=coverage,
            warnings=warnings or [],
            blocking_reasons=blocking_reasons or [],
        )
        return self
    
    def with_lineage(
        self,
        active_ingestion_id: Optional[str] = None,
        sources: Optional[List[Dict]] = None,
        filters: Optional[Dict] = None,
    ) -> "ExplainedValueBuilder":
        """Set lineage."""
        source_objects = []
        if sources:
            for s in sources:
                source_objects.append(LineageSource(**s))
        
        self._lineage = LineageInfo(
            active_ingestion_id=active_ingestion_id,
            sources=source_objects,
            filters=filters or {},
        )
        return self
    
    def with_explain(
        self,
        definition: str,
        formula: str,
        what_it_means: str,
        assumptions: Optional[List[str]] = None,
        forbidden_claims: Optional[List[str]] = None,
        how_to_improve: Optional[List[str]] = None,
    ) -> "ExplainedValueBuilder":
        """Set explain."""
        self._explain = ExplainInfo(
            definition=definition,
            formula=formula,
            what_it_means=what_it_means,
            assumptions=assumptions or [],
            forbidden_claims=forbidden_claims or [],
            how_to_improve=how_to_improve or [],
        )
        return self
    
    def build(self) -> ExplainedValue:
        """Build the ExplainedValue."""
        if self._period is None:
            self._period = TimePeriod(
                type=PeriodType.AS_OF,
                timestamp=datetime.now(timezone.utc),
            )
        
        if self._scope is None:
            self._scope = ValueScope(level=ScopeLevel.FACTORY)
        
        if self._semantics is None:
            self._semantics = SemanticInfo()
        
        if self._trust is None:
            self._trust = TrustInfo(index_0_100=50, coverage_pct=50.0)
        
        if self._lineage is None:
            self._lineage = LineageInfo()
        
        if self._explain is None:
            raise ValueError("ExplainInfo is required. Use with_explain().")
        
        return ExplainedValue(
            metric_id=self.metric_id,
            value=self._value,
            unit=self._unit,
            display_value=getattr(self, "_display", None),
            period=self._period,
            scope=self._scope,
            semantics=self._semantics,
            trust=self._trust,
            lineage=self._lineage,
            explain=self._explain,
        )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_insufficient_value(
    metric_id: str,
    unit: str,
    reason: str,
    explain: ExplainInfo,
) -> ExplainedValue:
    """
    Create an ExplainedValue for insufficient data.
    
    Use when data is not available to compute a metric.
    """
    return (
        ExplainedValueBuilder(metric_id)
        .with_value(None, unit)
        .with_period_as_of()
        .with_scope(ScopeLevel.FACTORY)
        .with_semantics(
            kind=SemanticKind.UNKNOWN,
            completeness=SemanticCompleteness.INSUFFICIENT,
        )
        .with_trust(
            index=0,
            coverage=0.0,
            blocking_reasons=[reason],
        )
        .with_explain(
            definition=explain.definition,
            formula=explain.formula,
            what_it_means=explain.what_it_means,
            assumptions=explain.assumptions,
            forbidden_claims=explain.forbidden_claims,
            how_to_improve=explain.how_to_improve,
        )
        .build()
    )


def create_blocked_value(
    metric_id: str,
    value: Any,
    unit: str,
    reason: str,
    explain: ExplainInfo,
) -> ExplainedValue:
    """
    Create an ExplainedValue for blocked metrics.
    
    Use when data exists but should not be used for automation.
    """
    return (
        ExplainedValueBuilder(metric_id)
        .with_value(value, unit)
        .with_period_as_of()
        .with_scope(ScopeLevel.FACTORY)
        .with_semantics(
            kind=SemanticKind.THEORETICAL,
            completeness=SemanticCompleteness.PARTIAL,
        )
        .with_trust(
            index=30,
            coverage=50.0,
            blocking_reasons=[reason],
        )
        .with_explain(
            definition=explain.definition,
            formula=explain.formula,
            what_it_means=explain.what_it_means,
            assumptions=explain.assumptions,
            forbidden_claims=explain.forbidden_claims,
            how_to_improve=explain.how_to_improve,
        )
        .build()
    )


