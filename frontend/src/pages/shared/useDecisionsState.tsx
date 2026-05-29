// Hook de state, queries, mutations e handlers da DecisionsPage (Q.60.AE).
import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { decisionsApi, type DecisionRun, type ApprovalRequest } from '../../lib/api';
import { useToastContext } from '../../components/ToastProvider';
import { type DecisionStatus, type Severity, ANTIFATIGUE_THRESHOLD, ANTIFATIGUE_TOP_N, deriveSeverity } from './decisionsHelpers';

export function useDecisionsState() {
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
    // Q.59.G.1 — SSE `governance` já dispara DECISION_EXECUTED /
    // _ROLLED_BACK em tempo real. 30 s era poll redundante; 60 s mantém
    // safety-net (PROPOSED novos ainda sem evento SSE direto) sem
    // duplicação de carga.
    refetchInterval: 60_000,
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

  const decisions = decisionsData?.decisions || [];
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

  // Nota: o ramo de erro renderiza-se na shell (DecisionsPage.tsx) — o hook
  // só devolve state. Q.60.AE.

  return { filterStatus, setFilterStatus, search, setSearch, currentPage, setCurrentPage, selectedDecision, setSelectedDecision, isDetailModalOpen, setIsDetailModalOpen, isAuditModalOpen, setIsAuditModalOpen, selectedIds, setSelectedIds, antiFatigueOn, setAntiFatigueOn, modifyDraft, setModifyDraft, modifyReason, setModifyReason, modifyOpen, setModifyOpen, itemsPerPage, queryClient, toast, decisionsData, isLoading, error, approveMutation, executeMutation, rollbackMutation, bulkApproveMutation, modifyMutation, decisions, totalPages, searchedDecisions, filteredDecisions, antiFatigueActive, severityCounts, proposedSelectableIds, allSelectable, toggleId, toggleAllVisible, handleBulkApprove, getStatusVariant, canApprove, canExecute, canRollback, handleApprove, handleExecute, handleRollback, stats };
}
