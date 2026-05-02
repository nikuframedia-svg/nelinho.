"""Sprint Q.9 (3.2) — pagination guard."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.shared.pagination import MAX_LIMIT, validate_pagination


def test_valid_pagination_passes():
    validate_pagination(50, 0)
    validate_pagination(MAX_LIMIT, 200)


def test_limit_too_high_raises_400():
    with pytest.raises(HTTPException) as exc:
        validate_pagination(MAX_LIMIT + 1, 0)
    assert exc.value.status_code == 400
    assert "between 1 and" in exc.value.detail


def test_limit_zero_raises_400():
    with pytest.raises(HTTPException) as exc:
        validate_pagination(0, 0)
    assert exc.value.status_code == 400


def test_negative_offset_raises_400():
    with pytest.raises(HTTPException) as exc:
        validate_pagination(50, -1)
    assert exc.value.status_code == 400


def test_custom_max_limit_overrides_default():
    validate_pagination(20, 0, max_limit=20)
    with pytest.raises(HTTPException) as exc:
        validate_pagination(21, 0, max_limit=20)
    assert "between 1 and 20" in exc.value.detail
