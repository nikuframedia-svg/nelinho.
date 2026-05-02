"""
ProdPlan ONE — DPO Fine-Tune Runner (Sprint R.5.2, Camada 3)
==============================================================

CLI that turns a stratified DPO dataset (built by ``dataset_mixer.py``)
into a QLoRA adapter on top of Gemma 4 8B. Runs **on-prem** on the
RTX 5060 Ti — no cloud, no Docker.

The runner is **idempotent and never auto-promotes**:

* Loads the base model in 4-bit nf4 (bitsandbytes).
* Applies a LoRA adapter (peft) on the attention projections.
* Runs ``trl.DPOTrainer`` with β=0.1, LR=5e-6, 3 epochs by default
  (all configurable via ConfigStore — see ``config/learning.fine_tune``).
* Writes the adapter weights to ``models/adapters/<version>/`` plus a
  ``finetune_report.json`` audit row.
* Promote is a separate, human-gated workflow (R.5.3) — the runner
  does **not** flip the active adapter.

Heavy ML deps (transformers, peft, trl, bitsandbytes, datasets) are
imported lazily so this module is safe to import on a laptop without
GPU. The ``--smoke`` flag short-circuits the actual training and just
exercises the I/O wiring — used by CI to confirm the runner is wired
without burning a GPU on every commit.

Usage::

    python scripts/dpo_finetune.py \\
        --dataset data/learning/datasets/dataset_2026-04-25.jsonl \\
        --output models/adapters/gemma4-8b-nelo-v2026-04-25 \\
        --base google/gemma-2-9b-it \\
        --epochs 3
    python scripts/dpo_finetune.py --smoke  # I/O wiring only
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Defaults — keep aligned with `config/learning.fine_tune` keys so the
# CLI overrides ConfigStore overrides hardcoded defaults in a single
# direction (CLI > ConfigStore > here).
DEFAULTS: Dict[str, Any] = {
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "learning_rate": 5e-6,
    "dpo_beta": 0.1,
    "epochs": 3,
    "batch_size": 4,
    "max_pairs": 5000,
    "eval_split_pct": 0.10,
    "max_prompt_length": 1024,
    "max_length": 2048,
}


@dataclass
class FineTuneReport:
    """Audit record persisted next to the adapter."""

    version: str
    base_model: str
    dataset_path: str
    adapter_path: str
    pairs_total: int
    pairs_train: int
    pairs_eval: int
    config: Dict[str, Any]
    started_at: str
    finished_at: Optional[str] = None
    status: str = "pending"            # "pending" | "ok" | "skipped" | "error"
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Data loading ────────────────────────────────────────────────────────


def load_triplets(dataset_path: Path, *, max_pairs: int) -> List[Dict[str, Any]]:
    """Read JSONL → list of triplets, drop malformed rows, cap to max_pairs."""
    rows: List[Dict[str, Any]] = []
    with dataset_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if "prompt" not in payload or "chosen" not in payload or "rejected" not in payload:
                continue
            rows.append(payload)
            if len(rows) >= max_pairs:
                break
    return rows


def split_train_eval(
    triplets: List[Dict[str, Any]],
    *,
    eval_pct: float,
    seed: int = 42,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Random shuffle + split. Eval set caps at 10% of the data."""
    import random

    if not triplets:
        return [], []
    rng = random.Random(seed)
    rng.shuffle(triplets)
    n_eval = max(1, int(len(triplets) * max(0.0, min(0.5, eval_pct))))
    return triplets[n_eval:], triplets[:n_eval]


# ─── Trainer ─────────────────────────────────────────────────────────────


