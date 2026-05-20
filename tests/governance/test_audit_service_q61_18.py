"""Q.61.18 + Q.66.B.1 — pipeline unificado de auditoria.

`src/governance/audit_service.audit_change` e a UNICA forma de criar
uma `AuditLog` row em todo o backend. Estes testes pinam:

  * Forma da row (campos populados como esperado).
  * Side-effect: `session.add(audit)` foi chamado, sem commit.
  * trace_id (Q.61.12) auto-populado na COLUNA `trace_id` (Q.66.B.1) —
    antes era hackado no `reason`.
  * Ausencia de trace_id deixa coluna `trace_id` a None e reason intacto.
  * `reason` nunca mais leva o prefixo `[trace_id=...]`.
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
    # Sem trace_id no contexto -> reason intacto, coluna trace_id a None.
    assert row.reason == "propose"
    assert row.trace_id is None

    # Side-effect: adicionada a session, mas sem commit (caller controla).
    assert session.added == [row]
    assert session.commits == 0


@pytest.mark.asyncio
async def test_audit_change_writes_trace_id_to_dedicated_column():
    """Q.66.B.1: trace_id vai para a COLUNA `trace_id`, nao para o
    `reason`. Antes (Q.61.18) era prefixado como `[trace_id=...]`."""
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

    # Q.66.B.1: trace_id na coluna dedicada.
    assert row.trace_id == "test-trace-abc"
    # `reason` fica LIMPO — sem prefixo.
    assert row.reason == "approve"
    assert "trace_id" not in (row.reason or "")
    assert row.action == "UPDATE"
    assert row.old_values == {"status": "PROPOSED"}


@pytest.mark.asyncio
async def test_audit_change_accepts_none_reason():
    """`reason=None` continua a funcionar — com ou sem trace_id.

    Q.66.B.1: trace_id e independente do reason — pode haver trace_id
    sem reason e vice-versa.
    """
    session = _CapturingSession()

    # Sem trace_id, sem reason.
    row = await audit_change(
        session,
        tenant_id=TENANT,
        entity_type="schedule_commit",
        entity_id=ENTITY,
        action="DELETE",
        old_values={"sha": "abc"},
    )
    assert row.reason is None
    assert row.trace_id is None

    # Com trace_id no contexto, sem reason: trace_id vai para a coluna,
    # reason fica None.
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
    assert row2.reason is None
    assert row2.trace_id == "xyz"


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
