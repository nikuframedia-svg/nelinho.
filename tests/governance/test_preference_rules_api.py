"""Sprint E.3 — PreferenceRuleService + /v1/governance/preference-rules endpoints.

Service-level tests (`TestPreferenceRuleService`) cover the CRUD + the
state-machine constraints (only detected rules are reviewable, reject
demands a reason). API tests (`TestPreferenceRulesApi`) exercise the
FastAPI router through a TestClient with a fake session/service pair.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.governance.api_preference_rules import (
    _service as service_dependency,
    router as preference_rules_router,
)
from src.governance.models import (
    PreferenceRule,
    PreferenceRuleStatus,
    PreferenceRuleType,
)
from src.governance.preference_learning.rule_service import (
    PreferenceRuleInvalidTransitionError,
    PreferenceRuleNotFoundError,
    PreferenceRuleService,
)


TENANT = UUID("33333333-3333-3333-3333-333333333333")
ADMIN_USER = UUID("44444444-4444-4444-4444-444444444444")


# ─── In-memory stubs ───────────────────────────────────────────────────────


def _make_rule(
    *,
    status: str = PreferenceRuleStatus.DETECTED.value,
    rule_type: str = PreferenceRuleType.TEMPORAL_BLOCK.value,
    confidence: float = 0.85,
    description: str = "Rejects Laminagem on Fridays",
    rule_id: Optional[UUID] = None,
) -> PreferenceRule:
    rule = PreferenceRule(
        id=rule_id or uuid4(),
        tenant_id=TENANT,
        type=rule_type,
        description=description,
        predicate={"weekday": 5, "rejected_count": 6},
        confidence=Decimal(str(confidence)),
        status=status,
        detected_from_commits=["abc123", "def456"],
        confirmed_at=None,
        confirmed_by=None,
        review_notes=None,
    )
    return rule


class _FakeSession:
    """Minimum surface to satisfy PreferenceRuleService without a live DB.

    Returns the seeded list on ``list_rules`` queries and, when a
    ``rule.id`` UUID appears in the compiled parameters (``get_rule``),
    filters down to that single row. We only treat a parameter as a
    rule_id if it matches an id already in the fake store — this
    prevents the tenant_id parameter (also a UUID) from being mistaken
    for a rule id.
    """

    def __init__(self, rules: List[PreferenceRule]) -> None:
        self.rules = list(rules)
        self.flush_calls = 0
        self.last_stmt: Any = None

    async def execute(self, stmt):
        self.last_stmt = stmt

        class _Scalars:
            def __init__(self, rows: List[PreferenceRule]) -> None:
                self._rows = rows

            def all(self) -> List[PreferenceRule]:
                return list(self._rows)

            def one_or_none(self) -> Optional[PreferenceRule]:
                return self._rows[0] if self._rows else None

        class _Result:
            def __init__(self, rows: List[PreferenceRule]) -> None:
                self._rows = rows

            def scalars(self) -> _Scalars:
                return _Scalars(self._rows)

            def scalar_one_or_none(self) -> Optional[PreferenceRule]:
                return self._rows[0] if self._rows else None

        known_ids = {r.id for r in self.rules}
        rid = _extract_rule_id_from_stmt(stmt, known_ids)
        if rid is not None:
            match = [r for r in self.rules if r.id == rid]
            return _Result(match)
        # Also honour a "ghost id" query (get_rule on a missing UUID):
        # if the statement carries a UUID that is NOT our tenant and not
        # a seeded rule, return an empty result rather than the full
        # list so the 404 path lights up correctly.
        if _stmt_has_ghost_id(stmt, known_ids, tenant_id=TENANT):
            return _Result([])
        return _Result(list(self.rules))

    async def flush(self) -> None:
        self.flush_calls += 1


def _extract_rule_id_from_stmt(
    stmt: Any, known_rule_ids: set[UUID],
) -> Optional[UUID]:
    """Return the rule id filter if the compiled params mention a UUID
    that matches a seeded rule. Falls back to ``None`` (treat as a list
    query) when the only UUID in scope is the tenant id."""
    try:
        params = stmt.compile().params  # type: ignore[attr-defined]
    except Exception:
        return None
    for value in params.values():
        if isinstance(value, UUID) and value in known_rule_ids:
            return value
    return None


def _stmt_has_ghost_id(
    stmt: Any, known_rule_ids: set[UUID], *, tenant_id: UUID,
) -> bool:
    """True when the statement carries a UUID that's neither the tenant
    id nor any seeded rule id — signals a ``get_rule`` call on a UUID
    the test set doesn't own."""
    try:
        params = stmt.compile().params  # type: ignore[attr-defined]
    except Exception:
        return False
    uuids = [v for v in params.values() if isinstance(v, UUID)]
    if len(uuids) < 2:
        return False
    return any(u != tenant_id and u not in known_rule_ids for u in uuids)


