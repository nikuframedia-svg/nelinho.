"""Q.67.1.C — fecho do TODO em `quality/gates.py:check_no_duplicate_business_keys`.

Antes de Q.67.1.C a severidade da gate de duplicados estava hardcoded em
``CheckSeverity.WARNING`` (Sprint Q.4 downgrade). O TODO pedia
"mover para `tenant_config["quality.duplicates"]`". Este ficheiro ancora o
novo comportamento:

1. **Default WARNING (sem config):** quando o contexto não traz
   `tenant_config`, a gate continua a reportar WARNING — preserva o
   contrato Sprint Q.4 para tenants que nunca tocam na chave.
2. **Override BLOCKING via tenant_config:** tenants com dados já limpos
   podem escalar a gate a BLOCKING sem alteração de código; o
   ``QualityRunner`` passa a contar a falha como `failed_blocking`.
3. **Override INFO via tenant_config:** tenants que ainda toleram mais
   ruído podem reduzir a gate a INFO; o runner deixa de contar a
   falha como warning e o overall status mantém-se PASSED.

Cobre:

- ``gates.check_no_duplicate_business_keys`` (resolução da severity).
- ``gates.load_quality_tenant_config`` (helper assíncrono).
- ``runner.QualityRunner`` (aggregator agora honra a severity devolvida).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.factory_data_product.models.meta import (
    CheckSeverity,
    QualityGateStatus,
)
from src.factory_data_product.quality.gates import (
    DEFAULT_DUPLICATES_SEVERITY,
    TENANT_CONFIG_CATEGORY_QUALITY,
    TENANT_CONFIG_KEY_DUPLICATES_SEVERITY,
    QUALITY_CHECKS,
    QualityCheck,
    check_no_duplicate_business_keys,
    load_quality_tenant_config,
)
from src.factory_data_product.quality.runner import QualityRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _duplicate_rows() -> list[dict]:
    """Two rows, same sheet, same business key — guaranteed duplicate."""
    return [
        {
            "sheet_name": "OrdensFabrico",
            "business_key_sha256": "abc123",
            "row_number": 2,
        },
        {
            "sheet_name": "OrdensFabrico",
            "business_key_sha256": "abc123",
            "row_number": 3,
        },
    ]


def _duplicates_only_runner() -> QualityRunner:
    """Runner restricted to the duplicates gate so we can read the aggregate."""
    return QualityRunner(
        checks={
            "no_duplicate_business_keys": QUALITY_CHECKS[
                "no_duplicate_business_keys"
            ],
        },
    )


# ---------------------------------------------------------------------------
# 1. Default WARNING (no tenant_config in context)
# ---------------------------------------------------------------------------


def test_duplicate_check_defaults_to_warning_when_no_config() -> None:
    """Without tenant_config, severity stays WARNING (Sprint Q.4 default)."""
    result = check_no_duplicate_business_keys(_duplicate_rows(), {})

    assert result.severity is CheckSeverity.WARNING
    assert DEFAULT_DUPLICATES_SEVERITY is CheckSeverity.WARNING
    assert result.passed is False
    assert result.details["duplicate_count"] == 1

    # The runner must aggregate the failure as a warning, NOT a blocking
    # failure — the overall status stays PASSED.
    runner = _duplicates_only_runner()
    aggregate = runner.run_all_checks(uuid4(), _duplicate_rows())
    assert aggregate.failed_blocking == 0
    assert aggregate.failed_warning == 1
    assert aggregate.overall_status == QualityGateStatus.PASSED
    assert aggregate.checks[0]["severity"] == "warning"


# ---------------------------------------------------------------------------
# 2. Override BLOCKING via tenant_config
# ---------------------------------------------------------------------------


def test_duplicate_check_escalates_to_blocking_via_tenant_config() -> None:
    """tenant_config["quality.duplicates.severity"]="BLOCKING" escalates the gate."""
    context = {
        "tenant_config": {
            TENANT_CONFIG_KEY_DUPLICATES_SEVERITY: "BLOCKING",
        },
    }
    result = check_no_duplicate_business_keys(_duplicate_rows(), context)

    assert result.severity is CheckSeverity.BLOCKING
    assert result.passed is False

    # Runner aggregation honours the dynamic severity — overall status
    # must flip to FAILED.
    runner = _duplicates_only_runner()
    aggregate = runner.run_all_checks(uuid4(), _duplicate_rows(), context=context)
    assert aggregate.failed_blocking == 1
    assert aggregate.failed_warning == 0
    assert aggregate.overall_status == QualityGateStatus.FAILED
    assert aggregate.checks[0]["severity"] == "blocking"


# ---------------------------------------------------------------------------
# 3. Override INFO via tenant_config
# ---------------------------------------------------------------------------


def test_duplicate_check_can_be_reduced_to_info_via_tenant_config() -> None:
    """tenant_config["quality.duplicates.severity"]="info" reduces noise to INFO."""
    context = {
        "tenant_config": {
            TENANT_CONFIG_KEY_DUPLICATES_SEVERITY: "info",  # lowercase accepted
        },
    }
    result = check_no_duplicate_business_keys(_duplicate_rows(), context)

    assert result.severity is CheckSeverity.INFO
    assert result.passed is False

    # INFO is neither blocking nor warning in the aggregator — both
    # counters stay at zero, overall status stays PASSED.
    runner = _duplicates_only_runner()
    aggregate = runner.run_all_checks(uuid4(), _duplicate_rows(), context=context)
    assert aggregate.failed_blocking == 0
    assert aggregate.failed_warning == 0
    assert aggregate.overall_status == QualityGateStatus.PASSED
    assert aggregate.checks[0]["severity"] == "info"


# ---------------------------------------------------------------------------
# Bonus: unknown value falls back to default (defensive contract)
# ---------------------------------------------------------------------------


def test_duplicate_check_unknown_severity_falls_back_to_default() -> None:
    """Garbage in tenant_config never crashes the gate; we fall back to WARNING."""
    context = {
        "tenant_config": {
            TENANT_CONFIG_KEY_DUPLICATES_SEVERITY: "definitely-not-a-severity",
        },
    }
    result = check_no_duplicate_business_keys(_duplicate_rows(), context)

    assert result.severity is DEFAULT_DUPLICATES_SEVERITY  # WARNING
    assert result.passed is False


# ---------------------------------------------------------------------------
# Bonus: load_quality_tenant_config wraps TenantConfigService.get_category
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_quality_tenant_config_proxies_get_category() -> None:
    """The async helper reads the `quality` category from the service."""

    captured: dict[str, str] = {}

    class _FakeService:
        async def get_category(self, category: str) -> dict[str, object]:
            captured["category"] = category
            return {TENANT_CONFIG_KEY_DUPLICATES_SEVERITY: "BLOCKING"}

    values = await load_quality_tenant_config(_FakeService())

    assert captured["category"] == TENANT_CONFIG_CATEGORY_QUALITY
    assert values == {TENANT_CONFIG_KEY_DUPLICATES_SEVERITY: "BLOCKING"}


@pytest.mark.asyncio
async def test_load_quality_tenant_config_swallows_errors() -> None:
    """If TenantConfigService blows up, we return an empty dict — defaults win."""

    class _BrokenService:
        async def get_category(self, category: str) -> dict[str, object]:
            raise RuntimeError("DB unreachable")

    values = await load_quality_tenant_config(_BrokenService())

    assert values == {}
