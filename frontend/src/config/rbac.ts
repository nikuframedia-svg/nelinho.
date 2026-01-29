/**
 * RBAC Configuration
 * ==================
 * 
 * Source of truth: src/shared/auth/rbac.py
 * 
 * These are static configuration values that mirror the backend.
 * If backend RBAC changes, this file must be updated.
 * 
 * Last synced from backend: 2026-01-28
 */

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

export interface Role {
  id: string;
  name: string;
  description: string;
  permissions: string[];
}

export interface Permission {
  id: string;
  name: string;
  category: 'CORE' | 'PLAN' | 'PROFIT' | 'HR';
  description: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// ROLES
// Source: src/shared/auth/rbac.py lines 18-135
// ═══════════════════════════════════════════════════════════════════════════════

export const ROLES: Role[] = [
  {
    id: 'admin_platform',
    name: 'Admin Platform',
    description: 'Full system access',
    permissions: ['*'],
  },
  {
    id: 'manager_operations',
    name: 'Manager Operations',
    description: 'Operations and production management',
    permissions: [
      'master_data:read',
      'master_data:write',
      'config:read',
      'schedule:read',
      'schedule:write',
      'mrp:read',
      'mrp:write',
      'capacity:read',
      'cogs:read',
      'cogs:write',
      'pricing:read',
      'scenario:read',
      'scenario:write',
      'allocation:read',
      'allocation:write',
      'productivity:read',
    ],
  },
  {
    id: 'planner_supply',
    name: 'Planner Supply',
    description: 'Supply chain planning',
    permissions: [
      'master_data:read',
      'schedule:read',
      'schedule:write',
      'mrp:read',
      'mrp:write',
      'capacity:read',
      'cogs:read',
      'allocation:read',
    ],
  },
  {
    id: 'finance_controller',
    name: 'Finance Controller',
    description: 'Financial control and costing',
    permissions: [
      'master_data:read',
      'config:read',
      'config:write',
      'schedule:read',
      'cogs:read',
      'cogs:write',
      'pricing:read',
      'pricing:write',
      'scenario:read',
      'scenario:write',
      'payroll:read',
    ],
  },
  {
    id: 'hr_manager',
    name: 'HR Manager',
    description: 'Human resources management',
    permissions: [
      'master_data:read',
      'schedule:read',
      'allocation:read',
      'allocation:write',
      'payroll:read',
      'payroll:write',
      'productivity:read',
      'productivity:write',
    ],
  },
  {
    id: 'operator',
    name: 'Operator',
    description: 'Production operator',
    permissions: [
      'schedule:read',
      'allocation:read',
      'productivity:read',
    ],
  },
  {
    id: 'viewer',
    name: 'Viewer',
    description: 'View only access',
    permissions: [
      'master_data:read',
      'schedule:read',
      'capacity:read',
      'cogs:read',
      'allocation:read',
    ],
  },
];

// ═══════════════════════════════════════════════════════════════════════════════
// PERMISSIONS
// Source: src/shared/auth/rbac.py lines 29-60
// ═══════════════════════════════════════════════════════════════════════════════

export const PERMISSIONS: Permission[] = [
  // CORE
  { id: 'tenant:read', name: 'Tenant Read', category: 'CORE', description: 'Read tenant information' },
  { id: 'tenant:write', name: 'Tenant Write', category: 'CORE', description: 'Create/edit tenants' },
  { id: 'master_data:read', name: 'Master Data Read', category: 'CORE', description: 'Read master data' },
  { id: 'master_data:write', name: 'Master Data Write', category: 'CORE', description: 'Create/edit master data' },
  { id: 'config:read', name: 'Config Read', category: 'CORE', description: 'Read configurations' },
  { id: 'config:write', name: 'Config Write', category: 'CORE', description: 'Edit configurations' },
  
  // PLAN
  { id: 'schedule:read', name: 'Schedule Read', category: 'PLAN', description: 'Read schedules' },
  { id: 'schedule:write', name: 'Schedule Write', category: 'PLAN', description: 'Create/edit schedules' },
  { id: 'mrp:read', name: 'MRP Read', category: 'PLAN', description: 'Read MRP' },
  { id: 'mrp:write', name: 'MRP Write', category: 'PLAN', description: 'Create/edit MRP' },
  { id: 'capacity:read', name: 'Capacity Read', category: 'PLAN', description: 'Read capacity' },
  
  // PROFIT
  { id: 'cogs:read', name: 'COGS Read', category: 'PROFIT', description: 'Read costs' },
  { id: 'cogs:write', name: 'COGS Write', category: 'PROFIT', description: 'Edit costs' },
  { id: 'pricing:read', name: 'Pricing Read', category: 'PROFIT', description: 'Read prices' },
  { id: 'pricing:write', name: 'Pricing Write', category: 'PROFIT', description: 'Edit prices' },
  { id: 'scenario:read', name: 'Scenario Read', category: 'PROFIT', description: 'Read scenarios' },
  { id: 'scenario:write', name: 'Scenario Write', category: 'PROFIT', description: 'Create/edit scenarios' },
  
  // HR
  { id: 'allocation:read', name: 'Allocation Read', category: 'HR', description: 'Read allocations' },
  { id: 'allocation:write', name: 'Allocation Write', category: 'HR', description: 'Create/edit allocations' },
  { id: 'payroll:read', name: 'Payroll Read', category: 'HR', description: 'Read payroll' },
  { id: 'payroll:write', name: 'Payroll Write', category: 'HR', description: 'Edit payroll' },
  { id: 'productivity:read', name: 'Productivity Read', category: 'HR', description: 'Read productivity' },
  { id: 'productivity:write', name: 'Productivity Write', category: 'HR', description: 'Edit productivity' },
];

// ═══════════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Check if a role has a specific permission
 */
export function hasPermission(role: Role, permissionId: string): boolean {
  if (role.permissions.includes('*')) return true;
  return role.permissions.includes(permissionId);
}

/**
 * Get role by ID
 */
export function getRoleById(id: string): Role | undefined {
  return ROLES.find(r => r.id === id);
}

/**
 * Get permission by ID
 */
export function getPermissionById(id: string): Permission | undefined {
  return PERMISSIONS.find(p => p.id === id);
}

/**
 * Get permissions grouped by category
 */
export function getPermissionsByCategory(): Record<string, Permission[]> {
  return PERMISSIONS.reduce((acc, perm) => {
    if (!acc[perm.category]) acc[perm.category] = [];
    acc[perm.category].push(perm);
    return acc;
  }, {} as Record<string, Permission[]>);
}

/**
 * Get all permissions for a role
 */
export function getRolePermissions(role: Role): Permission[] {
  if (role.permissions.includes('*')) return PERMISSIONS;
  return PERMISSIONS.filter(p => role.permissions.includes(p.id));
}

export default { ROLES, PERMISSIONS };

