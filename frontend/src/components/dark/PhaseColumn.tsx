/**
 * PhaseColumn — coluna por fase no mapa fábrica (ProducaoPage).
 *
 * Header mostra: nome da fase + contagem de barcos + cor estado.
 * Sub-header: carga/capacidade, operadores alocados/disponíveis.
 * Barra de utilização (% load), gradient verde→amarelo→vermelho.
 * Aviso de retrabalho se >20% (Lixagem água é 49.2%).
 * Body: lista vertical de BoatCards droppable.
 *
 * Plan v4 §4.2 / FRONTEND_DESIGN_PROMPT §4.2.
 * Sprint Q.18.UI.A.
 */

import type { ReactNode, DragEvent } from 'react';
import { Users, Repeat, Hourglass } from 'lucide-react';

export interface PhaseColumnProps {
  phase_id: number | string;
  phase_name: string;
  /** Slot de BoatCards já renderizados pelo caller. */
  children: ReactNode;
  /** Contagem visível (≠ children.length em casos com filtros). */
  count: number;
  /** Capacidade máxima simultânea. */
  capacity?: number;
  /** Carga actual (barcos a ocupar a fase). */
  current_load?: number;
  /** Operadores alocados / disponíveis. */
  workers?: { allocated: number; available: number };
  /** Fase obriga cura/secagem (cinza, não conta como atraso). */
  curing_hours?: number;
  /** Taxa de retrabalho histórica — alerta se > 0.20. */
  rework_rate?: number;
  /** True quando current_load/capacity > 0.80. */
  is_bottleneck?: boolean;
  className?: string;
  onDropBoat?: (boatId: number | string, phaseId: number | string) => void;
}

function utilizationColor(pct: number): string {
  if (pct >= 0.95) return 'bg-danger';
  if (pct >= 0.80) return 'bg-warning';
  if (pct >= 0.50) return 'bg-success';
  return 'bg-primary-500';
}

export function PhaseColumn({
  phase_id,
  phase_name,
  children,
  count,
  capacity,
  current_load,
  workers,
  curing_hours,
  rework_rate,
  is_bottleneck = false,
  className = '',
  onDropBoat,
}: PhaseColumnProps): ReactNode {
  const utilization =
    capacity && capacity > 0 && current_load !== undefined
      ? Math.min(1, current_load / capacity)
      : null;
  const reworkAlert = rework_rate !== undefined && rework_rate > 0.20;

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    if (!onDropBoat) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    if (!onDropBoat) return;
    e.preventDefault();
    const boatId = e.dataTransfer.getData('text/plain');
    if (boatId) onDropBoat(boatId, phase_id);
  };

  return (
    <div
      className={`
        flex flex-col min-w-[160px] max-w-[200px]
        bg-dark-800/50 rounded-lg border ${is_bottleneck ? 'border-warning/40' : 'border-white/[0.06]'}
        ${className}
      `}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      data-phase-id={phase_id}
    >
      {/* Header */}
      <div className="flex flex-col gap-1.5 p-3 border-b border-white/[0.06]">
        <div className="flex items-center justify-between gap-1">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-text-dark-primary truncate">
            {phase_name}
          </h3>
          <span
            className={`
              text-xs font-bold tabular-nums px-1.5 py-0.5 rounded
              ${is_bottleneck ? 'bg-warning/20 text-warning' : 'bg-dark-700 text-text-dark-secondary'}
            `}
            aria-label={`${count} barcos`}
          >
            {count}
          </span>
        </div>

        {/* Carga / capacidade */}
        {capacity !== undefined && current_load !== undefined ? (
          <div className="flex items-center gap-2 text-[10px] text-text-dark-tertiary tabular-nums">
            <span>
              {current_load}/{capacity}
            </span>
            {workers ? (
              <span className="inline-flex items-center gap-0.5">
                <Users className="w-2.5 h-2.5" />
                {workers.allocated}/{workers.available}
              </span>
            ) : null}
          </div>
        ) : null}

        {/* Barra utilização */}
        {utilization !== null ? (
          <div className="flex items-center gap-1.5">
            <div className="flex-1 h-1.5 bg-dark-900 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ${utilizationColor(utilization)}`}
                style={{ width: `${utilization * 100}%` }}
              />
            </div>
            <span className="text-[10px] text-text-dark-tertiary tabular-nums shrink-0">
              {Math.round(utilization * 100)}%
            </span>
          </div>
        ) : null}

        {/* Cura indicator */}
        {curing_hours !== undefined ? (
          <div className="inline-flex items-center gap-1 text-[10px] text-slate-400">
            <Hourglass className="w-2.5 h-2.5" />
            <span className="tabular-nums">cura {curing_hours}h</span>
          </div>
        ) : null}

        {/* Rework alert */}
        {reworkAlert ? (
          <div className="inline-flex items-center gap-1 text-[10px] font-semibold text-warning">
            <Repeat className="w-2.5 h-2.5" />
            <span className="tabular-nums">retrabalho {Math.round(rework_rate! * 100)}%</span>
          </div>
        ) : null}
      </div>

      {/* Body — lista de BoatCards droppable */}
      <div className="flex flex-col gap-1.5 p-2 flex-1 min-h-[80px]">
        {children}
      </div>
    </div>
  );
}
