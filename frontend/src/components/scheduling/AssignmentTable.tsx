/**
 * AssignmentTable — Plan v4 §4.3 (Vista Atribuição) + §6.2 (alternative pairs).
 *
 * Tabela de atribuição diária: para uma data alvo (default hoje), mostra
 * cada operação agendada da última snapshot CPO (`/v1/plan/cpo/commits/{sha}
 * ?include_operations=true`) com a fase, operadores actuais e estado.
 *
 * Por linha, o gestor clica [Trocar ▾] para abrir uma sugestão de pares
 * alternativos (`/v1/plan/cpo/operations/{op_id}/worker-pairs`). Ao
 * escolher um par, o componente chama `preview-delta` em sub-segundo e
 * mostra um ConsequenceBlock com fitness Δ + conflitos + warnings. O
 * gestor confirma com uma razão (≥10 chars — espelha constraint
 * backend) e o `apply-move` cria um novo ScheduleCommit.
 *
 * Consumido por SchedulingPage (tab "Atribuição") e DailyDispatchPage.
 * ZERO MOCKS — empty/loading/error explícitos. Não toca no
 * DragDropPlanner existente; é vista alternativa na mesma data.
 */

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  RefreshCw,
  ServerCrash,
  Sparkles,
  X,
} from 'lucide-react';
import {
  cpoCommitsApi,
  schedulePreviewApi,
  type CpoCommit,
  type CpoWorkerPairItem,
  type PreviewDeltaResult,
} from '../../lib/api';
import {
  ConsequenceBlock,
  type ConsequenceLine,
  DarkBadge,
  DarkButton,
  DarkCard,
  WorkerPairCard,
} from '../dark';

const APPLY_REASON_MIN = 10;

interface ScheduledOp {
  id: string;
  phase_id: string;
  phase_name?: string;
  workers: string[];
  start?: string;
  end?: string;
  product_id?: string;
  order_id?: string;
  quality_risk?: number;
  mold_id?: string;
}

export interface AssignmentTableProps {
  /** Target date: only ops whose `start` falls on this YYYY-MM-DD render. */
  date: Date;
  /** Optional resolver: convert ERP employee_id → readable name. */
  resolveName?: (employeeId: string) => string | undefined;
  className?: string;
}

