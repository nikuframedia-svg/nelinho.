import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  CheckCircle2,
  RotateCcw,
  Clock,
  FileText,
  Loader2,
  ChevronRight,
  ChevronLeft as ChevronLeftIcon,
  Eye,
  Play,
  AlertTriangle,
} from 'lucide-react';
import { decisionsApi, type DecisionRun, type ApprovalRequest } from '../../lib/api';
import { format } from 'date-fns';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../../components/ui/Dialog';
import { DarkPageLayout } from '../../layouts';
import {
  DarkCard,
  DarkStatCard,
  DarkTable,
  DarkTableHead,
  DarkTableBody,
  DarkTableRow,
  DarkTableHeader,
  DarkTableCell,
  DarkButton,
  DarkPillButton,
  DarkBadge,
  DarkSearchInput,
  DarkIconButton,
} from '../../components/dark';
import { useToastContext } from '../../components/ToastProvider';

type DecisionStatus = 'PROPOSED' | 'APPROVED' | 'EXECUTED' | 'ROLLED_BACK' | 'REJECTED';

export function DecisionsPage() {
  const [filterStatus, setFilterStatus] = useState<DecisionStatus | 'ALL'>('ALL');
  const [search, setSearch] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedDecision, setSelectedDecision] = useState<DecisionRun | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [isAuditModalOpen, setIsAuditModalOpen] = useState(false);
  const itemsPerPage = 20;

  const queryClient = useQueryClient();
  const toast = useToastContext();

  // Fetch decisions from API
  const { data: decisionsData, isLoading, error } = useQuery({
    queryKey: ['decisions', filterStatus === 'ALL' ? undefined : filterStatus, currentPage],
    queryFn: () => decisionsApi.list({ 
      status: filterStatus === 'ALL' ? undefined : filterStatus,
      page: currentPage,
      page_size: itemsPerPage,
    }),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Approve mutation
  const approveMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: ApprovalRequest }) => decisionsApi.approve(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decisions'] });
      toast.success('Decision approved successfully');
    },
    onError: (err: any) => toast.error(err.message || 'Failed to approve'),
  });

  // Execute mutation
  const executeMutation = useMutation({
    mutationFn: (id: string) => decisionsApi.execute(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decisions'] });
      toast.success('Decision executed successfully');
    },
    onError: (err: any) => toast.error(err.message || 'Failed to execute'),
  });

  // Rollback mutation
  const rollbackMutation = useMutation({
    mutationFn: (id: string) => decisionsApi.rollback(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decisions'] });
      toast.success('Decision rolled back successfully');
    },
    onError: (err: any) => toast.error(err.message || 'Failed to rollback'),
  });

  const decisions = decisionsData?.items || [];
  const totalPages = decisionsData ? Math.ceil(decisionsData.total / itemsPerPage) : 0;

  // Filter decisions by search
  const filteredDecisions = useMemo(() => {
    return decisions.filter(d => {
      const matchesSearch = d.title.toLowerCase().includes(search.toLowerCase()) || 
                            d.action_type.toLowerCase().includes(search.toLowerCase()) ||
                            d.target.toLowerCase().includes(search.toLowerCase());
      return matchesSearch;
    });
  }, [decisions, search]);

  // Get status badge variant
  const getStatusVariant = (status: DecisionStatus): 'success' | 'warning' | 'danger' | 'info' | 'neutral' => {
    const variants: Record<DecisionStatus, 'success' | 'warning' | 'danger' | 'info' | 'neutral'> = {
      PROPOSED: 'warning',
      APPROVED: 'info',
      EXECUTED: 'success',
      ROLLED_BACK: 'neutral',
      REJECTED: 'danger',
    };
    return variants[status];
  };

  // Check if action is available
  const canApprove = (decision: DecisionRun) => decision.status === 'PROPOSED';
  const canExecute = (decision: DecisionRun) => decision.status === 'APPROVED';
  const canRollback = (decision: DecisionRun) => {
    if (decision.status !== 'EXECUTED') return false;
    if (!decision.executed_at) return false;
    const executedAt = new Date(decision.executed_at);
    const now = new Date();
    const hoursSinceExecution = (now.getTime() - executedAt.getTime()) / (1000 * 60 * 60);
    return hoursSinceExecution <= 24;
  };

  const handleApprove = async (decision: DecisionRun) => {
    if (!window.confirm(`Approve decision "${decision.title}"?`)) return;
    approveMutation.mutate({ 
      id: decision.id, 
      data: { status: 'APPROVED', comment: 'Approved via UI' } 
    });
  };

  const handleExecute = async (decision: DecisionRun) => {
    if (!window.confirm(`Execute decision "${decision.title}"? This action cannot be undone.`)) return;
    executeMutation.mutate(decision.id);
  };

  const handleRollback = async (decision: DecisionRun) => {
    if (!window.confirm(`Rollback decision "${decision.title}"? This will revert all changes.`)) return;
    rollbackMutation.mutate(decision.id);
  };

  const stats = useMemo(() => {
    const statusCounts = decisions.reduce((acc, d) => {
      acc[d.status] = (acc[d.status] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    
    return {
      total: decisionsData?.total || 0,
      proposed: statusCounts.PROPOSED || 0,
      approved: statusCounts.APPROVED || 0,
      executed: statusCounts.EXECUTED || 0,
      rolledBack: statusCounts.ROLLED_BACK || 0,
    };
  }, [decisions, decisionsData]);

  if (error) {
    return (
      <DarkPageLayout title="Decision Ledger" icon={<FileText size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div>
              <p className="font-medium">Error loading decisions</p>
              <p className="text-sm">{(error as Error).message}</p>
            </div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  return (
    <DarkPageLayout
      title="Decision Ledger"
      subtitle={isLoading ? 'Loading...' : `${decisionsData?.total || 0} decisions tracked`}
      icon={<FileText size={20} />}
    >
      {/* Stats */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <DarkStatCard icon={<FileText size={18} />} label="Total" value={stats.total} size="sm" />
        <DarkStatCard icon={<Clock size={18} />} iconBg="bg-amber/20" label="Proposed" value={stats.proposed} size="sm" />
        <DarkStatCard icon={<CheckCircle2 size={18} />} iconBg="bg-blue/20" label="Approved" value={stats.approved} size="sm" />
        <DarkStatCard icon={<CheckCircle2 size={18} />} iconBg="bg-success/20" label="Executed" value={stats.executed} size="sm" />
        <DarkStatCard icon={<RotateCcw size={18} />} iconBg="bg-bg-elevated" label="Rolled Back" value={stats.rolledBack} size="sm" />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <DarkSearchInput
          placeholder="Search decisions..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }}
          onClear={() => setSearch('')}
          containerClassName="w-72"
        />
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1 overflow-x-auto">
          {(['ALL', 'PROPOSED', 'APPROVED', 'EXECUTED', 'ROLLED_BACK', 'REJECTED'] as const).map((status) => (
            <DarkPillButton
              key={status}
              active={filterStatus === status}
              onClick={() => { setFilterStatus(status); setCurrentPage(1); }}
            >
              {status === 'ALL' ? 'All' : status.replace('_', ' ')}
            </DarkPillButton>
          ))}
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <DarkCard className="text-center py-12">
          <Loader2 className="animate-spin mx-auto text-accent" size={32} />
          <p className="text-text-secondary mt-3">Loading decisions...</p>
        </DarkCard>
      ) : (
        <DarkCard padding="none">
          <DarkTable>
            <DarkTableHead>
              <DarkTableRow>
                <DarkTableHeader>Title</DarkTableHeader>
                <DarkTableHeader>Action Type</DarkTableHeader>
                <DarkTableHeader>Target</DarkTableHeader>
                <DarkTableHeader>Status</DarkTableHeader>
                <DarkTableHeader>Proposed</DarkTableHeader>
                <DarkTableHeader align="right">Actions</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {filteredDecisions.map((decision) => (
                <DarkTableRow key={decision.id}>
                  <DarkTableCell>
                    <button
                      onClick={() => { setSelectedDecision(decision); setIsDetailModalOpen(true); }}
                      className="text-text-white font-medium hover:text-accent transition-colors text-left"
                    >
                      {decision.title}
                    </button>
                  </DarkTableCell>
                  <DarkTableCell className="text-text-secondary">{decision.action_type}</DarkTableCell>
                  <DarkTableCell className="text-text-secondary">{decision.target}</DarkTableCell>
                  <DarkTableCell>
                    <DarkBadge variant={getStatusVariant(decision.status)} dot>
                      {decision.status.replace('_', ' ')}
                    </DarkBadge>
                  </DarkTableCell>
                  <DarkTableCell className="text-text-tertiary">
                    {format(new Date(decision.proposed_at), 'MMM d, yyyy HH:mm')}
                  </DarkTableCell>
                  <DarkTableCell align="right">
                    <div className="flex items-center justify-end gap-1">
                      <DarkIconButton
                        icon={<Eye size={16} />}
                        size="sm"
                        variant="ghost"
                        onClick={() => { setSelectedDecision(decision); setIsDetailModalOpen(true); }}
                        title="View details"
                      />
                      {canApprove(decision) && (
                        <DarkButton
                          variant="ghost"
                          size="sm"
                          icon={approveMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                          onClick={() => handleApprove(decision)}
                          disabled={approveMutation.isPending}
                        >
                          Approve
                        </DarkButton>
                      )}
                      {canExecute(decision) && (
                        <DarkButton
                          variant="ghost"
                          size="sm"
                          icon={executeMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                          onClick={() => handleExecute(decision)}
                          disabled={executeMutation.isPending}
                        >
                          Execute
                        </DarkButton>
                      )}
                      {canRollback(decision) && (
                        <DarkButton
                          variant="ghost"
                          size="sm"
                          icon={rollbackMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
                          onClick={() => handleRollback(decision)}
                          disabled={rollbackMutation.isPending}
                        >
                          Rollback
                        </DarkButton>
                      )}
                    </div>
                  </DarkTableCell>
                </DarkTableRow>
              ))}
              {filteredDecisions.length === 0 && (
                <DarkTableRow>
                  <DarkTableCell colSpan={6} className="text-center py-12">
                    <FileText size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
                    <p className="font-medium text-text-secondary">No decisions found</p>
                    <p className="text-sm text-text-tertiary">
                      {search ? "Try adjusting your search or filters" : "No decisions have been created yet"}
                    </p>
                  </DarkTableCell>
                </DarkTableRow>
              )}
            </DarkTableBody>
          </DarkTable>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-6 py-4 border-t border-border-subtle">
              <p className="text-sm text-text-tertiary">
                Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, decisionsData?.total || 0)} of {decisionsData?.total || 0} decisions
              </p>
              <div className="flex items-center gap-2">
                <DarkButton
                  variant="ghost"
                  size="sm"
                  icon={<ChevronLeftIcon size={16} />}
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                >
                  Previous
                </DarkButton>
                <span className="text-sm text-text-secondary px-2">
                  Page {currentPage} of {totalPages}
                </span>
                <DarkButton
                  variant="ghost"
                  size="sm"
                  iconRight={<ChevronRight size={16} />}
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next
                </DarkButton>
              </div>
            </div>
          )}
        </DarkCard>
      )}

      {/* Detail Modal */}
      {selectedDecision && (
        <Dialog open={isDetailModalOpen} onOpenChange={setIsDetailModalOpen}>
          <DialogContent className="sm:max-w-[700px] max-h-[80vh] overflow-y-auto bg-bg-card border-border-subtle">
            <DialogHeader>
              <DialogTitle className="text-text-white">{selectedDecision.title}</DialogTitle>
              <DialogDescription className="text-text-tertiary">
                Decision details and workflow status
              </DialogDescription>
            </DialogHeader>
            <div className="py-4 space-y-4">
              <div>
                <h4 className="text-sm font-semibold text-text-secondary mb-3">Basic Information</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="bg-bg-elevated p-3 rounded-lg">
                    <p className="text-text-tertiary text-xs mb-1">Action Type</p>
                    <p className="font-medium text-text-white">{selectedDecision.action_type}</p>
                  </div>
                  <div className="bg-bg-elevated p-3 rounded-lg">
                    <p className="text-text-tertiary text-xs mb-1">Target</p>
                    <p className="font-medium text-text-white">{selectedDecision.target}</p>
                  </div>
                  <div className="bg-bg-elevated p-3 rounded-lg">
                    <p className="text-text-tertiary text-xs mb-1">Status</p>
                    <DarkBadge variant={getStatusVariant(selectedDecision.status)} dot>
                      {selectedDecision.status.replace('_', ' ')}
                    </DarkBadge>
                  </div>
                  <div className="bg-bg-elevated p-3 rounded-lg">
                    <p className="text-text-tertiary text-xs mb-1">Proposed By</p>
                    <p className="font-medium text-text-white">{selectedDecision.proposed_by}</p>
                  </div>
                  <div className="bg-bg-elevated p-3 rounded-lg">
                    <p className="text-text-tertiary text-xs mb-1">Proposed At</p>
                    <p className="font-medium text-text-white">{format(new Date(selectedDecision.proposed_at), 'PPpp')}</p>
                  </div>
                  {selectedDecision.executed_at && (
                    <div className="bg-bg-elevated p-3 rounded-lg">
                      <p className="text-text-tertiary text-xs mb-1">Executed At</p>
                      <p className="font-medium text-text-white">{format(new Date(selectedDecision.executed_at), 'PPpp')}</p>
                    </div>
                  )}
                </div>
              </div>
              
              {selectedDecision.approvals && selectedDecision.approvals.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-text-secondary mb-3">Approvals</h4>
                  <div className="space-y-2">
                    {selectedDecision.approvals.map((approval, idx) => (
                      <div key={idx} className="flex items-center justify-between p-3 bg-bg-elevated rounded-lg">
                        <div>
                          <p className="text-sm font-medium text-text-white">{approval.approver_id}</p>
                          {approval.comment && <p className="text-xs text-text-tertiary mt-0.5">{approval.comment}</p>}
                        </div>
                        <DarkBadge variant={
                          approval.status === 'APPROVED' ? 'success' :
                          approval.status === 'REJECTED' ? 'danger' : 'warning'
                        } dot>
                          {approval.status}
                        </DarkBadge>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              <div className="flex gap-2 pt-4 border-t border-border-subtle">
                <DarkButton
                  variant="secondary"
                  onClick={() => { setIsAuditModalOpen(true); setIsDetailModalOpen(false); }}
                >
                  View Audit Trail
                </DarkButton>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Audit Trail Modal */}
      {selectedDecision && (
        <DecisionAuditTrailModal
          decisionId={selectedDecision.id}
          isOpen={isAuditModalOpen}
          onClose={() => { setIsAuditModalOpen(false); setSelectedDecision(null); }}
        />
      )}
    </DarkPageLayout>
  );
}

// Audit Trail Modal Component
function DecisionAuditTrailModal({ decisionId, isOpen, onClose }: { decisionId: string; isOpen: boolean; onClose: () => void }) {
  const { data: auditTrail, isLoading } = useQuery({
    queryKey: ['decisions', decisionId, 'audit'],
    queryFn: () => decisionsApi.getAuditTrail(decisionId),
    enabled: isOpen,
  });

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px] bg-bg-card border-border-subtle">
        <DialogHeader>
          <DialogTitle className="text-text-white">Audit Trail</DialogTitle>
          <DialogDescription className="text-text-tertiary">
            Complete history of this decision
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={24} className="text-accent animate-spin" />
            </div>
          ) : !auditTrail || auditTrail.length === 0 ? (
            <p className="text-sm text-text-tertiary text-center py-8">No audit trail entries found</p>
          ) : (
            <div className="space-y-3">
              {auditTrail.map((entry, idx) => (
                <div key={idx} className="flex gap-3 p-3 bg-bg-elevated rounded-lg">
                  <div className="flex-shrink-0 w-2 h-2 rounded-full bg-accent mt-2" />
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-sm font-medium text-text-white">{entry.event}</p>
                      <p className="text-xs text-text-tertiary">{format(new Date(entry.timestamp), 'PPpp')}</p>
                    </div>
                    <p className="text-xs text-text-secondary">By: {entry.by}</p>
                    {entry.details && Object.keys(entry.details).length > 0 && (
                      <pre className="mt-2 text-xs bg-bg-base p-2 rounded border border-border-subtle overflow-x-auto text-text-secondary">
                        {JSON.stringify(entry.details, null, 2)}
                      </pre>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