# ═══════════════════════════════════════════════════════════════════════════
# Service-level tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPreferenceRuleService:
    def _svc(self, rules: List[PreferenceRule]) -> PreferenceRuleService:
        return PreferenceRuleService(_FakeSession(rules), TENANT)

    def test_list_returns_rules_for_tenant(self) -> None:
        rules = [_make_rule(), _make_rule()]
        svc = self._svc(rules)
        result = asyncio.run(svc.list_rules())
        assert len(result) == 2

    def test_list_rejects_unknown_status(self) -> None:
        svc = self._svc([_make_rule()])
        with pytest.raises(ValueError):
            asyncio.run(svc.list_rules(status="bogus"))

    def test_get_rule_raises_when_missing(self) -> None:
        svc = self._svc([])
        with pytest.raises(PreferenceRuleNotFoundError):
            asyncio.run(svc.get_rule(uuid4()))

    def test_confirm_flips_status_and_stamps_reviewer(self) -> None:
        rule = _make_rule()
        svc = self._svc([rule])
        updated = asyncio.run(svc.confirm(
            rule.id, confirmed_by=ADMIN_USER, review_notes="solid pattern",
        ))
        assert updated.status == PreferenceRuleStatus.CONFIRMED.value
        assert updated.confirmed_by == ADMIN_USER
        assert updated.confirmed_at is not None
        assert updated.review_notes == "solid pattern"

    def test_confirm_rejects_already_confirmed_rule(self) -> None:
        rule = _make_rule(status=PreferenceRuleStatus.CONFIRMED.value)
        svc = self._svc([rule])
        with pytest.raises(PreferenceRuleInvalidTransitionError):
            asyncio.run(svc.confirm(rule.id, confirmed_by=ADMIN_USER))

    def test_reject_requires_non_empty_reason(self) -> None:
        rule = _make_rule()
        svc = self._svc([rule])
        with pytest.raises(ValueError):
            asyncio.run(svc.reject(rule.id, rejected_by=ADMIN_USER, reason="   "))

    def test_reject_stores_reason_and_reviewer(self) -> None:
        rule = _make_rule()
        svc = self._svc([rule])
        updated = asyncio.run(svc.reject(
            rule.id,
            rejected_by=ADMIN_USER,
            reason="false positive — 2-week vacation gap",
        ))
        assert updated.status == PreferenceRuleStatus.REJECTED.value
        assert updated.confirmed_by == ADMIN_USER  # doubles as "reviewed_by"
        assert "vacation" in updated.review_notes

    def test_update_metadata_tightens_detected_rule(self) -> None:
        rule = _make_rule()
        svc = self._svc([rule])
        updated = asyncio.run(svc.update_metadata(
            rule.id,
            description="Only K4 Laminagem on Fridays",
            predicate={"weekday": 5, "mold_code": "K4"},
            confidence=0.92,
        ))
        assert updated.description == "Only K4 Laminagem on Fridays"
        assert updated.predicate["mold_code"] == "K4"
        assert float(updated.confidence) == pytest.approx(0.92)

    def test_update_metadata_blocks_confirmed_rule(self) -> None:
        rule = _make_rule(status=PreferenceRuleStatus.CONFIRMED.value)
        svc = self._svc([rule])
        with pytest.raises(PreferenceRuleInvalidTransitionError):
            asyncio.run(svc.update_metadata(rule.id, description="no-op"))

    def test_update_metadata_rejects_bad_confidence(self) -> None:
        rule = _make_rule()
        svc = self._svc([rule])
        with pytest.raises(ValueError):
            asyncio.run(svc.update_metadata(rule.id, confidence=2.5))


# ═══════════════════════════════════════════════════════════════════════════
# API-level tests (FastAPI TestClient)
# ═══════════════════════════════════════════════════════════════════════════


def _make_test_app(rules: List[PreferenceRule]) -> FastAPI:
    """Mount only the preference-rules router, overriding the service
    dependency with one backed by an in-memory session."""

    session = _FakeSession(rules)

    async def _fake_service() -> PreferenceRuleService:
        return PreferenceRuleService(session, TENANT)

    app = FastAPI()
    app.include_router(preference_rules_router)
    app.dependency_overrides[service_dependency] = _fake_service
    app.state._fake_session = session  # handy for assertions
    return app


