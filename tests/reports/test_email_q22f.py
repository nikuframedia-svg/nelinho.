"""Sprint Q.22.F — SMTP delivery + `/v1/reports/email`.

Covers ``send_report_email`` in its three modes (disabled / sent /
failed) and the endpoint that records the delivery as a ``ReportRun``.
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
USER = UUID("11111111-1111-1111-1111-111111111111")


def _headers():
    return {"X-Tenant-Id": str(TENANT), "X-User-Id": str(USER)}


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


async def test_send_skipped_when_smtp_disabled(monkeypatch):
    monkeypatch.setattr(settings, "smtp_enabled", False)
    result = await send_report_email(["luis@nikufra.ai"], "s", "b")

    assert result["skipped"] is True
    assert result["sent"] is False
    assert result["recipients"] == ["luis@nikufra.ai"]


async def test_send_skipped_when_no_recipients():
    result = await send_report_email([], "s", "b")
    assert result["skipped"] is True


async def test_send_real_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp.local")
    _FakeSMTP.instances.clear()
    monkeypatch.setattr(email_mod.smtplib, "SMTP", _FakeSMTP)

    result = await send_report_email(
        ["luis@nikufra.ai"], "Relatório", "corpo",
        attachment_name="cogs.csv", attachment_text="a,b\n1,2\n",
    )

    assert result["sent"] is True
    assert len(_FakeSMTP.instances) == 1
    assert len(_FakeSMTP.instances[0].sent) == 1


async def test_send_raises_on_smtp_failure(monkeypatch):
    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "smtp.local")

    def _boom(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(email_mod.smtplib, "SMTP", _boom)

    with pytest.raises(EmailDeliveryError):
        await send_report_email(["luis@nikufra.ai"], "s", "b")


def _build_client(session):
    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(reports_router)
    app.dependency_overrides[get_session] = _fake_session
    return TestClient(app)


def test_email_endpoint_records_delivered_run(monkeypatch):
    monkeypatch.setattr(settings, "smtp_enabled", False)  # dev default
    session = FakeSession()
    client = _build_client(session)

    resp = client.post(
        "/v1/reports/email",
        json={"report_type": "cogs", "recipients": ["luis@nikufra.ai"]},
        headers=_headers(),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "delivered"
    assert body["delivered_to"] == ["luis@nikufra.ai"]
    assert len(session.runs) == 1
    assert any(a.entity_type == "report_run" for a in session.audit)


def test_email_endpoint_records_failed_run(monkeypatch):
    async def _failing_send(*args, **kwargs):
        raise EmailDeliveryError("smtp down")

    monkeypatch.setattr("src.reports.api.send_report_email", _failing_send)
    session = FakeSession()
    client = _build_client(session)

    resp = client.post(
        "/v1/reports/email",
        json={"report_type": "payroll", "recipients": ["luis@nikufra.ai"]},
        headers=_headers(),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "failed"
    assert "smtp down" in body["error"]


def test_email_endpoint_requires_recipients():
    session = FakeSession()
    client = _build_client(session)
    resp = client.post(
        "/v1/reports/email",
        json={"report_type": "cogs", "recipients": []},
        headers=_headers(),
    )
    assert resp.status_code == 422
