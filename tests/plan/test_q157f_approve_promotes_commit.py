"""Q.157.F.2 — aprovar uma decisão de planeamento promove o commit CPO.

`CommitsService.promote_to_live`: DRAFT→LIVE + audit na mesma sessão (sem
commit próprio); idempotente quando já LIVE; None quando o commit não existe.
É o que liga o "Sim" do /decisoes ao plano real do CPO.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, List
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from src.plan.cpo.commits import CommitsService

TENANT = UUID("11111111-1111-1111-1111-111111111111")


class FakeSession:
    def __init__(self) -> None:
        self.added: List[Any] = []
        self.flushed = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushed += 1
        for obj in self.added:
            if not hasattr(obj, "id") or obj.id is None:
                object.__setattr__(obj, "id", uuid4())


@pytest.mark.asyncio
async def test_promote_to_live_flips_draft_and_audits():
    from src.core.models.audit import AuditLog

    session = FakeSession()
    svc = CommitsService(session, TENANT)
    commit = SimpleNamespace(id=uuid4(), commit_sha256="sha123456", status="DRAFT")
    approver = uuid4()
    with patch.object(svc, "get_by_sha", AsyncMock(return_value=commit)):
        out = await svc.promote_to_live("sha123456", approver_id=approver)

    assert out is commit
    assert commit.status == "LIVE"
    audits = [a for a in session.added if isinstance(a, AuditLog)]
    assert audits, "audit_change na mesma sessão (axioma 7)"
    a = audits[0]
    assert a.new_values.get("status") == "LIVE"
    assert a.old_values.get("status") == "DRAFT"


@pytest.mark.asyncio
async def test_promote_to_live_idempotent_when_already_live():
    from src.core.models.audit import AuditLog

    session = FakeSession()
    svc = CommitsService(session, TENANT)
    commit = SimpleNamespace(id=uuid4(), commit_sha256="sha123456", status="LIVE")
    with patch.object(svc, "get_by_sha", AsyncMock(return_value=commit)):
        out = await svc.promote_to_live("sha123456", approver_id=uuid4())

    assert out is commit
    assert commit.status == "LIVE"
    # já-LIVE → não re-audita
    assert not [a for a in session.added if isinstance(a, AuditLog)]


@pytest.mark.asyncio
async def test_promote_to_live_none_when_commit_missing():
    session = FakeSession()
    svc = CommitsService(session, TENANT)
    with patch.object(svc, "get_by_sha", AsyncMock(return_value=None)), \
         patch.object(svc, "get_by_sha_prefix", AsyncMock(return_value=None)):
        out = await svc.promote_to_live("nope", approver_id=uuid4())
    assert out is None
    assert session.added == []
