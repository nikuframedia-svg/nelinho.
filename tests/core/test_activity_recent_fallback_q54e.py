"""Sprint Q.54.E — `/v1/activity/recent` cai para o audit log.

A auditoria: o feed `/v1/activity/recent` devolvia sempre `{items:[]}`
porque lê o `event_outbox`, que em dev está vazio (o dispatcher drena-o
ou nunca houve eventos). O audit log (`core.audit_log`) regista cada
mudança de estado na mesma transacção — é a fonte honesta de "o que a
fábrica fez". O handler passa a cair para o audit log quando o outbox
está vazio.

Estes testes injectam uma sessão fake que devolve linhas SQL
pré-cozinhadas — teste unitário, não tocam DB.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.database import get_session
from src.shared.realtime.activity_api import router as activity_router


class _Result:
    """Mínimo result com `fetchall()` — o handler usa SQL raw via text()."""

    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _SqlFakeSession:
    """Sessão fake que serve respostas em fila para `execute(text(...))`.

    Cada item da fila é uma lista de linhas (tuplos) ou uma Exception a
    levantar (para simular tabela em falta).
    """

    def __init__(self, queue):
        self._queue = list(queue)
        self.rollbacks = 0

    async def execute(self, _stmt, _params=None):
        item = self._queue.pop(0) if self._queue else []
        if isinstance(item, Exception):
            raise item
        return _Result(item)

    async def rollback(self):
        # A failed statement leaves the asyncpg transaction aborted; the
        # handler rolls back before the audit-log fallback so it can run.
        self.rollbacks += 1


def _client(session) -> TestClient:
    async def _override():
        yield session

    app = FastAPI()
    app.include_router(activity_router)
    app.dependency_overrides[get_session] = _override
    return TestClient(app)


_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=timezone.utc)


def test_recent_prefers_outbox_when_it_has_rows():
    # event_outbox row: (id, tenant_id, event_type, payload, created_at)
    outbox_rows = [
        ("ev-1", "t-1", "DECISION_PROPOSED", {"decision_type": "REROUTE"}, _NOW),
    ]
    session = _SqlFakeSession([outbox_rows])
    resp = _client(session).get("/v1/activity/recent")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Decisão proposta"
    # No audit-log fallback consulted — only one execute happened.


def test_recent_falls_back_to_audit_log_when_outbox_empty():
    # First execute → empty outbox; second → audit_log rows.
    audit_rows = [
        # (id, entity_type, entity_id, action, reason, actor_role, created_at)
        ("a-1", "production_order", "po-1", "INSERT", "OF criada", "planner", _NOW),
        ("a-2", "rework_entry", "rw-1", "UPDATE", None, "qa", _NOW),
    ]
    session = _SqlFakeSession([[], audit_rows])
    resp = _client(session).get("/v1/activity/recent")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    assert items[0]["title"] == "Production order criado"
    assert items[0]["type"] == "scenario"
    assert items[0]["status"] == "success"
    assert items[0]["metadata"]["source"] == "audit_log"
    # UPDATE with no reason → description omitted, status None.
    assert items[1]["title"] == "Rework entry actualizado"
    assert items[1]["type"] == "quality"


def test_recent_empty_when_outbox_and_audit_both_empty():
    session = _SqlFakeSession([[], []])
    resp = _client(session).get("/v1/activity/recent")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_recent_falls_back_when_outbox_table_missing():
    """Outbox table absent (UndefinedTable) → still tries the audit log."""
    from sqlalchemy.exc import ProgrammingError

    audit_rows = [
        ("a-9", "decision", "d-9", "INSERT", "Aprovada", "admin", _NOW),
    ]
    missing = ProgrammingError("UndefinedTable", None, Exception("no table"))
    session = _SqlFakeSession([missing, audit_rows])
    resp = _client(session).get("/v1/activity/recent")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["type"] == "user"
    # The aborted transaction must be rolled back before the audit-log
    # query — otherwise it raises InFailedSQLTransactionError.
    assert session.rollbacks == 1
