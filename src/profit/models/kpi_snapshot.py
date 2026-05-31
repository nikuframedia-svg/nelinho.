"""
ProdPlan ONE — KPI snapshot history (Q.117.D)
=============================================

A página LLM › KPIs mostra o valor actual de cada KPI (FPY, retrabalho,
ordens) calculado live em ``src/profit/api/kpis.py``. Faltava a série
histórica para o gráfico de tendência.

Esta tabela guarda **um ponto por (tenant, kpi, dia)** — escrito uma vez
por dia pelo job ``_kpi_snapshot_job`` (00:45 UTC, depois do
daily_feedback). O endpoint ``GET /v1/profit/kpis/{name}/history`` lê
daqui. ``value`` é nullable: quando o KPI não tem dados nesse dia
(``reason="NO_SOURCE_DATA"``) gravamos NULL em vez de inventar um zero —
o gráfico salta o ponto, nunca mente.

Idempotente: a chave única (tenant_id, kpi_name, captured_date) permite
re-correr o job no mesmo dia (upsert) sem duplicar pontos.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Date, Float, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class KpiSnapshot(TenantBase):
    """Um ponto histórico (tenant, kpi_name, dia) → valor."""

    __tablename__ = "kpi_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "kpi_name", "captured_date",
            name="uq_kpi_snapshot_tenant_kpi_date",
        ),
        Index(
            "ix_kpi_snapshot_tenant_kpi_date",
            "tenant_id", "kpi_name", "captured_date",
        ),
        {"schema": "profit"},
    )

    kpi_name: Mapped[str] = mapped_column(String(40), nullable=False)
    captured_date: Mapped[date] = mapped_column(Date, nullable=False)
    # NULL = sem dados nesse dia (NO_SOURCE_DATA). Nunca gravar 0 falso.
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(8), nullable=False, default="")
