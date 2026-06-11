"""Q.168 F4.E — ``.limit(1)`` sem ORDER BY era não-determinístico.

Dois sítios auditados:

* ``DecisionQuery._fetch_decision_by_audit_hash`` — ``audit_hash`` não tem
  UNIQUE constraint; com duplicados (corrupção) o ``_verify_hash_chain``
  podia seguir linhas diferentes em execuções diferentes.
* ``DecisionRollbacker.is_kill_switch_active`` — com 2+ scopes ativos
  ("all" + "decision_type:X") a auditoria de QUAL kill switch bloqueou
  variava entre execuções.

Os testes compilam o statement capturado e exigem ``ORDER BY``.
"""
from __future__ import annotations

from typing import Any

import pytest

from src.governance.decision_query import DecisionQuery
from src.governance.decision_rollbacker import DecisionRollbacker
from tests.conftest import FakeSession, TEST_TENANT_ID


class _CapturingSession(FakeSession):
    """FakeSession canónica que guarda o último statement executado."""

    def __init__(self) -> None:
        super().__init__()
        self.last_stmt: Any = None

    async def execute(self, stmt: Any, *args: Any, **kwargs: Any):
        self.last_stmt = stmt
        return await super().execute(stmt, *args, **kwargs)


@pytest.mark.asyncio
async def test_fetch_by_audit_hash_orders_deterministically_q168_f4e():
    session = _CapturingSession()
    session.queue_scalar(None)
    query = DecisionQuery(session, TEST_TENANT_ID)

    await query._fetch_decision_by_audit_hash("a" * 64)

    sql = str(session.last_stmt)
    assert "ORDER BY" in sql, (
        "limit(1) sem ORDER BY é não-determinístico com audit_hash duplicado"
    )
    assert "LIMIT" in sql


@pytest.mark.asyncio
async def test_is_kill_switch_active_orders_by_activated_at_q168_f4e():
    session = _CapturingSession()
    session.queue_scalar(None)
    rollbacker = DecisionRollbacker(session, TEST_TENANT_ID)

    await rollbacker.is_kill_switch_active(decision_type="adjust_schedule")

    sql = str(session.last_stmt)
    assert "ORDER BY" in sql, (
        "com 2+ scopes ativos a escolha do kill switch tem de ser determinística"
    )
    assert "activated_at" in sql
