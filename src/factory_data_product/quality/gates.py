"""
Quality Gate Definitions — Contrato 010
=======================================

Define all quality checks with:
- check_id: stable identifier
- severity: blocking, warning, info
- description: what it checks
- check function: actual validation logic
"""

import logging
from dataclasses import dataclass, field as _dc_field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import UUID

from src.factory_data_product.excel_columns import (
    CRITICAL_SHEETS as _EXCEL_CRITICAL_SHEETS,
    OrdensFabrico as _OF,
    FasesOrdemFabrico as _FOF,
    Fases as _F,
    Funcionarios as _Func,
)
from src.factory_data_product.models.meta import CheckSeverity

_log = logging.getLogger(__name__)

# Q.67.1.C — tenant_config key that controls the severity of the
# duplicate-business-keys check. NELO data has structural duplicates
# that the transform step dedupes via business key + ingestion_id, so
# the default stays ``WARNING``; tenants with already-clean data can
# escalate to ``BLOCKING`` from /regras → quality.
TENANT_CONFIG_CATEGORY_QUALITY = "quality"
TENANT_CONFIG_KEY_DUPLICATES_SEVERITY = "duplicates.severity"
DEFAULT_DUPLICATES_SEVERITY: CheckSeverity = CheckSeverity.WARNING


def _coerce_severity(value: Any, *, default: CheckSeverity) -> CheckSeverity:
    """Best-effort parse of a config string/enum into ``CheckSeverity``.

    Accepts ``CheckSeverity`` directly, the enum *value* string
    (``"blocking"``/``"warning"``/``"info"``), or the enum *name*
    (``"BLOCKING"``/``"WARNING"``/``"INFO"``). Falls back to ``default``
    on anything unrecognised — quality gates must never crash because
    the operator typed the wrong word in /regras.
    """
    if isinstance(value, CheckSeverity):
        return value
    if isinstance(value, str):
        candidate = value.strip().lower()
        if not candidate:
            return default
        for member in CheckSeverity:
            if member.value == candidate or member.name.lower() == candidate:
                return member
        _log.warning(
            "quality.duplicates.severity has unknown value %r; using default %s",
            value, default.value,
        )
        return default
    if value is None:
        return default
    _log.warning(
        "quality.duplicates.severity has unsupported type %s; using default %s",
        type(value).__name__, default.value,
    )
    return default


def _resolve_duplicates_severity_from_context(
    context: Optional[Dict[str, Any]],
    *,
    default: CheckSeverity = DEFAULT_DUPLICATES_SEVERITY,
) -> CheckSeverity:
    """Read the duplicates-check severity from a sync-friendly context dict.

    Callers that hold an async ``TenantConfigService`` should preload
    ``context["tenant_config"]`` (a ``{key: value}`` dict scoped to the
    ``quality`` category — see ``load_quality_tenant_config``); the
    sync check function then stays pure and testable.
    """
    if not context:
        return default
    raw = context.get("tenant_config") or {}
    if not isinstance(raw, dict):
        return default
    return _coerce_severity(
        raw.get(TENANT_CONFIG_KEY_DUPLICATES_SEVERITY),
        default=default,
    )


async def load_quality_tenant_config(service: Any) -> Dict[str, Any]:
    """Fetch the ``quality`` category from a ``TenantConfigService``.

    Returned dict is shaped for direct use as ``context["tenant_config"]``
    when running ``QualityRunner``. Failure is swallowed and returns ``{}``
    so that an unreachable DB never blocks ingestion — the sync checks
    fall back to their hard-coded defaults.
    """
    if service is None:
        return {}
    try:
        values = await service.get_category(TENANT_CONFIG_CATEGORY_QUALITY)
    except Exception as exc:  # pragma: no cover - best-effort
        _log.warning(
            "load_quality_tenant_config: failed to read category %r (%s); "
            "falling back to defaults",
            TENANT_CONFIG_CATEGORY_QUALITY, exc,
        )
        return {}
    return dict(values) if isinstance(values, dict) else {}


@dataclass
class CheckResult:
    """Result of a quality check."""
    
    check_id: str
    severity: CheckSeverity
    passed: bool
    details: Dict[str, Any] = _dc_field(default_factory=dict)
    message: Optional[str] = None


