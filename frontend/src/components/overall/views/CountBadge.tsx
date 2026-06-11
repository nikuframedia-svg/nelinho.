/**
 * CountBadge — resumo de uma célula da timeline em escalas grossas (Q.141.J).
 *
 * Em vez de empilhar centenas de cartões num intervalo grande (semana/mês),
 * mostra um badge com o nº de operações. Verde se há realizado, tracejado
 * cinza se só plano. Tooltip separa realizadas/planeadas.
 *
 * Q.173.AE — recebe `onClick` opcional para abrir CellOpsSheet (drill-down
 * nas escalas semana/mês, que antes eram leitura cega).
 */
import { memo } from 'react';
import type { ScheduledOp } from '../types';

interface CountBadgeProps {
  ops: ScheduledOp[];
  /** Q.173.AE — drill-down: abre a lista de ops da célula. */
  onClick?: () => void;
}

export const CountBadge = memo(function CountBadge({ ops, onClick }: CountBadgeProps) {
  const nAct = ops.filter((o) => o.source === 'actual').length;
  const nPlan = ops.length - nAct;
  const hasActual = nAct > 0;

  const style = hasActual
    ? { background: 'var(--green-bg)', border: '1px solid var(--green-bd)', color: 'var(--fg-1)' }
    : { background: 'var(--gray-bg)', border: '1px dashed var(--gray-bd)', color: 'var(--fg-2)' };

  const title = `${nAct} realizada(s) · ${nPlan} planeada(s)${onClick ? ' — clica para ver detalhe' : ''}`;

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="px-1.5 py-0.5 rounded text-[10px] font-semibold tabular-nums cursor-pointer hover:opacity-80 transition-opacity"
        style={style}
        title={title}
      >
        {ops.length}
      </button>
    );
  }

  return (
    <span
      className="px-1.5 py-0.5 rounded text-[10px] font-semibold tabular-nums"
      style={style}
      title={title}
    >
      {ops.length}
    </span>
  );
});

export default CountBadge;
