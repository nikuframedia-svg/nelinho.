"""
ProdPlan ONE - RBAC
====================

Role-Based Access Control.
"""

from enum import Enum
from functools import wraps
from typing import Callable, List, Set, Optional, Tuple
from uuid import UUID

from fastapi import Depends, HTTPException, status

from .jwt_handler import UserContext
# Q.121.D3 — dev-fallback por headers (prod continua a exigir Bearer JWT).
from .headers import get_current_user_or_dev_header


class Role(str, Enum):
    """User roles."""
    ADMIN_PLATFORM = "admin_platform"
    MANAGER_OPERATIONS = "manager_operations"
    PLANNER_SUPPLY = "planner_supply"
    FINANCE_CONTROLLER = "finance_controller"
    HR_MANAGER = "hr_manager"
    OPERATOR = "operator"
    # Sprint Q.13.F F.2 — CEO is read-only across the dashboard surface;
    # distinct from VIEWER (which is broader / used for support staff).
    CEO = "ceo"
    VIEWER = "viewer"


class Permission(str, Enum):
    """Permissions."""
    # CORE
    TENANT_READ = "tenant:read"
    TENANT_WRITE = "tenant:write"
    MASTER_DATA_READ = "master_data:read"
    MASTER_DATA_WRITE = "master_data:write"
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"
    
    # PLAN
    SCHEDULE_READ = "schedule:read"
    SCHEDULE_WRITE = "schedule:write"
    MRP_READ = "mrp:read"
    MRP_WRITE = "mrp:write"
    CAPACITY_READ = "capacity:read"
    # Q.133.B.1 — editar templates de routing (reordenar fases + marcar fase
    # flexível/posição alternativa). Permissão DEDICADA, não SCHEDULE_WRITE:
    # /v1/plan/routing-templates é gateado SÓ pelo PermissionDependency da rota
    # (não está na matriz de prefixos), por isso esta permissão abre EXACTAMENTE
    # esse editor sem vazar acesso a /v1/plan/cpo, /v1/governance, /v1/decisions.
    # Concedida a todos os roles (decisão do owner: "qualquer user pode editar").
    ROUTING_EDIT = "routing:edit"

    # QUALITY — Q.171.C: registo/resolução de retrabalho era escrita SEM
    # gate de papel (qualquer viewer escrevia). Operador PODE registar
    # (é quem aponta o defeito no terreno); viewer/CEO não.
    QUALITY_WRITE = "quality:write"

    # PROFIT
    COGS_READ = "cogs:read"
    COGS_WRITE = "cogs:write"
    PRICING_READ = "pricing:read"
    PRICING_WRITE = "pricing:write"
    SCENARIO_READ = "scenario:read"
    SCENARIO_WRITE = "scenario:write"
    
    # HR
    ALLOCATION_READ = "allocation:read"
    ALLOCATION_WRITE = "allocation:write"
    PAYROLL_READ = "payroll:read"
    PAYROLL_WRITE = "payroll:write"
    PRODUCTIVITY_READ = "productivity:read"
    PRODUCTIVITY_WRITE = "productivity:write"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.ADMIN_PLATFORM: set(Permission),  # All permissions
    
    Role.MANAGER_OPERATIONS: {
        Permission.QUALITY_WRITE,  # Q.171.C
        Permission.ROUTING_EDIT,  # Q.133.B.1
        Permission.MASTER_DATA_READ,
        Permission.MASTER_DATA_WRITE,
        Permission.CONFIG_READ,
        Permission.SCHEDULE_READ,
        Permission.SCHEDULE_WRITE,
        Permission.MRP_READ,
        Permission.MRP_WRITE,
        Permission.CAPACITY_READ,
        Permission.COGS_READ,
        Permission.COGS_WRITE,
        Permission.PRICING_READ,
        Permission.SCENARIO_READ,
        Permission.SCENARIO_WRITE,
        Permission.ALLOCATION_READ,
        Permission.ALLOCATION_WRITE,
        Permission.PRODUCTIVITY_READ,
    },
    
    Role.PLANNER_SUPPLY: {
        Permission.ROUTING_EDIT,  # Q.133.B.1
        Permission.MASTER_DATA_READ,
        Permission.SCHEDULE_READ,
        Permission.SCHEDULE_WRITE,
        Permission.MRP_READ,
        Permission.MRP_WRITE,
        Permission.CAPACITY_READ,
        Permission.COGS_READ,
        Permission.ALLOCATION_READ,
    },
    
    Role.FINANCE_CONTROLLER: {
        Permission.ROUTING_EDIT,  # Q.133.B.1
        Permission.MASTER_DATA_READ,
        Permission.CONFIG_READ,
        Permission.CONFIG_WRITE,
        Permission.SCHEDULE_READ,
        Permission.COGS_READ,
        Permission.COGS_WRITE,
        Permission.PRICING_READ,
        Permission.PRICING_WRITE,
        Permission.SCENARIO_READ,
        Permission.SCENARIO_WRITE,
        Permission.PAYROLL_READ,
    },
    
    Role.HR_MANAGER: {
        Permission.ROUTING_EDIT,  # Q.133.B.1
        Permission.MASTER_DATA_READ,
        Permission.SCHEDULE_READ,
        Permission.ALLOCATION_READ,
        Permission.ALLOCATION_WRITE,
        Permission.PAYROLL_READ,
        Permission.PAYROLL_WRITE,
        Permission.PRODUCTIVITY_READ,
        Permission.PRODUCTIVITY_WRITE,
    },
    
    Role.OPERATOR: {
        Permission.ROUTING_EDIT,  # Q.133.B.1 — operador pode editar fases/flex
        Permission.SCHEDULE_READ,
        Permission.ALLOCATION_READ,
        Permission.PRODUCTIVITY_READ,
        Permission.QUALITY_WRITE,  # Q.171.C — regista retrabalho no terreno
    },

    Role.CEO: {
        # Read-only across the dashboard surface (cogs/pricing/scenarios/cpo).
        # Q.133.B.1 — excepção explícita (decisão do owner): o CEO PODE editar
        # fases de routing (ROUTING_EDIT). Continua sem SCHEDULE_WRITE, logo não
        # acede a /v1/plan/cpo, /v1/governance nem /v1/decisions; SoD intacto.
        Permission.ROUTING_EDIT,
        Permission.SCHEDULE_READ,
        Permission.MASTER_DATA_READ,
        Permission.CAPACITY_READ,
        Permission.COGS_READ,
        Permission.PRICING_READ,
        Permission.SCENARIO_READ,
        Permission.ALLOCATION_READ,
        Permission.PRODUCTIVITY_READ,
    },

    Role.VIEWER: {
        Permission.ROUTING_EDIT,  # Q.133.B.1
        Permission.MASTER_DATA_READ,
        Permission.SCHEDULE_READ,
        Permission.CAPACITY_READ,
        Permission.COGS_READ,
        Permission.ALLOCATION_READ,
    },
}


