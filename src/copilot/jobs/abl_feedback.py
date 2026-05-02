"""
ProdPlan ONE — ABL Feedback Job (Sprint R.3, Camada 4)
========================================================

The piece that brings Camada 4 from "infra exists" to "feeds Camada 3".

For every (``CausalChain``, ``CausalVerificationResult``) pair the
Copilot produced in the last day, this job:

1. Runs ``DivergenceDetector.detect_divergences`` to extract structured
   disagreements between the LLM and the kernel.
2. Renders each divergence as a DPO triplet (same shape as
   ``DPODatasetBuilder``) via ``render_dpo_triplet``.
3. Appends the triplets to today's JSONL file at
   ``data/learning/abl_triplets/{YYYY-MM-DD}.jsonl``.
4. Reports counters the R.1 dashboard surfaces.

Idempotent — running the job twice on the same day with the same
inputs does not duplicate rows. Idempotency key is the SHA of
``prompt + chosen + rejected``.

The wiring of "where do (chain, result) pairs come from in production"
is deliberately abstracted: the job receives them as an iterable so
downstream code (the scheduler hook, a Kafka consumer, a manual test
harness) can supply them without coupling this module to any specific
source.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from uuid import UUID

from src.copilot.causal.ablkit import (
    detect_divergences,
    render_dpo_triplet,
)
from src.copilot.causal.chain import (
    CausalChain,
    CausalVerificationResult,
)

logger = logging.getLogger(__name__)


# Default output directory; mirrors what LearningMetricsService reads.
DEFAULT_ABL_OUTPUT_DIR = Path("data/learning/abl_triplets")


@dataclass
class ABLFeedbackReport:
    """Counters returned to the scheduler / R.1 dashboard."""

    chains_processed: int
    divergences_detected: int
    triplets_written: int
    triplets_skipped_duplicate: int
    output_path: Optional[str]
    target_date: str


# Pair the job consumes — a chain plus its verification, optionally a
# kernel delta the verifier already used.
ChainPair = Tuple[CausalChain, CausalVerificationResult, Optional[float]]


def _triplet_signature(triplet: dict) -> str:
    """SHA-256 over the (prompt, chosen, rejected) tuple. Used to skip
    duplicates when re-running on the same day."""
    payload = json.dumps(
        [triplet.get("prompt", ""), triplet.get("chosen", ""), triplet.get("rejected", "")],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_existing_signatures(output_path: Path) -> set[str]:
    """Read the day's JSONL (if any) and return the SHA of every line.

    Corrupt lines are skipped — a malformed row must never block a
    fresh write. The job logs the skip so ops can investigate.
    """
    if not output_path.exists():
        return set()
    sigs: set[str] = set()
    try:
        with output_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    sigs.add(_triplet_signature(payload))
                except Exception as exc:  # pragma: no cover — defensive
                    # Sprint Q.7 Fase 4 — was bare `continue`. Skip
                    # malformed JSONL but log so corruption surfaces.
                    logger.debug("abl_feedback: skip malformed line: %s", exc)
                    continue
    except OSError as exc:  # pragma: no cover — defensive
        logger.warning(
            "abl_feedback: could not read %s for dedup (%s) — proceeding",
            output_path, exc,
        )
    return sigs


def run_abl_feedback(
    chain_pairs: Iterable[ChainPair],
    *,
    tenant_id: Optional[UUID] = None,
    output_dir: Path = DEFAULT_ABL_OUTPUT_DIR,
    today: Optional[date] = None,
) -> ABLFeedbackReport:
    """Drive the full ABL → JSONL pipeline for one day.

    ``chain_pairs`` is an iterable of ``(chain, verification, kernel_delta)``
    tuples. Pairs whose verification passed are skipped silently —
    they're not training material, just successful answers.
    """
    if today is None:
        today = datetime.now(timezone.utc).date()
    output_dir = Path(output_dir)
    output_path = output_dir / f"{today.isoformat()}.jsonl"

    chains_processed = 0
    divergences_total = 0
    triplets_written = 0
    triplets_skipped_duplicate = 0

    existing_sigs = _load_existing_signatures(output_path)

    rows_to_write: List[dict] = []
    for pair in chain_pairs:
        try:
            chain, verification, kernel_delta = pair
        except (TypeError, ValueError):
            logger.warning("abl_feedback: malformed chain pair, skipping")
            continue
        chains_processed += 1
        divergences = detect_divergences(
            chain, verification,
            kernel_delta=kernel_delta,
            tenant_id=tenant_id,
        )
        divergences_total += len(divergences)
        for div in divergences:
            triplet = render_dpo_triplet(div)
            sig = _triplet_signature(triplet)
            if sig in existing_sigs:
                triplets_skipped_duplicate += 1
                continue
            existing_sigs.add(sig)
            rows_to_write.append(triplet)

    if rows_to_write:
        output_dir.mkdir(parents=True, exist_ok=True)
        with output_path.open("a", encoding="utf-8") as fh:
            for triplet in rows_to_write:
                fh.write(json.dumps(triplet, ensure_ascii=False))
                fh.write("\n")
        triplets_written = len(rows_to_write)

    logger.info(
        "abl_feedback: tenant=%s date=%s chains=%d divergences=%d "
        "written=%d duplicates=%d",
        tenant_id, today.isoformat(),
        chains_processed, divergences_total,
        triplets_written, triplets_skipped_duplicate,
    )

    return ABLFeedbackReport(
        chains_processed=chains_processed,
        divergences_detected=divergences_total,
        triplets_written=triplets_written,
        triplets_skipped_duplicate=triplets_skipped_duplicate,
        output_path=str(output_path) if triplets_written else None,
        target_date=today.isoformat(),
    )


# ─── Source adapter — Copilot DB → chain pairs ───────────────────────────


async def _load_chain_pairs_from_db(
    tenant_id: UUID, target_date: date,
) -> List[ChainPair]:
    """Sprint S.2 — pull chain audit rows out of CopilotMessage.

    Reads any ``copilot``-actor message whose ``content_structured``
    carries a ``causal_audit`` key (written by
    :func:`src.copilot.causal.audit.persist_chain_audit` when a
    causal response runs). Rows are hydrated back into Pydantic
    objects so the downstream ABL pipeline doesn't have to know
    about JSONB.

    Returns an empty list when:
    * No copilot has wired ``persist_chain_audit`` yet (the rows
      simply don't exist).
    * The DB session can't be opened (logged, never raises).
    """
    from src.shared.database import get_session_context

    try:
        async with get_session_context() as session:
            from src.copilot.causal.audit import load_chain_pairs_for_date

            return await load_chain_pairs_for_date(
                session, tenant_id, target_date,
            )
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            "abl_feedback: chain pair load failed for tenant=%s date=%s (%s) — "
            "returning empty list",
            tenant_id, target_date.isoformat(), exc,
        )
        return []


__all__ = [
    "ABLFeedbackReport",
    "ChainPair",
    "DEFAULT_ABL_OUTPUT_DIR",
    "run_abl_feedback",
]
