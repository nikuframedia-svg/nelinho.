"""Q.20.A — ETL runner: idempotent upsert + audit-row lifecycle.

:class:`EtlRunner` is the single helper every mirror module uses. It

* opens a ``core.etl_run`` audit row on enter, closes it on exit;
* exposes :meth:`upsert` — an idempotent, business-key-keyed write that
  inserts new rows and updates changed ones, **never duplicating**.

The upsert is done Python-side (load-existing-by-key, then insert/update)
rather than ``INSERT ... ON CONFLICT`` because the operational tables
(``core.products`` etc.) carry no DB-level unique constraint on every
business key the mirrors use. Volumes are small (master data <15 k;
quality imported in windows) so one indexed lookup per batch is cheap
and avoids touching existing table DDL.

Usage::

    async with EtlRunner(session, tenant_id, source="master") as run:
        rows = await list_products()
        run.count_read(len(rows))
        await run.upsert(Product, mapped_rows, key_fields=["product_code"])
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.etl_run import EtlRun

logger = logging.getLogger(__name__)

_CHUNK = 1000  # IN-clause chunk size for the existing-row lookup


class EtlRunResult:
    """Mutable tally for one mirror run — mirrors the ``EtlRun`` columns."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.rows_read = 0
        self.rows_inserted = 0
        self.rows_updated = 0
        self.rows_skipped = 0
        self.status = "running"
        self.error: Optional[str] = None

    def __repr__(self) -> str:
        return (
            f"<EtlRunResult {self.source} {self.status} "
            f"read={self.rows_read} ins={self.rows_inserted} "
            f"upd={self.rows_updated} skip={self.rows_skipped}>"
        )


class EtlRunner:
    """Async context manager wrapping one ERP→Postgres mirror execution.

    The caller does the fetching + row mapping; the runner owns the
    idempotent write and the audit trail. Exceptions are recorded on the
    ``EtlRun`` row (``status='error'``) and then re-raised — the caller
    (sync script / scheduler job) decides whether one failed mirror
    should abort the rest.
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        source: str,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.result = EtlRunResult(source)
        self._run: Optional[EtlRun] = None

    async def __aenter__(self) -> "EtlRunner":
        self._run = EtlRun(
            tenant_id=self.tenant_id,
            source=self.result.source,
            status="running",
            started_at=datetime.utcnow(),
        )
        self.session.add(self._run)
        await self.session.flush()
        logger.info(
            "etl_run start source=%s tenant=%s", self.result.source, self.tenant_id,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if exc is not None:
            self.result.status = "error"
            self.result.error = f"{exc_type.__name__}: {exc}"
        else:
            self.result.status = "ok"
        if self._run is not None:
            self._run.status = self.result.status
            self._run.finished_at = datetime.utcnow()
            self._run.rows_read = self.result.rows_read
            self._run.rows_inserted = self.result.rows_inserted
            self._run.rows_updated = self.result.rows_updated
            self._run.rows_skipped = self.result.rows_skipped
            self._run.error = self.result.error
            await self.session.flush()
        logger.info(
            "etl_run end source=%s status=%s read=%d ins=%d upd=%d skip=%d",
            self.result.source, self.result.status, self.result.rows_read,
            self.result.rows_inserted, self.result.rows_updated,
            self.result.rows_skipped,
        )
        return False  # never suppress — caller handles

    # ─── Tallies ─────────────────────────────────────────────────────

    def count_read(self, n: int) -> None:
        self.result.rows_read += int(n)

    def count_skipped(self, n: int) -> None:
        self.result.rows_skipped += int(n)

    # ─── Idempotent upsert ───────────────────────────────────────────

    async def upsert(
        self,
        model_class: Type[Any],
        rows: Sequence[Dict[str, Any]],
        *,
        key_fields: Sequence[str],
        update_fields: Optional[Sequence[str]] = None,
        insert_only_fields: Optional[Sequence[str]] = None,
    ) -> Tuple[int, int]:
        """Insert new rows / update changed rows for ``model_class``.

        ``rows`` are dicts of ORM-column → value (``tenant_id`` is set by
        the runner, never by the caller). ``key_fields`` is the business
        key; a row matching an existing ``(tenant_id, *key)`` is updated,
        otherwise inserted. ``update_fields`` defaults to every non-key
        field present in ``rows``.

        ``insert_only_fields`` are applied **only when inserting** a new
        row, never on update — for columns the mirror must seed (e.g. a
        NOT NULL column) but must not overwrite once another source has
        enriched the existing row.

        Returns ``(inserted, updated)`` and adds the same to the run
        tally. Re-running with identical data yields ``(0, 0)``.
        """
        key_fields = list(key_fields)
        if not key_fields:
            raise ValueError("upsert needs at least one key field")
        if not rows:
            return (0, 0)

        insert_only = list(insert_only_fields or [])
        all_fields = {f for row in rows for f in row}
        if update_fields is None:
            update_fields = sorted(all_fields - set(key_fields) - set(insert_only))
        else:
            update_fields = list(update_fields)

        existing = await self._load_existing(model_class, rows, key_fields)

        inserted = 0
        updated = 0
        for row in rows:
            key = tuple(row[f] for f in key_fields)
            obj = existing.get(key)
            if obj is None:
                obj = model_class(tenant_id=self.tenant_id)
                for f in key_fields:
                    setattr(obj, f, row[f])
                for f in (*update_fields, *insert_only):
                    if f in row:
                        setattr(obj, f, row[f])
                self.session.add(obj)
                existing[key] = obj
                inserted += 1
            else:
                changed = False
                for f in update_fields:
                    if f in row and getattr(obj, f) != row[f]:
                        setattr(obj, f, row[f])
                        changed = True
                if changed:
                    updated += 1
        await self.session.flush()

        self.result.rows_inserted += inserted
        self.result.rows_updated += updated
        return (inserted, updated)

    async def _load_existing(
        self,
        model_class: Type[Any],
        rows: Sequence[Dict[str, Any]],
        key_fields: List[str],
    ) -> Dict[Tuple[Any, ...], Any]:
        """Load rows already in the table whose business key matches the
        incoming batch, indexed by key tuple. Scoped to ``tenant_id`` and
        to the incoming keys so we never load the whole table.
        """
        keys = sorted({tuple(row[f] for f in key_fields) for row in rows}, key=str)
        cols = [getattr(model_class, f) for f in key_fields]
        out: Dict[Tuple[Any, ...], Any] = {}
        for start in range(0, len(keys), _CHUNK):
            chunk = keys[start:start + _CHUNK]
            stmt = select(model_class).where(
                model_class.tenant_id == self.tenant_id
            )
            if len(key_fields) == 1:
                stmt = stmt.where(cols[0].in_([k[0] for k in chunk]))
            else:
                stmt = stmt.where(tuple_(*cols).in_(chunk))
            for obj in (await self.session.execute(stmt)).scalars():
                out[tuple(getattr(obj, f) for f in key_fields)] = obj
        return out
