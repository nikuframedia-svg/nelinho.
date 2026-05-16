"""Q.20.A — ETL audit model.

Every ERP→Postgres sync writes one ``core.etl_run`` row: which source,
when, how many rows in/out, and the outcome. Satisfies the project
invariant *"audit trail intact"* — "why does the system have this data"
has an answer without ``git blame``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class EtlRun(TenantBase):
    """One ERP→Postgres sync execution.

    ``source`` is the mirror name (``master_data``, ``molds``, ``skills``,
    ``quality``, ``time_mining``). ``status`` is ``running`` while in
    flight, then ``ok`` or ``error``. Counts let an operator see at a
    glance whether a nightly sync actually moved data.
    """

    __tablename__ = "etl_run"
    __table_args__ = {"schema": "core"}

    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="running",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    rows_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<EtlRun {self.source} {self.status} "
            f"read={self.rows_read} ins={self.rows_inserted} "
            f"upd={self.rows_updated}>"
        )