def run_finetune(
    *,
    dataset_path: Path,
    output_path: Path,
    base_model: str,
    config: Dict[str, Any],
    smoke: bool = False,
) -> FineTuneReport:
    """Drive the QLoRA + DPO training pipeline.

    With ``smoke=True`` the loader + manifest are exercised but no
    GPU work happens — used by CI to keep the runner honest without
    pulling 16 GB of weights into the test path.
    """
    cfg = {**DEFAULTS, **(config or {})}
    started = datetime.now(timezone.utc)
    version = output_path.name or f"gemma4-8b-nelo-{started.date().isoformat()}"

    triplets = load_triplets(dataset_path, max_pairs=int(cfg["max_pairs"]))
    train, eval_set = split_train_eval(
        triplets,
        eval_pct=float(cfg["eval_split_pct"]),
    )

    report = FineTuneReport(
        version=version,
        base_model=base_model,
        dataset_path=str(dataset_path),
        adapter_path=str(output_path),
        pairs_total=len(triplets),
        pairs_train=len(train),
        pairs_eval=len(eval_set),
        config=cfg,
        started_at=started.isoformat(),
    )

    if not triplets:
        report.status = "skipped"
        report.error = "empty_dataset"
        report.finished_at = datetime.now(timezone.utc).isoformat()
        _write_report(output_path, report)
        return report

    if smoke:
        # I/O wiring only — confirm the runner can read, split, and
        # write the report without touching the GPU.
        report.status = "ok"
        report.finished_at = datetime.now(timezone.utc).isoformat()
        report.metrics = {"mode": "smoke", "loss_proxy": None}
        _write_report(output_path, report)
        return report

    try:
        metrics = _real_train(
            train=train, eval_set=eval_set,
            base_model=base_model, output_path=output_path, config=cfg,
        )
        report.status = "ok"
        report.metrics = metrics
    except ImportError as exc:
        report.status = "skipped"
        report.error = f"missing_dep:{exc}"
        logger.warning(
            "dpo_finetune: ML stack missing (%s). Install peft + trl + "
            "bitsandbytes + transformers + datasets to run real training.",
            exc,
        )
    except Exception as exc:  # pragma: no cover — keep training failures visible
        report.status = "error"
        report.error = str(exc)
        logger.error("dpo_finetune: training failed: %s", exc, exc_info=True)
    finally:
        report.finished_at = datetime.now(timezone.utc).isoformat()
        _write_report(output_path, report)
    return report


def _real_train(  # pragma: no cover — exercised on-prem with GPU
    *,
    train: List[Dict[str, Any]],
    eval_set: List[Dict[str, Any]],
    base_model: str,
    output_path: Path,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """The actual QLoRA + DPO training. Imports heavy deps lazily."""
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )
    from trl import DPOConfig, DPOTrainer

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=bnb_config,
        device_map="auto",
    )
    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=int(config["lora_r"]),
        lora_alpha=int(config["lora_alpha"]),
        lora_dropout=float(config["lora_dropout"]),
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    model = get_peft_model(model, lora_config)

    train_ds = Dataset.from_list(train)
    eval_ds = Dataset.from_list(eval_set) if eval_set else None

    output_path.mkdir(parents=True, exist_ok=True)
    # TRL 1.x removed `max_prompt_length` (only `max_length` survives) and
    # renamed `evaluation_strategy` → `eval_strategy`. The tokenizer arg
    # moved to `processing_class` on DPOTrainer.
    dpo_args = DPOConfig(
        output_dir=str(output_path),
        num_train_epochs=int(config["epochs"]),
        per_device_train_batch_size=int(config["batch_size"]),
        learning_rate=float(config["learning_rate"]),
        beta=float(config["dpo_beta"]),
        max_length=int(config["max_length"]),
        logging_steps=10,
        save_strategy="epoch",
        eval_strategy="epoch" if eval_ds else "no",
        report_to=[],
    )

    trainer = DPOTrainer(
        model=model,
        args=dpo_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        processing_class=tokenizer,
    )
    train_result = trainer.train()
    trainer.save_model(str(output_path))

    return {
        "train_loss": float(train_result.training_loss),
        "epochs": int(config["epochs"]),
        "samples": train_result.metrics.get("train_samples", len(train)),
    }


def _write_report(output_path: Path, report: FineTuneReport) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    report_path = output_path / "finetune_report.json"
    with report_path.open("w", encoding="utf-8") as fh:
        json.dump(report.to_dict(), fh, ensure_ascii=False, indent=2)


# ─── CLI entrypoint ─────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="DPO + QLoRA fine-tune runner (Sprint R.5.2)")
    p.add_argument("--dataset", type=Path, help="Path to mixed JSONL dataset")
    p.add_argument("--output", type=Path, help="Adapter output directory")
    p.add_argument("--base", default="google/gemma-2-9b-it", help="Base model id")
    p.add_argument("--epochs", type=int, default=DEFAULTS["epochs"])
    p.add_argument("--lr", type=float, default=DEFAULTS["learning_rate"])
    p.add_argument("--batch-size", type=int, default=DEFAULTS["batch_size"])
    p.add_argument("--max-pairs", type=int, default=DEFAULTS["max_pairs"])
    p.add_argument(
        "--smoke", action="store_true",
        help="Skip real training; exercise loader + report writing only.",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.dataset or not args.output:
        print("--dataset and --output are required", file=sys.stderr)
        return 2
    config = {
        "epochs": args.epochs,
        "learning_rate": args.lr,
        "batch_size": args.batch_size,
        "max_pairs": args.max_pairs,
    }
    report = run_finetune(
        dataset_path=args.dataset,
        output_path=args.output,
        base_model=args.base,
        config=config,
        smoke=args.smoke,
    )
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0 if report.status in {"ok", "skipped"} else 1


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
