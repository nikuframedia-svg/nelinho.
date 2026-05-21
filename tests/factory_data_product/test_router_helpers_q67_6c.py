"""Q.67.6.C — Coverage for router-level pure helpers in
``factory_data_product.api.routers``.

Two helpers are pure-Python and easy to pin without standing up FastAPI:

* ``ingest._is_under`` — path-containment check used by the
  ``/v1/factory/ingest-by-path`` allowlist (Onda 5.4 path-traversal guard).
  The function must distinguish ``/data/foo`` (child of ``/data``) from
  ``/data_other/foo`` (NOT a child, despite the string prefix match).
* ``lifecycle._emit_drift_alert_safe`` — best-effort drift emission. The
  contract: missing ``tenant_id`` ⇒ no DB calls, returns ``None``; any
  failure inside the emission path ⇒ returns ``None`` (never raises).

These are the branches the bigger characterization suite skips because it
exercises only the HTTP surface.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.factory_data_product.api.routers.ingest import _is_under
from src.factory_data_product.api.routers.lifecycle import (
    _emit_drift_alert_safe,
)


# ---------------------------------------------------------------------------
# ingest._is_under — separator-aware path-containment check
# ---------------------------------------------------------------------------


def test_is_under_recognises_direct_child(tmp_path: Path) -> None:
    """A direct child of the allowlist root is "under" it."""
    parent = tmp_path
    child = parent / "f.xlsx"
    child.touch()
    assert _is_under(child.resolve(), parent.resolve()) is True


def test_is_under_recognises_deep_descendant(tmp_path: Path) -> None:
    """Nested descendants count as well."""
    parent = tmp_path
    deep = parent / "a" / "b" / "c" / "f.xlsx"
    deep.parent.mkdir(parents=True)
    deep.touch()
    assert _is_under(deep.resolve(), parent.resolve()) is True


def test_is_under_treats_path_itself_as_under(tmp_path: Path) -> None:
    """A path is trivially "under" itself — keeps the recursion base case."""
    assert _is_under(tmp_path.resolve(), tmp_path.resolve()) is True


def test_is_under_rejects_sibling_with_same_prefix(tmp_path: Path) -> None:
    """The separator guard prevents ``/data`` from "containing" ``/data_other``.

    This is the entire point of the helper — a naïve string-prefix check
    would let an attacker submit ``/data_other/anything`` against an
    allowlist of ``/data``."""
    parent = tmp_path / "data"
    sibling = tmp_path / "data_other"
    parent.mkdir()
    sibling.mkdir()
    sibling_file = sibling / "f.xlsx"
    sibling_file.touch()
    assert _is_under(sibling_file.resolve(), parent.resolve()) is False


def test_is_under_rejects_unrelated_path(tmp_path: Path) -> None:
    """Completely unrelated paths return False."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert _is_under(b.resolve(), a.resolve()) is False


# ---------------------------------------------------------------------------
# lifecycle._emit_drift_alert_safe — best-effort + no-raise contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_drift_alert_safe_returns_none_when_tenant_missing() -> None:
    """Without an X-Tenant-Id header, the helper short-circuits to None and
    never touches the DB — the alert simply can't be routed."""

    class _Engine:
        def get_schema_history(self):  # pragma: no cover — guarded
            raise AssertionError("must not be called without tenant_id")

    result = await _emit_drift_alert_safe(_Engine(), uuid4(), tenant_id=None)
    assert result is None


@pytest.mark.asyncio
async def test_emit_drift_alert_safe_swallows_inner_errors() -> None:
    """If the engine's ``get_schema_history`` raises (or any other inner
    step fails), the helper logs and returns ``None`` — activation must
    NEVER fail because of a drift-alert hiccup."""

    class _BrokenEngine:
        def get_schema_history(self):
            raise RuntimeError("schema history unreadable")

    result = await _emit_drift_alert_safe(
        _BrokenEngine(), uuid4(), tenant_id=uuid4(),
    )
    assert result is None