# ============================================================================
# ROUTE PREFIX → REQUIRED PERMISSIONS (Sprint Q.13.F F.2)
# ============================================================================
#
# Plan v4 §11.2: a defensible RBAC posture means EVERY route maps to a
# permission, the matrix is enumerable, and the tests can lock the
# table. The mapping below is precedence-ordered: longer / more
# specific prefixes win over shorter ones.
#
# Routes not in the table fall through to the default
# (`PermissionDependency` per-route decorator). Adding a new router
# without a matrix entry is a defensible default — no escalation, but
# operators see a 403 until the matrix is updated.
#
# Method scope: "*" applies to all methods; ("GET",) restricts to read.

from collections import OrderedDict

_RoutePolicy = Tuple[Tuple[str, ...], List[Permission]]
"""(allowed_methods, required_permissions). Empty methods tuple = all."""

ROUTE_PREFIX_REQUIREMENTS: "OrderedDict[str, _RoutePolicy]" = OrderedDict([
    # ── Operator surface (tablet) — Sprint Q.13 §10 ────────────────────
    ("/v1/operador",                ((), [Permission.SCHEDULE_READ])),
    # ── Observability (trace lookup) — leitura interna, não pública ────
    ("/v1/observability",           ((), [Permission.SCHEDULE_READ])),
    # ── Quality rework — operators record + resolve rework ────────────
    ("/v1/quality/rework",          ((), [Permission.SCHEDULE_READ])),

    # ── CEO dashboard surface (read-only) ──────────────────────────────
    ("/v1/profit/dashboard",        (("GET",), [Permission.COGS_READ])),
    ("/v1/profit/throughput",       (("GET",), [Permission.COGS_READ])),
    ("/v1/profit/cogs",             (("GET",), [Permission.COGS_READ])),
    ("/v1/profit/pricing",          (("GET",), [Permission.PRICING_READ])),
    ("/v1/profit/scenarios",        ((), [Permission.SCENARIO_READ])),

    # ── Plan / scheduling ──────────────────────────────────────────────
    ("/v1/plan/cpo",                ((), [Permission.SCHEDULE_WRITE])),
    ("/v1/plan/schedule",           ((), [Permission.SCHEDULE_WRITE])),
    ("/v1/plan/preview-delta",      ((), [Permission.SCHEDULE_WRITE])),
    ("/v1/plan/mrp",                ((), [Permission.MRP_WRITE])),
    ("/v1/plan/capacity",           (("GET",), [Permission.CAPACITY_READ])),
    ("/v1/plan/transport",          ((), [Permission.SCHEDULE_WRITE])),
    ("/v1/plan/worker",             (("GET",), [Permission.SCHEDULE_READ])),

    # ── Master data + config ───────────────────────────────────────────
    ("/v1/core/customers",          ((), [Permission.MASTER_DATA_WRITE])),
    ("/v1/core/suppliers",          ((), [Permission.MASTER_DATA_WRITE])),
    ("/v1/core/machines",           ((), [Permission.MASTER_DATA_WRITE])),
    ("/v1/core/products",           ((), [Permission.MASTER_DATA_WRITE])),
    ("/v1/core/bom",                ((), [Permission.MASTER_DATA_WRITE])),
    ("/v1/core/operations",         ((), [Permission.MASTER_DATA_WRITE])),
    ("/v1/core/rates",              ((), [Permission.CONFIG_WRITE])),
    ("/v1/core/tenants",            ((), [Permission.TENANT_WRITE])),
    ("/v1/core/config",             ((), [Permission.CONFIG_WRITE])),
    ("/v1/core/tenant-config",      ((), [Permission.CONFIG_WRITE])),

    # ── HR / workforce ────────────────────────────────────────────────
    ("/v1/hr/allocations",          ((), [Permission.ALLOCATION_WRITE])),
    ("/v1/hr/payroll",              ((), [Permission.PAYROLL_WRITE])),
    ("/v1/hr/productivity",         ((), [Permission.PRODUCTIVITY_WRITE])),
    ("/v1/workforce",               (("GET",), [Permission.ALLOCATION_READ])),

    # ── Governance / decisions / RBAC admin ───────────────────────────
    ("/v1/governance",              ((), [Permission.SCHEDULE_WRITE])),
    ("/v1/decisions",               ((), [Permission.SCHEDULE_WRITE])),
    ("/v1/dqa",                     (("GET",), [Permission.SCHEDULE_READ])),
    ("/v1/diagnostics",             (("GET",), [Permission.SCHEDULE_READ])),

    # ── Copilot ───────────────────────────────────────────────────────
    ("/v1/copilot",                 ((), [Permission.SCHEDULE_READ])),

    # ── Sprint Q.18.A.3 — close fall-through gaps ─────────────────────
    # Each prefix here used to fall through the middleware (no entry =
    # no enforcement). Picked permissions match the dominant verb of the
    # router: SCENARIO_WRITE for twin/sandbox (both create+publish what-if
    # scenarios), SCHEDULE_WRITE for improve (approve/reject mutates the
    # plan), MRP_WRITE for supply (ROP/ABC/forecast write outputs), and
    # READ for the analyses / catalogues.
    ("/v1/twin",                    ((), [Permission.SCENARIO_WRITE])),
    ("/v1/sandbox",                 ((), [Permission.SCENARIO_WRITE])),
    ("/v1/improve",                 ((), [Permission.SCHEDULE_WRITE])),
    ("/v1/supply",                  ((), [Permission.MRP_WRITE])),
    ("/v1/explain",                 (("GET",), [Permission.SCHEDULE_READ])),
    ("/v1/factory-map",             (("GET",), [Permission.MASTER_DATA_READ])),
    ("/v1/factory",                 (("GET",), [Permission.MASTER_DATA_READ])),
    ("/v1/runbooks",                ((), [Permission.SCHEDULE_READ])),
    ("/v1/tools",                   ((), [Permission.SCHEDULE_READ])),
    ("/v1/ml",                      ((), [Permission.SCHEDULE_READ])),
    ("/v1/activity",                (("GET",), [Permission.SCHEDULE_READ])),
])


