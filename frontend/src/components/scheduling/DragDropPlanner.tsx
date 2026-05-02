/**
 * DragDropPlanner — Sprint Q.4 / PL01-PL24
 * =========================================
 *
 * Two-layer drag-and-drop planner that consumes the latest CPO commit's
 * operations and lets the operator move them between phase columns
 * (Layer 1) or between operator swimlanes (Layer 2).
 *
 * Every drop fires `/v1/plan/schedule/preview-delta` (sub-second, no CPO
 * run) and renders the result in the right rail with explicit
 * conflicts / warnings / pair-rule violations. Operator confirms via
 * "Aplicar" which calls `/v1/plan/schedule/apply-move` and creates a
 * new ScheduleCommit child.
 *
 * Principle "explica sempre" (Plan v4 §11): the suggestion panel ALWAYS
 * shows what would change, why, what happens if accepted/rejected, and
 * a free-text "Porquê?" field that is mandatory on apply (≥10 chars).
 */

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  DndContext,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Move,
  User,
} from 'lucide-react';
import {
  cpoCommitsApi,
  schedulePreviewApi,
  type CpoCommit,
  type PreviewDeltaResult,
  type PreviewIssue,
} from '../../lib/api';
import {
  ConsequenceBlock,
  DarkBadge,
  DarkButton,
  DarkCard,
  GhostOverlay,
  type ConsequenceLine,
} from '../dark';

// ───────────────────────────────────────────────────────────────────────────
// Types
// ───────────────────────────────────────────────────────────────────────────

interface ScheduledOp {
  id: string;
  phase_id: string;
  phase_name?: string;
  workers?: string[];
  start?: string;
  end?: string;
  product_id?: string;
  order_id?: string;
  quality_risk?: number;
}

type TargetKind = 'phase' | 'worker';

interface DropTarget {
  kind: TargetKind;
  id: string;
}

interface PendingDrop {
  operationId: string;
  target: DropTarget;
  preview: PreviewDeltaResult;
}

const URGENCY_COLOR_HINT = `
* vermelho: end < now
* amarelo: end <= now + 1d
* verde: > 1d adiantado
`.trim();

// ───────────────────────────────────────────────────────────────────────────
// Hook helpers
// ───────────────────────────────────────────────────────────────────────────

function useLatestCommitOps() {
  // Get the most recent commit (with operations).
  const { data: commits, isLoading: listLoading } = useQuery({
    queryKey: ['cpo', 'commits', 'list'],
    queryFn: () => cpoCommitsApi.list({ limit: 1 }),
  });
  const sha = commits?.[0]?.commit_sha256 ?? null;
  const { data: commit, isLoading: detailLoading } = useQuery({
    queryKey: ['cpo', 'commits', 'detail', sha],
    queryFn: () =>
      sha ? cpoCommitsApi.get(sha, { include_operations: true }) : Promise.resolve(null),
    enabled: Boolean(sha),
  });
  return {
    commit: commit as CpoCommit | null | undefined,
    isLoading: listLoading || detailLoading,
  };
}

function urgencyColor(end?: string): string {
  if (!end) return 'border-slate-700/50';
  const ms = new Date(end).getTime() - Date.now();
  if (Number.isNaN(ms)) return 'border-slate-700/50';
  if (ms < 0) return 'border-red-500/60 bg-red-500/5';
  if (ms < 86_400_000) return 'border-amber-500/60 bg-amber-500/5';
  return 'border-emerald-500/30';
}

// ───────────────────────────────────────────────────────────────────────────
// Component
// ───────────────────────────────────────────────────────────────────────────

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

