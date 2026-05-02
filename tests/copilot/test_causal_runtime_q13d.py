"""Sprint Q.13.D D.1 — `record_causal_audit` runtime helper test.

Plan v4 §22-§26 — the moat depends on Camada 4 collecting
(chain, verification) pairs nightly. Q.11 Onda 1.5 wired the daily
job; Q.13.D D.1 ships the helper every copilot codepath calls to
feed it. These tests pin the contract:

  * Verify-then-persist round-trip stages a row with the audit
    payload in `content_structured.causal_audit`.
  * Malformed `chain_dict` returns None instead of raising.
  * Persist failure returns None instead of raising.
  * The persisted row carries `validation_passed` matching the
    verification result.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.copilot.causal.runtime import record_causal_audit
from src.copilot.models import CopilotMessage


# Valid edge in NELO_DAG that the verifier accepts: mold_age →
# mold_setup_time. Both directions explicit so the chain is well-formed.
_VALID_CHAIN_DICT = {
    "question": "Why did mold setup time rise this week?",
    "target": "mold_setup_time",
    "root_cause": "mold_age",
    "mechanism": [
        {
            "node": "mold_age",
            "direction": "increase",
            "magnitude": 0.2,
            "rationale": "Mold has cycled 1200 times since maintenance.",
        },
        {
            "node": "mold_setup_time",
            "direction": "increase",
            "magnitude": 0.5,
            "rationale": "Older molds need longer alignment.",
        },
    ],
    "counterfactual": "Had we replaced the mold last month, setup would be flat.",
    "recommendation": "Schedule maintenance for mold_id 7.",
    "confidence": 0.78,
    "evidence": ["maintenance_log:2026-04-12", "metric:mold_setup_time:p50"],
}

_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_CONVERSATION = UUID("22222222-2222-2222-2222-222222222222")


class _FakeSession:
    """In-memory stand-in for AsyncSession — captures `add` calls.

    `record_causal_audit` only calls `session.add(msg)`; flush/commit
    happens in the caller's transaction. So a tiny double is enough."""

    def __init__(self) -> None:
        self.staged: list = []
        self.add_should_raise: bool = False

    def add(self, instance) -> None:
        if self.add_should_raise:
            raise RuntimeError("simulated DB outage")
        self.staged.append(instance)


@pytest.mark.asyncio
async def test_record_causal_audit_stages_audit_row():
    session = _FakeSession()
    msg = await record_causal_audit(
        session=session,  # type: ignore[arg-type]
        tenant_id=_TENANT,
        conversation_id=_CONVERSATION,
        chain_dict=dict(_VALID_CHAIN_DICT),
    )
    assert msg is not None
    assert isinstance(msg, CopilotMessage)
    assert msg.tenant_id == _TENANT
    assert msg.conversation_id == _CONVERSATION
    assert msg.actor_role == "copilot"
    # The audit payload lives under `content_structured.causal_audit`
    # — that's the shape the ABL feedback job reads.
    assert "causal_audit" in (msg.content_structured or {})
    assert "chain" in msg.content_structured["causal_audit"]
    assert "verification" in msg.content_structured["causal_audit"]
    # Exactly one row staged on the session.
    assert len(session.staged) == 1
    assert session.staged[0] is msg


@pytest.mark.asyncio
async def test_record_causal_audit_returns_none_on_malformed_chain():
    session = _FakeSession()
    bad_chain = {"question": "?"}  # missing required fields
    msg = await record_causal_audit(
        session=session,  # type: ignore[arg-type]
        tenant_id=_TENANT,
        conversation_id=_CONVERSATION,
        chain_dict=bad_chain,
    )
    assert msg is None
    # Nothing staged — verification failed before persist.
    assert session.staged == []


@pytest.mark.asyncio
async def test_record_causal_audit_returns_none_on_persist_failure():
    session = _FakeSession()
    session.add_should_raise = True
    msg = await record_causal_audit(
        session=session,  # type: ignore[arg-type]
        tenant_id=_TENANT,
        conversation_id=_CONVERSATION,
        chain_dict=dict(_VALID_CHAIN_DICT),
    )
    assert msg is None  # caught the simulated DB outage


@pytest.mark.asyncio
async def test_record_causal_audit_carries_optional_kernel_delta():
    session = _FakeSession()
    msg = await record_causal_audit(
        session=session,  # type: ignore[arg-type]
        tenant_id=_TENANT,
        conversation_id=_CONVERSATION,
        chain_dict=dict(_VALID_CHAIN_DICT),
        kernel_delta=0.42,
    )
    assert msg is not None
    payload = msg.content_structured["causal_audit"]
    assert payload["kernel_delta"] == 0.42


@pytest.mark.asyncio
async def test_record_causal_audit_validation_passed_propagates_to_message():
    """The `validation_passed` boolean on CopilotMessage must reflect
    the verification outcome — it's how downstream code (e.g. the
    Camada-4 ABL detector) decides whether the chain is "training
    material" (failed verification) or just an audit log."""
    session = _FakeSession()
    msg = await record_causal_audit(
        session=session,  # type: ignore[arg-type]
        tenant_id=_TENANT,
        conversation_id=_CONVERSATION,
        chain_dict=dict(_VALID_CHAIN_DICT),
    )
    assert msg is not None
    # Whether the chain passes verification depends on the kernel's
    # ground truth (which the test doesn't exercise); the contract is
    # that the field reflects the verification result, not silently
    # always True.
    payload = msg.content_structured["causal_audit"]
    assert msg.validation_passed == payload["verification"]["passed"]
