"""Sprint Q.22.F — SMTP delivery + `POST /v1/reports/email`.

Before Q.22.F the endpoint logged + echoed ``status="stubbed"``. Now it
generates the report, persists a ``reports.report_run`` and delivers it
via :func:`send_report_email`.

Covers ``send_report_email`` in its three modes (disabled / sent /
failed) and the endpoint outcome (``generated`` when SMTP is off,
``delivered`` when it sent, 502 + ``failed`` run on SMTP error).
``smtplib.SMTP`` is never really contacted — it is patched.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.reports.email as email_mod
from src.reports.api import router as reports_router
from src.reports.email import EmailDeliveryError, send_report_email
from src.shared.config import settings
from src.shared.database import get_session
from tests.reports.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _build_app(session):
    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(reports_router)
    app.dependency_overrides[get_session] = _fake_session
    return app


def _headers():
    return {"X-Tenant-Id": str(TENANT)}


class _FakeSMTP:
    """Context-manager stand-in for ``smtplib.SMTP``."""

    instances: list = []

    def __init__(self, *args, **kwargs):
        self.sent: list = []
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, message):
        self.sent.append(message)


class _FailingSMTP(_FakeSMTP):
    def send_message(self, message):
        raise OSError("connection reset")


# --- send_report_email unit modes ------------------------------------------


async def test_send_skipped_when_smtp_disabled(monkeypatch):
    monkeypatch.setattr(settings, "smtp_enabled", False)
    result = await send_report_email(["luis@nikufra.ai"], "s", "b")

    assert result["skipped"] is True
    assert result["sent"] is False
    assert result["recipients"] == ["luis@nikufra.ai"]


async def test_send_skipped_when_no_recipients():
    result = await send_report_email([], "s", "b")
    assert result["skipped"] is True
    assert result["sent"] is False


async def test_send_real_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp.local")
    _FakeSMTP.instances.clear()
    monkeypatch.setattr(email_mod.smtplib, "SMTP", _FakeSMTP)

    result = await send_report_email(["luis@nikufra.ai"], "Assunto", "Corpo")

    assert result["sent"] is True
    assert result["skipped"] is False
    assert len(_FakeSMTP.instances) == 1
    assert len(_FakeSMTP.instances[0].sent) == 1


async def test_send_raises_email_delivery_error_on_smtp_failure(monkeypatch):
    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp.local")
    monkeypatch.setattr(email_mod.smtplib, "SMTP", _FailingSMTP)

    with pytest.raises(EmailDeliveryError):
        await send_report_email(["luis@nikufra.ai"], "s", "b")


# --- POST /v1/reports/email endpoint ---------------------------------------


def test_email_endpoint_smtp_off_persists_run_as_generated(monkeypatch):
    """SMTP disabled (dev) → run persisted with status='generated', skipped."""
    monkeypatch.setattr(settings, "smtp_enabled", False)
    session = FakeSession()
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/email",
        headers=_headers(),
        json={"template_id": "cogs", "to": ["luis@nikufra.ai"]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "generated"
    assert body["sent"] is False
    assert body["skipped"] is True
    # The run was persisted + audited + committed.
    assert len(session.runs) == 1
    assert session.runs[0].status == "generated"
    assert len(session.audit) == 1
    assert session.commits == 1


def test_email_endpoint_smtp_on_marks_run_delivered(monkeypatch):
    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp.local")
    _FakeSMTP.instances.clear()
    monkeypatch.setattr(email_mod.smtplib, "SMTP", _FakeSMTP)
    session = FakeSession()
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/email",
        headers=_headers(),
        json={"template_id": "payroll", "to": ["a@nelo.local", "b@nelo.local"]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "delivered"
    assert body["sent"] is True
    assert session.runs[0].status == "delivered"
    assert session.runs[0].delivered_to == ["a@nelo.local", "b@nelo.local"]


def test_email_endpoint_smtp_failure_returns_502_and_failed_run(monkeypatch):
    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp.local")
    monkeypatch.setattr(email_mod.smtplib, "SMTP", _FailingSMTP)
    session = FakeSession()
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/email",
        headers=_headers(),
        json={"template_id": "inventario", "to": ["luis@nikufra.ai"]},
    )

    assert resp.status_code == 502
    # The failed run is still persisted (audit trail intact).
    assert len(session.runs) == 1
    assert session.runs[0].status == "failed"
    assert session.runs[0].error is not None
    assert session.commits == 1


def test_email_endpoint_rejects_empty_recipients(monkeypatch):
    """`to` must have at least one address — Pydantic min_length=1."""
    monkeypatch.setattr(settings, "smtp_enabled", False)
    session = FakeSession()
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/email",
        headers=_headers(),
        json={"template_id": "cogs", "to": []},
    )

    assert resp.status_code == 422
    assert session.runs == []