function PhaseColumn({ phaseId, ops }: { phaseId: string; ops: ScheduledOp[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: `phase:${phaseId}` });
  return (
    <div
      ref={setNodeRef}
      className={`p-2 rounded-lg border transition ${
        isOver ? 'bg-emerald-500/10 border-emerald-500/40' : 'bg-slate-800/30 border-slate-700/40'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-slate-300 font-medium truncate" title={phaseId}>
          {phaseId}
        </span>
        <span className="text-xs text-slate-500">{ops.length}</span>
      </div>
      <div className="space-y-1">
        {ops.map((op) => (
          <OpCard key={op.id} op={op} />
        ))}
      </div>
    </div>
  );
}

function WorkerSwimlane({ workerId, ops }: { workerId: string; ops: ScheduledOp[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: `worker:${workerId}` });
  return (
    <div
      ref={setNodeRef}
      className={`p-2 rounded-lg border transition ${
        isOver ? 'bg-emerald-500/10 border-emerald-500/40' : 'bg-slate-800/30 border-slate-700/40'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-slate-300 font-medium truncate" title={workerId}>
          {workerId}
        </span>
        <span className="text-xs text-slate-500">{ops.length}</span>
      </div>
      <div className="flex gap-1 flex-wrap">
        {ops.map((op) => (
          <OpCard key={op.id} op={op} compact />
        ))}
      </div>
    </div>
  );
}

function OpCard({ op, compact = false }: { op: ScheduledOp; compact?: boolean }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: op.id });
  const style = { opacity: isDragging ? 0.4 : 1 };
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={`px-2 py-1 rounded border bg-slate-900/50 cursor-grab active:cursor-grabbing ${urgencyColor(op.end)} ${compact ? 'text-xs' : ''}`}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="text-xs text-white truncate" title={op.id}>
          {op.order_id ?? op.id.slice(0, 8)}
        </span>
        {op.quality_risk != null && op.quality_risk >= 0.4 && (
          <AlertTriangle size={10} className="text-red-400 flex-shrink-0" />
        )}
      </div>
      {!compact && op.workers && op.workers.length > 0 && (
        <div className="text-[10px] text-slate-500 truncate">
          {op.workers.length}× {op.workers[0]}
        </div>
      )}
    </div>
  );
}

