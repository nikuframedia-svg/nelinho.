"""
ProdPlan ONE - COPILOT Schemas
===============================

Pydantic schemas for request/response validation.
"""

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================

class CopilotAskRequest(BaseModel):
    """Request para fazer pergunta ao COPILOT."""

    user_query: str = Field(..., min_length=1, max_length=2000)
    entity_type: Optional[str] = Field(None, max_length=50)
    entity_id: Optional[UUID] = None
    conversation_id: Optional[UUID] = Field(None, description="Conversation ID for multi-turn context")
    context_window_hours: int = Field(default=24, ge=1, le=168)
    include_citations: bool = Field(default=True)
    idempotency_key: Optional[str] = Field(None, max_length=100)


class CopilotActionRequest(BaseModel):
    """Request para executar ação permitida."""
    
    action_type: Literal["CREATE_DECISION_PR", "DRY_RUN", "OPEN_ENTITY", "RUN_RUNBOOK"]
    suggestion_id: UUID
    payload: Dict[str, Any] = Field(default_factory=dict)


class SandboxRequest(BaseModel):
    """Request para executar ação em sandbox."""
    
    action_type: str = Field(..., min_length=1, max_length=50)  # "INCREASE_SS", "ADJUST_PRICE", etc.
    target: str = Field(..., min_length=1, max_length=255)  # SKU ID, product ID, etc.
    params: Dict[str, Any] = Field(default_factory=dict)
    capture_state: Optional[List[str]] = Field(default=None)  # ["inventory", "kpis", "schedules"]


class SandboxResponse(BaseModel):
    """Response do sandbox execution."""
    
    success: bool
    before_state: Dict[str, Any]
    after_state: Dict[str, Any]
    deltas: Dict[str, Any]
    actual_impact: Dict[str, Any]
    message: str


# ============================================================================
# RESPONSE SCHEMAS (JSON estruturado obrigatório)
# ============================================================================

class Citation(BaseModel):
    """Citação obrigatória para cada facto."""
    
    source_type: Literal["db", "rag", "event", "calculation", "recommendation", "system_data"]
    ref: str = Field(..., max_length=500)  # ex: "table:orders;query_hash:abc123;chunk_id:xyz"
    label: str = Field(..., max_length=200)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    trust_index: float = Field(0.0, ge=0.0, le=1.0)


class Fact(BaseModel):
    """Facto factual com citations obrigatórias."""
    
    text: str = Field(..., min_length=1)
    citations: List[Citation] = Field(..., min_items=1)  # OBRIGATÓRIO (exceto INSUFFICIENT_EVIDENCE)


class Action(BaseModel):
    """Ação proposta pelo COPILOT."""
    
    action_type: Literal["CREATE_DECISION_PR", "DRY_RUN", "OPEN_ENTITY", "RUN_RUNBOOK"]
    label: str = Field(..., min_length=1, max_length=200)
    requires_approval: bool = Field(default=False)
    payload: Dict[str, Any] = Field(default_factory=dict)


class Warning(BaseModel):
    """Aviso ou limitação."""
    
    code: Literal["INSUFFICIENT_EVIDENCE", "SECURITY_FLAG", "LOW_TRUST_INDEX", "MODEL_OFFLINE", "VALIDATION_FAILED", "EXPLANATION_TOO_SHALLOW", "EXPLANATION_MISSING_CAUSAL_LINK", "EXPLANATION_FALSE_CAUSALITY"]
    message: str = Field(..., min_length=1)


class CopilotResponse(BaseModel):
    """
    Resposta estruturada do COPILOT.
    
    REGRA CRÍTICA: facts[] NÃO pode estar vazio quando type=ANSWER/PROPOSAL
    (exceto se warnings incluir INSUFFICIENT_EVIDENCE).
    """
    
    suggestion_id: UUID
    correlation_id: UUID
    type: Literal["ANSWER", "RUNBOOK_RESULT", "PROPOSAL", "ERROR"]
    intent: Literal["explain_oee", "explain_plan_change", "quality_summary", "data_integrity", "generic"]
    summary: str = Field(..., min_length=1, max_length=500)
    facts: List[Fact] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)
    warnings: List[Warning] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)  # model, tokens, latency_ms, validation_passed
    
    def model_post_init(self, __context: Any) -> None:
        """Validação customizada: facts não pode estar vazio (exceto INSUFFICIENT_EVIDENCE)."""
        has_insufficient_evidence = any(
            w.code == "INSUFFICIENT_EVIDENCE" for w in self.warnings
        )
        
        if self.type in ("ANSWER", "PROPOSAL") and not self.facts and not has_insufficient_evidence:
            raise ValueError(
                "facts[] não pode estar vazio quando type=ANSWER/PROPOSAL "
                "(exceto se warnings incluir INSUFFICIENT_EVIDENCE)"
            )


class DailyFeedbackBullet(BaseModel):
    """Bullet individual do feedback diário."""
    
    severity: Literal["INFO", "WARN", "CRITICAL"]
    title: str = Field(..., min_length=1, max_length=200)
    text: str = Field(..., min_length=1)
    citations: List[Citation] = Field(default_factory=list)
    suggested_runbooks: List[str] = Field(default_factory=list)
    suggested_actions: List[Action] = Field(default_factory=list)


class DailyFeedbackResponse(BaseModel):
    """Resposta do feedback diário."""
    
    date: str  # YYYY-MM-DD
    bullets: List[DailyFeedbackBullet] = Field(..., min_items=3, max_items=7)
    generated_at: str  # ISO datetime
    last_updated: str  # ISO datetime
