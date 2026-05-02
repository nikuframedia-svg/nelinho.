"""
ProdPlan ONE — DPO Dataset Builder (Sprint I.1, Camada 3)
============================================================

Camada 3 of the learning stack is **Direct Preference Optimization**:
take the operator's accept/reject choices already sitting inside
``ScheduleCommit.rejected_alternatives`` + ``user_preference_signal``
and turn them into ``(prompt, chosen, rejected)`` triplets a QLoRA
+ DPO trainer can consume. The fine-tune itself runs offline /
quarterly (infra from Sprint S), so this module's job is simply
**dataset curation** — never LLM calls, always pure I/O + text.

Why build the dataset now even though fine-tuning is later
----------------------------------------------------------
* It accumulates on every commit the operator reviews — the earlier
  we harvest it, the more pairs the eventual fine-tune has.
* It's JSONL that can be version-controlled / reviewed offline.
* Ops can spot-check triplets ("does this actually encode my
  preference?") before trusting the fine-tune.

File format
-----------
``builds[i]`` is a dict::

    {
      "prompt": "Tu és o escalonador da fábrica NELO. …",
      "chosen":   "Prefiro o plano A: makespan 182 h, 2 setups, …",
      "rejected": "Prefiro o plano B: makespan 168 h, 6 setups, …",
      "meta": {
        "commit_sha": "abc12345",
        "decided_by": "alice",
        "weekday": 3,
        "alt_idx": 4,
        "reason": "trade throughput for quality",
        "created_at": "2026-04-20T10:12:33+00:00"
      }
    }

Exactly *N* triplets per commit with *N* rejected alternatives — we
never collapse them because DPO benefits from pairwise signal even
when the rejects are near-ties.

The builder writes UTF-8 JSONL (one object per line) so huggingface
``datasets.load_dataset('json', data_files=...)`` picks it up
directly, without a wrapper.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.cpo.commits import ScheduleCommit

logger = logging.getLogger(__name__)


# KPI keys we copy into the chosen / rejected text. Ordered so the
# generated strings read consistently across commits.
_KPI_KEYS_ORDER: tuple[str, ...] = (
    "makespan_hours",
    "total_tardiness_hours",
    "setups",
    "throughput_eur_day",
    "quality_risk_score",
    "avg_utilization",
    "num_late_orders",
)

# Friendly labels for the LLM's reading side.
_KPI_LABELS: Dict[str, str] = {
    "makespan_hours": "makespan (h)",
    "total_tardiness_hours": "atraso total (h)",
    "setups": "setups",
    "throughput_eur_day": "throughput (€/dia)",
    "quality_risk_score": "risco de qualidade",
    "avg_utilization": "utilização média (%)",
    "num_late_orders": "ordens atrasadas",
}


@dataclass
class DPOTriplet:
    """Typed wrapper around one JSONL line.

    Kept as a dataclass so tests can assert structure without juggling
    dict keys, and so the (future) HuggingFace converter has a typed
    object to hang annotations off.
    """
    prompt: str
    chosen: str
    rejected: str
    meta: Dict[str, Any]

    def to_json(self) -> Dict[str, Any]:
        return {
            "prompt": self.prompt,
            "chosen": self.chosen,
            "rejected": self.rejected,
            "meta": self.meta,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Text rendering helpers
# ═══════════════════════════════════════════════════════════════════════════


def _format_kpis(kpis: Mapping[str, Any]) -> str:
    """Render a KPI dict as a ``- label: value`` bullet list.

    Missing KPIs are skipped silently so one commit can omit fields
    that the schema has, and the triplet still reads cleanly.
    """
    lines: List[str] = []
    for key in _KPI_KEYS_ORDER:
        if key not in kpis or kpis[key] is None:
            continue
        value = kpis[key]
        if isinstance(value, float):
            formatted = f"{value:.1f}"
        else:
            formatted = str(value)
        lines.append(f"- {_KPI_LABELS.get(key, key)}: {formatted}")
    return "\n".join(lines) if lines else "- (sem KPIs registados)"


PROMPT_TEMPLATE = """\
Tu és o escalonador da fábrica NELO. Recebes duas propostas de plano de produção
para a mesma janela e as mesmas ordens em aberto. Indica qual preferes e
explica em uma frase.

Plano A:
{plan_a}

Plano B:
{plan_b}

