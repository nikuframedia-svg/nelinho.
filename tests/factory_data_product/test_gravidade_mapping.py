"""Tests for OFCH_GRAVIDADE → severity mapping (Sprint Q.8).

CEO confirmed 2026-04-26 that all 3 gravity levels in the NELO ERP
count as defects. The transformer translates the integer gravity into
a string severity ("low"/"medium"/"high") so downstream models can
keep using the existing string enum.
"""

from __future__ import annotations

import pytest

from src.factory_data_product.ingest.curated_transformer import (
    GRAVIDADE_TO_SEVERITY,
    CuratedTransformer,
    map_gravidade_to_severity,
)


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


def test_transform_erros_attaches_severity_and_raw():
    """The transformer adds `severity` (string) and `gravidade_raw`
    (preserves the original numeric for UI granularity)."""
    from unittest.mock import AsyncMock
    from uuid import uuid4

    transformer = CuratedTransformer(db=AsyncMock(), ingestion_id=uuid4())
    rows = [
        {"OrdemFabricoErro_Id": 1, "OFCH_GRAVIDADE": 1},
        {"OrdemFabricoErro_Id": 2, "OFCH_GRAVIDADE": 2},
        {"OrdemFabricoErro_Id": 3, "OFCH_GRAVIDADE": 3},
        {"OrdemFabricoErro_Id": 4},  # missing gravity
    ]
    out = transformer._transform_erros(rows)
    sev = [r["severity"] for r in out]
    raw = [r["gravidade_raw"] for r in out]
    assert sev == ["low", "medium", "high", "medium"]
    assert raw == [1, 2, 3, None]
