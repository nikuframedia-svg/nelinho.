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
  Filter as FilterIcon,
  Layers,
  XCircle,
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

// ─── Sprint Q.9 Onda 3.4 — severity buckets + anti-fatigue ───────────────
//
// Plan v4 §8 calls out three behaviours we owed the manager:
//   1. Bulk approve (WG04)  — multi-select + a single round trip
//   2. Severity grouping (WG04) — red / amber / green badges so a quick
//      scan tells you which decisions need attention now.
//   3. Anti-fatigue (WG05) — when there are >ANTIFATIGUE_THRESHOLD
//      pending decisions, default to showing the top N by impact so
//      the operator isn't drowning. Toggle off to see all.
const ANTIFATIGUE_THRESHOLD = 20;
const ANTIFATIGUE_TOP_N = 5;

type Severity = 'critical' | 'warning' | 'normal';

function deriveSeverity(d: DecisionRun): Severity {
  // Heuristic from action_type + status, with a safe default of "normal".
  // Real severity should land via a dedicated `severity` field on the
  // payload (Sprint Q.9 backend follow-up); until then we infer.
  const t = (d.action_type || '').toLowerCase();
  if (t.includes('emergency') || t.includes('critical') || t.includes('rollback')) {
    return 'critical';
  }
  if (
    d.status === 'PROPOSED' &&
    (t.includes('reschedule') || t.includes('mold') || t.includes('rework'))
  ) {
    return 'warning';
  }
  return 'normal';
}

const SEVERITY_TONE: Record<Severity, { dot: string; label: string }> = {
  critical: { dot: 'bg-rose-400', label: 'Crítico' },
  warning: { dot: 'bg-amber-400', label: 'Atenção' },
  normal: { dot: 'bg-emerald-400', label: 'Optimização' },
};


