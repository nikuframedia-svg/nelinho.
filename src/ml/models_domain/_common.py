"""
Shared helpers for the Sprint H models.

- `FeatureVector`: shape-safe wrapper around a list-of-dicts training set.
- `encode_categoricals`: stable one-hot encoding using a provided vocabulary.
- `wmape`: weighted mean absolute percentage error (used by Duration model).
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

import numpy as np


def encode_categoricals(
    rows: Sequence[Dict[str, Any]],
    categorical_cols: Sequence[str],
    numeric_cols: Sequence[str],
    vocabulary: Dict[str, List[str]] = None,
) -> Tuple[np.ndarray, Dict[str, List[str]]]:
    """
    One-hot encode `categorical_cols` and concatenate with `numeric_cols`.

    If `vocabulary` is None (training time), the vocabulary is inferred from
    the rows and returned alongside the matrix — callers persist it in the
    model metadata so predictions see the same columns.

    Unknown categorical values at inference time are encoded as all zeros
    (their dimension is just absent from the row's one-hot vector).
    """
    inferred = vocabulary is None
    vocab: Dict[str, List[str]] = {} if inferred else {k: list(v) for k, v in vocabulary.items()}

    if inferred:
        for col in categorical_cols:
            values = sorted({str(r.get(col, "")) for r in rows})
            vocab[col] = values

    n_rows = len(rows)
    n_cols = sum(len(vocab[c]) for c in categorical_cols) + len(numeric_cols)
    X = np.zeros((n_rows, n_cols), dtype=np.float64)

    for i, row in enumerate(rows):
        col_offset = 0
        for cat in categorical_cols:
            values = vocab[cat]
            value = str(row.get(cat, ""))
            if value in values:
                X[i, col_offset + values.index(value)] = 1.0
            col_offset += len(values)
        for num in numeric_cols:
            raw = row.get(num, 0.0)
            try:
                X[i, col_offset] = float(raw) if raw is not None else 0.0
            except (TypeError, ValueError):
                X[i, col_offset] = 0.0
            col_offset += 1

    return X, vocab


def wmape(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """
    Weighted Mean Absolute Percentage Error — robust to zeros in y_true.

    WMAPE = sum(|y_true - y_pred|) / sum(|y_true|)
    """
    y_true_arr = np.asarray(y_true, dtype=np.float64)
    y_pred_arr = np.asarray(y_pred, dtype=np.float64)
    denom = float(np.abs(y_true_arr).sum())
    if denom == 0.0:
        return 0.0
    return float(np.abs(y_true_arr - y_pred_arr).sum() / denom)
