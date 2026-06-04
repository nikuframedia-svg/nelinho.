"""Coerções partilhadas (saneamento — dedup).

`safe_float` estava duplicado em 6 ficheiros (copilot/ask_cube, ml/jobs/base,
ml/models/promotion, ml/models_domain/{duration,otd_risk,quality_risk}) — todas
comportamentalmente idênticas. Casa única aqui (shared = base layer; import-linter
Contract 1 só proíbe shared→domínios, não o reverso).
"""

from __future__ import annotations

from typing import Any, Optional


def safe_float(value: Any) -> Optional[float]:
    """`float(value)` tolerante: `None` ou inválido → `None` (nunca levanta)."""
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Limita `value` ao intervalo `[lo, hi]` (default `[0, 1]`).

    Estava duplicado em 4 jobs do scheduler + dqa/trust_v2 (este como caso
    especial sem `lo`/`hi`, equivalente ao default).
    """
    return max(lo, min(hi, value))
