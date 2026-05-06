"""Tests for OFCH_GRAVIDADE → severity mapping (Sprint Q.8).

CEO confirmed 2026-04-26 that all 3 gravity levels in the NELO ERP
count as defects. The transformer translates the integer gravity into
a string severity ("low"/"medium"/"high") so downstream models can
keep using the existing string enum.

Onda 3.4 — module relocated from `curated_transformer.py` (now deleted)
to `gravidade.py`. The integration test that exercised the deleted
`CuratedTransformer._transform_erros` was removed; the active path is
now `RawToCuratedTransformer._transform_quality_events` which is covered
by `src/factory_data_product/tests/test_factory.py`.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.factory_data_product.ingest.gravidade import (
    GRAVIDADE_TO_SEVERITY,
    map_gravidade_to_severity,
)
from src.factory_data_product.ingest.transformer import RawToCuratedTransformer


def test_gravidade_mapping_table_matches_ceo_confirmation():
    """1=low (84% of rows), 2=medium (14%), 3=high (2%)."""
    assert GRAVIDADE_TO_SEVERITY == {1: "low", 2: "medium", 3: "high"}


@pytest.mark.parametrize(
    "raw, expected",
    [
        (1, "low"),
        (2, "medium"),
        (3, "high"),
        ("1", "low"),  # ERP can return strings
        ("2", "medium"),
        (None, "medium"),  # missing → safe default
        ("", "medium"),
        (99, "medium"),  # unknown values → safe default
        ("not_a_number", "medium"),
    ],
)
def test_map_gravidade_to_severity(raw, expected):
    assert map_gravidade_to_severity(raw) == expected


def test_transform_quality_events_uses_gravidade_mapping():
    """End-to-end: the wired transformer translates OFCH_GRAVIDADE into
    `erro_tipo` via the shared mapping."""
    ingestion_id = uuid4()
    raw_rows = [
        {
            "sheet_name": "OrdemFabricoErros",
            "row_number": r,
            "payload_json": {
                "Erro_OfId": str(r),
                "Erro_Descricao": "x",
                "OFCH_GRAVIDADE": grav,
            },
        }
        for r, grav in enumerate([1, 2, 3, None], start=2)
    ]
    result = RawToCuratedTransformer().transform(raw_rows, ingestion_id)
    erro_tipos = [e["erro_tipo"] for e in result.quality_events]
    # 1→low, 2→medium, 3→high; missing gravity → "unknown" (transformer
    # short-circuits before the mapping, see _transform_quality_events).
    assert erro_tipos == ["low", "medium", "high", "unknown"]
