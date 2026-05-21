"""Sprint R.5.2 — DPO fine-tune runner CLI (smoke path).

Validates the runner's I/O wiring without loading any model. Uses
``--smoke`` semantics: load triplets → split → write report. The real
QLoRA training is exercised on-prem with GPU; here we only confirm
the report is written and counts are right.
"""

from __future__ import annotations

import json
from pathlib import Path

# Add scripts/ to sys.path for the test import.
import sys
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from dpo_finetune import (
    FineTuneReport,
    load_triplets,
    run_finetune,
    split_train_eval,
)


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False))
            fh.write("\n")


def _row(idx: int) -> dict:
    return {
        "prompt": f"Prompt {idx}",
        "chosen": "Resposta certa.",
        "rejected": "Resposta errada.",
        "meta": {"alt_idx": idx},
    }


def test_load_triplets_skips_malformed_rows(tmp_path: Path):
    p = tmp_path / "ds.jsonl"
    p.write_text(
        "{ not json\n"
        + json.dumps(_row(0)) + "\n"
        + json.dumps({"prompt": "p"}) + "\n"  # missing chosen/rejected
        + json.dumps(_row(1)) + "\n",
        encoding="utf-8",
    )
    rows = load_triplets(p, max_pairs=10)
    assert len(rows) == 2
    assert rows[0]["meta"]["alt_idx"] == 0
    assert rows[1]["meta"]["alt_idx"] == 1


def test_load_triplets_respects_max_pairs(tmp_path: Path):
    p = tmp_path / "ds.jsonl"
    _write_jsonl(p, [_row(i) for i in range(20)])
    rows = load_triplets(p, max_pairs=5)
    assert len(rows) == 5


def test_split_train_eval_uses_eval_pct(tmp_path: Path):
    rows = [_row(i) for i in range(100)]
    train, eval_set = split_train_eval(rows, eval_pct=0.10, seed=1)
    assert len(eval_set) == 10
    assert len(train) == 90
    # No row appears in both halves.
    train_ids = {r["meta"]["alt_idx"] for r in train}
    eval_ids = {r["meta"]["alt_idx"] for r in eval_set}
    assert train_ids.isdisjoint(eval_ids)


def test_run_finetune_smoke_writes_report(tmp_path: Path):
    dataset = tmp_path / "dataset.jsonl"
    _write_jsonl(dataset, [_row(i) for i in range(30)])
    output = tmp_path / "adapter_v1"

    report = run_finetune(
        dataset_path=dataset,
        output_path=output,
        base_model="base/test",
        config={"max_pairs": 30, "eval_split_pct": 0.20},
        smoke=True,
    )
    assert isinstance(report, FineTuneReport)
    assert report.status == "ok"
    assert report.pairs_total == 30
    assert report.pairs_eval == 6
    assert report.pairs_train == 24
    assert report.metrics["mode"] == "smoke"

    # Audit file present.
    audit = output / "finetune_report.json"
    assert audit.exists()
    payload = json.loads(audit.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert payload["base_model"] == "base/test"
    assert payload["pairs_total"] == 30


def test_run_finetune_smoke_skipped_on_empty_dataset(tmp_path: Path):
    dataset = tmp_path / "empty.jsonl"
    dataset.write_text("", encoding="utf-8")
    output = tmp_path / "adapter_empty"

    report = run_finetune(
        dataset_path=dataset,
        output_path=output,
        base_model="base/test",
        config={},
        smoke=True,
    )
    assert report.status == "skipped"
    assert report.error == "empty_dataset"
    assert report.pairs_total == 0
