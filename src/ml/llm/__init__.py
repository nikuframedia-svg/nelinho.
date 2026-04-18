"""
ProdPlan ONE - LLM Fine-Tuning Pipeline (Sprint S.5)
======================================================

Blueprint v2.0 §4.1 + §5.1 require:
  * Base model: Qwen2.5-7B / Gemma-3-8B
  * Method: QLoRA via Unsloth (2x speedup, 30-50% less VRAM)
  * Dataset: synthetic Q/A from NELO data
  * Registry: re-use the Sprint G ModelRegistry for adapter versioning

Unsloth + PyTorch live outside `requirements-test.txt` so the trainer
runs off-process (subprocess) in production and the modules here stay
importable without the heavy deps.
"""

from .dataset_builder import DatasetBuilder, SyntheticExample
from .promoter import LLMAdapterPromoter
from .qlora_trainer import QLoRATrainer, QLoRATrainingConfig

__all__ = [
    "DatasetBuilder",
    "SyntheticExample",
    "QLoRATrainer",
    "QLoRATrainingConfig",
    "LLMAdapterPromoter",
]
