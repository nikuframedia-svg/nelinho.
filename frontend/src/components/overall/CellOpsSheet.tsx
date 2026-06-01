/**
 * CellOpsSheet — drill-down de uma célula do heatmap (Q.147.B).
 *
 * Clicar num bloco de densidade abre a lista LEGÍVEL das ops dessa célula
 * (#barco · fase · operador · data; realizada vs planeada). Clicar numa →
 * seleciona-a (em modo Editar abre o editor de operação).
 */
import { Sheet } from '../dark/Sheet';
import type { ScheduledOp } from './types';

export function CellOpsSheet({
  ops,
  onPick,
  onClose,
}: {
  ops: ScheduledOp[];
  onPick: (op: ScheduledOp) => void;
  onClose: () => void;
}) {
  const sorted = [...ops].sort(
    (a, b) => (a.start ?? '').localeCompare(b.start ?? '') || (a.order_id ?? '').localeCompare(b.order_id ?? ''),
  );

  return (
    <Sheet
      open
      onClose={onClose}
      title={`${ops.length} operações`}
      subtitle="Clica numa para ver ou editar"
      width={520}
    >
      <div className="flex flex-col gap-1">
        {sorted.map((op) => (
          <button
            key={op.id}
            type="button"
            onClick={() => onPick(op)}
            className="flex items-center gap-2.5 px-2.5 py-1.5 rounded text-left hover:bg-white/[0.05] transition-colors"
            style={{ background: 'var(--bg-2)', border: '1px solid var(--bd-1)' }}
          >
            <span
              className="w-1 h-8 rounded flex-shrink-0"
              style={{ background: op.source === 'actual' ? 'var(--green)' : 'var(--gray-bd)' }}
            />
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium truncate" style={{ color: 'var(--fg-0)' }}>
                {op.order_id ? `#${op.order_id}` : op.id} · {op.phase_name}
              </div>
              <div className="text-[11px] truncate" style={{ color: 'var(--fg-3)' }}>
                {op.operator_name ?? 'sem operador'}
                {op.start ? ` · ${op.start.slice(0, 10)}` : ''}
                {op.source === 'actual' ? ' · realizada' : ' · planeada'}
              </div>
            </div>
          </button>
        ))}
      </div>
    </Sheet>
  );
}
