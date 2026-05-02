"""Sprint R.3 — ABL feedback job pipeline.

Covers the wakeup of Camada 4: chain + verification → divergences →
DPO triplets in JSONL. Uses the same well-known kernel results the
ablkit tests exercise so the integration is end-to-end.

* ``run_abl_feedback`` writes nothing when chains pass verification.
* A sign-mismatch chain produces a triplet on disk with ``meta.source =
  "ablkit"`` and the day's filename.
* Re-running with the same input does NOT duplicate the row
  (idempotency by SHA of prompt+chosen+rejected).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest

from src.copilot.causal import (
    CausalChain,
    CausalClaim,
    causal_query,
    verify_chain,
)
from src.copilot.jobs.abl_feedback import (
    ABLFeedbackReport,
    run_abl_feedback,
)


TENANT = UUID("44444444-4444-4444-4444-444444444444")


def _passing_chain() -> tuple:
    kernel = causal_query("makespan_hours", do={"routing_variant": 1.0})
    chain = CausalChain(
        question="O que acontece ao makespan se mudarmos para a variante B?",
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
    result = verify_chain(chain, kernel_result=kernel)
    return chain, result, kernel.delta


def _sign_mismatch_chain() -> tuple:
    kernel = causal_query("makespan_hours", do={"routing_variant": 1.0})
    chain = CausalChain(
        question="E se mudarmos para a variante B?",
        target="makespan_hours",
        root_cause="routing_variant",
        mechanism=[
            CausalClaim(node="laminagem_duration", direction="decrease"),
            CausalClaim(
                node="makespan_hours",
                direction="increase",  # kernel says decrease — disagreement
                magnitude=abs(kernel.delta),
            ),
        ],
        confidence=0.7,
    )
    result = verify_chain(chain, kernel_result=kernel)
    return chain, result, kernel.delta


# ─── Tests ────────────────────────────────────────────────────────────────


def test_passing_chain_yields_no_triplets(tmp_path: Path):
    pairs = [_passing_chain()]
    report = run_abl_feedback(
        pairs,
        tenant_id=TENANT,
        output_dir=tmp_path,
        today=date(2026, 4, 25),
    )
    assert isinstance(report, ABLFeedbackReport)
    assert report.chains_processed == 1
    assert report.divergences_detected == 0
    assert report.triplets_written == 0
    assert report.output_path is None
    # File should not have been created.
    assert not (tmp_path / "2026-04-25.jsonl").exists()


def test_sign_mismatch_writes_triplet_with_ablkit_source(tmp_path: Path):
    pairs = [_sign_mismatch_chain()]
    report = run_abl_feedback(
        pairs,
        tenant_id=TENANT,
        output_dir=tmp_path,
        today=date(2026, 4, 25),
    )
    assert report.chains_processed == 1
    assert report.divergences_detected >= 1
    assert report.triplets_written >= 1

    output = tmp_path / "2026-04-25.jsonl"
    assert output.exists()
    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 1
    payload = json.loads(lines[0])
    assert set(payload.keys()) == {"prompt", "chosen", "rejected", "meta"}
    assert payload["meta"]["source"] == "ablkit"
    assert payload["meta"]["tenant_id"] == str(TENANT)


def test_idempotent_when_run_twice_same_day(tmp_path: Path):
    pairs1 = [_sign_mismatch_chain()]
    first = run_abl_feedback(
        pairs1,
        tenant_id=TENANT,
        output_dir=tmp_path,
        today=date(2026, 4, 25),
    )
    written_first = first.triplets_written
    assert written_first >= 1

    # Same chain pair — every triplet's signature already exists.
    pairs2 = [_sign_mismatch_chain()]
    second = run_abl_feedback(
        pairs2,
        tenant_id=TENANT,
        output_dir=tmp_path,
        today=date(2026, 4, 25),
    )
    assert second.triplets_written == 0
    assert second.triplets_skipped_duplicate == written_first

    # File still has only the original rows.
    output = tmp_path / "2026-04-25.jsonl"
    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == written_first


def test_malformed_pair_skipped_without_crash(tmp_path: Path):
    pairs = [
        ("not", "a", "valid", "tuple"),  # too many elements
        _passing_chain(),
    ]
    report = run_abl_feedback(
        pairs,
        tenant_id=TENANT,
        output_dir=tmp_path,
        today=date(2026, 4, 25),
    )
    # Only the valid pair was processed.
    assert report.chains_processed == 1
    assert report.triplets_written == 0
