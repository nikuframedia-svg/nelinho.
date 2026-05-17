/**
 * Audit Trail Page
 * 
 * Displays audit logs and decision governance trail.
 * Uses REAL API data - NO mock data.
 * 
 * Integrates with:
 * - Decision Governance API: /v1/governance/decisions
 * - Entity Changes API: (placeholder for when implemented)
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  History, 
  Filter, 
  Download, 
  User, 
  Eye, 
  Loader2,
  ShieldCheck,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RotateCcw,
  Hash,
  Info,
  AlertCircle,
} from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/Dialog';
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
  DarkInput,
  DarkSelect,
  DarkIconButton,
} from '../../components/dark';
import { governanceApi } from '../../lib/factoryApi';
import type { DecisionRun } from '../../lib/factoryApi';
import { getApiBase } from '../../lib/api';

// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
const API_BASE = getApiBase();

// ============================================================================
// TYPES
// ============================================================================

interface AuditLog {
  id: string;
  timestamp: string;
  user_id: string;
  user_name?: string;
  entity_type: string;
  entity_id: string;
  action: string;
  changes: Record<string, any>;
  before_state?: Record<string, any> | null;
  after_state?: Record<string, any> | null;
  metadata?: Record<string, any>;
}

type ViewMode = 'table' | 'timeline';
type TabMode = 'audit' | 'decisions';

// ============================================================================
// API FUNCTIONS
// ============================================================================

async function fetchAuditLogs(filters: {
  entity_type?: string;
  user?: string;
  date_from?: string;
  date_to?: string;
}): Promise<AuditLog[]> {
  const tenantId = localStorage.getItem('tenant_id') || '00000000-0000-0000-0000-000000000000';
  
  const params = new URLSearchParams();
  if (filters.entity_type) params.append('entity_type', filters.entity_type);
  if (filters.user) params.append('user', filters.user);
  if (filters.date_from) params.append('date_from', filters.date_from);
  if (filters.date_to) params.append('date_to', filters.date_to);
  
  const response = await fetch(`${API_BASE}/v1/governance/audit-logs?${params}`, {
    headers: {
      'X-Tenant-Id': tenantId,
    },
  });
  
  if (!response.ok) {
    // If 404, endpoint not yet implemented - return empty array with notice
    if (response.status === 404) {
      return [];
    }
    throw new Error(`Failed to fetch audit logs: ${response.status}`);
  }
  
  return response.json();
}

// ============================================================================
// COMPONENT
// ============================================================================

export function AuditTrailPage() {
  const queryClient = useQueryClient();
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);
  const [selectedDecision, setSelectedDecision] = useState<DecisionRun | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [tabMode, setTabMode] = useState<TabMode>('decisions');
  const [filters, setFilters] = useState({
    entity_type: '',
    user: '',
    action: '',
    date_from: '',
    date_to: '',
    status: '',
  });

  // Fetch decisions from governance API
  const { 
    data: decisions, 
    isLoading: isLoadingDecisions,
    error: decisionsError,
    refetch: refetchDecisions,
  } = useQuery({
    queryKey: ['governance-decisions', filters.status],
    queryFn: () => governanceApi.getDecisions(filters.status || undefined),
    enabled: tabMode === 'decisions',
    retry: 2,
  });

  // Fetch audit logs from real API
  const { 
    data: auditLogs, 
    isLoading: isLoadingAudit,
    error: auditError,
    refetch: refetchAudit,
  } = useQuery<AuditLog[]>({
    queryKey: ['audit-logs', filters.entity_type, filters.user, filters.date_from, filters.date_to],
    queryFn: () => fetchAuditLogs({
      entity_type: filters.entity_type || undefined,
      user: filters.user || undefined,
      date_from: filters.date_from || undefined,
      date_to: filters.date_to || undefined,
    }),
    enabled: tabMode === 'audit',
    retry: 2,
  });

  // Rollback mutation
  const rollbackMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      governanceApi.rollbackDecision(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['governance-decisions'] });
      setSelectedDecision(null);
    },
  });

  const isLoading = tabMode === 'decisions' ? isLoadingDecisions : isLoadingAudit;
  const error = tabMode === 'decisions' ? decisionsError : auditError;

  // Export handlers
  const handleExport = (format: 'csv' | 'json') => {
    const data = tabMode === 'decisions' ? decisions : auditLogs;
    if (!data || data.length === 0) {
      alert('No data to export');
      return;
    }
    
    if (format === 'csv') {
      const headers = tabMode === 'decisions'
        ? ['ID', 'Action Type', 'Status', 'Created At', 'Created By', 'Audit Hash']
        : ['Timestamp', 'User', 'Entity Type', 'Entity ID', 'Action'];
      
      const rows = tabMode === 'decisions'
        ? (data as DecisionRun[]).map(d => [
            d.id.slice(0, 8),
            d.action_type,
            d.status,
            new Date(d.created_at).toLocaleString(),
            d.created_by,
            d.audit_hash.slice(0, 12),
          ])
        : (data as AuditLog[]).map(log => [
            new Date(log.timestamp).toLocaleString(),
            log.user_name || log.user_id,
            log.entity_type,
            log.entity_id,
            log.action,
          ]);
      
      const csv = [headers, ...rows].map(row => row.join(',')).join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${tabMode}-trail-${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
    } else {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${tabMode}-trail-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
    }
  };

  // Badge variants
  const getActionVariant = (action: string): 'success' | 'warning' | 'danger' | 'neutral' => {
    const variants: Record<string, 'success' | 'warning' | 'danger' | 'neutral'> = {
      CREATE: 'success',
      UPDATE: 'warning',
      DELETE: 'danger',
    };
    return variants[action] || 'neutral';
  };

  const getDecisionStatusVariant = (status: string): 'success' | 'warning' | 'danger' | 'neutral' => {
    const variants: Record<string, 'success' | 'warning' | 'danger' | 'neutral'> = {
      PROPOSED: 'neutral',
      APPROVED: 'success',
      EXECUTED: 'success',
      REJECTED: 'danger',
      ROLLED_BACK: 'warning',
      KILLED: 'danger',
    };
    return variants[status] || 'neutral';
  };

  const getDecisionStatusIcon = (status: string) => {
    switch (status) {
      case 'APPROVED':
      case 'EXECUTED':
        return <CheckCircle size={14} className="text-green-400" />;
      case 'REJECTED':
      case 'KILLED':
        return <XCircle size={14} className="text-red-400" />;
      case 'ROLLED_BACK':
        return <RotateCcw size={14} className="text-amber-400" />;
      default:
        return <AlertTriangle size={14} className="text-gray-400" />;
    }
  };

  const entityTypeOptions = [
    { value: '', label: 'All' },
    { value: 'products', label: 'Products' },
    { value: 'orders', label: 'Orders' },
    { value: 'employees', label: 'Employees' },
    { value: 'machines', label: 'Machines' },
  ];

  const statusOptions = [
    { value: '', label: 'All' },
    { value: 'PROPOSED', label: 'Proposed' },
    { value: 'APPROVED', label: 'Approved' },
    { value: 'EXECUTED', label: 'Executed' },
    { value: 'REJECTED', label: 'Rejected' },
    { value: 'ROLLED_BACK', label: 'Rolled Back' },
  ];

  return (
    <DarkPageLayout
      breadcrumbs={[{ label: 'Sistema' }, { label: 'Auditoria' }]}
      title="Audit Trail"
      subtitle="Complete history of all system changes and decisions"
      icon={<History size={20} />}
      actions={
        <div className="flex gap-2">
          <DarkButton variant="secondary" size="sm" icon={<Download size={16} />} onClick={() => handleExport('csv')}>
            Export CSV
          </DarkButton>
          <DarkButton variant="secondary" size="sm" icon={<Download size={16} />} onClick={() => handleExport('json')}>
            Export JSON
          </DarkButton>
        </div>
      }
    >
      {/* Tab Selection */}
      <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1 w-fit mb-4">
        <DarkPillButton
          active={tabMode === 'decisions'}
          onClick={() => setTabMode('decisions')}
        >
          <ShieldCheck size={14} className="mr-1" />
          Decision Governance
        </DarkPillButton>
        <DarkPillButton
          active={tabMode === 'audit'}
          onClick={() => setTabMode('audit')}
        >
          <History size={14} className="mr-1" />
          Entity Changes
        </DarkPillButton>
      </div>

      {/* API Error Notice */}
      {error && (
        <DarkCard className="mb-4 border-red-500/30 bg-red-500/10">
          <div className="flex items-center gap-3">
            <AlertCircle size={20} className="text-red-400" />
            <div className="flex-1">
              <p className="font-medium text-red-300">Error loading data</p>
              <p className="text-sm text-red-400/80">{(error as Error).message}</p>
            </div>
            <DarkButton 
              variant="secondary" 
              size="sm" 
              onClick={() => tabMode === 'decisions' ? refetchDecisions() : refetchAudit()}
            >
              Retry
            </DarkButton>
          </div>
        </DarkCard>
      )}

      {/* Filters */}
      <DarkCard className="mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Filter size={18} className="text-text-tertiary" />
          <h3 className="font-semibold text-text-white">Filters</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {tabMode === 'audit' ? (
            <>
              <DarkSelect
                options={entityTypeOptions}
                value={filters.entity_type}
                onChange={(e) => setFilters({ ...filters, entity_type: e.target.value })}
                label="Entity Type"
              />
              <DarkInput
                value={filters.user}
                onChange={(e) => setFilters({ ...filters, user: e.target.value })}
                placeholder="ID or name"
                label="User"
              />
            </>
          ) : (
            <DarkSelect
              options={statusOptions}
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              label="Status"
            />
          )}
          <DarkInput
            type="date"
            value={filters.date_from}
            onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
            label="Date From"
          />
          <DarkInput
            type="date"
            value={filters.date_to}
            onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
            label="Date To"
          />
        </div>
      </DarkCard>

      {/* View Mode Toggle (only for audit tab) */}
      {tabMode === 'audit' && (
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1 w-fit mb-4">
          <DarkPillButton
            active={viewMode === 'table'}
            onClick={() => setViewMode('table')}
          >
            Table
          </DarkPillButton>
          <DarkPillButton
            active={viewMode === 'timeline'}
            onClick={() => setViewMode('timeline')}
          >
            Timeline
          </DarkPillButton>
        </div>
      )}

      {/* Decision Governance Table */}
      {tabMode === 'decisions' && (
        <DarkCard padding="none">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={32} className="text-accent animate-spin" />
              <span className="ml-3 text-text-secondary">Loading decisions from API...</span>
            </div>
          ) : decisions && decisions.length > 0 ? (
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>ID</DarkTableHeader>
                  <DarkTableHeader>Action Type</DarkTableHeader>
                  <DarkTableHeader>Status</DarkTableHeader>
                  <DarkTableHeader>Created By</DarkTableHeader>
                  <DarkTableHeader>Created At</DarkTableHeader>
                  <DarkTableHeader>Audit Hash</DarkTableHeader>
                  <DarkTableHeader align="right">Actions</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {decisions.map((decision) => (
                  <DarkTableRow key={decision.id}>
                    <DarkTableCell mono className="text-text-tertiary">
                      {decision.id.slice(0, 8)}...
                    </DarkTableCell>
                    <DarkTableCell>
                      <span className="text-text-white">{decision.action_type}</span>
                    </DarkTableCell>
                    <DarkTableCell>
                      <div className="flex items-center gap-2">
                        {getDecisionStatusIcon(decision.status)}
                        <DarkBadge variant={getDecisionStatusVariant(decision.status)}>
                          {decision.status}
                        </DarkBadge>
                      </div>
                    </DarkTableCell>
                    <DarkTableCell>
                      <div className="flex items-center gap-2">
                        <User size={14} className="text-text-tertiary" />
                        <span className="text-text-white">{decision.created_by}</span>
                      </div>
                    </DarkTableCell>
                    <DarkTableCell className="text-text-secondary">
                      {new Date(decision.created_at).toLocaleString()}
                    </DarkTableCell>
                    <DarkTableCell>
                      <div className="flex items-center gap-1 font-mono text-xs text-text-tertiary">
                        <Hash size={12} />
                        {decision.audit_hash.slice(0, 12)}...
                      </div>
                    </DarkTableCell>
                    <DarkTableCell align="right">
                      <DarkIconButton
                        icon={<Eye size={16} />}
                        size="sm"
                        variant="ghost"
                        onClick={() => setSelectedDecision(decision)}
                        title="View details"
                      />
                    </DarkTableCell>
                  </DarkTableRow>
                ))}
              </DarkTableBody>
            </DarkTable>
          ) : !error ? (
            <div className="text-center py-12">
              <ShieldCheck size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
              <p className="text-text-secondary">No decisions found.</p>
              <p className="text-text-tertiary text-sm mt-1">
                Decisions will appear here when actions are proposed and executed.
              </p>
            </div>
          ) : null}
        </DarkCard>
      )}

      {/* Audit Log Table View */}
      {tabMode === 'audit' && viewMode === 'table' && (
        <DarkCard padding="none">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={32} className="text-accent animate-spin" />
              <span className="ml-3 text-text-secondary">Loading audit logs from API...</span>
            </div>
          ) : auditLogs && auditLogs.length > 0 ? (
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>Timestamp</DarkTableHeader>
                  <DarkTableHeader>User</DarkTableHeader>
                  <DarkTableHeader>Type</DarkTableHeader>
                  <DarkTableHeader>ID</DarkTableHeader>
                  <DarkTableHeader>Action</DarkTableHeader>
                  <DarkTableHeader align="right">Actions</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {auditLogs.map((log) => (
                  <DarkTableRow key={log.id}>
                    <DarkTableCell className="text-text-secondary">
                      {new Date(log.timestamp).toLocaleString()}
                    </DarkTableCell>
                    <DarkTableCell>
                      <div className="flex items-center gap-2">
                        <User size={14} className="text-text-tertiary" />
                        <span className="text-text-white">{log.user_name || log.user_id}</span>
                      </div>
                    </DarkTableCell>
                    <DarkTableCell>
                      <DarkBadge variant="neutral">{log.entity_type}</DarkBadge>
                    </DarkTableCell>
                    <DarkTableCell mono className="text-text-tertiary">{log.entity_id}</DarkTableCell>
                    <DarkTableCell>
                      <DarkBadge variant={getActionVariant(log.action)}>{log.action}</DarkBadge>
                    </DarkTableCell>
                    <DarkTableCell align="right">
                      <DarkIconButton
                        icon={<Eye size={16} />}
                        size="sm"
                        variant="ghost"
                        onClick={() => setSelectedLog(log)}
                        title="View details"
                      />
                    </DarkTableCell>
                  </DarkTableRow>
                ))}
              </DarkTableBody>
            </DarkTable>
          ) : !error ? (
            <div className="text-center py-12">
              <History size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
              <p className="text-text-secondary">No audit logs found.</p>
              <p className="text-text-tertiary text-sm mt-1">
                Entity change logs will appear here when entities are modified.
              </p>
              <div className="mt-4 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg max-w-md mx-auto">
                <div className="flex items-start gap-2">
                  <Info size={16} className="text-blue-400 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-blue-300">
                    The audit logs endpoint may not be implemented yet. 
                    Check /v1/governance/audit-logs in the backend.
                  </p>
                </div>
              </div>
            </div>
          ) : null}
        </DarkCard>
      )}

      {/* Timeline View */}
      {tabMode === 'audit' && viewMode === 'timeline' && (
        <DarkCard>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={32} className="text-accent animate-spin" />
            </div>
          ) : auditLogs && auditLogs.length > 0 ? (
            <div className="relative">
              <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-border-subtle" />
              <div className="space-y-6">
                {auditLogs.map((log) => (
                  <div key={log.id} className="relative pl-12">
                    <div className="absolute left-2 top-1.5 w-4 h-4 bg-accent rounded-full border-4 border-bg-card shadow" />
                    <div className="bg-bg-elevated border border-border-subtle rounded-lg p-4 hover:border-border-hover transition-colors">
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <DarkBadge variant={getActionVariant(log.action)}>{log.action}</DarkBadge>
                            <span className="text-sm font-medium text-text-white capitalize">
                              {log.entity_type}
                            </span>
                            <span className="text-xs text-text-tertiary font-mono">
                              #{log.entity_id}
                            </span>
                          </div>
                          <p className="text-xs text-text-tertiary">
                            by {log.user_name || log.user_id} • {new Date(log.timestamp).toLocaleString()}
                          </p>
                        </div>
                        <DarkIconButton
                          icon={<Eye size={14} />}
                          size="sm"
                          variant="ghost"
                          onClick={() => setSelectedLog(log)}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : !error ? (
            <div className="text-center py-12">
              <History size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
              <p className="text-text-secondary">No audit logs found.</p>
            </div>
          ) : null}
        </DarkCard>
      )}

      {/* Decision Detail Modal */}
      {selectedDecision && (
        <Dialog open={!!selectedDecision} onOpenChange={() => setSelectedDecision(null)}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-bg-card border-border-subtle">
            <DialogHeader>
              <DialogTitle className="text-text-white flex items-center gap-2">
                <ShieldCheck size={20} />
                Decision Details
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-bg-elevated p-3 rounded-lg">
                  <p className="text-xs font-medium text-text-tertiary mb-1">Decision ID</p>
                  <p className="text-sm text-text-white font-mono">{selectedDecision.id}</p>
                </div>
                <div className="bg-bg-elevated p-3 rounded-lg">
                  <p className="text-xs font-medium text-text-tertiary mb-1">Action Type</p>
                  <p className="text-sm text-text-white">{selectedDecision.action_type}</p>
                </div>
                <div className="bg-bg-elevated p-3 rounded-lg">
                  <p className="text-xs font-medium text-text-tertiary mb-1">Status</p>
                  <div className="flex items-center gap-2">
                    {getDecisionStatusIcon(selectedDecision.status)}
                    <DarkBadge variant={getDecisionStatusVariant(selectedDecision.status)}>
                      {selectedDecision.status}
                    </DarkBadge>
                  </div>
                </div>
                <div className="bg-bg-elevated p-3 rounded-lg">
                  <p className="text-xs font-medium text-text-tertiary mb-1">Created By</p>
                  <p className="text-sm text-text-white">{selectedDecision.created_by}</p>
                </div>
                <div className="bg-bg-elevated p-3 rounded-lg">
                  <p className="text-xs font-medium text-text-tertiary mb-1">Created At</p>
                  <p className="text-sm text-text-white">
                    {new Date(selectedDecision.created_at).toLocaleString()}
                  </p>
                </div>
                {selectedDecision.approved_by && (
                  <div className="bg-bg-elevated p-3 rounded-lg">
                    <p className="text-xs font-medium text-text-tertiary mb-1">Approved By</p>
                    <p className="text-sm text-text-white">{selectedDecision.approved_by}</p>
                  </div>
                )}
                {selectedDecision.executed_at && (
                  <div className="bg-bg-elevated p-3 rounded-lg">
                    <p className="text-xs font-medium text-text-tertiary mb-1">Executed At</p>
                    <p className="text-sm text-text-white">
                      {new Date(selectedDecision.executed_at).toLocaleString()}
                    </p>
                  </div>
                )}
              </div>

              {/* Hashes */}
              <div className="bg-bg-elevated p-4 rounded-lg">
                <p className="text-xs font-medium text-text-tertiary mb-3">Integrity Hashes</p>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Hash size={14} className="text-text-tertiary" />
                    <span className="text-xs text-text-secondary">Audit Hash:</span>
                    <code className="text-xs text-text-white bg-bg-base px-2 py-1 rounded font-mono">
                      {selectedDecision.audit_hash}
                    </code>
                  </div>
                  <div className="flex items-center gap-2">
                    <Hash size={14} className="text-text-tertiary" />
                    <span className="text-xs text-text-secondary">Input Snapshot:</span>
                    <code className="text-xs text-text-white bg-bg-base px-2 py-1 rounded font-mono">
                      {selectedDecision.input_snapshot_hash}
                    </code>
                  </div>
                </div>
              </div>

              {/* Actions */}
              {selectedDecision.status === 'EXECUTED' && (
                <div className="flex justify-end gap-2 pt-4 border-t border-border-subtle">
                  <DarkButton
                    variant="secondary"
                    size="sm"
                    icon={<RotateCcw size={14} />}
                    onClick={() => {
                      const reason = prompt('Enter rollback reason:');
                      if (reason) {
                        rollbackMutation.mutate({ id: selectedDecision.id, reason });
                      }
                    }}
                    disabled={rollbackMutation.isPending}
                  >
                    {rollbackMutation.isPending ? 'Rolling back...' : 'Rollback Decision'}
                  </DarkButton>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Audit Log Detail Modal */}
      {selectedLog && (
        <Dialog open={!!selectedLog} onOpenChange={() => setSelectedLog(null)}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-bg-card border-border-subtle">
            <DialogHeader>
              <DialogTitle className="text-text-white">Audit Log Details</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-bg-elevated p-3 rounded-lg">
                  <p className="text-xs font-medium text-text-tertiary mb-1">Timestamp</p>
                  <p className="text-sm text-text-white">
                    {new Date(selectedLog.timestamp).toLocaleString()}
                  </p>
                </div>
                <div className="bg-bg-elevated p-3 rounded-lg">
                  <p className="text-xs font-medium text-text-tertiary mb-1">User</p>
                  <p className="text-sm text-text-white">
                    {selectedLog.user_name || selectedLog.user_id}
                  </p>
                </div>
                <div className="bg-bg-elevated p-3 rounded-lg">
                  <p className="text-xs font-medium text-text-tertiary mb-1">Entity Type</p>
                  <p className="text-sm text-text-white capitalize">{selectedLog.entity_type}</p>
                </div>
                <div className="bg-bg-elevated p-3 rounded-lg">
                  <p className="text-xs font-medium text-text-tertiary mb-1">Entity ID</p>
                  <p className="text-sm text-text-white font-mono">{selectedLog.entity_id}</p>
                </div>
                <div className="bg-bg-elevated p-3 rounded-lg">
                  <p className="text-xs font-medium text-text-tertiary mb-1">Action</p>
                  <DarkBadge variant={getActionVariant(selectedLog.action)}>{selectedLog.action}</DarkBadge>
                </div>
              </div>

              {selectedLog.before_state && (
                <div>
                  <p className="text-xs font-medium text-text-secondary mb-2">Before State</p>
                  <pre className="bg-bg-base p-3 rounded-lg text-xs overflow-auto max-h-40 text-text-secondary border border-border-subtle">
                    {JSON.stringify(selectedLog.before_state, null, 2)}
                  </pre>
                </div>
              )}

              {selectedLog.after_state && (
                <div>
                  <p className="text-xs font-medium text-text-secondary mb-2">After State</p>
                  <pre className="bg-bg-base p-3 rounded-lg text-xs overflow-auto max-h-40 text-text-secondary border border-border-subtle">
                    {JSON.stringify(selectedLog.after_state, null, 2)}
                  </pre>
                </div>
              )}

              {Object.keys(selectedLog.changes).length > 0 && (
                <div>
                  <p className="text-xs font-medium text-text-secondary mb-2">Changes</p>
                  <pre className="bg-bg-base p-3 rounded-lg text-xs overflow-auto max-h-40 text-text-secondary border border-border-subtle">
                    {JSON.stringify(selectedLog.changes, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </DarkPageLayout>
  );
}
