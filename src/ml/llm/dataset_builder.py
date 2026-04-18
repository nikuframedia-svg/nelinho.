"""
ProdPlan ONE - Fine-tune Dataset Builder (Sprint S.5)
========================================================

Synthesises instruction-tuning examples from real NELO data via the
in-memory semantic queries. No LLM call: each example is a template-filled
Q/A pair so the dataset is deterministic and reproducible across runs.

The output is JSONL — the format every QLoRA / Unsloth trainer accepts.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SyntheticExample:
    """One (instruction, input, output) triple — Alpaca-compatible shape."""

    instruction: str
    input: str
    output: str
    meta: dict

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class DatasetBuilder:
    """Build a synthetic instruction dataset from real NELO semantic data."""

    def __init__(self, semantic_service: Any = None) -> None:
        self.semantic = semantic_service

    # ─── Public API ───────────────────────────────────────────────────────

    def build(
        self,
        *,
        max_per_topic: int = 50,
        topics: Optional[List[str]] = None,
    ) -> List[SyntheticExample]:
        topics = topics or self.default_topics()
        examples: List[SyntheticExample] = []
        for topic in topics:
            producer = getattr(self, f"_build_{topic}", None)
            if producer is None:
                logger.warning("DatasetBuilder: unknown topic %s", topic)
                continue
            try:
                examples.extend(list(producer(max_per_topic)))
            except Exception as exc:  # pragma: no cover — defensive
                logger.warning("DatasetBuilder topic=%s failed: %s", topic, exc)
        return examples

    def write_jsonl(self, examples: Iterable[SyntheticExample], path: Path) -> int:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with path.open("w", encoding="utf-8") as f:
            for ex in examples:
                f.write(ex.to_jsonl() + "\n")
                count += 1
        logger.info("DatasetBuilder: wrote %d examples to %s", count, path)
        return count

    @staticmethod
    def default_topics() -> List[str]:
        return ["bottlenecks", "wip", "quality", "lead_time"]

    # ─── Topic producers ──────────────────────────────────────────────────

    def _build_bottlenecks(self, limit: int) -> Iterable[SyntheticExample]:
        rows = self._call_semantic("get_bottlenecks")
        if not rows:
            return []
        bottlenecks = (rows.get("bottlenecks") or [])[:limit]
        for b in bottlenecks:
            phase = b.get("phase_name") or b.get("fase_id")
            severity = b.get("severity", "MEDIUM")
            backlog = b.get("backlog_dias") or b.get("backlog_horas")
            yield SyntheticExample(
                instruction="Explica o gargalo actual em {fase} em 2 frases.".format(fase=phase),
                input=f"severidade={severity} backlog={backlog}",
                output=(
                    f"A fase {phase} está classificada como {severity.lower()} "
                    f"com backlog de {backlog} — priorizar realocação imediata "
                    f"de operadores e verificar disponibilidade de moldes."
                ),
                meta={"topic": "bottlenecks", "fase": phase},
            )

    def _build_wip(self, limit: int) -> Iterable[SyntheticExample]:
        rows = self._call_semantic("get_wip")
        if not rows:
            return []
        open_orders = rows.get("open_orders_pct")
        total = rows.get("total_orders")
        yield SyntheticExample(
            instruction="Descreve o estado do WIP em frases curtas.",
            input=f"open_pct={open_orders} total={total}",
            output=(
                f"Cerca de {open_orders}% das {total} ordens de fabrico estão "
                f"em curso. Sugere foco nas fases com backlog > 5 dias."
            ),
            meta={"topic": "wip"},
        )

    def _build_quality(self, limit: int) -> Iterable[SyntheticExample]:
        rows = self._call_semantic("get_quality")
        if not rows:
            return []
        top = (rows.get("top_items") or [])[:limit]
        for entry in top:
            error_name = entry.get("erro_tipo") or entry.get("name") or "erro"
            count = entry.get("count") or entry.get("total_erros") or 0
            phase = entry.get("fase_culpada") or entry.get("phase") or "?"
            yield SyntheticExample(
                instruction=(
                    "Recomenda uma acção preventiva para o erro '{err}' "
                    "na fase '{ph}'."
                ).format(err=error_name, ph=phase),
                input=f"count={count}",
                output=(
                    f"Fluxo recomendado: (1) auditar molde/ferramenta da fase "
                    f"{phase}, (2) reforçar checklist do operador responsável, "
                    f"(3) agendar manutenção preventiva se erro persistir."
                ),
                meta={"topic": "quality", "error": error_name, "phase": phase},
            )

    def _build_lead_time(self, limit: int) -> Iterable[SyntheticExample]:
        rows = self._call_semantic("get_lead_time")
        if not rows:
            return []
        avg = rows.get("avg_lead_time_days")
        p90 = rows.get("p90_lead_time_days")
        yield SyntheticExample(
            instruction="Resume o lead-time observado em 2 frases.",
            input=f"avg={avg} p90={p90}",
            output=(
                f"Lead-time médio: {avg} dias, com P90 em {p90}. "
                f"Gaps acima da mediana concentram-se nas fases com queue-time elevado."
            ),
            meta={"topic": "lead_time"},
        )

    # ─── Private helpers ──────────────────────────────────────────────────

    def _call_semantic(self, method: str) -> dict:
        if self.semantic is None:
            return {}
        fn = getattr(self.semantic, method, None)
        if fn is None:
            return {}
        try:
            return fn() or {}
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("semantic.%s failed: %s", method, exc)
            return {}
