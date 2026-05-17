"""Q.24.A — the ETL mirrors run source-agnostically.

The Q.20 mirrors gained a ``source`` parameter so the same idempotent
upsert pipeline ingests either the live ERP (:mod:`services`) or the
bundled demo package (:mod:`demo_source`). These tests drive the master
mirror with the demo source against the RecordingSession fake.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.adapters.nelo import demo_source
from src.adapters.nelo.etl.master_data import mirror_master_data
from src.adapters.nelo.etl.sync import _resolve_source
from src.core.models.product import Product
from src.plan.models.routing_template import (
    ModelRoutingAssignment,
    RoutingTemplate,
)


@pytest.fixture(autouse=True)
def _clean_cache():
    demo_source._load.cache_clear()
    yield
    demo_source._load.cache_clear()


def test_resolve_source_selectors():
    from src.adapters.nelo import demo_source as ds
    from src.adapters.nelo import services

    assert _resolve_source("erp") is services
    assert _resolve_source(None) is services
    assert _resolve_source("demo") is ds


def test_resolve_source_rejects_unknown():
    with pytest.raises(ValueError, match="unknown source"):
        _resolve_source("sqlite")


def test_resolve_source_passes_objects_through():
    sentinel = object()
    assert _resolve_source(sentinel) is sentinel


async def test_master_mirror_ingests_demo_package(recording_session):
    """Driving the master mirror with the demo source lands the 50 real
    OFs' products + routing templates into the (fake) Postgres."""
    tenant = uuid4()
    result = await mirror_master_data(
        session=recording_session,
        tenant_id=tenant,
        source=demo_source,
    )

    assert result.status == "ok"
    assert result.rows_read > 0

    products = [o for o in recording_session.added if isinstance(o, Product)]
    templates = [o for o in recording_session.added if isinstance(o, RoutingTemplate)]
    assignments = [
        o for o in recording_session.added if isinstance(o, ModelRoutingAssignment)
    ]

    # Demo package references 50 boats + their components.
    assert len(products) > 50
    # The 50 boats collapse onto a handful of routing patterns.
    assert templates
    assert assignments
    assert all(p.tenant_id == tenant for p in products)
