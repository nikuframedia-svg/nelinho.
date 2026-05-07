"""Sprint S8 — guards for precision (Π9), mass-assignment (Π10) and Π7."""
from __future__ import annotations

from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]


# --- Π9: cache stores Decimal as string -------------------------------------

def test_configuration_service_caches_decimal_as_string():
    text = (REPO / "src" / "core" / "services" / "configuration_service.py").read_text(
        encoding="utf-8"
    )
    # Strip comment-only lines so the historical "Was `float(...)`" notes
    # don't trip the guard.
    code_only = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    for old in ("float(loaded_rate)", "float(rate.loaded_rate)",
                "float(total_rate)", "float(rate.total_rate)"):
        assert old not in code_only, f"{old} still present in production code"
    for new in ("str(loaded_rate)", "str(rate.loaded_rate)",
                "str(total_rate)", "str(rate.total_rate)"):
        assert new in code_only


# --- Π10: TenantCreate no longer accepts subscription_level ------------------

def test_tenant_create_drops_subscription_level():
    from src.core.api.schemas import TenantCreate

    fields = set(TenantCreate.model_fields.keys())
    assert "subscription_level" not in fields, (
        "subscription_level must be set server-side, not from request body"
    )


def test_tenant_create_still_accepts_required_fields():
    from src.core.api.schemas import TenantCreate

    payload = TenantCreate(tenant_name="Nelo", tenant_code="NELO")
    assert payload.tenant_name == "Nelo"
    assert payload.tenant_code == "NELO"


# --- Π7: master-data list endpoints raise 503 on DB outage -------------------

@pytest.mark.parametrize(
    "module, fn_name",
    [
        ("src.core.api.products", "list_products"),
        ("src.core.api.employees", "list_employees"),
        ("src.core.api.operations", "list_operations"),
    ],
)
def test_master_data_list_no_longer_returns_empty_on_db_outage(module, fn_name):
    """Old code: `return []` masking DB outage. New code: HTTPException(503)."""
    import importlib
    import inspect

    mod = importlib.import_module(module)
    fn = getattr(mod, fn_name)
    src = inspect.getsource(fn)
    # The old `return []` from the except branch must be gone.
    assert "return []" not in src
    # The new 503 must be there.
    assert "HTTP_503_SERVICE_UNAVAILABLE" in src