function isoDayKey(d: Date): string {
  // Local YYYY-MM-DD so the operator's clock matters, not UTC.
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function fmtTime(iso?: string): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleTimeString('pt-PT', {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function fmtDuration(start?: string, end?: string): string {
  if (!start || !end) return '—';
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (!Number.isFinite(ms) || ms <= 0) return '—';
  const hours = ms / 3_600_000;
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  return `${hours.toFixed(1)} h`;
}

function qualityRiskBadge(risk?: number) {
  if (typeof risk !== 'number') {
    return <DarkBadge variant="neutral">—</DarkBadge>;
  }
  const pct = Math.round(risk * 100);
  if (pct >= 25) return <DarkBadge variant="danger">{pct}% risco</DarkBadge>;
  if (pct >= 10) return <DarkBadge variant="warning">{pct}% risco</DarkBadge>;
  return <DarkBadge variant="success">{pct}% risco</DarkBadge>;
}

function previewToConsequenceLines(p: PreviewDeltaResult): ConsequenceLine[] {
  const lines: ConsequenceLine[] = [];

  const fitnessDelta = p.fitness_delta ?? 0;
  lines.push({
    label: 'Fitness',
    value: `${fitnessDelta >= 0 ? '+' : ''}${fitnessDelta.toFixed(3)}`,
    detail: `${p.fitness_before.toFixed(3)} → ${p.fitness_after.toFixed(3)}`,
    severity: fitnessDelta > 0 ? 'positive' : fitnessDelta < 0 ? 'warning' : 'info',
  });

  const tputDelta = p.throughput_eur_delta ?? 0;
  if (tputDelta !== 0) {
    lines.push({
      label: 'Throughput',
      value: `${tputDelta >= 0 ? '+' : ''}€${tputDelta.toFixed(0)}`,
      severity: tputDelta > 0 ? 'positive' : 'warning',
    });
  }

  if (p.pair_rule_violation) {
    lines.push({
      label: 'Regra de par',
      value: 'VIOLAÇÃO',
      detail: 'Esta troca quebra a regra de pares Laminagem.',
      severity: 'critical',
    });
  }

  for (const c of p.conflicts ?? []) {
    lines.push({
      label: c.type ?? 'Conflito',
      value: c.message,
      severity: 'critical',
    });
  }
  for (const w of p.warnings ?? []) {
    lines.push({
      label: w.type ?? 'Aviso',
      value: w.message,
      severity: 'warning',
    });
  }

  return lines;
}

interface SwapState {
  newWorkerIds: string[];
  preview?: PreviewDeltaResult;
  reason: string;
}

function SwapPanel({
  op,
  resolveName,
  onClose,
  onApplied,
}: {
  op: ScheduledOp;
  resolveName?: (id: string) => string | undefined;
  onClose: () => void;
  onApplied: () => void;
}) {
  const [swap, setSwap] = useState<SwapState | null>(null);

  const pairsQuery = useQuery({
    queryKey: ['cpo', 'worker-pairs', op.id],
    queryFn: () => cpoCommitsApi.workerPairs(op.id, { top_n: 5 }),
    staleTime: 30_000,
  });

  const previewMutation = useMutation({
    mutationFn: (workerIds: string[]) =>
      schedulePreviewApi.previewDelta({
        operation_id: op.id,
        new_worker_ids: workerIds,
      }),
  });

  const applyMutation = useMutation({
    mutationFn: (payload: { workerIds: string[]; reason: string }) =>
      schedulePreviewApi.applyMove({
        operation_id: op.id,
        new_worker_ids: payload.workerIds,
        reason: payload.reason,
      }),
    onSuccess: () => {
      onApplied();
    },
  });

  const handlePick = async (pair: CpoWorkerPairItem) => {
    const workerIds: string[] = [pair.chefe_id];
    if (pair.partner_id) workerIds.push(pair.partner_id);
    setSwap({ newWorkerIds: workerIds, reason: '' });
    const preview = await previewMutation.mutateAsync(workerIds);
    setSwap({ newWorkerIds: workerIds, preview, reason: '' });
  };

  const reasonValid =
    swap !== null && swap.reason.trim().length >= APPLY_REASON_MIN;
  const canApply =
    swap !== null &&
    swap.preview !== undefined &&
    reasonValid &&
    !applyMutation.isPending;

  return (
    <div className="bg-slate-900/60 border-t border-slate-700/60 p-3 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-wider text-slate-400">
          Trocar operadores · Op{' '}
          <span className="font-mono">#{op.id.slice(0, 8)}</span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-slate-400 hover:text-slate-200"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {pairsQuery.isLoading ? (
        <WorkerPairCard pairs={[]} loading />
      ) : pairsQuery.error ? (
        <div className="text-sm text-rose-300">
          Não consegui ler pares alternativos:{' '}
          {pairsQuery.error instanceof Error
            ? pairsQuery.error.message
            : String(pairsQuery.error)}
        </div>
      ) : (
        <WorkerPairCard
          pairs={pairsQuery.data?.pairs ?? []}
          resolveName={resolveName}
          onPick={handlePick}
          title={
            pairsQuery.data?.needs_pair
              ? 'Pares alternativos (Laminagem requer 2)'
              : 'Operadores alternativos'
          }
        />
      )}

      {previewMutation.isPending ? (
        <div className="flex items-center gap-2 text-sm text-slate-300">
          <Loader2 className="w-4 h-4 animate-spin" /> A calcular impacto...
        </div>
      ) : null}

      {swap?.preview ? (
        <ConsequenceBlock
          title="Impacto desta troca"
          lines={previewToConsequenceLines(swap.preview)}
        />
      ) : null}

      {swap?.preview ? (
        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] uppercase tracking-wider text-slate-400">
            Razão para esta troca (mín. {APPLY_REASON_MIN} chars · alimenta
            aprendizagem)
          </label>
          <textarea
            value={swap.reason}
            onChange={(e) =>
              setSwap((prev) => (prev ? { ...prev, reason: e.target.value } : prev))
            }
            disabled={applyMutation.isPending}
            rows={2}
            placeholder="Ex: Operador A teve formação extra na fase, score subiu na semana"
            className={`w-full rounded-md border bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 disabled:opacity-60 ${
              swap.reason.length === 0 || reasonValid
                ? 'border-slate-700/70'
                : 'border-amber-500/60'
            }`}
          />
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-400">
              {reasonValid
                ? '✓ Razão suficiente'
                : `Faltam ${Math.max(
                    0,
                    APPLY_REASON_MIN - swap.reason.trim().length,
                  )} caracteres`}
            </span>
            <DarkButton
              variant="primary"
              disabled={!canApply}
              onClick={() =>
                applyMutation.mutate({
                  workerIds: swap.newWorkerIds,
                  reason: swap.reason.trim(),
                })
              }
            >
              {applyMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <CheckCircle2 className="w-3.5 h-3.5" />
              )}
              Confirmar troca
            </DarkButton>
          </div>
          {applyMutation.error ? (
            <div className="text-xs text-rose-300">
              {applyMutation.error instanceof Error
                ? applyMutation.error.message
                : String(applyMutation.error)}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function AssignmentTable({
  date,
  resolveName,
  className = '',
}: AssignmentTableProps) {
  const queryClient = useQueryClient();
  const [openSwapId, setOpenSwapId] = useState<string | null>(null);

  // Step 1: get latest commit SHA.
  const listQuery = useQuery({
    queryKey: ['cpo', 'commits', 'list'],
    queryFn: () => cpoCommitsApi.list({ limit: 1 }),
    staleTime: 30_000,
  });
  const sha = listQuery.data?.[0]?.commit_sha256 ?? null;

  // Step 2: pull operations from that commit.
  const detailQuery = useQuery({
    queryKey: ['cpo', 'commits', 'detail', sha],
    queryFn: () =>
      sha
        ? cpoCommitsApi.get(sha, { include_operations: true })
        : Promise.resolve(null as CpoCommit | null),
    enabled: Boolean(sha),
    staleTime: 30_000,
  });

  const ops: ScheduledOp[] = useMemo(() => {
    const commit = detailQuery.data;
    if (!commit?.operations) return [];
    return commit.operations.map((op) => ({
      id: String(op.id ?? op.operation_id ?? ''),
      phase_id: String(op.phase_id ?? op.phase_name ?? 'UNKNOWN'),
      phase_name:
        typeof op.phase_name === 'string' ? op.phase_name : undefined,
      workers: Array.isArray(op.workers) ? (op.workers as string[]) : [],
      start: typeof op.start === 'string' ? op.start : undefined,
      end: typeof op.end === 'string' ? op.end : undefined,
      product_id:
        typeof op.product_id === 'string' ? op.product_id : undefined,
      order_id: typeof op.order_id === 'string' ? op.order_id : undefined,
      quality_risk:
        typeof op.quality_risk === 'number' ? op.quality_risk : undefined,
      mold_id: typeof op.mold_id === 'string' ? op.mold_id : undefined,
    }));
  }, [detailQuery.data]);

  const targetKey = useMemo(() => isoDayKey(date), [date]);

  const filtered = useMemo(() => {
    return ops
      .filter((o) => {
        if (!o.start) return false;
        try {
          const startKey = isoDayKey(new Date(o.start));
          return startKey === targetKey;
        } catch {
          return false;
        }
      })
      .sort((a, b) => {
        const sa = a.start ? new Date(a.start).getTime() : 0;
        const sb = b.start ? new Date(b.start).getTime() : 0;
        return sa - sb;
      });
  }, [ops, targetKey]);

  const isLoading = listQuery.isLoading || detailQuery.isLoading;
  const error = listQuery.error ?? detailQuery.error;

  // Empty state guards
  if (isLoading) {
    return (
      <DarkCard className={`p-10 flex items-center justify-center gap-2 text-slate-300 ${className}`}>
        <Loader2 className="w-5 h-5 animate-spin text-sky-300" />
        A carregar atribuição...
      </DarkCard>
    );
  }
  if (error) {
    return (
      <DarkCard
        className={`p-10 flex flex-col items-center gap-3 border-rose-500/30 bg-rose-500/5 text-rose-200 ${className}`}
      >
        <ServerCrash className="w-8 h-8" />
        <div className="text-base font-semibold">
          Não consegui ler o último schedule.
        </div>
        <div className="text-sm text-rose-200/80 max-w-lg text-center">
          {error instanceof Error ? error.message : String(error)}
        </div>
        <DarkButton onClick={() => listQuery.refetch()} variant="primary">
          Tentar de novo
        </DarkButton>
      </DarkCard>
    );
  }
  if (!sha) {
    return (
      <DarkCard className={`p-10 flex flex-col items-center gap-2 text-slate-400 ${className}`}>
        <Sparkles className="w-10 h-10 text-slate-600" />
        <div className="text-base text-slate-200">
          Sem schedule gerado ainda.
        </div>
        <div className="text-sm text-center max-w-md">
          Vai a <strong className="text-slate-200">Production Scheduling</strong> e
          carrega <strong>Generate Schedule</strong> para criar o primeiro plano.
        </div>
      </DarkCard>
    );
  }
  if (filtered.length === 0) {
    return (
      <DarkCard className={`p-10 flex flex-col items-center gap-2 text-slate-400 ${className}`}>
        <CheckCircle2 className="w-10 h-10 text-slate-600" />
        <div className="text-base text-slate-200">
          Nenhuma operação agendada para{' '}
          <span className="text-slate-100">{targetKey}</span>.
        </div>
        <div className="text-sm">
          {ops.length > 0
            ? 'Existem ops noutras datas — muda o filtro acima.'
            : 'O último schedule não tem operações.'}
        </div>
      </DarkCard>
    );
  }

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      <div className="flex items-center justify-between text-[11px] uppercase tracking-wider text-slate-400 px-1">
        <span>
          {filtered.length} operação{filtered.length === 1 ? '' : 'ões'} para{' '}
          <span className="text-slate-200">{targetKey}</span>
        </span>
        <button
          type="button"
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ['cpo', 'commits'] });
          }}
          className="inline-flex items-center gap-1 hover:text-slate-200"
        >
          <RefreshCw className="w-3 h-3" /> Refrescar
        </button>
      </div>

      <DarkCard className="p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-400 text-[11px] uppercase tracking-wider border-b border-slate-800">
              <th className="px-3 py-2">Início</th>
              <th className="px-3 py-2">Encomenda</th>
              <th className="px-3 py-2">Fase</th>
              <th className="px-3 py-2">Operadores</th>
              <th className="px-3 py-2">Duração</th>
              <th className="px-3 py-2">Risco</th>
              <th className="px-3 py-2 text-right">Acção</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((op) => {
              const isOpen = openSwapId === op.id;
              return (
                <>
                  <tr
                    key={op.id}
                    className="border-b border-slate-800 hover:bg-slate-800/30"
                  >
                    <td className="px-3 py-2 font-mono text-slate-200 whitespace-nowrap">
                      {fmtTime(op.start)}
                    </td>
                    <td className="px-3 py-2 text-slate-200 truncate max-w-[160px]">
                      {op.order_id ?? '—'}
                    </td>
                    <td className="px-3 py-2 text-slate-300">
                      {op.phase_name ?? op.phase_id}
                    </td>
                    <td className="px-3 py-2 text-slate-300">
                      {op.workers.length === 0 ? (
                        <span className="italic text-slate-500">sem atribuição</span>
                      ) : (
                        op.workers
                          .map((w) => resolveName?.(w) ?? w)
                          .join(' + ')
                      )}
                    </td>
                    <td className="px-3 py-2 font-mono text-slate-300">
                      {fmtDuration(op.start, op.end)}
                    </td>
                    <td className="px-3 py-2">
                      {qualityRiskBadge(op.quality_risk)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => setOpenSwapId(isOpen ? null : op.id)}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-slate-700 text-xs text-slate-200 hover:bg-slate-800"
                      >
                        Trocar
                        {isOpen ? (
                          <ChevronUp className="w-3 h-3" />
                        ) : (
                          <ChevronDown className="w-3 h-3" />
                        )}
                      </button>
                    </td>
                  </tr>
                  {isOpen ? (
                    <tr key={`${op.id}-swap`}>
                      <td colSpan={7} className="p-0">
                        <SwapPanel
                          op={op}
                          resolveName={resolveName}
                          onClose={() => setOpenSwapId(null)}
                          onApplied={() => {
                            setOpenSwapId(null);
                            queryClient.invalidateQueries({
                              queryKey: ['cpo', 'commits'],
                            });
                          }}
                        />
                      </td>
                    </tr>
                  ) : null}
                </>
              );
            })}
          </tbody>
        </table>
      </DarkCard>
    </div>
  );
}