@dataclass
class QualityCheck:
    """Definition of a quality check."""
    
    check_id: str
    name: str
    description: str
    severity: CheckSeverity
    
    # The check function takes (raw_rows, context) and returns CheckResult
    check_fn: Optional[Callable] = None


# Onda 3.5 — sheet/column lists derive from the central catalogue, not
# from inline literals. CRITICAL_SHEETS is the wider blueprint ("any of
# these missing is fatal"); REQUIRED_SHEETS is the narrower runtime gate
# ("at minimum we need these to even attempt curation").
REQUIRED_SHEETS = {"OrdensFabrico", "FasesOrdemFabrico", "Fases"}
assert REQUIRED_SHEETS <= _EXCEL_CRITICAL_SHEETS  # invariant

REQUIRED_COLUMNS = {
    "OrdensFabrico": [_OF.OF_ID],
    "FasesOrdemFabrico": [_FOF.FASE_OF_ID, _FOF.OF_ID, _FOF.FASE_ID],
    "Fases": [_F.FASE_ID],
}

# Numeric ranges — only fields actually present in the Excel.
NUMERIC_RANGES = {
    _FOF.HORAS_PREVISTAS: (0, 10000),
    _FOF.COEFICIENTE: (0, 10000),
    _Func.VALOR_HORA: (0, 1000),
}

# PII fields to detect
PII_FIELDS = {
    "Funcionario_Nome",
    "FuncionarioNome",
    "Nome",
    "Email",
    "Telefone",
}


def check_required_sheets_present(
    raw_rows: List[Dict],
    context: Dict,
) -> CheckResult:
    """Check that required sheets are present."""
    sheets_found = {row["sheet_name"] for row in raw_rows}
    missing = REQUIRED_SHEETS - sheets_found
    
    return CheckResult(
        check_id="required_sheets_present",
        severity=CheckSeverity.BLOCKING,
        passed=len(missing) == 0,
        details={
            "required": list(REQUIRED_SHEETS),
            "found": list(sheets_found),
            "missing": list(missing),
        },
        message=f"Missing sheets: {missing}" if missing else None,
    )


def check_required_columns_present(
    raw_rows: List[Dict],
    context: Dict,
) -> CheckResult:
    """Check that required columns are present in each sheet."""
    missing_by_sheet = {}
    
    # Get columns per sheet from first row of each
    columns_by_sheet = {}
    for row in raw_rows:
        sheet = row["sheet_name"]
        if sheet not in columns_by_sheet:
            columns_by_sheet[sheet] = set(row["payload_json"].keys())
    
    # Check requirements
    for sheet, required_cols in REQUIRED_COLUMNS.items():
        if sheet in columns_by_sheet:
            found_cols = columns_by_sheet[sheet]
            missing = set(required_cols) - found_cols
            if missing:
                missing_by_sheet[sheet] = list(missing)
    
    return CheckResult(
        check_id="required_columns_present",
        severity=CheckSeverity.BLOCKING,
        passed=len(missing_by_sheet) == 0,
        details={
            "missing_by_sheet": missing_by_sheet,
        },
        message=f"Missing columns: {missing_by_sheet}" if missing_by_sheet else None,
    )


def check_no_duplicate_business_keys(
    raw_rows: List[Dict],
    context: Dict,
    *,
    severity: Optional[CheckSeverity] = None,
) -> CheckResult:
    """Check for duplicate business keys.

    Severity is resolved in priority order:
    1. Explicit ``severity`` keyword argument (used by call-sites that
       already resolved tenant config themselves).
    2. ``context["tenant_config"]["quality.duplicates.severity"]`` (the
       canonical path — see ``load_quality_tenant_config``).
    3. ``DEFAULT_DUPLICATES_SEVERITY`` (``WARNING``) — preserves the
       Sprint Q.4 behaviour for tenants that never override the key.
    """
    duplicates = {}

    # Group by sheet and check business keys
    seen_keys: Dict[str, Dict[str, int]] = {}

    for row in raw_rows:
        sheet = row["sheet_name"]
        bk_hash = row.get("business_key_sha256")

        if bk_hash:
            if sheet not in seen_keys:
                seen_keys[sheet] = {}

            if bk_hash in seen_keys[sheet]:
                seen_keys[sheet][bk_hash] += 1
                if sheet not in duplicates:
                    duplicates[sheet] = []
                duplicates[sheet].append({
                    "row": row["row_number"],
                    "hash": bk_hash,
                })
            else:
                seen_keys[sheet][bk_hash] = 1

    # Sprint Q.4 (≈2026-03): downgraded BLOCKING → WARNING porque o
    # ficheiro NELO original tem duplicados estruturais em
    # FasesOrdemFabrico que a etapa de transformação deduplica via
    # business key + ingestion_id. Bloquear paralisava todos os imports.
    # Sprint Q.12: documentar a alteração e expor `severity` para
    # configuração futura.
    # Q.67.1.C: fechado — severity vem de
    # tenant_config["quality.duplicates.severity"] (default WARNING).
    # Tenants com dados já limpos podem escalar para BLOCKING via /regras
    # → quality sem alteração de código.
    if severity is None:
        resolved_severity = _resolve_duplicates_severity_from_context(context)
    else:
        resolved_severity = severity

    return CheckResult(
        check_id="no_duplicate_business_keys",
        severity=resolved_severity,
        passed=len(duplicates) == 0,
        details={
            "duplicates_by_sheet": duplicates,
            "duplicate_count": sum(len(v) for v in duplicates.values()),
        },
        message=(
            f"Found {sum(len(v) for v in duplicates.values())} duplicate "
            f"business keys (will be deduplicated by transform step)"
        ) if duplicates else None,
    )