export function DecisionsPage() {
  const [filterStatus, setFilterStatus] = useState<DecisionStatus | 'ALL'>('ALL');
  const [search, setSearch] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedDecision, setSelectedDecision] = useState<DecisionRun | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [isAuditModalOpen, setIsAuditModalOpen] = useState(false);
  // Sprint Q.9 Onda 3.4 — multi-select + anti-fatigue toggles.
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [antiFatigueOn, setAntiFatigueOn] = useState(true);
  // Sprint Q.13.C C.3.2 — modify-before-approve scratch state. The
  // detail modal exposes a JSON editor for `action_data`; on save it
  // calls `modifyPayload(id, {patch, reason})`. Reset on modal open
  // so old edits don't leak across decisions.
  const [modifyDraft, setModifyDraft] = useState<string>('');
  const [modifyReason, setModifyReason] = useState<string>('');
  const [modifyOpen, setModifyOpen] = useState<boolean>(false);
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

  // Sprint Q.9 Onda 3.4 — bulk approve mutation. Backend route accepts
  // any mix of approve/reject/request_changes; we send `approve` here
  // because the UI flow is "select pending decisions, OK them all".
  const bulkApproveMutation = useMutation({
    mutationFn: (ids: string[]) =>
      decisionsApi.bulkAct(
        ids.map((id) => ({
          decision_id: id,
          action: 'approve',
          reason: 'Bulk approve via Timeline',
        })),
      ),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['decisions'] });
      setSelectedIds(new Set());
      toast.success(`Bulk approve: ${data.ok} ok, ${data.failed} falharam`);
    },
    onError: (err: any) => toast.error(err.message || 'Bulk approve failed'),
  });

  // Sprint Q.13.C C.3.2 — Plan v4 §8 WG05 "modificar antes de aprovar".
  // The operator may edit `action_data` before flipping the decision
  // to APPROVED — useful for catching small payload mistakes (wrong
  // mold_id, off-by-one date) without forcing a full reject + repropose
  // round-trip. Reason is mandatory ≥10 chars so the audit trail
  // explains the diff.
  const modifyMutation = useMutation({
    mutationFn: ({
      id,
      patch,
      reason,
    }: { id: string; patch: Record<string, unknown>; reason: string }) =>
      decisionsApi.modifyPayload(id, { patch, reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decisions'] });
      toast.success('Decision payload updated');
    },
    onError: (err: any) => toast.error(err.message || 'Modify failed'),
  });

  const decisions = decisionsData?.items || [];
  const totalPages = decisionsData ? Math.ceil(decisionsData.total / itemsPerPage) : 0;

  // Filter decisions by search
  const searchedDecisions = useMemo(() => {
    return decisions.filter(d => {
      const matchesSearch = d.title.toLowerCase().includes(search.toLowerCase()) ||
                            d.action_type.toLowerCase().includes(search.toLowerCase()) ||
                            d.target.toLowerCase().includes(search.toLowerCase());
      return matchesSearch;
    });
  }, [decisions, search]);

  // Sprint Q.9 Onda 3.4 — group by severity + anti-fatigue downsample.
  // Severity is derived locally (see deriveSeverity). When anti-fatigue
  // is on AND total pending exceeds the threshold, only the top
  // ANTIFATIGUE_TOP_N criticals/warnings are shown. The operator can
  // toggle off to see everything.
  const { filteredDecisions, antiFatigueActive, severityCounts } = useMemo(() => {
    const annotated = searchedDecisions.map((d) => ({ ...d, _sev: deriveSeverity(d) }));
    const counts: Record<Severity, number> = { critical: 0, warning: 0, normal: 0 };
    for (const d of annotated) counts[d._sev as Severity]++;
    const pending = annotated.filter((d) => d.status === 'PROPOSED');
    const shouldFatigue = antiFatigueOn && pending.length > ANTIFATIGUE_THRESHOLD;
    let visible: typeof annotated = annotated;
    if (shouldFatigue) {
      // Order by severity priority then by proposed_at (newest first).
      const order: Record<Severity, number> = { critical: 0, warning: 1, normal: 2 };
      const ranked = [...pending].sort((a, b) => {
        const sa = order[a._sev as Severity] ?? 9;
        const sb = order[b._sev as Severity] ?? 9;
        if (sa !== sb) return sa - sb;
        return new Date(b.proposed_at).getTime() - new Date(a.proposed_at).getTime();
      });
      visible = ranked.slice(0, ANTIFATIGUE_TOP_N);
    }
    return {
      filteredDecisions: visible,
      antiFatigueActive: shouldFatigue,
      severityCounts: counts,
    };
  }, [searchedDecisions, antiFatigueOn]);

  const proposedSelectableIds = filteredDecisions
    .filter((d) => d.status === 'PROPOSED')
    .map((d) => d.id);

  const allSelectable =
    proposedSelectableIds.length > 0 &&
    proposedSelectableIds.every((id) => selectedIds.has(id));

  const toggleId = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAllVisible = () => {
    setSelectedIds((prev) => {
      if (allSelectable) {
        const next = new Set(prev);
        proposedSelectableIds.forEach((id) => next.delete(id));
        return next;
      }
      const next = new Set(prev);
      proposedSelectableIds.forEach((id) => next.add(id));
      return next;
    });
  };

  const handleBulkApprove = () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    if (
      !window.confirm(
        `Aprovar ${ids.length} decisão(ões) em massa? Acção não reversível por linha; usa rollback se precisares de voltar atrás.`,
      )
    ) {
      return;
    }
    bulkApproveMutation.mutate(ids);
  };

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
      <div className="flex items-center gap-4 mb-3 flex-wrap">
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

      {/* Sprint Q.9 Onda 3.4 — severity legend + anti-fatigue toggle + bulk bar */}
      <div className="flex items-center gap-3 mb-4 flex-wrap text-xs">
        <span className="inline-flex items-center gap-1 text-text-tertiary">
          <Layers size={12} /> Severidade:
        </span>
        {(['critical', 'warning', 'normal'] as Severity[]).map((sev) => (
          <span key={sev} className="inline-flex items-center gap-1 text-text-secondary">
            <span className={`w-2 h-2 rounded-full ${SEVERITY_TONE[sev].dot}`} />
            {SEVERITY_TONE[sev].label}
            <span className="text-text-tertiary">({severityCounts[sev]})</span>
          </span>
        ))}
        <span className="text-text-tertiary mx-2">|</span>
        <button
          type="button"
          onClick={() => setAntiFatigueOn((v) => !v)}
          className={`inline-flex items-center gap-1 px-2 py-1 rounded border transition-colors ${
            antiFatigueOn
              ? 'border-amber-500/40 text-amber-200 bg-amber-500/10'
              : 'border-slate-700 text-slate-300'
          }`}
          title={`Anti-fatigue: quando há mais de ${ANTIFATIGUE_THRESHOLD} decisões pendentes, mostra só ${ANTIFATIGUE_TOP_N} top por severidade.`}
        >
          <FilterIcon size={12} />
          Anti-fatigue {antiFatigueOn ? 'ON' : 'OFF'}
          {antiFatigueActive ? (
            <span className="ml-1 text-amber-300 font-semibold">activo</span>
          ) : null}
        </button>
        {selectedIds.size > 0 ? (
          <div className="ml-auto flex items-center gap-2">
            <span className="text-text-secondary">{selectedIds.size} seleccionada(s)</span>
            <DarkButton
              variant="primary"
              size="sm"
              icon={
                bulkApproveMutation.isPending ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <CheckCircle2 size={14} />
                )
              }
              onClick={handleBulkApprove}
              disabled={bulkApproveMutation.isPending}
            >
              Aprovar em massa
            </DarkButton>
            <DarkButton
              variant="ghost"
              size="sm"
              icon={<XCircle size={14} />}
              onClick={() => setSelectedIds(new Set())}
            >
              Limpar
            </DarkButton>
          </div>
        ) : null}
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
                <DarkTableHeader>
                  {/* Sprint Q.9 Onda 3.4 — select-all toggle visible only
                      when at least one row in view is PROPOSED. */}
                  {proposedSelectableIds.length > 0 ? (
                    <input
                      type="checkbox"
                      checked={allSelectable}
                      onChange={toggleAllVisible}
                      className="cursor-pointer"
                      title="Seleccionar todas as propostas visíveis"
                    />
                  ) : null}
                </DarkTableHeader>
                <DarkTableHeader>Title</DarkTableHeader>
                <DarkTableHeader>Action Type</DarkTableHeader>
                <DarkTableHeader>Target</DarkTableHeader>
                <DarkTableHeader>Status</DarkTableHeader>
                <DarkTableHeader>Proposed</DarkTableHeader>
                <DarkTableHeader align="right">Actions</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {filteredDecisions.map((decision) => {
                const sev = (decision as any)._sev as Severity;
                const checkable = decision.status === 'PROPOSED';
                return (
                <DarkTableRow key={decision.id}>
                  <DarkTableCell>
                    <div className="flex items-center gap-2">
                      {checkable ? (
                        <input
                          type="checkbox"
                          checked={selectedIds.has(decision.id)}
                          onChange={() => toggleId(decision.id)}
                          className="cursor-pointer"
                        />
                      ) : null}
                      <span
                        className={`w-2 h-2 rounded-full ${SEVERITY_TONE[sev].dot}`}
                        title={SEVERITY_TONE[sev].label}
                      />
                    </div>
                  </DarkTableCell>
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
                );
              })}
              {filteredDecisions.length === 0 && (
                <DarkTableRow>
                  <DarkTableCell colSpan={7} className="text-center py-12">
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
              
              {/* Sprint Q.13.C C.3.2 — Plan v4 §8 WG05 "modificar antes de
                  aprovar". Only available on PROPOSED decisions; APPROVED/
                  EXECUTED ones are immutable by design. Operator clicks
                  "Editar payload", JSON editor opens with the current
                  action_data, edits, gives a reason ≥10 chars, saves.
                  The decision stays PROPOSED — operator can then approve
                  in the same flow with the modified payload. */}
              {selectedDecision.status === 'PROPOSED' ? (
                <div className="border-t border-border-subtle pt-4">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-semibold text-text-secondary">
                      Action Data
                    </h4>
                    <button
                      type="button"
                      onClick={() => {
                        if (!modifyOpen) {
                          setModifyDraft(
                            JSON.stringify(selectedDecision.action_data ?? {}, null, 2),
                          );
                          setModifyReason('');
                        }
                        setModifyOpen((v) => !v);
                      }}
                      className="text-xs text-accent hover:text-accent-light underline-offset-2 hover:underline"
                    >
                      {modifyOpen ? 'Cancelar edição' : 'Editar payload (WG05)'}
                    </button>
                  </div>
                  {modifyOpen ? (
                    <div className="space-y-2">
                      <textarea
                        rows={8}
                        value={modifyDraft}
                        onChange={(e) => setModifyDraft(e.target.value)}
                        className="w-full font-mono text-xs px-3 py-2 bg-bg-elevated border border-border-subtle rounded text-text-white focus:border-accent focus:outline-none"
                        placeholder='{"new_start_date": "2026-05-01", ...}'
                      />
                      <input
                        type="text"
                        value={modifyReason}
                        onChange={(e) => setModifyReason(e.target.value)}
                        className="w-full text-xs px-3 py-2 bg-bg-elevated border border-border-subtle rounded text-text-white focus:border-accent focus:outline-none"
                        placeholder="Porquê? (≥10 caracteres) — alimenta o audit trail"
                      />
                      <div className="flex items-center gap-2">
                        <DarkButton
                          variant="primary"
                          size="sm"
                          disabled={
                            modifyMutation.isPending ||
                            modifyReason.trim().length < 10
                          }
                          onClick={() => {
                            try {
                              const patch = JSON.parse(modifyDraft || '{}');
                              if (!selectedDecision) return;
                              modifyMutation.mutate(
                                {
                                  id: selectedDecision.id,
                                  patch,
                                  reason: modifyReason.trim(),
                                },
                                {
                                  onSuccess: () => {
                                    setModifyOpen(false);
                                    setModifyDraft('');
                                    setModifyReason('');
                                  },
                                },
                              );
                            } catch (parseErr) {
                              toast.error(
                                `JSON inválido: ${
                                  parseErr instanceof Error
                                    ? parseErr.message
                                    : String(parseErr)
                                }`,
                              );
                            }
                          }}
                        >
                          Guardar
                        </DarkButton>
                        <span className="text-xs text-text-tertiary">
                          {modifyReason.trim().length}/10 chars · cada edição
                          fica registada no audit trail.
                        </span>
                      </div>
                    </div>
                  ) : (
                    <pre className="text-xs font-mono bg-bg-elevated p-3 rounded text-text-tertiary max-h-40 overflow-auto">
                      {JSON.stringify(selectedDecision.action_data ?? {}, null, 2)}
                    </pre>
                  )}
                </div>
              ) : null}

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
