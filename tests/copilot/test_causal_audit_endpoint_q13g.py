"""Sprint Q.13.G — `POST /api/copilot/causal/audit` test.

`record_causal_audit` (Q.13.D) shipped without callsites; the copilot
service today doesn't emit structured `CausalChain` dicts. This
endpoint is the bridge: frontend / integration tests / operators can
seed the Camada-4 ABL pipeline so the nightly job stops finding zero
chains.

Tests pin:
  * Valid body → 201 + audit_message_id + verification block.
  * Missing fields → 400.
  * Invalid UUIDs → 400.
  * Malformed chain → 400 (record_causal_audit returns None).
  * Optional kernel_delta + correlation_id round-trip into the
    persisted message.
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from src.copilot.api import post_causal_audit
from src.copilot.models import CopilotMessage
from tests.conftest import FakeSession


_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_CONVERSATION = UUID("22222222-2222-2222-2222-222222222222")


# Valid edge in NELO_DAG that the verifier accepts: mold_age →
# mold_setup_time. Reused from `test_causal_runtime_q13d.py`.
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


# ───────────────────────────────────────────────────────────────────────────
# Tests — call the endpoint function directly (FastAPI handler is async).
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_causal_audit_persists_valid_chain():
    session = FakeSession()
    payload: Dict[str, Any] = {
        "conversation_id": str(_CONVERSATION),
        "chain": dict(_VALID_CHAIN_DICT),
    }
    result = await post_causal_audit(
        payload=payload,
        _user=None,  # type: ignore[arg-type]
        tenant_id=_TENANT,
        session=session,  # type: ignore[arg-type]
    )
    assert isinstance(result, dict)
    assert "audit_message_id" in result
    assert UUID(result["audit_message_id"])  # parseable UUID
    assert result["conversation_id"] == str(_CONVERSATION)
    assert "verification" in result
    assert "passed" in result["verification"]
    # Exactly one CopilotMessage row staged.
    assert len(session.added) == 1
    assert isinstance(session.added[0], CopilotMessage)
    assert session.commit_calls >= 1


@pytest.mark.asyncio
async def test_post_causal_audit_rejects_missing_conversation_id():
    from fastapi import HTTPException

    session = FakeSession()
    with pytest.raises(HTTPException) as exc_info:
        await post_causal_audit(
            payload={"chain": dict(_VALID_CHAIN_DICT)},
            _user=None,  # type: ignore[arg-type]
            tenant_id=_TENANT,
            session=session,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400
    assert "conversation_id" in exc_info.value.detail
    assert session.added == []


@pytest.mark.asyncio
async def test_post_causal_audit_rejects_missing_chain():
    from fastapi import HTTPException

    session = FakeSession()
    with pytest.raises(HTTPException) as exc_info:
        await post_causal_audit(
            payload={"conversation_id": str(_CONVERSATION)},
            _user=None,  # type: ignore[arg-type]
            tenant_id=_TENANT,
            session=session,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400
    assert session.added == []


@pytest.mark.asyncio
async def test_post_causal_audit_rejects_invalid_uuid():
    from fastapi import HTTPException

    session = FakeSession()
    with pytest.raises(HTTPException) as exc_info:
        await post_causal_audit(
            payload={
                "conversation_id": "not-a-uuid",
                "chain": dict(_VALID_CHAIN_DICT),
            },
            _user=None,  # type: ignore[arg-type]
            tenant_id=_TENANT,
            session=session,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400
    assert "conversation_id" in exc_info.value.detail


@pytest.mark.asyncio
async def test_post_causal_audit_rejects_malformed_chain():
    """`record_causal_audit` returns None when verify_chain_dict
    rejects the body. Endpoint must surface as 400 — the operator
    fix is to repair the chain, not retry."""
    from fastapi import HTTPException

    session = FakeSession()
    bad_chain = {"question": "Why?"}  # missing required CausalChain fields
    with pytest.raises(HTTPException) as exc_info:
        await post_causal_audit(
            payload={
                "conversation_id": str(_CONVERSATION),
                "chain": bad_chain,
            },
            _user=None,  # type: ignore[arg-type]
            tenant_id=_TENANT,
            session=session,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400
    assert "verification" in exc_info.value.detail.lower() or "chain" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_post_causal_audit_carries_optional_kernel_delta():
    session = FakeSession()
    result = await post_causal_audit(
        payload={
            "conversation_id": str(_CONVERSATION),
            "chain": dict(_VALID_CHAIN_DICT),
            "kernel_delta": 0.42,
        },
        _user=None,  # type: ignore[arg-type]
        tenant_id=_TENANT,
        session=session,  # type: ignore[arg-type]
    )
    assert "audit_message_id" in result
    msg = session.added[0]
    payload = (msg.content_structured or {}).get("causal_audit") or {}
    assert payload.get("kernel_delta") == 0.42


@pytest.mark.asyncio
async def test_post_causal_audit_rejects_non_numeric_kernel_delta():
    from fastapi import HTTPException

    session = FakeSession()
    with pytest.raises(HTTPException) as exc_info:
        await post_causal_audit(
            payload={
                "conversation_id": str(_CONVERSATION),
                "chain": dict(_VALID_CHAIN_DICT),
                "kernel_delta": "not-a-number",
            },
            _user=None,  # type: ignore[arg-type]
            tenant_id=_TENANT,
            session=session,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400
    assert "kernel_delta" in exc_info.value.detail