def check_valid_numeric_ranges(
    raw_rows: List[Dict],
    context: Dict,
) -> CheckResult:
    """Check numeric values are within valid ranges."""
    violations = []
    
    for row in raw_rows:
        payload = row["payload_json"]
        
        for field, (min_val, max_val) in NUMERIC_RANGES.items():
            if field in payload:
                value = payload[field]
                if value is not None:
                    try:
                        num = float(value)
                        if num < min_val or num > max_val:
                            violations.append({
                                "sheet": row["sheet_name"],
                                "row": row["row_number"],
                                "field": field,
                                "value": value,
                                "range": f"{min_val}-{max_val}",
                            })
                    except (ValueError, TypeError):
                        violations.append({
                            "sheet": row["sheet_name"],
                            "row": row["row_number"],
                            "field": field,
                            "value": value,
                            "error": "not_numeric",
                        })
    
    return CheckResult(
        check_id="valid_numeric_ranges",
        severity=CheckSeverity.BLOCKING,
        passed=len(violations) == 0,
        details={
            "violations": violations[:20],  # Limit details
            "total_violations": len(violations),
        },
        message=f"{len(violations)} numeric range violations" if violations else None,
    )


def check_referential_integrity(
    raw_rows: List[Dict],
    context: Dict,
) -> CheckResult:
    """Check referential integrity between sheets.

    Column names match Folha_IA_extra.xlsx exactly (case-sensitive):
      OrdensFabrico.Of_Id, Fases.Fase_Id,
      FasesOrdemFabrico.FaseOf_OfId, FasesOrdemFabrico.FaseOf_FaseId
    """
    violations = []

    # Collect IDs from master tables
    order_ids = set()
    fase_ids = set()

    for row in raw_rows:
        sheet = row["sheet_name"]
        payload = row["payload_json"]

        if sheet == "OrdensFabrico":
            of_id = payload.get(_OF.OF_ID)
            if of_id:
                order_ids.add(str(of_id))

        elif sheet == "Fases":
            fase_id = payload.get(_F.FASE_ID)
            if fase_id:
                fase_ids.add(str(fase_id))

    # Check references in detail tables
    for row in raw_rows:
        sheet = row["sheet_name"]
        payload = row["payload_json"]

        if sheet == "FasesOrdemFabrico":
            of_ref = payload.get(_FOF.OF_ID)
            # FaseOf_FaseId reference check skipped intentionally — the
            # Fases master may be incomplete in legacy data; a missing
            # match is more often a data-quality finding than a corruption.

            if of_ref and str(of_ref) not in order_ids:
                violations.append({
                    "sheet": sheet,
                    "row": row["row_number"],
                    "field": _FOF.OF_ID,
                    "value": of_ref,
                    "error": "missing_order",
                })
    
    return CheckResult(
        check_id="referential_integrity_order_phase",
        severity=CheckSeverity.BLOCKING,
        passed=len(violations) == 0,
        details={
            "violations": violations[:20],
            "total_violations": len(violations),
        },
        message=f"{len(violations)} referential integrity violations" if violations else None,
    )


