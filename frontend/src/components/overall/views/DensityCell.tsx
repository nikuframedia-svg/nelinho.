/**
 * DensityCell — célula de heatmap para escala "dia" quando há muitas ops (Q.147.A).
 *
 * A 6395 ops, cramar cartões por célula é ilegível. Padrão schedule-density:
 * acima de N ops a célula vira um bloco de intensidade + contagem (heatmap —
 * mais ops = mais intenso; verde se há realizado, neutro/tracejado se só plano).
 * Clicar abre o drill-down (lista das ops da célula).
 */
import { memo } from 'react';
import type { ScheduledOp } from '../types';

/** Acima disto a célula vira heatmap; ≤ isto mostra os cartões. */
export const DENSITY_THRESHOLD = 3;

export const DensityCell = memo(function DensityCell({
  ops,
  onClick,
}: {
  ops: ScheduledOp[];
  onClick?: () => void;
}) {
  const n = ops.length;
  const nAct = ops.filter((o) => o.source === 'actual').length;
  const hasActual = nAct > 0;
  // Intensidade log (≈4 → 50+ ops mapeia 0..1).
  const intensity = Math.min(1, Math.log10(Math.max(2, n)) / Math.log10(50));
  const base = hasActual ? '16,185,129' /* emerald */ : '125,143,170' /* slate */;

  return (
    <button
      type="button"
      onClick={onClick}
      className="h-full w-full flex flex-col items-center justify-center rounded transition hover:ring-1 hover:ring-[color:var(--accent)]"
      style={{
        background: `rgba(${base}, ${(0.1 + intensity * 0.55).toFixed(2)})`,
        border: `1px ${hasActual ? 'solid' : 'dashed'} rgba(${base}, ${(0.35 + intensity * 0.4).toFixed(2)})`,
        cursor: onClick ? 'pointer' : 'default',
      }}
      title={`${n} operações (${nAct} realizadas · ${n - nAct} planeadas) — clicar para ver/editar`}
    >
      <span className="text-sm font-semibold tabular-nums leading-none" style={{ color: 'var(--fg-0)' }}>
        {n}
      </span>
      <span className="text-[8px] uppercase tracking-wide mt-0.5" style={{ color: 'var(--fg-2)' }}>
        ops
      </span>
    </button>
  );
});

export default DensityCell;