def requirements_for_route(
    path: str, method: str = "GET",
) -> Optional[List[Permission]]:
    """Return the required permissions for an HTTP path + method.

    Picks the longest matching prefix (most specific wins). Returns
    ``None`` when no prefix matches — callers default to "deny" when
    they want fail-closed semantics, or "fall through to per-route
    decorator" when they want gradual rollout.
    """
    method = method.upper()
    best: Optional[Tuple[int, _RoutePolicy]] = None
    for prefix, policy in ROUTE_PREFIX_REQUIREMENTS.items():
        if not path.startswith(prefix):
            continue
        allowed_methods, _perms = policy
        if allowed_methods and method not in allowed_methods:
            continue
        if best is None or len(prefix) > best[0]:
            best = (len(prefix), policy)
    if best is None:
        return None
    return list(best[1][1])


def is_route_allowed_for_role(
    path: str, method: str, role: str,
) -> bool:
    """One-call helper: does this role have at least one of the
    permissions the route demands? Returns True when the route has no
    matrix entry (gradual rollout — caller may still gate via the
    legacy per-route decorator).
    """
    required = requirements_for_route(path, method)
    if required is None:
        return True
    return has_any_permission(role, required)


def has_permission(role: str, permission: Permission) -> bool:
    """Check if role has permission."""
    try:
        role_enum = Role(role)
        return permission in ROLE_PERMISSIONS.get(role_enum, set())
    except ValueError:
        return False