Responde no formato "Prefiro o plano X: <razão>".
"""


def build_prompt(chosen_kpis: Mapping[str, Any], rejected_kpis: Mapping[str, Any]) -> str:
    """Render the standard DPO prompt for one (chosen, rejected) pair."""
    return PROMPT_TEMPLATE.format(
        plan_a=_format_kpis(chosen_kpis),
        plan_b=_format_kpis(rejected_kpis),
    )


def _choice_text(label: str, reason: Optional[str]) -> str:
    core = f"Prefiro o plano {label}"
    if reason:
        return f"{core}: {reason.strip().rstrip('.')}."
    return f"{core}."


# ═══════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class DPOBuildReport:
    """Summary returned by :meth:`DPODatasetBuilder.build`."""
    commits_scanned: int
    commits_used: int
    triplets_emitted: int
    skipped_empty_rejections: int
    output_path: Optional[str] = None


class DPODatasetBuilder:
    """Walk recent ``ScheduleCommit`` rows and emit DPO-ready
    triplets.

    ``min_reason_len`` guards against noise. Sprint R.2 lifted the
    default from 0 to 10: the cpo/decide endpoint now refuses
    rejections without a ≥10-char rationale, so any commit produced
    after R.2 has a real reason to train on. Callers that want to
    inspect raw history (debugging, ad-hoc analytics) can drop the
    bar back to 0 explicitly.
    """

    DEFAULT_MIN_REASON_LEN = 10

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        min_reason_len: int = DEFAULT_MIN_REASON_LEN,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.min_reason_len = max(0, int(min_reason_len))

    # ─── Public entry ──────────────────────────────────────────────────

    async def build(
        self,
        *,
        window_days: int = 90,
        output_path: Optional[Path] = None,
    ) -> DPOBuildReport:
        """Fetch commits → emit triplets → optionally write to JSONL.

        Returns a :class:`DPOBuildReport`. When ``output_path`` is
        ``None`` the triplets are *only* returned via
        :meth:`build_to_list` — use that entry point in tests.
        """
        triplets, commits_scanned, commits_used, skipped = await self._collect(
            window_days=window_days,
        )
        output_str: Optional[str] = None
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_jsonl(triplets, output_path)
            output_str = str(output_path)
            logger.info(
                "dpo_dataset: tenant=%s wrote %d triplets to %s "
                "(from %d commits)",
                self.tenant_id, len(triplets), output_path, commits_used,
            )
        return DPOBuildReport(
            commits_scanned=commits_scanned,
            commits_used=commits_used,
            triplets_emitted=len(triplets),
            skipped_empty_rejections=skipped,
            output_path=output_str,
        )

    async def build_to_list(
        self,
        *,
        window_days: int = 90,
    ) -> List[DPOTriplet]:
        """Same as :meth:`build` but returns the triplets in memory —
        useful for tests and for small dataset inspection."""
        triplets, *_ = await self._collect(window_days=window_days)
        return triplets

    # ─── Internals ─────────────────────────────────────────────────────

    async def _collect(
        self, *, window_days: int,
    ) -> tuple[List[DPOTriplet], int, int, int]:
        since = datetime.now(timezone.utc) - timedelta(days=window_days)
        stmt = (
            select(ScheduleCommit)
            .where(
                and_(
                    ScheduleCommit.tenant_id == self.tenant_id,
                    ScheduleCommit.created_at >= since,
                )
            )
            .order_by(ScheduleCommit.created_at.asc())
        )
        rows = list((await self.session.execute(stmt)).scalars().all())

        triplets: List[DPOTriplet] = []
        commits_used = 0
        skipped_empty = 0

        for commit in rows:
            rejected_list = commit.rejected_alternatives or []
            if not rejected_list:
                skipped_empty += 1
                continue
            signal = commit.user_preference_signal or {}
            reason = signal.get("reason") if isinstance(signal, Mapping) else None
            if self.min_reason_len > 0 and (
                not isinstance(reason, str) or len(reason.strip()) < self.min_reason_len
            ):
                skipped_empty += 1
                continue

            chosen_kpis = commit.kpis or {}
            commit_used_this_row = False
            for idx, rejected in enumerate(rejected_list):
                rejected_kpis = (
                    rejected.get("kpis") if isinstance(rejected, Mapping) else None
                )
                if not isinstance(rejected_kpis, Mapping) or not rejected_kpis:
                    continue

                prompt = build_prompt(chosen_kpis, rejected_kpis)
                chosen = _choice_text("A", reason if isinstance(reason, str) else None)
                rejected_text = _choice_text("B", None)

                triplets.append(DPOTriplet(
                    prompt=prompt,
                    chosen=chosen,
                    rejected=rejected_text,
                    meta={
                        "commit_sha": (commit.commit_sha256 or "")[:12],
                        "decided_by": signal.get("decided_by")
                            if isinstance(signal, Mapping) else None,
                        "weekday": signal.get("weekday")
                            if isinstance(signal, Mapping) else None,
                        "alt_idx": rejected.get("alt_idx", idx)
                            if isinstance(rejected, Mapping) else idx,
                        "reason": reason if isinstance(reason, str) else None,
                        "created_at": (
                            commit.created_at.isoformat()
                            if commit.created_at else None
                        ),
                    },
                ))
                commit_used_this_row = True
            if commit_used_this_row:
                commits_used += 1
            else:
                skipped_empty += 1

        return triplets, len(rows), commits_used, skipped_empty

    @staticmethod
    def _write_jsonl(triplets: Iterable[DPOTriplet], path: Path) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for triplet in triplets:
                fh.write(json.dumps(triplet.to_json(), ensure_ascii=False))
                fh.write("\n")


__all__ = [
    "DPOBuildReport",
    "DPODatasetBuilder",
    "DPOTriplet",
    "build_prompt",
]
