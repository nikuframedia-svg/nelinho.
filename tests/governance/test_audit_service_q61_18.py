"""Q.61.18 — pipeline unificado de auditoria.

`src/governance/audit_service.audit_change` e a UNICA forma de criar
uma `AuditLog` row em todo o backend. Estes testes pinam:

  * Forma da row (campos populados como esperado).
  * Side-effect: `session.add(audit)` foi chamado, sem commit.
  * trace_id (Q.61.12) auto-injectado no `reason` quando ContextVar
    tem valor.
  * Ausencia de trace_id deixa reason intacto.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from src.core.models.audit import AuditLog
from src.governance.audit_service import audit_change
from src.shared.observability import set_trace_id, reset_trace_id


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ACTOR = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ENTITY = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


class _CapturingSession:
    """AsyncSession stand-in que captura `session.add`."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_audit_change_creates_row_with_expected_fields():
    session = _CapturingSession()
    row = await audit_change(
        session,
        tenant_id=TENANT,
        entity_type="decision_run",
        entity_id=ENTITY,
        action="INSERT",
        new_values={"status": "PROPOSED"},
        actor_id=ACTOR,
        reason="propose",
    )
    assert isinstance(row, AuditLog)
    assert row.tenant_id == TENANT
    assert row.entity_type == "decision_run"
    assert row.entity_id == ENTITY
    assert row.action == "INSERT"
    assert row.new_values == {"status": "PROPOSED"}
    assert row.old_values is None
    assert row.actor_id == ACTOR
    # Sem trace_id no contexto -> reason intacto.
    assert row.reason == "propose"

    # Side-effect: adicionada a session, mas sem commit (caller controla).
    assert session.added == [row]
    assert session.commits == 0


@pytest.mark.asyncio
async def test_audit_change_prefixes_reason_with_trace_id():
    """Q.61.18 + Q.61.12: trace_id automatica no reason ate Q.61.18.1
    adicionar coluna dedicada."""
    session = _CapturingSession()
    token = set_trace_id("test-trace-abc")
    try:
        row = await audit_change(
            session,
            tenant_id=TENANT,
            entity_type="decision_run",
            entity_id=ENTITY,
            action="UPDATE",
            old_values={"status": "PROPOSED"},
            new_values={"status": "APPROVED"},
            actor_id=ACTOR,
            reason="approve",
        )
    finally:
        reset_trace_id(token)

    assert row.reason == "[trace_id=test-trace-abc] approve"
    assert row.action == "UPDATE"
    assert row.old_values == {"status": "PROPOSED"}


@pytest.mark.asyncio
async def test_audit_change_accepts_none_reason():
    """`reason=None` continua a funcionar — com ou sem trace_id."""
    session = _CapturingSession()

    # Sem trace_id.
    row = await audit_change(
        session,
        tenant_id=TENANT,
        entity_type="schedule_commit",
        entity_id=ENTITY,
        action="DELETE",
        old_values={"sha": "abc"},
    )
    assert row.reason is None

    # Com trace_id no contexto.
    token = set_trace_id("xyz")
    try:
        row2 = await audit_change(
            session,
            tenant_id=TENANT,
            entity_type="schedule_commit",
            entity_id=ENTITY,
            action="DELETE",
        )
    finally:
        reset_trace_id(token)
    assert row2.reason == "[trace_id=xyz]"


@pytest.mark.asyncio
async def test_audit_change_does_not_commit():
    """Contrato: audit_change NUNCA chama commit — caller controla a tx
    (preserva invariante 7 sobre audit na mesma tx que a mudanca)."""
    session = _CapturingSession()
    await audit_change(
        session,
        tenant_id=TENANT,
        entity_type="x",
        entity_id=ENTITY,
        action="INSERT",
    )
    assert session.commits == 0
