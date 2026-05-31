"""
ProdPlan ONE - Routing Template Models (Sprint P.4 / PL08 / CG07)
==================================================================

Blueprint v2.0 §2.3 reveals that the 899 NELO models collapse onto only 50
*routing patterns*. Templates capture those patterns explicitly so the
scheduler can:

1. Stop inferring the routing from individual order history on every run.
2. Let admins promote a new template + A/B assignment without redeploying.
3. Share durations (p50/p90) and phase ordering across models that share
   a pattern — 219 models share pattern #1 alone.

Schema
------
`RoutingTemplate` — the pattern itself (a named sequence of phases).
`RoutingTemplatePhase` — one row per phase of the template; `seq` gives
  canonical order and `alternative_group_id` lets two siblings form an
  A/B pair (e.g. "Laminagem Standard" vs "Laminagem Infusão").
`ModelRoutingAssignment` — per-model binding. A model can have a
  `primary_template_id` and an optional `alt_template_id`; the chromosome
  variant choice decides which the decoder honours.

No FK to `core.products.id` on `ModelRoutingAssignment.model_id` because
the NELO model identifier is a string business key, not a UUID.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class RoutingTemplate(TenantBase):
    """A named routing pattern. `code` must be unique per tenant."""

    __tablename__ = "routing_template"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_routing_template_code"),
        {"schema": "plan"},
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phase_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Telemetry from the mining job — counts of models that share this pattern.
    model_coverage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RoutingTemplatePhase(TenantBase):
    """One phase inside a `RoutingTemplate`. `seq` is 1-indexed."""

    __tablename__ = "routing_template_phase"
    __table_args__ = (
        Index(
            "ix_routing_template_phase_template_seq",
            "template_id", "seq",
        ),
        {"schema": "plan"},
    )

    template_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plan.routing_template.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    phase_id: Mapped[str] = mapped_column(String(100), nullable=False)
    phase_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Historical medians — the scheduler consumes these directly when no
    # order-specific sample is available.
    duration_p50_h: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True,
    )
    duration_p90_h: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True,
    )
    requires_mold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    team_size_default: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    can_skip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Phases sharing the same alternative_group_id in the same template form
    # an A/B exclusive pair — pick one, skip the other.
    alternative_group_id: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True,
    )
    # Q.116.B — fases em posicao alternativa. `is_flexible=True` significa
    # que esta fase pode aparecer em mais do que uma posicao no routing;
    # `allowed_predecessors` declara quais phase_id strings podem
    # legitimamente precede-la. Valida-se no service + verify_invariants.
    is_flexible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    allowed_predecessors: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String(100)), nullable=True,
    )


class ModelRoutingAssignment(TenantBase):
    """Maps a model business-key to its routing template(s).

    `primary_template_id` is the default "A"; `alt_template_id` is the
    optional "B". Without an alt, variant="B" requests fall back to the
    primary (logged as a warning).
    """

    __tablename__ = "model_routing_assignment"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "model_id",
            name="uq_model_routing_assignment_model",
        ),
        {"schema": "plan"},
    )

    model_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # FASE 6.2 (HIGH-40) — ondelete defaults previously left assignments
    # orphaned when a template was deleted. Now we cascade primary
    # (assignment is meaningless without the primary template it points
    # to) and SET NULL on the alt (the variant just goes away — the
    # assignment still works, falling back to primary).
    primary_template_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plan.routing_template.id", ondelete="CASCADE"),
        nullable=False,
    )
    alt_template_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plan.routing_template.id", ondelete="SET NULL"),
        nullable=True,
    )
