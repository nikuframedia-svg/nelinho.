/**
 * WorkerPairCard — Plan v4 §6.2 contract.
 *
 * Renders the alternative worker pairs the manager sees BEFORE
 * confirming a Laminagem assignment. The plan example reads:
 *
 *   "Operadores disponíveis: Paulo Gomes + Maria Silva (score 8.2)
 *    OU João Costa + Ana Reis (score 6.1)"
 *
 * This component renders that list of pair candidates with scores.
 * The first row is the recommended pick (highest score); the others
 * are alternatives the manager can override.
 *
 * Score visualisation:
 *   score ≥ 8.0   → emerald (top tier)
 *   score 6.0–8.0 → amber (acceptable)
 *   score < 6.0   → rose (degraded — picking this is a deliberate
 *                   trade-off, e.g. on-the-job training)
 *
 * The card is read-mostly: clicking a pair row fires `onPick(pair)` so
 * the parent (DragDropPlanner) can apply the choice. When `loading`
 * is true a skeleton renders. Empty pairs[] → "sem alternativas"
 * (caller falls back to single-worker UI).
 *
 * Sprint Q.13.A.
 */

import type { ReactNode } from 'react';
import { Sparkles, Users } from 'lucide-react';
import type { CpoWorkerPairItem } from '../../lib/api';

export interface WorkerPairCardProps {
  pairs: CpoWorkerPairItem[];
  /** Optional resolver: convert ERP employee_id → readable name. When
   *  omitted, the id is shown verbatim. */
  resolveName?: (employeeId: string) => string | undefined;
  /** Fired when the manager picks a row. */
  onPick?: (pair: CpoWorkerPairItem) => void;
  loading?: boolean;
  className?: string;
  /** Header label override; defaults to "Operadores disponíveis". */
  title?: string;
}

const SCORE_TONE = (score: number): { bg: string; text: string; ring: string } => {
  if (score >= 8.0) {
    return {
      bg: 'bg-emerald-500/10',
      text: 'text-emerald-200',
      ring: 'ring-emerald-500/40',
    };
  }
  if (score >= 6.0) {
    return {
      bg: 'bg-amber-500/10',
      text: 'text-amber-200',
      ring: 'ring-amber-500/40',
    };
  }
  return {
    bg: 'bg-rose-500/10',
    text: 'text-rose-200',
    ring: 'ring-rose-500/40',
  };
};

function _formatPairLabel(
  pair: CpoWorkerPairItem,
  resolveName?: (id: string) => string | undefined,
): ReactNode {
  const chefeName = resolveName?.(pair.chefe_id) ?? pair.chefe_id;
  if (!pair.partner_id) {
    return (
      <span>
        <strong>{chefeName}</strong>{' '}
        <span className="text-slate-400 text-xs">(solo)</span>
      </span>
    );
  }
  const partnerName = resolveName?.(pair.partner_id) ?? pair.partner_id;
  return (
    <span>
      <strong>{chefeName}</strong>
      <span className="text-slate-400 mx-1">+</span>
      <strong>{partnerName}</strong>
    </span>
  );
}

export function WorkerPairCard({
  pairs,
  resolveName,
  onPick,
  loading = false,
  className = '',
  title = 'Operadores disponíveis',
}: WorkerPairCardProps) {
  return (
    <div
      className={`rounded-lg border border-slate-700/60 bg-slate-800/40 p-3 flex flex-col gap-2 ${className}`}
    >
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-slate-300">
        <Users className="w-3.5 h-3.5 text-slate-400" />
        <span>{title}</span>
      </div>

      {loading ? (
        <div className="flex flex-col gap-1.5 animate-pulse">
          <div className="h-7 rounded bg-slate-700/50" />
          <div className="h-7 rounded bg-slate-700/50 w-5/6" />
          <div className="h-7 rounded bg-slate-700/50 w-4/6" />
        </div>
      ) : pairs.length === 0 ? (
        <p className="text-xs text-slate-500 italic">
          Sem pares alternativos para esta operação.
        </p>
      ) : (
        <ul className="flex flex-col gap-1">
          {pairs.map((pair, idx) => {
            const tone = SCORE_TONE(pair.score);
            const isTop = idx === 0;
            return (
              <li key={`${pair.chefe_id}-${pair.partner_id ?? 'solo'}`}>
                <button
                  type="button"
                  onClick={() => onPick?.(pair)}
                  disabled={!onPick}
                  className={`w-full flex items-center justify-between gap-2 px-2 py-1.5 rounded-md ${tone.bg} ${
                    onPick
                      ? 'cursor-pointer hover:ring-1 hover:ring-offset-1 hover:ring-offset-slate-900 hover:' +
                        tone.ring
                      : 'cursor-default'
                  }`}
                >
                  <span className="flex items-center gap-2 text-sm text-slate-100">
                    {isTop ? (
                      <Sparkles className="w-3 h-3 text-cyan-300 shrink-0" />
                    ) : (
                      <span className="w-3" />
                    )}
                    {_formatPairLabel(pair, resolveName)}
                  </span>
                  <span
                    className={`text-sm font-bold ${tone.text} tabular-nums`}
                    aria-label={`score ${pair.score}`}
                  >
                    {pair.score.toFixed(1)}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
