"""Sprint R.5.1 — Dataset mixer (DPO + ABL → stratified JSONL).

Covers:
* Empty inputs produce an empty manifest, no crash.
* DPO-only and ABL-only paths still work.
* Mixed inputs are stratified — a dominant category cannot exceed
  the cap_ratio.
* Manifest records SHA-256 of every source file.
* Stratification is deterministic for a given seed.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.governance.preference_learning.dataset_mixer import (
    MixerManifest,
    discover_abl_files,
    mix_datasets,
)


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False))
            fh.write("\n")


def _dpo_row(category: str, idx: int) -> dict:
    return {
        "prompt": f"Plano A vs Plano B (cat={category}, idx={idx})",
        "chosen": "Prefiro o plano A: razão clara e completa.",
        "rejected": "Prefiro o plano B: motivo qualquer.",
        "meta": {
            "source": "dpo",
            "rejection_category": category,
            "alt_idx": idx,
        },
    }


def _abl_row(layer: str, idx: int) -> dict:
    return {
        "prompt": f"Pergunta {idx}\nKPI alvo: makespan_hours",
        "chosen": "Resposta certa do kernel.",
        "rejected": "Resposta errada do LLM.",
        "meta": {
            "source": "ablkit",
            "layer": layer,
            "severity": "major",
        },
    }


def test_empty_inputs_produce_empty_manifest(tmp_path: Path):
    out = tmp_path / "mix.jsonl"
    manifest = mix_datasets(
        dpo_paths=[], abl_paths=[], output_path=out, seed=7,
    )
    assert isinstance(manifest, MixerManifest)
    assert manifest.triplets_total == 0
    assert manifest.sources == []
    assert out.exists()  # empty file still created
    assert out.read_text(encoding="utf-8") == ""


def test_dpo_only_path(tmp_path: Path):
    dpo_path = tmp_path / "dpo.jsonl"
    _write_jsonl(dpo_path, [_dpo_row("CUSTOMER", i) for i in range(3)])
    out = tmp_path / "mix.jsonl"

    manifest = mix_datasets(
        dpo_paths=[dpo_path], abl_paths=[], output_path=out, seed=42,
    )

    assert manifest.triplets_total == 3
    assert manifest.by_kind == {"dpo": 3}
    assert manifest.sources[0].kind == "dpo"
    assert len(manifest.sources[0].sha256) == 64

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3


def test_mixed_dpo_and_abl(tmp_path: Path):
    dpo_path = tmp_path / "dpo.jsonl"
    abl_path = tmp_path / "abl.jsonl"
    _write_jsonl(dpo_path, [_dpo_row("CUSTOMER", i) for i in range(5)])
    _write_jsonl(abl_path, [_abl_row("kernel", i) for i in range(5)])
    out = tmp_path / "mix.jsonl"

    manifest = mix_datasets(
        dpo_paths=[dpo_path], abl_paths=[abl_path], output_path=out, seed=42,
    )

    assert manifest.triplets_total == 10
    assert manifest.by_kind["dpo"] == 5
    assert manifest.by_kind["ablkit"] == 5
    assert "CUSTOMER" in manifest.by_category
    assert "ABL_KERNEL" in manifest.by_category


def test_dominant_category_is_capped(tmp_path: Path):
    """A category contributing >40% of the raw input must be down-sampled."""
    dpo_path = tmp_path / "dpo.jsonl"
    rows = (
        [_dpo_row("CUSTOMER", i) for i in range(80)]
        + [_dpo_row("QUALITY", i) for i in range(10)]
        + [_dpo_row("MOLD", i) for i in range(10)]
    )
    _write_jsonl(dpo_path, rows)
    out = tmp_path / "mix.jsonl"

    manifest = mix_datasets(
        dpo_paths=[dpo_path], abl_paths=[], output_path=out, seed=1,
    )

    customer = manifest.by_category.get("CUSTOMER", 0)
    # Cap is 40% of 100 = 40; CUSTOMER must NOT exceed that.
    assert customer <= 40
    # Other categories survive intact.
    assert manifest.by_category.get("QUALITY", 0) == 10
    assert manifest.by_category.get("MOLD", 0) == 10


def test_manifest_is_written_alongside_jsonl(tmp_path: Path):
    dpo_path = tmp_path / "dpo.jsonl"
    _write_jsonl(dpo_path, [_dpo_row("COST", i) for i in range(2)])
    out = tmp_path / "ds.jsonl"

    manifest = mix_datasets(
        dpo_paths=[dpo_path], abl_paths=[], output_path=out, seed=1,
    )

    manifest_path = out.with_suffix(out.suffix + ".manifest.json")
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["output_path"] == str(out)
    assert payload["triplets_total"] == manifest.triplets_total
    assert isinstance(payload["sources"], list)
    assert payload["sources"][0]["sha256"]


def test_seed_makes_sampling_deterministic(tmp_path: Path):
    dpo_path = tmp_path / "dpo.jsonl"
    rows = [_dpo_row("CUSTOMER", i) for i in range(60)]
    _write_jsonl(dpo_path, rows)

    out_a = tmp_path / "mix_a.jsonl"
    out_b = tmp_path / "mix_b.jsonl"

    mix_datasets(dpo_paths=[dpo_path], abl_paths=[], output_path=out_a, seed=99)
    mix_datasets(dpo_paths=[dpo_path], abl_paths=[], output_path=out_b, seed=99)

    assert out_a.read_text(encoding="utf-8") == out_b.read_text(encoding="utf-8")


def test_discover_abl_files_handles_missing_dir(tmp_path: Path):
    nonexistent = tmp_path / "does_not_exist"
    assert discover_abl_files(nonexistent) == []

    real = tmp_path / "abl"
    real.mkdir()
    (real / "2026-04-25.jsonl").write_text("{}", encoding="utf-8")
    (real / "2026-04-26.jsonl").write_text("{}", encoding="utf-8")
    found = discover_abl_files(real)
    assert len(found) == 2
    assert all(p.suffix == ".jsonl" for p in found)
