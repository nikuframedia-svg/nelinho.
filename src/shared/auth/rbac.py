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

from .jwt_handler import UserContext, get_current_user


class Role(str, Enum):
    """User roles."""
    ADMIN_PLATFORM = "admin_platform"
    MANAGER_OPERATIONS = "manager_operations"
    PLANNER_SUPPLY = "planner_supply"
    FINANCE_CONTROLLER = "finance_controller"
    HR_MANAGER = "hr_manager"
    OPERATOR = "operator"
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
        Permission.SCHEDULE_READ,
        Permission.ALLOCATION_READ,
        Permission.PRODUCTIVITY_READ,
    },
    
    Role.VIEWER: {
        Permission.MASTER_DATA_READ,
        Permission.SCHEDULE_READ,
        Permission.CAPACITY_READ,
        Permission.COGS_READ,
        Permission.ALLOCATION_READ,
    },
}


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
    
    # Rule 2: Approver must have required role for this action type
    required_roles = SOD_POLICIES.get(action_type, SOD_POLICIES.get("GENERIC_ACTION", []))
    
    if not required_roles:
        # If no policy exists and not generic, allow any approver (except proposer)
        return True, None
    
    if approver_role not in required_roles:
        roles_str = ", ".join([r.value for r in required_roles])
        return False, f"Approver role '{approver_role.value}' not authorized. Required roles: {roles_str}"
    
    # Rule 3: Proposer cannot have approver role for this action type
    # (Additional layer: proposer should not be able to approve their own action type)
    if proposer_role in required_roles and proposer_id == approver_id:
        return False, "Proposer role is in approved roles list, but self-approval is blocked by SoD"
    
    return True, None


def require_permission(permission: Permission):
    """Decorator to require a specific permission."""
    async def permission_checker(
        user: UserContext = Depends(get_current_user),
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
        user: UserContext = Depends(get_current_user),
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
        user: UserContext = Depends(get_current_user),
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

