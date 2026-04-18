"""
Tests for src.core.models.tenant_configuration (Sprint L.1).

Unit-only: validates the ORM surface without persistence. Roundtrip of the
JSONB envelope (`wrap` / `unwrap`), vocabulary sets, and __repr__. Persistence
(constraints, indexes) is exercised in the integration suite against a real
Postgres (Sprint V.2).
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from src.core.models.tenant_configuration import (
    ALLOWED_CATEGORIES,
    ALLOWED_DATA_TYPES,
    CATEGORY_PLANNING,
    CATEGORY_TRUST,
    DATA_TYPE_BOOL,
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DATA_TYPE_JSON,
    DATA_TYPE_STRING,
    TenantConfiguration,
)


def test_vocabulary_categories_exposed():
    # Blueprint v2.0 §3.11 (CG01-CG13) spans these categories.
    assert CATEGORY_PLANNING in ALLOWED_CATEGORIES
    assert CATEGORY_TRUST in ALLOWED_CATEGORIES
    assert "mold" in ALLOWED_CATEGORIES
    assert "governance" in ALLOWED_CATEGORIES
    # Must not be empty, must not contain the empty string.
    assert "" not in ALLOWED_CATEGORIES
    assert len(ALLOWED_CATEGORIES) >= 10


def test_vocabulary_data_types_cover_blueprint_needs():
    # planning.cpo.gen_count (int), planning.fitness.makespan_weight (float),
    # planning.laminagem.require_pair (bool), llm.backend (string),
    # planning.routing.templates.default_id (json/UUID-as-string)
    assert {DATA_TYPE_INT, DATA_TYPE_FLOAT, DATA_TYPE_BOOL, DATA_TYPE_STRING, DATA_TYPE_JSON} <= ALLOWED_DATA_TYPES


def test_wrap_roundtrip_primitives():
    for raw in [42, 3.14, True, False, "hello", None]:
        wrapped = TenantConfiguration.wrap(raw)
        assert wrapped == {"v": raw}
        assert TenantConfiguration.unwrap(wrapped) == raw


def test_wrap_roundtrip_collections():
    for raw in [[1, 2, 3], {"nested": {"deep": 7}}, []]:
        wrapped = TenantConfiguration.wrap(raw)
        assert TenantConfiguration.unwrap(wrapped) == raw


def test_unwrap_tolerates_legacy_raw_dict():
    # Legacy rows that stored the object directly (without the "v" envelope)
    # must still be readable.
    assert TenantConfiguration.unwrap({"foo": 1}) == {"foo": 1}
    # But the common case (dict WITH "v") unwraps correctly.
    assert TenantConfiguration.unwrap({"v": 123}) == 123


def test_model_instantiation_and_repr():
    tid = uuid4()
    cfg = TenantConfiguration(
        tenant_id=tid,
        category=CATEGORY_PLANNING,
        key="cpo.ga.gen_count",
        value=TenantConfiguration.wrap(200),
        data_type=DATA_TYPE_INT,
        valid_from=datetime(2026, 4, 18, 12, 0, 0),
        created_at=datetime.utcnow(),
        last_modified_at=datetime.utcnow(),
    )

    assert cfg.raw_value == 200
    rep = repr(cfg)
    assert "cpo.ga.gen_count" in rep
    assert str(tid) in rep


def test_model_tablename_and_schema():
    # The migration (013) and env.py wiring rely on these.
    assert TenantConfiguration.__tablename__ == "tenant_configuration"
    assert TenantConfiguration.__table__.schema == "core"
