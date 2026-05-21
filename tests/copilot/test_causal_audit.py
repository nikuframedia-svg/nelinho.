"""Sprint S.2 — chain audit capture + replay.

Covers:
* ``persist_chain_audit`` writes a CopilotMessage with the expected
  ``causal_audit`` JSONB shape.
* ``load_chain_pairs_for_date`` hydrates the rows back into live
  ``CausalChain`` + ``CausalVerificationResult`` Pydantic objects.
* Malformed payloads (missing keys, wrong types) are skipped quietly.
* End-to-end with the ABL feedback job: persist → load → triplet on
  disk.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, List
from uuid import UUID, uuid4

import pytest

from src.copilot.causal import (
    CausalChain,
    CausalClaim,
    causal_query,
    verify_chain,
)
from src.copilot.causal.audit import (
    CAUSAL_AUDIT_KEY,
    load_chain_pairs_for_date,
    persist_chain_audit,
)
from src.copilot.jobs.abl_feedback import run_abl_feedback
from src.copilot.models import CopilotMessage
from tests.conftest import FakeSession


TENANT = UUID("55555555-5555-5555-5555-555555555555")


# ─── Test doubles ─────────────────────────────────────────────────────────


def _make_session(rows: List[Any] | None = None) -> FakeSession:
    """Q.68.3.3 — Build a canonical FakeSession with the given rows queued
    for the next ``execute(...).scalars().all()`` call.
    """
    session = FakeSession()
    session.queue_scalars(list(rows or []))
    return session


def _sign_mismatch_chain():
    kernel = causal_query("makespan_hours", do={"routing_variant": 1.0})
    chain = CausalChain(
        question="O que acontece ao makespan?",
        target="makespan_hours",
        root_cause="routing_variant",
        mechanism=[
            CausalClaim(node="laminagem_duration", direction="decrease"),
            CausalClaim(
                node="makespan_hours",
                direction="increase",
                magnitude=abs(kernel.delta),
            ),
        ],
        confidence=0.7,
    )
    return chain, verify_chain(chain, kernel_result=kernel), kernel.delta


def _passing_chain():
    kernel = causal_query("makespan_hours", do={"routing_variant": 1.0})
    chain = CausalChain(
        question="O que acontece ao makespan?",
        target="makespan_hours",
        root_cause="routing_variant",
        mechanism=[
            CausalClaim(node="laminagem_duration", direction="decrease"),
            CausalClaim(
                node="makespan_hours",
                direction="decrease",
                magnitude=abs(kernel.delta),
            ),
        ],
        confidence=0.8,
    )
    return chain, verify_chain(chain, kernel_result=kernel), kernel.delta


def _make_message(payload, *, created_at=None) -> CopilotMessage:
    msg = CopilotMessage(
        id=uuid4(),
        tenant_id=TENANT,
        conversation_id=uuid4(),
        actor_role="copilot",
        content_text="Q",
        content_structured=payload,
    )
    msg.created_at = created_at or datetime.now(timezone.utc)
    return msg


# ─── persist_chain_audit ──────────────────────────────────────────────────


def test_persist_chain_audit_writes_expected_payload():
    chain, verification, delta = _sign_mismatch_chain()
    session = _make_session()
    conv = uuid4()

    msg = asyncio.run(persist_chain_audit(
        session=session,
        tenant_id=TENANT,
        conversation_id=conv,
        chain=chain,
        verification=verification,
        kernel_delta=delta,
    ))

    assert isinstance(msg, CopilotMessage)
    assert msg.tenant_id == TENANT
    assert msg.conversation_id == conv
    assert msg.actor_role == "copilot"
    assert msg.content_text == chain.question
    assert msg in session.added

    payload = msg.content_structured
    assert isinstance(payload, dict)
    assert CAUSAL_AUDIT_KEY in payload
    audit = payload[CAUSAL_AUDIT_KEY]
    assert audit["chain"]["target"] == "makespan_hours"
    assert audit["verification"]["passed"] is False
    assert audit["kernel_delta"] == pytest.approx(delta)
    # Roundtrip-safe (must be JSON-serialisable for JSONB).
    json.dumps(payload)


# ─── load_chain_pairs_for_date ────────────────────────────────────────────


def test_load_chain_pairs_for_date_hydrates_pydantic_models():
    chain, verification, delta = _sign_mismatch_chain()
    payload = {
        CAUSAL_AUDIT_KEY: {
            "chain": chain.model_dump(),
            "verification": verification.model_dump(),
            "kernel_delta": delta,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    session = _make_session([_make_message(payload)])

    pairs = asyncio.run(load_chain_pairs_for_date(
        session, TENANT, date.today(),
    ))

    assert len(pairs) == 1
    loaded_chain, loaded_verification, loaded_delta = pairs[0]
    assert loaded_chain.question == chain.question
    assert loaded_chain.target == "makespan_hours"
    assert loaded_verification.passed == verification.passed
    assert loaded_delta == pytest.approx(delta)


def test_load_skips_messages_without_causal_audit_key():
    session = _make_session([
        _make_message(None),                              # no payload
        _make_message({}),                                # missing key
        _make_message({"unrelated": {"foo": "bar"}}),     # other key
    ])
    pairs = asyncio.run(load_chain_pairs_for_date(
        session, TENANT, date.today(),
    ))
    assert pairs == []


def test_load_skips_malformed_audit_payloads():
    """Schema drift on either chain or verification → row skipped."""
    session = _make_session([
        _make_message({CAUSAL_AUDIT_KEY: {"chain": "not a dict"}}),
        _make_message({CAUSAL_AUDIT_KEY: {
            "chain": {"missing": "required fields"},
            "verification": {"passed": True, "coherence": 1.0, "layers": []},
        }}),
    ])
    pairs = asyncio.run(load_chain_pairs_for_date(
        session, TENANT, date.today(),
    ))
    assert pairs == []


# ─── E2E: persist → load → run_abl_feedback ──────────────────────────────


def test_persist_then_load_feeds_abl_feedback_job(tmp_path: Path):
    chain_bad, ver_bad, delta_bad = _sign_mismatch_chain()
    chain_ok, ver_ok, delta_ok = _passing_chain()

    bad_payload = {
        CAUSAL_AUDIT_KEY: {
            "chain": chain_bad.model_dump(),
            "verification": ver_bad.model_dump(),
            "kernel_delta": delta_bad,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    ok_payload = {
        CAUSAL_AUDIT_KEY: {
            "chain": chain_ok.model_dump(),
            "verification": ver_ok.model_dump(),
            "kernel_delta": delta_ok,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    session = _make_session([
        _make_message(bad_payload),
        _make_message(ok_payload),
    ])

    pairs = asyncio.run(load_chain_pairs_for_date(
        session, TENANT, date.today(),
    ))
    assert len(pairs) == 2

    target = date(2026, 4, 25)
    report = run_abl_feedback(
        pairs, tenant_id=TENANT, output_dir=tmp_path, today=target,
    )
    # Two chains in, only the divergent one writes triplets.
    assert report.chains_processed == 2
    assert report.divergences_detected >= 1
    assert report.triplets_written >= 1
    assert (tmp_path / "2026-04-25.jsonl").exists()
