import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { DndContext, PointerSensor, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core';
import { Move, User } from 'lucide-react';
import { schedulePreviewApi } from '../../lib/api';
import { DarkCard } from '../dark';
import { URGENCY_COLOR_HINT, useLatestCommitOps, PhaseColumn, WorkerSwimlane, SuggestionPanel, type ScheduledOp, type PendingDrop } from './dragDropParts';

export function DragDropPlanner() {
  const queryClient = useQueryClient();
  const { commit, isLoading } = useLatestCommitOps();
  const [pending, setPending] = useState<PendingDrop | null>(null);
  const [reason, setReason] = useState('');

  const ops: ScheduledOp[] = useMemo(() => {
    if (!commit?.operations) return [];
    return commit.operations.map((op) => ({
      id: String(op.id ?? op.operation_id ?? ''),
      phase_id: String(op.phase_id ?? op.phase_name ?? 'UNKNOWN'),
      phase_name: op.phase_name,
      workers: Array.isArray(op.workers) ? (op.workers as string[]) : [],
      start: op.start,
      end: op.end,
      product_id: op.product_id,
      order_id: op.order_id,
      quality_risk: typeof op.quality_risk === 'number' ? op.quality_risk : undefined,
    }));
  }, [commit]);

  const phaseGroups = useMemo(() => {
    const groups = new Map<string, ScheduledOp[]>();
    for (const op of ops) {
      const key = op.phase_id || 'UNKNOWN';
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(op);
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [ops]);

  const workerGroups = useMemo(() => {
    const groups = new Map<string, ScheduledOp[]>();
    for (const op of ops) {
      for (const w of op.workers ?? []) {
        if (!groups.has(w)) groups.set(w, []);
        groups.get(w)!.push(op);
      }
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [ops]);

  // ── Sensors ─────────────────────────────────────────────────────────────
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  // ── Mutations ───────────────────────────────────────────────────────────
  const previewMutation = useMutation({
    mutationFn: (payload: {
      operation_id: string;
      new_phase_id?: string;
      new_worker_ids?: string[];
    }) => schedulePreviewApi.previewDelta(payload),
  });

  const applyMutation = useMutation({
    mutationFn: (payload: {
      operation_id: string;
      new_phase_id?: string;
      new_worker_ids?: string[];
      reason: string;
    }) => schedulePreviewApi.applyMove(payload),
    onSuccess: () => {
      setPending(null);
      setReason('');
      queryClient.invalidateQueries({ queryKey: ['cpo', 'commits'] });
    },
  });

  // ── Drag handlers ───────────────────────────────────────────────────────
  const handleDragEnd = async (event: DragEndEvent) => {
    if (!event.over) return;
    const opId = String(event.active.id);
    const targetRaw = String(event.over.id);
    const [kindRaw, ...rest] = targetRaw.split(':');
    const targetId = rest.join(':');
    if (!kindRaw || !targetId) return;
    if (kindRaw !== 'phase' && kindRaw !== 'worker') return;

    const op = ops.find((o) => o.id === opId);
    if (!op) return;
    if (kindRaw === 'phase' && op.phase_id === targetId) return;

    let payload: {
      operation_id: string;
      new_phase_id?: string;
      new_worker_ids?: string[];
    };
    if (kindRaw === 'phase') {
      payload = { operation_id: opId, new_phase_id: targetId };
    } else {
      // Drop op onto worker swimlane → assign worker (preserves any
      // existing partner; if the chefe slot is empty we put this worker
      // in slot 0).
      const existing = op.workers ?? [];
      const next = existing.includes(targetId) ? existing : [targetId, ...existing.slice(0, 1)];
      payload = { operation_id: opId, new_worker_ids: next };
    }

    try {
      const result = await previewMutation.mutateAsync(payload);
      setPending({
        operationId: opId,
        target: { kind: kindRaw, id: targetId },
        preview: result,
      });
    } catch (err) {
      console.error('preview-delta failed', err);
    }
  };

  // Reset reason when pending changes.
  useEffect(() => {
    setReason('');
  }, [pending?.operationId, pending?.target.id]);

  if (isLoading) {
    return <DarkCard className="text-center py-10 text-slate-400">A carregar último commit…</DarkCard>;
  }
  if (!commit || ops.length === 0) {
    return (
      <DarkCard className="p-5">
        <p className="text-sm text-slate-400">
          Sem operações na última commit do CPO. Corre <code>POST /v1/plan/cpo/run</code>{' '}
          primeiro para gerar um plano que se possa editar aqui.
        </p>
      </DarkCard>
    );
  }

  return (
    <div>
      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <div className="grid grid-cols-12 gap-4">
          {/* Layer 1 + Layer 2 stacked left */}
          <div className="col-span-9 space-y-4">
            <DarkCard className="p-4">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Move size={14} className="text-teal-400" />
                Layer 1 — Barcos por fase
              </h3>
              <div className="grid grid-cols-4 gap-3 max-h-[420px] overflow-auto">
                {phaseGroups.map(([phaseId, phaseOps]) => (
                  <PhaseColumn key={phaseId} phaseId={phaseId} ops={phaseOps} />
                ))}
              </div>
            </DarkCard>

            <DarkCard className="p-4">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <User size={14} className="text-teal-400" />
                Layer 2 — Operadores
              </h3>
              <div className="space-y-2 max-h-[300px] overflow-auto">
                {workerGroups.map(([workerId, workerOps]) => (
                  <WorkerSwimlane key={workerId} workerId={workerId} ops={workerOps} />
                ))}
                {workerGroups.length === 0 && (
                  <p className="text-xs text-slate-500">
                    Nenhum operador atribuído nas operações desta commit.
                  </p>
                )}
              </div>
            </DarkCard>
          </div>

          {/* Right rail: suggestion panel */}
          <aside className="col-span-3">
            <SuggestionPanel
              pending={pending}
              ops={ops}
              previewing={previewMutation.isPending}
              applying={applyMutation.isPending}
              reason={reason}
              setReason={setReason}
              onApply={() => {
                if (!pending) return;
                if (pending.target.kind === 'phase') {
                  applyMutation.mutate({
                    operation_id: pending.operationId,
                    new_phase_id: pending.target.id,
                    reason,
                  });
                } else {
                  const op = ops.find((o) => o.id === pending.operationId);
                  const existing = op?.workers ?? [];
                  const next = existing.includes(pending.target.id)
                    ? existing
                    : [pending.target.id, ...existing.slice(0, 1)];
                  applyMutation.mutate({
                    operation_id: pending.operationId,
                    new_worker_ids: next,
                    reason,
                  });
                }
              }}
              onCancel={() => setPending(null)}
            />
          </aside>
        </div>
      </DndContext>

      <p className="text-xs text-slate-600 mt-3">
        <strong>Cor por urgência:</strong> {URGENCY_COLOR_HINT}
      </p>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Sub-components — phase column / worker swimlane / op card / suggestion
// ───────────────────────────────────────────────────────────────────────────

export default DragDropPlanner;
