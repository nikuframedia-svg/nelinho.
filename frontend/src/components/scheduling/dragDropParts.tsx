// Decomposto de DragDropPlanner.tsx (Q.60.AB).
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import { AlertTriangle, Ban, CheckCircle2 } from 'lucide-react';
import { cpoCommitsApi, type CpoCommit, type CpoWorkerPairsResponse, type PreviewDeltaResult, type PreviewIssue } from '../../lib/api';
import { ConsequenceBlock, DarkBadge, DarkButton, GhostOverlay, WorkerPairCard, type ConsequenceLine } from '../dark';

// ───────────────────────────────────────────────────────────────────────────
// Types
// ───────────────────────────────────────────────────────────────────────────

export interface ScheduledOp {
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

export type TargetKind = 'phase' | 'worker';

export interface DropTarget {
  kind: TargetKind;
  id: string;
}

export interface PendingDrop {
  operationId: string;
  target: DropTarget;
  preview: PreviewDeltaResult;
}

export const URGENCY_COLOR_HINT = `
* vermelho: end < now
* amarelo: end <= now + 1d
* verde: > 1d adiantado
`.trim();

// ───────────────────────────────────────────────────────────────────────────
// Hook helpers
// ───────────────────────────────────────────────────────────────────────────

export function useLatestCommitOps() {
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

export function urgencyColor(end?: string): string {
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

export function PhaseColumn({ phaseId, ops }: { phaseId: string; ops: ScheduledOp[] }) {
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

// Sprint Q.13.C C.3.1 — Plan v4 §6 Layer 2 enrichments. Each swimlane
// now shows (when available): worker name, quality score, today's
// capacity bar (filled by ops sum vs SHIFT_HOURS_PER_DAY). Defaults
// keep the Layer-2 DragDropPlanner working when the parent doesn't
// inject the resolver — fail-graceful on every prop.
export const _SHIFT_HOURS_PER_DAY = 8;

export function WorkerSwimlane({
  workerId,
  ops,
  workerName,
  qualityScore,
}: {
  workerId: string;
  ops: ScheduledOp[];
  workerName?: string;
  qualityScore?: number;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: `worker:${workerId}` });

  // Sum of duration across this worker's ops today (in hours). Used
  // to draw a capacity meter so the operator sees overload at-a-glance.
  const totalHoursToday = useMemo(() => {
    return ops.reduce((acc, op) => {
      const start = op.start ? new Date(op.start).getTime() : 0;
      const end = op.end ? new Date(op.end).getTime() : 0;
      if (!start || !end || end <= start) return acc;
      return acc + (end - start) / (1000 * 60 * 60);
    }, 0);
  }, [ops]);

  const utilPct = Math.min(
    150,
    Math.round((totalHoursToday / _SHIFT_HOURS_PER_DAY) * 100),
  );
  const utilTone =
    utilPct > 100
      ? 'bg-rose-500'
      : utilPct >= 90
      ? 'bg-amber-400'
      : 'bg-emerald-400';

  // Quality score chip colour. Higher score (1-10 scale, Laplace
  // smoothed) = better; <5 is a yellow flag, ≥8 is the gold standard.
  const qualityTone =
    qualityScore == null
      ? null
      : qualityScore >= 8
      ? 'bg-emerald-500/15 text-emerald-300'
      : qualityScore >= 5
      ? 'bg-amber-500/15 text-amber-300'
      : 'bg-rose-500/15 text-rose-300';

  return (
    <div
      ref={setNodeRef}
      className={`p-2 rounded-lg border transition ${
        isOver
          ? 'bg-emerald-500/10 border-emerald-500/40'
          : 'bg-slate-800/30 border-slate-700/40'
      }`}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span
          className="text-xs text-slate-200 font-medium truncate"
          title={workerName ? `${workerName} · ${workerId}` : workerId}
        >
          {workerName ?? workerId}
        </span>
        <div className="flex items-center gap-1 shrink-0">
          {qualityTone && qualityScore != null ? (
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${qualityTone}`}
              title="Quality score (1-10)"
            >
              {qualityScore.toFixed(1)}
            </span>
          ) : null}
          <span className="text-xs text-slate-500" title="Ops hoje">
            {ops.length}
          </span>
        </div>
      </div>

      {/* Capacity bar — visible even with 0 ops so the swimlane has
          a consistent visual rhythm down the rail. */}
      <div
        className="h-1 rounded-full bg-slate-700/50 mb-2 overflow-hidden"
        title={`${totalHoursToday.toFixed(1)}h / ${_SHIFT_HOURS_PER_DAY}h (${utilPct}%)`}
      >
        <div
          className={`h-full ${utilTone} transition-all`}
          style={{ width: `${Math.min(100, utilPct)}%` }}
        />
      </div>

      <div className="flex gap-1 flex-wrap">
        {ops.map((op) => (
          <OpCard key={op.id} op={op} compact />
        ))}
      </div>
    </div>
  );
}

export function OpCard({ op, compact = false }: { op: ScheduledOp; compact?: boolean }) {
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

export function SuggestionPanel({
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
  // Sprint Q.13.A — Plan v4 §6.2 alternative pairs. Only fetch when the
  // drag target is a phase (Layer 1) AND the op was a real op_id; for
  // worker drops (Layer 2) the manager already chose a specific worker
  // so the alternatives view doesn't apply. The query is lazy + cached
  // 30s so multiple drags on the same op don't re-fetch.
  //
  // MUST be called before any conditional return so that React Hook
  // ordering stays stable across renders (rules-of-hooks).
  const operationId = pending?.operationId;
  const isPhaseDrop = pending?.target?.kind === 'phase';
  const pairsQuery = useQuery<CpoWorkerPairsResponse>({
    queryKey: ['cpo', 'worker-pairs', operationId ?? 'idle'],
    queryFn: () => cpoCommitsApi.workerPairs(operationId!, { top_n: 3 }),
    enabled: !!operationId && !!isPhaseDrop && !previewing,
    staleTime: 30_000,
    retry: false,
  });

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

      {/* Sprint Q.13.A — Plan v4 §6.2: alternative pairs (only on phase
          drops). Loading state shows a skeleton; needs_pair=false hides
          the card entirely (caller fell back to single-worker UI). */}
      {isPhaseDrop && pairsQuery.data?.needs_pair ? (
        <div className="mt-3">
          <WorkerPairCard
            pairs={pairsQuery.data.pairs}
            loading={pairsQuery.isLoading}
            title="Pares disponíveis (operador)"
          />
        </div>
      ) : null}

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

export function IssueLi({ issue }: { issue: PreviewIssue }) {
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

export function DeltaRow({
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