function SuggestionPanel({
  pending,
  ops,
  previewing,
  applying,
  reason,
  setReason,
  onApply,
  onCancel,
}: {
  pending: PendingDrop | null;
  ops: ScheduledOp[];
  previewing: boolean;
  applying: boolean;
  reason: string;
  setReason: (s: string) => void;
  onApply: () => void;
  onCancel: () => void;
}) {
  // Sprint Q.9 Onda 3.2 — explica-sempre via GhostOverlay + ConsequenceBlock.
  // The "loading" + "idle" + "active" states all flow through the same
  // GhostOverlay shell so the visual anchor (cyan border, "preview · não
  // escreve no plano" disclaimer) is consistent across states.
  if (previewing) {
    return (
      <div className="sticky top-4">
        <GhostOverlay mode="inline" loading badge="A calcular preview…" />
      </div>
    );
  }
  if (!pending) {
    return (
      <div className="sticky top-4">
        <GhostOverlay mode="inline" badge="Sugestão">
          <p className="text-xs text-slate-400">
            Arrasta um barco para uma fase ou um operador. Ao soltar,
            calculamos o impacto e mostramos as consequências antes de
            tu aplicares.
          </p>
        </GhostOverlay>
      </div>
    );
  }

  const { preview, target } = pending;
  const op = ops.find((o) => o.id === pending.operationId);
  const hasConflicts = preview.conflicts.length > 0;
  const canApply = !hasConflicts && reason.trim().length >= 10;

  // Build the 5-line consequence block from the preview-delta result.
  const consequenceLines: ConsequenceLine[] = [
    {
      label: 'Movimento',
      value: (
        <code>
          {op?.order_id ?? pending.operationId.slice(0, 8)} →{' '}
          {target.kind === 'phase' ? 'fase' : 'operador'} {target.id}
        </code>
      ),
      severity: 'info',
    },
    {
      label: 'Fitness',
      value: `${preview.fitness_before.toFixed(2)} → ${preview.fitness_after.toFixed(2)}`,
      detail: `Δ ${preview.fitness_delta >= 0 ? '+' : ''}${preview.fitness_delta.toFixed(2)} (menor é melhor)`,
      severity: preview.fitness_delta <= 0 ? 'positive' : 'warning',
    },
    {
      label: 'Throughput €/dia',
      value: `€${preview.throughput_eur_after.toLocaleString('pt-PT', {
        maximumFractionDigits: 0,
      })}`,
      detail: `Δ ${preview.throughput_eur_delta >= 0 ? '+' : ''}€${preview.throughput_eur_delta.toFixed(0)}`,
      severity: preview.throughput_eur_delta >= 0 ? 'positive' : 'warning',
    },
  ];
  if (preview.pair_rule_violation) {
    consequenceLines.push({
      label: 'Regra de pares',
      value: 'Violação',
      detail:
        'Laminagem standard precisa de 2 operadores (88.5% histórico). Indica o porquê para forçar.',
      severity: 'warning',
    });
  }
  if (preview.conflicts.length > 0) {
    consequenceLines.push({
      label: 'Conflitos',
      value: `${preview.conflicts.length} bloqueio(s)`,
      detail: preview.conflicts[0]?.message ?? 'Resolver antes de aplicar.',
      severity: 'critical',
    });
  }
  if (preview.warnings.length > 0) {
    consequenceLines.push({
      label: 'Avisos',
      value: `${preview.warnings.length}`,
      detail: preview.warnings[0]?.message ?? '',
      severity: 'warning',
    });
  }

  return (
    <div className="sticky top-4">
      <GhostOverlay mode="inline" badge="Sugestão · arrasto">
      <ConsequenceBlock title="Consequências" lines={consequenceLines} />

      {preview.conflicts.length > 0 ? (
        <div className="mt-3">
          <p className="text-xs text-red-400 font-semibold mb-1">
            Detalhe dos conflitos:
          </p>
          <ul className="space-y-1">
            {preview.conflicts.map((c, i) => (
              <IssueLi key={i} issue={c} />
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mt-3">
        <label className="block text-xs text-slate-400 mb-1">
          Porquê? <span className="text-slate-600">(≥10 caracteres — alimenta Camada 1)</span>
        </label>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          placeholder="Ex: cliente premium, K1 competição, Paulo livre."
          className="w-full px-2 py-1 bg-slate-900 border border-slate-700 rounded text-xs text-white"
          disabled={hasConflicts}
        />
      </div>

      <div className="flex justify-end gap-2 mt-3">
        <DarkButton variant="secondary" size="sm" onClick={onCancel}>
          Cancelar
        </DarkButton>
        <DarkButton
          size="sm"
          icon={<CheckCircle2 size={12} />}
          onClick={onApply}
          disabled={!canApply || applying}
        >
          {applying ? 'A aplicar…' : hasConflicts ? 'Bloqueado' : 'Aplicar'}
        </DarkButton>
      </div>
      </GhostOverlay>
    </div>
  );
}

function IssueLi({ issue }: { issue: PreviewIssue }) {
  return (
    <li className="flex items-start gap-1 text-xs">
      {issue.severity === 'conflict' ? (
        <Ban size={11} className="text-red-400 mt-0.5 flex-shrink-0" />
      ) : (
        <AlertTriangle size={11} className="text-amber-400 mt-0.5 flex-shrink-0" />
      )}
      <span className="text-slate-300">{issue.message}</span>
    </li>
  );
}

function DeltaRow({
  label,
  before,
  after,
  delta,
  unit = '',
  lowerIsBetter = false,
}: {
  label: string;
  before: number;
  after: number;
  delta: number;
  unit?: string;
  lowerIsBetter?: boolean;
}) {
  const isImprovement = lowerIsBetter ? delta < 0 : delta > 0;
  const sign = delta > 0 ? '+' : '';
  return (
    <div className="text-xs text-slate-400 flex items-center justify-between mt-1">
      <span>{label}:</span>
      <span>
        <span className="text-slate-500">{before.toFixed(2)}{unit}</span>
        <span className="mx-1">→</span>
        <span className="text-slate-200">{after.toFixed(2)}{unit}</span>
        <DarkBadge
          variant={isImprovement ? 'success' : delta === 0 ? 'neutral' : 'warning'}
          size="sm"
          className="ml-2"
        >
          {sign}{delta.toFixed(2)}{unit}
        </DarkBadge>
      </span>
    </div>
  );
}

export default DragDropPlanner;
