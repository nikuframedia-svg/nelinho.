"""
ProdPlan ONE — Dataset Mixer (Sprint R.5.1, Camada 3)
=======================================================

Combines DPO triplets (Camada 3 source) with ABLkit triplets
(Camada 4 source) into a single stratified JSONL file the on-prem
QLoRA fine-tuner consumes. Pure I/O — no LLM calls, no GPU.

Why mix
-------

* DPO pairs come from operator decisions on schedule alternatives —
  rich, factory-specific signal but expensive (one needs the operator
  to actually decide).
* ABL pairs come from kernel-vs-LLM disagreements — abundant, cheap
  to harvest, but biased toward the LLM's failure modes.

Mixing both with a deterministic seed gives the trainer balanced
exposure. The output manifest records SHA-256 of every source file
plus per-bucket counts so a later evaluation can prove which version
trained which adapter.

Output layout
-------------

::

    data/learning/datasets/
        dataset_2026-04-25.jsonl      # one triplet per line
        dataset_2026-04-25.manifest.json  # provenance record

Both files share the date stem so the eval/promote workflow can
collapse them into one bundle.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

logger = logging.getLogger(__name__)


# Default categories the stratification preserves when sampling. The
# mix never collapses to a single category, even if one dominates the
# raw input; over-represented categories are downsampled to the cap.
_CATEGORY_CAP_RATIO = 0.40


@dataclass
class DatasetSource:
    """One JSONL file pulled into the mix."""

    path: str
    kind: str            # "dpo" | "abl"
    sha256: str
    triplets: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MixerManifest:
    """Audit record written next to the mixed JSONL."""

    output_path: str
    triplets_total: int
    by_kind: Dict[str, int]
    by_category: Dict[str, int]
    sources: List[DatasetSource]
    seed: int
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "sources": [s.to_dict() for s in self.sources],
        }


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                if isinstance(payload, dict):
                    rows.append(payload)
            except json.JSONDecodeError:
                logger.warning("dataset_mixer: skipping malformed line in %s", path)
    return rows


def _category_of(triplet: Mapping[str, Any]) -> str:
    """Derive a stratification category from the triplet meta.

    DPO triplets carry ``meta.category`` or a ``[CAT:X]``-prefixed
    reason. ABL triplets carry ``meta.layer`` (kernel/direction/nli/
    dag_consistent). Unknown sources fall into ``OTHER`` so the mixer
    still stratifies cleanly.
    """
    meta = triplet.get("meta") if isinstance(triplet.get("meta"), Mapping) else {}
    cat = meta.get("category") or meta.get("rejection_category")
    if isinstance(cat, str) and cat:
        return cat.upper()
    layer = meta.get("layer")
    if isinstance(layer, str) and layer:
        return f"ABL_{layer.upper()}"
    reason = meta.get("reason")
    if isinstance(reason, str) and reason.startswith("[CAT:"):
        end = reason.find("]")
        if end > 5:
            return reason[5:end].upper()
    return "OTHER"


_CAP_FLOOR = 5  # categories with ≤ floor rows are never capped


def _stratified_sample(
    triplets: List[Dict[str, Any]],
    *,
    seed: int,
    cap_ratio: float = _CATEGORY_CAP_RATIO,
) -> List[Dict[str, Any]]:
    """Down-sample any category contributing more than ``cap_ratio``
    of the dataset. Prevents one chatty category from drowning out
    the others — the trainer sees broad coverage even when DPO data
    is dominated by, say, CUSTOMER rejections.

    Cap is skipped when there's only one category (no diversity to
    preserve) or when a category sits at or below ``_CAP_FLOOR`` rows
    (small samples are kept whole — sampling them adds variance, not
    fairness).
    """
    if not triplets:
        return []
    rng = random.Random(seed)
    by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in triplets:
        by_category[_category_of(t)].append(t)

    if len(by_category) <= 1:
        out = list(triplets)
        rng.shuffle(out)
        return out

    cap = max(_CAP_FLOOR, int(len(triplets) * cap_ratio))
    selected: List[Dict[str, Any]] = []
    for cat, rows in by_category.items():
        if len(rows) > cap:
            rng.shuffle(rows)
            selected.extend(rows[:cap])
        else:
            selected.extend(rows)
    rng.shuffle(selected)
    return selected


def mix_datasets(
    *,
    dpo_paths: Iterable[Path],
    abl_paths: Iterable[Path],
    output_path: Path,
    seed: int = 42,
    cap_ratio: float = _CATEGORY_CAP_RATIO,
) -> MixerManifest:
    """Read DPO + ABL JSONL files, stratify, write mixed JSONL + manifest.

    Returns the manifest so the caller can log counts. The manifest
    is also written to ``{output_path}.manifest.json``.
    """
    dpo_paths = [Path(p) for p in dpo_paths]
    abl_paths = [Path(p) for p in abl_paths]

    sources: List[DatasetSource] = []
    all_rows: List[Dict[str, Any]] = []

    for path in dpo_paths:
        rows = _read_jsonl(path)
        for r in rows:
            r.setdefault("meta", {})
            if isinstance(r["meta"], dict):
                r["meta"].setdefault("source", "dpo")
        all_rows.extend(rows)
        if path.exists():
            sources.append(DatasetSource(
                path=str(path),
                kind="dpo",
                sha256=_sha256_of_file(path),
                triplets=len(rows),
            ))

    for path in abl_paths:
        rows = _read_jsonl(path)
        for r in rows:
            r.setdefault("meta", {})
            if isinstance(r["meta"], dict):
                r["meta"].setdefault("source", "abl")
        all_rows.extend(rows)
        if path.exists():
            sources.append(DatasetSource(
                path=str(path),
                kind="abl",
                sha256=_sha256_of_file(path),
                triplets=len(rows),
            ))

    sampled = _stratified_sample(all_rows, seed=seed, cap_ratio=cap_ratio)

    by_kind: Dict[str, int] = defaultdict(int)
    by_category: Dict[str, int] = defaultdict(int)
    for r in sampled:
        kind = (r.get("meta", {}) or {}).get("source", "unknown")
        by_kind[str(kind)] += 1
        by_category[_category_of(r)] += 1

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for r in sampled:
            fh.write(json.dumps(r, ensure_ascii=False))
            fh.write("\n")

    manifest = MixerManifest(
        output_path=str(output_path),
        triplets_total=len(sampled),
        by_kind=dict(by_kind),
        by_category=dict(by_category),
        sources=sources,
        seed=seed,
    )
    manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
    with manifest_path.open("w", encoding="utf-8") as fh:
        json.dump(manifest.to_dict(), fh, ensure_ascii=False, indent=2)

    logger.info(
        "dataset_mixer: wrote %d triplets to %s (sources=%d, by_kind=%s)",
        len(sampled), output_path, len(sources), dict(by_kind),
    )
    return manifest


def discover_abl_files(root: Path = Path("data/learning/abl_triplets")) -> List[Path]:
    """List every ``*.jsonl`` ABL file under ``root`` (sorted)."""
    root = Path(root)
    if not root.exists():
        return []
    return sorted(root.glob("*.jsonl"))


__all__ = [
    "DatasetSource",
    "MixerManifest",
    "discover_abl_files",
    "mix_datasets",
]
