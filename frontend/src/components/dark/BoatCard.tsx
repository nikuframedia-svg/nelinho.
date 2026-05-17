/**
 * BoatCard — cartão compacto representando um barco (CuratedOrder + fase).
 *
 * Usado em PhaseColumn (mapa fábrica) e no Gantt detalhe.
 * Draggable entre fases (HTML5 DnD ou @dnd-kit, decidido pelo caller).
 *
 * Visual:
 *   ┌───────────┐
 *   │ K1   FR 🟢│  ← model_short + client flag + status dot
 *   │ Fed.Franc │  ← client (truncated)
 *   │ Lam. 2.5h │  ← phase + days/hours in phase
 *   │ Paulo+M.  │  ← workers (opt)
 *   └───────────┘
 *
 * Plan v4 §4.2 / FRONTEND_DESIGN_PROMPT §4.2.
 * Sprint Q.18.UI.A.
 */

import type { ReactNode, DragEvent } from 'react';
import { Clock, Layers } from 'lucide-react';

export type BoatStatus =
  | 'on_time'
  | 'at_risk'
  | 'late'
  | 'curing'
  | 'completed';

export interface BoatCardProps {
  /** OF id from CuratedOrder. */
  order_id: number;
  /** Full model name. Used in tooltip. */
  model: string;
  /** Short prefix: K1, K2, K4, C1, C2, C4. */
  model_short: string;
  /** Client name (truncated to 1 line). */
  client?: string;
  /** ISO 3166-1 alpha-2 — used as flag/badge: FR, DE, PT, IT, NO, SE, ... */
  client_code?: string;
  /** Current phase name (curto: "Lam.", "Pintura"). */
  phase: string;
  status: BoatStatus;
  /** Hours or days in current phase. */
  time_in_phase?: { value: number; unit: 'h' | 'd' };
  /** Workers atribuídos — só primeira inicial + última inicial em compact. */
  workers?: string[];
  /** Mold code (opt). */
  mold?: string;
  /** ISO date — só mostrado em tooltip. */
  transport_date?: string;
  /** Risk score 0..1 — se > 0.15 mostra warning indicator. */
  quality_risk?: number;
  draggable?: boolean;
  className?: string;
  onClick?: () => void;
  onDragStart?: (e: DragEvent<HTMLDivElement>) => void;
  onDragEnd?: (e: DragEvent<HTMLDivElement>) => void;
}

const STATUS_DOT: Record<BoatStatus, string> = {
  on_time: 'bg-success',
  at_risk: 'bg-warning',
  late: 'bg-danger',
  curing: 'bg-slate-400',
  completed: 'bg-primary-500',
};

const STATUS_LABEL: Record<BoatStatus, string> = {
  on_time: 'No prazo',
  at_risk: 'Em risco',
  late: 'Atrasado',
  curing: 'Em cura',
  completed: 'Concluído',
};

const STATUS_BORDER: Record<BoatStatus, string> = {
  on_time: 'border-success/30',
  at_risk: 'border-warning/40',
  late: 'border-danger/40',
  curing: 'border-slate-500/40',
  completed: 'border-primary-500/40',
};

function workersCompact(workers: string[]): string {
  if (workers.length === 0) return '';
  if (workers.length === 1) return workers[0].split(/\s+/)[0];
  if (workers.length === 2) {
    return `${workers[0].split(/\s+/)[0]}+${workers[1][0]}.`;
  }
  return `${workers[0].split(/\s+/)[0]}+${workers.length - 1}`;
}

export function BoatCard({
  order_id,
  model,
  model_short,
  client,
  client_code,
  phase,
  status,
  time_in_phase,
  workers,
  mold,
  transport_date,
  quality_risk,
  draggable = false,
  className = '',
  onClick,
  onDragStart,
  onDragEnd,
}: BoatCardProps): ReactNode {
  const interactive = onClick !== undefined;
  const tooltip = [
    `${model} #${order_id}`,
    client,
    mold ? `Molde: ${mold}` : null,
    transport_date ? `Expedição: ${transport_date}` : null,
    quality_risk !== undefined
      ? `Risco qualidade: ${(quality_risk * 100).toFixed(0)}%`
      : null,
  ]
    .filter(Boolean)
    .join('\n');

  return (
    <div
      className={`
        flex flex-col gap-1 p-2 min-w-[110px] max-w-[140px]
        rounded-md border ${STATUS_BORDER[status]}
        bg-dark-700 hover:bg-dark-600
        transition-colors duration-150
        ${interactive ? 'cursor-pointer' : ''}
        ${draggable ? 'cursor-grab active:cursor-grabbing' : ''}
        ${className}
      `}
      onClick={onClick}
      title={tooltip}
      draggable={draggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
    >
      {/* Linha 1: model + client flag + status dot */}
      <div className="flex items-center justify-between gap-1">
        <span className="text-xs font-bold text-text-dark-primary tabular-nums">
          {model_short}
        </span>
        <div className="flex items-center gap-1">
          {client_code ? (
            <span className="text-[10px] font-semibold text-text-dark-tertiary uppercase">
              {client_code}
            </span>
          ) : null}
          <span
            className={`w-2 h-2 rounded-full ${STATUS_DOT[status]}`}
            aria-label={STATUS_LABEL[status]}
          />
        </div>
      </div>

      {/* Linha 2: cliente */}
      {client ? (
        <span className="text-[10px] text-text-dark-secondary truncate">
          {client}
        </span>
      ) : null}

      {/* Linha 3: fase + tempo */}
      <div className="flex items-center justify-between gap-1 text-[10px] text-text-dark-tertiary">
        <span className="truncate">{phase}</span>
        {time_in_phase ? (
          <span className="inline-flex items-center gap-0.5 tabular-nums shrink-0">
            <Clock className="w-2.5 h-2.5" />
            {time_in_phase.value}
            {time_in_phase.unit}
          </span>
        ) : null}
      </div>

      {/* Linha 4: workers (opt) */}
      {workers && workers.length > 0 ? (
        <div className="flex items-center gap-1 text-[10px] text-text-dark-secondary">
          <Layers className="w-2.5 h-2.5" />
          <span className="truncate">{workersCompact(workers)}</span>
        </div>
      ) : null}

      {/* Indicador de risco qualidade */}
      {quality_risk !== undefined && quality_risk > 0.15 ? (
        <div className="text-[10px] font-semibold text-warning tabular-nums">
          ⚠ risco {(quality_risk * 100).toFixed(0)}%
        </div>
      ) : null}
    </div>
  );
}
