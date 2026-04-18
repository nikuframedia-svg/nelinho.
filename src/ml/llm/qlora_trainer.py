"""
ProdPlan ONE - QLoRA Trainer (Sprint S.5)
==========================================

Thin wrapper around the `unsloth`/`transformers` training stack. The
actual training runs off-process (subprocess) so the main API pod doesn't
need to keep PyTorch + CUDA in memory.

When unsloth isn't installed we record a "dry run" result so the pipeline
stays introspectable (useful for tests + CI). Production callers install
unsloth in the GPU worker image.
"""

from __future__ import annotations

import json
import logging
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class QLoRATrainingConfig:
    dataset_path: Path
    output_dir: Path
    base_model: str = "Qwen/Qwen2.5-7B-Instruct"
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    max_seq_length: int = 2048
    epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    seed: int = 42


@dataclass
class QLoRATrainingResult:
    config: QLoRATrainingConfig
    status: str                          # "completed" | "dry_run" | "failed"
    started_at: datetime
    completed_at: Optional[datetime] = None
    adapter_path: Optional[Path] = None
    metrics: dict = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_model": self.config.base_model,
            "lora_r": self.config.lora_r,
            "lora_alpha": self.config.lora_alpha,
            "epochs": self.config.epochs,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "adapter_path": str(self.adapter_path) if self.adapter_path else None,
            "metrics": self.metrics,
            "error": self.error,
        }


class QLoRATrainer:
    """Launches QLoRA training in a subprocess."""

    def __init__(self, config: QLoRATrainingConfig) -> None:
        self.config = config

    def train(self) -> QLoRATrainingResult:
        started = datetime.now(timezone.utc)
        if not self.config.dataset_path.exists():
            return QLoRATrainingResult(
                config=self.config, status="failed",
                started_at=started,
                completed_at=datetime.now(timezone.utc),
                error=f"dataset_not_found: {self.config.dataset_path}",
            )

        if not _has_unsloth():
            logger.info("unsloth not installed — returning dry_run result")
            self.config.output_dir.mkdir(parents=True, exist_ok=True)
            (self.config.output_dir / "README.md").write_text(
                "# QLoRA dry run\n\nNo unsloth available. This folder is "
                "intentionally empty.\n",
                encoding="utf-8",
            )
            return QLoRATrainingResult(
                config=self.config,
                status="dry_run",
                started_at=started,
                completed_at=datetime.now(timezone.utc),
                adapter_path=self.config.output_dir,
                metrics={"dry_run": True},
            )

        try:
            metrics = self._run_subprocess()
        except Exception as exc:  # pragma: no cover — subprocess-only path
            return QLoRATrainingResult(
                config=self.config, status="failed",
                started_at=started,
                completed_at=datetime.now(timezone.utc),
                error=str(exc),
            )

        return QLoRATrainingResult(
            config=self.config,
            status="completed",
            started_at=started,
            completed_at=datetime.now(timezone.utc),
            adapter_path=self.config.output_dir,
            metrics=metrics,
        )

    def _run_subprocess(self) -> dict[str, Any]:  # pragma: no cover — GPU-only
        """Launch a child process — production-only. Tests take the dry-run path."""
        cmd = [
            sys.executable, "-m", "src.ml.llm.qlora_trainer",
            "--config", json.dumps({
                "dataset_path": str(self.config.dataset_path),
                "output_dir": str(self.config.output_dir),
                "base_model": self.config.base_model,
                "lora_r": self.config.lora_r,
                "lora_alpha": self.config.lora_alpha,
                "epochs": self.config.epochs,
                "batch_size": self.config.batch_size,
                "seed": self.config.seed,
            }),
        ]
        logger.info("QLoRA subprocess: %s", shlex.join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        try:
            return json.loads(result.stdout.strip().splitlines()[-1])
        except Exception:
            return {"raw_stdout_tail": result.stdout[-500:]}


def _has_unsloth() -> bool:
    try:
        import unsloth  # noqa: F401
    except Exception:
        return False
    return True
