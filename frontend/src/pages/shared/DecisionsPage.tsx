import { CheckCircle2, RotateCcw, Clock, FileText, Loader2, ChevronRight, ChevronLeft as ChevronLeftIcon, Eye, Play, Filter as FilterIcon, Layers, XCircle, AlertTriangle } from 'lucide-react';
import { format } from 'date-fns';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../../components/ui/Dialog';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkPillButton, DarkBadge, DarkSearchInput, DarkIconButton } from '../../components/dark';
import { type Severity, ANTIFATIGUE_THRESHOLD, ANTIFATIGUE_TOP_N, SEVERITY_TONE } from './decisionsHelpers';
import { DecisionAuditTrailModal } from './decisionsModals';
import { useDecisionsState } from './useDecisionsState';

export function DecisionsPage() {
  const {
    filterStatus, setFilterStatus, search, setSearch, currentPage, setCurrentPage, selectedDecision, setSelectedDecision, isDetailModalOpen, setIsDetailModalOpen, isAuditModalOpen, setIsAuditModalOpen, selectedIds, setSelectedIds, antiFatigueOn, setAntiFatigueOn, modifyDraft, setModifyDraft, modifyReason, setModifyReason, modifyOpen, setModifyOpen, itemsPerPage, toast, decisionsData, isLoading, error, approveMutation, executeMutation, rollbackMutation, bulkApproveMutation, modifyMutation, totalPages, filteredDecisions, antiFatigueActive, severityCounts, proposedSelectableIds, allSelectable, toggleId, toggleAllVisible, handleBulkApprove, getStatusVariant, canApprove, canExecute, canRollback, handleApprove, handleExecute, handleRollback, stats,
  } = useDecisionsState();

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