def has_any_permission(role: str, permissions: List[Permission]) -> bool:
    """Check if role has any of the permissions."""
    return any(has_permission(role, p) for p in permissions)


def has_all_permissions(role: str, permissions: List[Permission]) -> bool:
    """Check if role has all permissions."""
    return all(has_permission(role, p) for p in permissions)


# ============================================================================
# SEGREGATION OF DUTIES (SoD) POLICIES
# ============================================================================

# SoD Policies: Maps action_type to required approver roles
# These policies ensure that decisions cannot be self-approved
# Format: action_type -> list of roles that can approve
SOD_POLICIES: dict[str, List[Role]] = {
    "INCREASE_SS": [Role.MANAGER_OPERATIONS, Role.PLANNER_SUPPLY],
    "DECREASE_SS": [Role.MANAGER_OPERATIONS, Role.PLANNER_SUPPLY],
    "ADJUST_PRICE": [Role.FINANCE_CONTROLLER, Role.MANAGER_OPERATIONS],
    "INCREASE_PRICE": [Role.FINANCE_CONTROLLER],
    "DECREASE_PRICE": [Role.FINANCE_CONTROLLER, Role.MANAGER_OPERATIONS],
    "RESCHEDULE_ORDER": [Role.MANAGER_OPERATIONS, Role.PLANNER_SUPPLY],
    "CANCEL_ORDER": [Role.MANAGER_OPERATIONS],
    "CHANGE_PRIORITY": [Role.MANAGER_OPERATIONS],
    "REALLOCATE_RESOURCE": [Role.MANAGER_OPERATIONS, Role.HR_MANAGER],
    "CHANGE_STANDARD_TIME": [Role.MANAGER_OPERATIONS, Role.PLANNER_SUPPLY],
    "UPDATE_COST": [Role.FINANCE_CONTROLLER],
    "APPROVE_OVERTIME": [Role.HR_MANAGER, Role.MANAGER_OPERATIONS],
    # Default policy for unknown action types
    "GENERIC_ACTION": [Role.MANAGER_OPERATIONS, Role.FINANCE_CONTROLLER],
}