class TestPreferenceRulesApi:
    def _client(self, rules: List[PreferenceRule]) -> TestClient:
        return TestClient(_make_test_app(rules))

    def _admin_headers(self) -> Dict[str, str]:
        return {
            "X-Tenant-ID": str(TENANT),
            "X-User-Id": str(ADMIN_USER),
            "X-User-Role": "admin",
        }

    def test_list_rules_returns_all_seeded(self) -> None:
        rules = [_make_rule(), _make_rule(confidence=0.72)]
        client = self._client(rules)
        resp = client.get(
            "/v1/governance/preference-rules",
            headers={"X-Tenant-ID": str(TENANT)},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert {r["status"] for r in body} == {PreferenceRuleStatus.DETECTED.value}

    def test_list_rejects_bad_status_filter(self) -> None:
        client = self._client([_make_rule()])
        resp = client.get(
            "/v1/governance/preference-rules?status=invalid",
            headers={"X-Tenant-ID": str(TENANT)},
        )
        assert resp.status_code == 400

    def test_get_single_rule_happy_path(self) -> None:
        rule = _make_rule()
        client = self._client([rule])
        resp = client.get(
            f"/v1/governance/preference-rules/{rule.id}",
            headers={"X-Tenant-ID": str(TENANT)},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == str(rule.id)

    def test_get_single_rule_404_when_missing(self) -> None:
        client = self._client([])
        resp = client.get(
            f"/v1/governance/preference-rules/{uuid4()}",
            headers={"X-Tenant-ID": str(TENANT)},
        )
        assert resp.status_code == 404

    def test_confirm_requires_admin_role(self) -> None:
        rule = _make_rule()
        client = self._client([rule])
        resp = client.post(
            f"/v1/governance/preference-rules/{rule.id}/confirm",
            headers={
                "X-Tenant-ID": str(TENANT),
                "X-User-Role": "user",  # non-admin
            },
        )
        assert resp.status_code == 403

    def test_confirm_flips_status(self) -> None:
        rule = _make_rule()
        client = self._client([rule])
        resp = client.post(
            f"/v1/governance/preference-rules/{rule.id}/confirm",
            headers=self._admin_headers(),
            json={"review_notes": "seen this a few weeks running"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == PreferenceRuleStatus.CONFIRMED.value
        assert body["review_notes"] == "seen this a few weeks running"
        assert body["confirmed_by"] == str(ADMIN_USER)

    def test_confirm_on_already_reviewed_rule_is_409(self) -> None:
        rule = _make_rule(status=PreferenceRuleStatus.CONFIRMED.value)
        client = self._client([rule])
        resp = client.post(
            f"/v1/governance/preference-rules/{rule.id}/confirm",
            headers=self._admin_headers(),
        )
        assert resp.status_code == 409

    def test_reject_demands_reason(self) -> None:
        rule = _make_rule()
        client = self._client([rule])
        # body missing → FastAPI returns 422 (schema validation)
        resp = client.post(
            f"/v1/governance/preference-rules/{rule.id}/reject",
            headers=self._admin_headers(),
        )
        assert resp.status_code == 422

    def test_reject_stores_reason(self) -> None:
        rule = _make_rule()
        client = self._client([rule])
        resp = client.post(
            f"/v1/governance/preference-rules/{rule.id}/reject",
            headers=self._admin_headers(),
            json={"reason": "detector overfit on a vacation gap"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == PreferenceRuleStatus.REJECTED.value
        assert "vacation" in body["review_notes"]

    def test_patch_narrows_predicate(self) -> None:
        rule = _make_rule()
        client = self._client([rule])
        resp = client.patch(
            f"/v1/governance/preference-rules/{rule.id}",
            headers=self._admin_headers(),
            json={
                "description": "Laminagem K4 on Fridays",
                "predicate": {"weekday": 5, "mold_code": "K4"},
                "confidence": 0.90,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["description"] == "Laminagem K4 on Fridays"
        assert body["predicate"]["mold_code"] == "K4"
        assert body["confidence"] == pytest.approx(0.9)

    def test_patch_on_confirmed_rule_is_409(self) -> None:
        rule = _make_rule(status=PreferenceRuleStatus.CONFIRMED.value)
        client = self._client([rule])
        resp = client.patch(
            f"/v1/governance/preference-rules/{rule.id}",
            headers=self._admin_headers(),
            json={"description": "whatever"},
        )
        assert resp.status_code == 409
