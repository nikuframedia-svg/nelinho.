/**
 * RBAC Management Page
 * ====================
 * 
 * Displays roles and permissions from static configuration.
 * Source of truth: src/shared/auth/rbac.py
 * 
 * NO mock data - uses config from frontend/src/config/rbac.ts
 * which mirrors the backend RBAC definitions.
 */

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Shield, Users, CheckCircle2, XCircle, Key, Info } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import {
  DarkCard,
  DarkButton,
  DarkBadge,
  DarkTable,
  DarkTableHead,
  DarkTableBody,
  DarkTableRow,
  DarkTableHeader,
  DarkTableCell,
  DarkPillButton,
} from '../../components/dark';
import { 
  ROLES, 
  PERMISSIONS, 
  hasPermission,
  getPermissionsByCategory,
  type Role, 
  type Permission 
} from '../../config/rbac';

export function RBACPage() {
  const [viewMode, setViewMode] = useState<'roles' | 'matrix'>('roles');

  // Static config - no API call needed, data never changes at runtime
  const { data: roles } = useQuery<Role[]>({
    queryKey: ['rbac', 'roles'],
    queryFn: async () => ROLES,
    staleTime: Infinity, // Static config never changes
  });

  const { data: permissions } = useQuery<Permission[]>({
    queryKey: ['rbac', 'permissions'],
    queryFn: async () => PERMISSIONS,
    staleTime: Infinity, // Static config never changes
  });

  const getCategoryVariant = (category: string): 'info' | 'accent' | 'success' | 'warning' | 'neutral' => {
    const variants: Record<string, 'info' | 'accent' | 'success' | 'warning' | 'neutral'> = {
      CORE: 'info',
      PLAN: 'accent',
      PROFIT: 'success',
      HR: 'warning',
    };
    return variants[category] || 'neutral';
  };

  return (
    <DarkPageLayout
      breadcrumbs={[{ label: 'Sistema' }, { label: 'Acessos' }, { label: 'RBAC' }]}
      title="RBAC Management"
      subtitle="Role-Based Access Control"
      icon={<Shield size={20} />}
    >
      {/* Static Configuration Notice */}
      <DarkCard className="mb-6 bg-blue-500/10 border-blue-500/20">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-blue-500/20 rounded-lg flex-shrink-0">
            <Info size={18} className="text-blue-400" />
          </div>
          <div>
            <h4 className="text-sm font-medium text-blue-400">Static Configuration</h4>
            <p className="text-xs text-slate-400 mt-1">
              Roles and permissions are defined in <code className="text-blue-300 bg-slate-800 px-1.5 py-0.5 rounded">src/shared/auth/rbac.py</code>.
              Changes require code deployment. This page displays the current RBAC configuration.
            </p>
          </div>
        </div>
      </DarkCard>

      {/* View Mode Toggle */}
      <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1 w-fit mb-6">
        <DarkPillButton
          active={viewMode === 'roles'}
          onClick={() => setViewMode('roles')}
        >
          <Users size={16} className="mr-1.5" />
          Roles ({ROLES.length})
        </DarkPillButton>
        <DarkPillButton
          active={viewMode === 'matrix'}
          onClick={() => setViewMode('matrix')}
        >
          <Key size={16} className="mr-1.5" />
          Permissions Matrix
        </DarkPillButton>
      </div>

      {/* Roles Overview */}
      {viewMode === 'roles' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {roles?.map((role) => (
            <DarkCard key={role.id}>
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <Shield size={20} className="text-accent" />
                    <h3 className="font-semibold text-text-white">{role.name}</h3>
                  </div>
                  {role.description && (
                    <p className="text-sm text-text-tertiary mb-3">{role.description}</p>
                  )}
                </div>
                <DarkBadge variant="neutral" size="sm">
                  {role.id}
                </DarkBadge>
              </div>
              
              <div className="mb-4">
                <p className="text-xs font-medium text-text-secondary mb-2">
                  Permissions ({role.permissions.includes('*') ? 'All' : role.permissions.length})
                </p>
                {role.permissions.includes('*') ? (
                  <DarkBadge variant="success">All permissions</DarkBadge>
                ) : (
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {role.permissions.slice(0, 5).map((perm) => (
                      <div key={perm} className="text-xs text-text-tertiary bg-bg-elevated px-2 py-1 rounded">
                        {perm}
                      </div>
                    ))}
                    {role.permissions.length > 5 && (
                      <p className="text-xs text-text-tertiary">
                        +{role.permissions.length - 5} more...
                      </p>
                    )}
                  </div>
                )}
              </div>

              <DarkButton
                variant="ghost"
                size="sm"
                fullWidth
                onClick={() => setViewMode('matrix')}
              >
                View Permissions
              </DarkButton>
            </DarkCard>
          ))}
        </div>
      )}

      {/* Permissions Matrix */}
      {viewMode === 'matrix' && (
        <DarkCard padding="none">
          <div className="p-6 border-b border-border-subtle">
            <h2 className="text-lg font-semibold text-text-white mb-1">Permissions Matrix</h2>
            <p className="text-sm text-text-tertiary">
              Visualization of which roles have which permissions
            </p>
          </div>

          {roles && permissions ? (
            <div className="overflow-x-auto">
              <DarkTable>
                <DarkTableHead>
                  <DarkTableRow>
                    <DarkTableHeader className="sticky left-0 bg-bg-card z-10 min-w-[200px]">
                      Permission
                    </DarkTableHeader>
                    {roles.map((role) => (
                      <DarkTableHeader key={role.id} className="min-w-[120px]" align="center">
                        <div className="flex flex-col items-center gap-1">
                          <span className="text-xs font-medium">{role.name}</span>
                        </div>
                      </DarkTableHeader>
                    ))}
                  </DarkTableRow>
                </DarkTableHead>
                <DarkTableBody>
                  {Object.entries(getPermissionsByCategory()).map(([category, categoryPermissions]) => (
                    <React.Fragment key={category}>
                      <DarkTableRow className="bg-bg-elevated">
                        <DarkTableCell className="font-semibold text-text-white">
                          <DarkBadge variant={getCategoryVariant(category)}>{category}</DarkBadge>
                        </DarkTableCell>
                        {roles.map((role) => (
                          <DarkTableCell key={role.id} align="center">—</DarkTableCell>
                        ))}
                      </DarkTableRow>
                      {categoryPermissions.map((perm) => (
                        <DarkTableRow key={perm.id}>
                          <DarkTableCell className="sticky left-0 bg-bg-card z-10">
                            <div>
                              <div className="font-medium text-sm text-text-white">{perm.name}</div>
                              <div className="text-xs text-text-tertiary font-mono">{perm.id}</div>
                              {perm.description && (
                                <div className="text-xs text-text-secondary mt-1">{perm.description}</div>
                              )}
                            </div>
                          </DarkTableCell>
                          {roles.map((role) => (
                            <DarkTableCell key={role.id} align="center">
                              {hasPermission(role, perm.id) ? (
                                <CheckCircle2 size={18} className="text-success mx-auto" />
                              ) : (
                                <XCircle size={18} className="text-text-tertiary opacity-30 mx-auto" />
                              )}
                            </DarkTableCell>
                          ))}
                        </DarkTableRow>
                      ))}
                    </React.Fragment>
                  ))}
                </DarkTableBody>
              </DarkTable>
            </div>
          ) : null}
        </DarkCard>
      )}

      {/* Footer with source info */}
      <div className="mt-6 px-4 py-3 bg-slate-800/30 border border-slate-700/30 rounded-xl">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Info size={12} />
          <span>
            Source: <code className="text-slate-400">src/shared/auth/rbac.py</code> | 
            Config synced from backend on 2026-01-28
          </span>
        </div>
      </div>
    </DarkPageLayout>
  );
}
