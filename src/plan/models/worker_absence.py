"""Q.174.F4 — WorkerAbsence: override local de ausências de operadores.

A fonte primária de ausências é o ERP (``factory_raw.ent_mov`` com
``ENT_MOV_TIPO.MET_MET_ID=2`` — faltas/baixas/férias, MET 4-10), lida
DIRETAMENTE pelo loader do CPO (sem duplicar o espelho). Esta tabela cobre
os dois casos que o ERP não cobre na hora:

* ``mode='add'`` — ausência que ainda não está no ERP (ex.: "o João ligou
  doente hoje de manhã") → o CPO exclui o operador no intervalo.
* ``mode='ignore_erp'`` — anular uma ausência ERRADA do ERP
  (``erp_movent_id`` aponta o MOVENT_ID a ignorar).

PK própria (uuid); ``employee_code`` = E_ID::text (o mesmo espaço de ids do
skill_matrix). Datas em DATE (dia inteiro — granularidade do ERP, que regista
ausências como janelas 08:00→17:00 por dia).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class WorkerAbsence(Base):
    """Ausência local (add) ou anulação de ausência ERP (ignore_erp)."""

    __tablename__ = "worker_absence"
    __table_args__ = ({"schema": "plan"},)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    employee_code: Mapped[str] = mapped_column(String(40), nullable=False)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    #: tipo livre (ex. 'doença', 'férias', 'formação') — informativo.
    kind: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    #: 'add' (default) | 'ignore_erp'
    mode: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="add"
    )
    #: MOVENT_ID do ent_mov a anular (só mode='ignore_erp').
    erp_movent_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