def check_sod(
    action_type: str,
    proposer_id: UUID,
    proposer_role: Role,
    approver_id: UUID,
    approver_role: Role,
) -> Tuple[bool, Optional[str]]:
    """
    Check Segregation of Duties (SoD) policy.
    
    Args:
        action_type: Type of action being approved
        proposer_id: UUID of the user who proposed the decision
        proposer_role: Role of the proposer
        approver_id: UUID of the user attempting to approve
        approver_role: Role of the approver
    
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if SoD check passes
        - error_message: None if valid, otherwise error description
    """
    # Rule 1: Approver cannot be the same as proposer
    if proposer_id == approver_id:
        return False, "Segregation of Duties violation: Cannot approve own decision"
    
    # Rule 2: Approver must have required role for this action type.
    # Q.171.B — admin_platform aprova qualquer action_type (papel de
    # plataforma; nenhum SOD_POLICIES o lista um a um). A regra 1
    # (proposer != approver) continua a aplicar-se a admins.
    if approver_role == Role.ADMIN_PLATFORM:
        return True, None

    required_roles = SOD_POLICIES.get(action_type, SOD_POLICIES.get("GENERIC_ACTION", []))
    
    if not required_roles:
        # If no policy exists and not generic, allow any approver (except proposer)
        return True, None
    
    if approver_role not in required_roles:
        roles_str = ", ".join([r.value for r in required_roles])
        return False, f"Approver role '{approver_role.value}' not authorized. Required roles: {roles_str}"

    return True, None


def require_permission(permission: Permission):
    """Decorator to require a specific permission."""
    async def permission_checker(
        user: UserContext = Depends(get_current_user_or_dev_header),
    ) -> UserContext:
        if not has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission.value}' required",
            )
        return user
    
    return permission_checker


def require_role(allowed_roles: List[Role]):
    """Decorator to require one of the specified roles."""
    async def role_checker(
        user: UserContext = Depends(get_current_user_or_dev_header),
    ) -> UserContext:
        try:
            user_role = Role(user.role)
            if user_role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{user.role}' not authorized",
                )
            return user
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unknown role '{user.role}'",
            )
    
    return role_checker


class PermissionDependency:
    """
    Permission dependency for FastAPI.
    
    Usage:
        @router.get("/items", dependencies=[Depends(PermissionDependency([Permission.ITEM_READ]))])
        async def get_items():
            ...
    """
    
    def __init__(self, permissions: List[Permission], require_all: bool = False):
        self.permissions = permissions
        self.require_all = require_all
    
    async def __call__(
        self,
        user: UserContext = Depends(get_current_user_or_dev_header),
    ) -> UserContext:
        if self.require_all:
            has_perms = has_all_permissions(user.role, self.permissions)
        else:
            has_perms = has_any_permission(user.role, self.permissions)
        
        if not has_perms:
            perms_str = ", ".join(p.value for p in self.permissions)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required permission(s): {perms_str}",
            )
        
        return user

