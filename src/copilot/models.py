"""
ProdPlan ONE - COPILOT Models
==============================

SQLAlchemy models for copilot module.
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Text, Integer, Date, ForeignKey, Index, JSON, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class CopilotSuggestion(TenantBase):
    """
    Audit log imutável de sugestões do COPILOT.
    
    Guarda prompt, resposta, validações, citations, etc.
    """
    
    __tablename__ = "copilot_suggestion"
    __table_args__ = (
        Index("idx_copilot_suggestion_tenant_created", "tenant_id", "created_at"),
        Index("idx_copilot_suggestion_correlation", "correlation_id"),
        Index("idx_copilot_suggestion_actor", "actor_id"),
    )
    
    correlation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    
    # Prompt
    prompt_rendered: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    
    # LLM Response
    llm_raw_response: Mapped[str] = mapped_column(Text, nullable=False)
    llm_response_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    
    # User Query
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    
    # Validated Response
    response_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    validation_passed: Mapped[bool] = mapped_column(nullable=False, default=False)
    validation_errors: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Citations
    citations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Metadata
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Actor
    actor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)


class CopilotRAGChunk(TenantBase):
    """
    Chunks de documentos para RAG (embeddings).
    """
    
    __tablename__ = "copilot_rag_chunk"
    __table_args__ = (
        Index("idx_copilot_rag_chunk_tenant", "tenant_id"),
        Index("idx_copilot_rag_chunk_source", "source_type", "source_id"),
    )
    
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "sop", "doc", "policy"
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Embedding: PostgreSQL usa VECTOR, SQLite usa TEXT
    # Para compatibilidade, usar TEXT e fazer cast quando necessário
    embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array ou pgvector
    
    # Metadata
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # url, title, etc.


class CopilotDailyFeedback(TenantBase):
    """
    Cache de feedback diário gerado pelo COPILOT.
    """
    
    __tablename__ = "copilot_daily_feedback"
    __table_args__ = (
        Index("idx_copilot_daily_feedback_tenant_date", "tenant_id", "date", unique=True),
    )
    
    date: Mapped[date] = mapped_column(Date, nullable=False)
    feedback_json: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Array de bullets
    generated_at: Mapped[datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)


class CopilotDecisionPR(TenantBase):
    """
    Decision PRs criados pelo COPILOT (sugestões de melhoria).
    """
    
    __tablename__ = "copilot_decision_pr"
    __table_args__ = (
        Index("idx_copilot_decision_pr_suggestion", "suggestion_id"),
        Index("idx_copilot_decision_pr_status", "status"),
    )
    
    suggestion_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("copilot_suggestion.id"),
        nullable=False,
    )
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
    )  # PENDING, APPROVED, REJECTED
    
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


class CopilotConversation(TenantBase):
    """
    Conversas do COPILOT (histórico de chat).
    """
    
    __tablename__ = "copilot_conversation"
    __table_args__ = (
        Index("idx_copilot_conversation_tenant_actor", "tenant_id", "actor_id", "last_message_at"),
        Index("idx_copilot_conversation_tenant_created", "tenant_id", "created_at"),
    )
    
    actor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_archived: Mapped[bool] = mapped_column(nullable=False, default=False)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


class CopilotMessage(TenantBase):
    """
    Mensagens individuais dentro de uma conversa.
    """
    
    __tablename__ = "copilot_message"
    __table_args__ = (
        Index("idx_copilot_message_conversation", "conversation_id", "created_at"),
        Index("idx_copilot_message_correlation", "correlation_id"),
    )
    
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("copilot_conversation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    actor_role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # "user" | "copilot"
    
    content_text: Mapped[str] = mapped_column(Text, nullable=False)  # Texto simples (user) ou summary (copilot)
    content_structured: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # CopilotResponse completo
    
    correlation_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    validation_passed: Mapped[Optional[bool]] = mapped_column(nullable=True)


class CopilotActionLog(TenantBase):
    """
    Audit log for Copilot actions.
    
    Tracks all executed actions with before/after state for rollback capability.
    """
    
    __tablename__ = "copilot_action_logs"
    __table_args__ = (
        Index("idx_copilot_action_logs_tenant", "tenant_id"),
        Index("idx_copilot_action_logs_user", "user_id"),
        Index("idx_copilot_action_logs_plan", "plan_id"),
        Index("idx_copilot_action_logs_status", "status"),
        Index("idx_copilot_action_logs_rollback", "rollback_until", postgresql_where=text("status = 'executed'")),
    )
    
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    plan_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    
    before_state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    after_state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="executed",
    )  # executed, failed, rolled_back
    
    executed_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    rollback_until: Mapped[Optional[datetime]] = mapped_column(nullable=True)  # 24h window for undo


