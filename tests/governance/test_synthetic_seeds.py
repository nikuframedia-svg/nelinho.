"""Sprint S.3 — Guard the curated synthetic seeds set.

The seeds at ``data/learning/datasets/synthetic_seeds_v1.jsonl`` exist
to bootstrap Camada 3 when ``eligible_for_dpo`` is below the 500-pair
threshold. This test prevents accidental drift:

* Every row parses as JSON with the four required DPO fields.
* Every row carries ``meta.source = "synthetic_seed"`` so the mixer
  can stratify it correctly.
* The set covers all seven ``RejectionCategory`` values so a fine-tune
  that uses only seeds isn't skewed to one kind of decision.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.governance.preference_learning.dataset_mixer import mix_datasets


SEEDS_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "learning" / "datasets" / "synthetic_seeds_v1.jsonl"
)


def _load_rows():
    return [
        json.loads(line)
        for line in SEEDS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_synthetic_seeds_file_exists():
    assert SEEDS_PATH.exists(), f"missing seeds file at {SEEDS_PATH}"


def test_every_row_has_required_dpo_fields():
    rows = _load_rows()
    assert len(rows) >= 40, f"expected ≥40 seeds, found {len(rows)}"
    for i, row in enumerate(rows, start=1):
        for key in ("prompt", "chosen", "rejected", "meta"):
            assert key in row, f"row {i}: missing {key!r}"
        assert isinstance(row["meta"], dict), f"row {i}: meta must be dict"
        assert row["meta"].get("source") == "synthetic_seed", (
            f"row {i}: meta.source must equal 'synthetic_seed'"
        )


def test_seeds_cover_all_rejection_categories():
    """If a category has zero seeds the seed-only fine-tune is biased."""
    rows = _load_rows()
    categories = {r["meta"].get("category") for r in rows}
    expected = {
        "COST", "QUALITY", "CUSTOMER", "CAPACITY",
        "MOLD", "WORKFORCE", "OTHER",
    }
    missing = expected - categories
    assert not missing, f"seeds missing categories: {sorted(missing)}"


def test_no_dominant_category_above_50pct():
    """A category contributing >50% of seeds means the mixer cap will
    silently down-sample. Catch that at curation time."""
    from collections import Counter

    rows = _load_rows()
    counts = Counter(r["meta"].get("category") for r in rows)
    most_common, count = counts.most_common(1)[0]
    ratio = count / len(rows)
    assert ratio < 0.50, (
        f"category {most_common!r} is {ratio:.0%} of seeds — "
        "split it across more categories so the mixer keeps everything"
    )


def test_seeds_run_through_mixer_without_drift(tmp_path: Path):
    """End-to-end smoke: mixer reads our seeds file → JSONL output is
    valid JSONL → manifest records SHA-256 of the source."""
    out = tmp_path / "ds.jsonl"
    manifest = mix_datasets(
        dpo_paths=[SEEDS_PATH],
        abl_paths=[],
        output_path=out,
        seed=42,
    )
    assert manifest.triplets_total >= 40
    assert len(manifest.sources) == 1
    assert manifest.sources[0].kind == "dpo"
    assert len(manifest.sources[0].sha256) == 64

    lines = out.read_text(encoding="utf-8").splitlines()
    for line in lines:
        payload = json.loads(line)
        assert {"prompt", "chosen", "rejected", "meta"} <= set(payload.keys())
