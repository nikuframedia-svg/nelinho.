"""Sprint S7 — guard tests for mock-data-out and audit-trail-in.

Two angles:
1. The sandbox baseline state no longer carries the discovery dataset
   numbers (1523, 55.5, 89836) as if they were real.
2. ``MasterDataService.create_product / update_product / delete_product``
   write rows to ``core.audit_log``.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest


REPO = Path(__file__).resolve().parents[2]


# --- Π8: sandbox baseline mock numbers stripped -----------------------------

def test_sandbox_baseline_no_longer_hardcodes_discovery_numbers():
    text = (REPO / "src" / "sandbox" / "api.py").read_text(encoding="utf-8")
    # The numbers came from Folha_IA_extra.xlsx and must not appear as
    # ``value=...`` inside ``create_baseline_state``.
    func_marker = "def create_baseline_state"
    end_marker = "# ===="  # the next section banner
    start = text.index(func_marker)
    end = text.index(end_marker, start)
    body = text[start:end]
    for literal in ("value=1523", "value=55.5", "value=89836"):
        assert literal not in body, (
            f"create_baseline_state still hardcodes {literal!r} — these "
            f"are discovery sample values, not real factory state."
        )


def test_sandbox_baseline_marks_metrics_blocked():
    """All baseline metrics must default to BLOCKED so callers know they
    have to provide an explicit initial_state."""
    text = (REPO / "src" / "sandbox" / "api.py").read_text(encoding="utf-8")
    func_marker = "def create_baseline_state"
    end_marker = "# ===="
    start = text.index(func_marker)
    end = text.index(end_marker, start)
    body = text[start:end]
    assert body.count('status="BLOCKED"') >= 6  # 6 metrics, all blocked
    assert 'status="OK"' not in body


# --- Π11: audit log on product CRUD ------------------------------------------

@pytest.mark.asyncio
async def test_create_product_writes_audit_row():
    from src.core.models.audit import AuditLog
    from src.core.services.master_data_service import MasterDataService

    actor = uuid4()
    tenant = uuid4()

    session = AsyncMock()
    session.add = AsyncMock(side_effect=lambda obj: None)
    # session.add is sync in real SQLAlchemy — re-spec to sync here.
    session.add = lambda obj: session._added.append(obj)
    session._added = []
    session.flush = AsyncMock()

    svc = MasterDataService(session=session, tenant_id=tenant, actor_id=actor)

    # The flush would normally populate Product.id; simulate via a side effect
    # that injects a UUID right before _audit reads it.
    async def _flush_assigns_id():
        for obj in session._added:
            if not getattr(obj, "id", None):
                obj.id = uuid4()
    session.flush = _flush_assigns_id

    product = await svc.create_product(
        product_code="P-001", product_name="Test Product",
    )

    assert product.id is not None
    audit_rows = [o for o in session._added if isinstance(o, AuditLog)]
    assert len(audit_rows) == 1
    a = audit_rows[0]
    assert a.action == "CREATE"
    assert a.entity_type == "product"
    assert a.actor_id == actor
    assert a.tenant_id == tenant
    assert a.new_values is not None
    assert a.new_values["product_code"] == "P-001"


@pytest.mark.asyncio
async def test_delete_product_writes_audit_row():
    from src.core.models.audit import AuditLog
    from src.core.models.product import Product, ProductStatus, ProductType
    from src.core.services.master_data_service import MasterDataService

    actor = uuid4()
    tenant = uuid4()
    product_id = uuid4()
    existing = Product(
        id=product_id,
        tenant_id=tenant,
        product_code="P-OLD",
        product_name="Old",
        product_type=ProductType.FINISHED_GOOD,
        status=ProductStatus.ACTIVE,
    )

    class _FakeResult:
        def scalar_one_or_none(self):
            return existing

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_FakeResult())
    session._added = []
    session.add = lambda obj: session._added.append(obj)
    session.flush = AsyncMock()
    session.delete = AsyncMock()

    svc = MasterDataService(session=session, tenant_id=tenant, actor_id=actor)
    deleted = await svc.delete_product(product_id)

    assert deleted is True
    audit_rows = [o for o in session._added if isinstance(o, AuditLog)]
    assert len(audit_rows) == 1
    a = audit_rows[0]
    assert a.action == "DELETE"
    assert a.entity_id == product_id
    assert a.old_values is not None
    assert a.old_values["product_code"] == "P-OLD"
    assert a.new_values is None
