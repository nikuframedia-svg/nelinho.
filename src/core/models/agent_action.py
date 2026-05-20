"""Q.66.E.3 — AgentAction observability model.

Cada chamada do copiloto (intent, model, latency, outcome, escalated)
fica registada aqui. Permite Honeycomb-style queries: "todos os agent
actions com outcome=error nas ultimas 24h", "latency P95 por intent",
"que % escalou para DecisionRun?".

Tenant-scoped (RLS aplicado em 060_q66_e_agent_actions). Pareado com
trace_id da middleware Q.61.12 para juntar com audit_log (Q.66.B.1).

Esta fase (Q.66.E.3) cria APENAS o schema + endpoint de leitura. A
populacao (call-site no copilot service) e trabalho de uma fase futura
do plano trust-index-v1 — touched-file pays para quem mexer em
src/copilot/service.py.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class AgentAction(Base):
    """Observability row para cada chamada do copiloto.

    Tabela tenant-scoped (RLS via tenant_isolation policy aplicada na
    migration 060_q66_e_agent_actions). Indices em tenant_id, intent,
    trace_id, created_at para suportar filtros do endpoint.
    """

    __tablename__ = "agent_actions"
    __table_args__ = ({"schema": "core"},)

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Tenant + user
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )

    # Intent + model
    intent: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    model: Mapped[Optional[str]] = mapped_column(
        String(80),
        nullable=True,
    )

    # Outcome
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # success | error | timeout | skipped
    escalated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    decision_run_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )  # FK soft para shared.decision_runs

    # Correlation
    trace_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AgentAction {self.intent} outcome={self.outcome} "
            f"latency_ms={self.latency_ms} escalated={self.escalated}>"
        )