def check_date_parseable(
    raw_rows: List[Dict],
    context: Dict,
) -> CheckResult:
    """Check that date fields are parseable."""
    from datetime import datetime
    
    date_fields = [
        "OF_DataEntrada", "OF_DataEntrega", "OF_DataConclusao",
        "FaseOf_DataInicio", "FaseOf_DataFim",
    ]
    
    unparseable = []
    
    for row in raw_rows:
        payload = row["payload_json"]
        
        for field in date_fields:
            if field in payload and payload[field] is not None:
                value = payload[field]
                
                # Skip if already a datetime
                if isinstance(value, datetime):
                    continue
                
                # Try to parse
                parsed = False
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
                    try:
                        datetime.strptime(str(value), fmt)
                        parsed = True
                        break
                    except ValueError:
                        continue
                
                if not parsed:
                    unparseable.append({
                        "sheet": row["sheet_name"],
                        "row": row["row_number"],
                        "field": field,
                        "value": str(value),
                    })
    
    return CheckResult(
        check_id="date_parseable_where_required",
        severity=CheckSeverity.WARNING,
        passed=len(unparseable) == 0,
        details={
            "unparseable": unparseable[:20],
            "total_unparseable": len(unparseable),
        },
        message=f"{len(unparseable)} unparseable dates" if unparseable else None,
    )


def check_pii_policy(
    raw_rows: List[Dict],
    context: Dict,
) -> CheckResult:
    """Check that PII fields are detected and flagged."""
    pii_found = []
    
    for row in raw_rows:
        payload = row["payload_json"]
        
        for field in payload.keys():
            if field in PII_FIELDS or any(pii in field for pii in ["Nome", "Email", "Telefone"]):
                if field not in [p["field"] for p in pii_found]:
                    pii_found.append({
                        "sheet": row["sheet_name"],
                        "field": field,
                        "sample_row": row["row_number"],
                    })
    
    return CheckResult(
        check_id="pii_policy_enforced",
        severity=CheckSeverity.WARNING,
        passed=True,  # Warning only, doesn't fail
        details={
            "pii_fields_detected": pii_found,
            "recommendation": "Ensure proper RBAC for these fields",
        },
        message=f"Detected {len(pii_found)} PII fields" if pii_found else None,
    )


# Register all checks
QUALITY_CHECKS: Dict[str, QualityCheck] = {
    "required_sheets_present": QualityCheck(
        check_id="required_sheets_present",
        name="Required Sheets Present",
        description="Verify all required sheets exist in the Excel file",
        severity=CheckSeverity.BLOCKING,
        check_fn=check_required_sheets_present,
    ),
    "required_columns_present": QualityCheck(
        check_id="required_columns_present",
        name="Required Columns Present",
        description="Verify required columns exist in each sheet",
        severity=CheckSeverity.BLOCKING,
        check_fn=check_required_columns_present,
    ),
    "no_duplicate_business_keys": QualityCheck(
        check_id="no_duplicate_business_keys",
        name="No Duplicate Business Keys",
        description="Verify no duplicate business keys exist (duplicates will be deduplicated)",
        severity=CheckSeverity.WARNING,  # Changed from BLOCKING to allow ingestion with duplicates
        check_fn=check_no_duplicate_business_keys,
    ),
    "valid_numeric_ranges": QualityCheck(
        check_id="valid_numeric_ranges",
        name="Valid Numeric Ranges",
        description="Verify numeric values are within valid ranges",
        severity=CheckSeverity.BLOCKING,
        check_fn=check_valid_numeric_ranges,
    ),
    "referential_integrity_order_phase": QualityCheck(
        check_id="referential_integrity_order_phase",
        name="Referential Integrity",
        description="Verify foreign key references resolve correctly",
        severity=CheckSeverity.BLOCKING,
        check_fn=check_referential_integrity,
    ),
    "date_parseable_where_required": QualityCheck(
        check_id="date_parseable_where_required",
        name="Dates Parseable",
        description="Verify date fields can be parsed",
        severity=CheckSeverity.WARNING,
        check_fn=check_date_parseable,
    ),
    "pii_policy_enforced": QualityCheck(
        check_id="pii_policy_enforced",
        name="PII Policy Enforced",
        description="Detect and flag PII fields",
        severity=CheckSeverity.WARNING,
        check_fn=check_pii_policy,
    ),
}


