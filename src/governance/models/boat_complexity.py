"""Q.155.A — BoatComplexity: índice de complexidade por barco (modelo/produto).

ICB (Índice de Complexidade do Barco) ∈ [0,1] por `product_id` (= `PRODUTO.P_ID`,
o mesmo `OF_P_ID`/`op.model_id` que o CPO usa). Combina 3 sinais reais do ERP,
complementares (validados: BOM×tinta ρ≈0.04):

  1. peças    — nº de componentes na BOM (`produto_componente`)
  2. tinta    — kg de tinta/resina/gelcoat consumida por OF (`movimento`)
  3. processo — nº médio de fases distintas por OF (`of_fp`)

`complexity_score = 0.40·pctile(peças) + 0.30·pctile(tinta) + 0.30·pctile(processo)`
(barcos prepreg: tinta≈0 estrutural → peso da tinta redistribuído p/ peças+fases).

Alimenta o `_pick_workers` do CPO (barco complexo puxa os melhores operadores) e
a UI (badge de complexidade). PK composta (tenant_id, product_id). RLS por tenant.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    Integer,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class BoatComplexity(Base):
    """Índice de complexidade [0,1] de um produto-barco para o planeamento."""

    __tablename__ = "boat_complexity"
    __table_args__ = (
        CheckConstraint(
            "complexity_score BETWEEN 0 AND 1",
            name="ck_boat_complexity_score",
        ),
        PrimaryKeyConstraint(
            "tenant_id", "product_id",
            name="pk_boat_complexity",
        ),
        {"schema": "governance"},
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    # product_id = PRODUTO.P_ID (string p/ compatibilidade com códigos ERP);
    # é o MESMO identificador que `op.model_id`/`OF_P_ID` no CPO.
    product_id: Mapped[str] = mapped_column(String(80), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    # Índice combinado [0,1] (UI mostra ×100).
    complexity_score: Mapped[float] = mapped_column(Float(), nullable=False)
    rank: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    # Sinais brutos (drill-down).
    n_components: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    paint_kg_per_of: Mapped[float] = mapped_column(Float(), nullable=False, server_default="0")
    n_distinct_phases: Mapped[float] = mapped_column(Float(), nullable=False, server_default="0")
    # nº de OFs no histórico-janela (confiança: <5 = sinais ruidosos).
    n_ofs: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    last_computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
