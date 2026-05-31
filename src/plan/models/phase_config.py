"""Q.135.F3.1 — PhaseConfig: overrides de operadores/team_size/estações por fase.

Config cross-model: uma linha por (tenant_id, phase_id).
Duração NÃO é override — vem sempre do histórico real (invariante Spelke).

O CPO respeita estes overrides em:
  * workers_for(fase_id)      → intersecta com allowed_worker_ids se definido
  * team_size_for(fase_id, …) → usa team_size_override se definido (≥ mínimo da fase)
  * phase_stations[fase_id]   → usa num_stations_override se definido (≥ 1)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class PhaseConfig(TenantBase):
    """Override de configuração de fase para o CPO.

    Campos NULL = sem override (CPO usa o baseline derivado do ERP).
    """

    __tablename__ = "phase_config"
    __table_args__ = (
        UniqueConstraint("tenant_id", "phase_id", name="uq_phase_config_tenant_phase"),
        Index("ix_phase_config_tenant", "tenant_id"),
        {"schema": "plan"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    phase_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="FP_ID da fase (chave de negócio ERP)",
    )
    team_size_override: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Nº de operadores por op (NULL = usar baseline da fase)",
    )
    num_stations_override: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Nº de estações paralelas (NULL = usar p95 do histórico)",
    )
    allowed_worker_ids: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        comment=(
            "Whitelist de funcionario_id autorizados (NULL = skill_matrix completo). "
            "Tem de ser subconjunto de skill_matrix[phase_id] — validado no upsert."
        ),
    )
    note: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Nota livre (motivo do override)",
    )
    updated_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="UUID do user que fez o último upsert",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
