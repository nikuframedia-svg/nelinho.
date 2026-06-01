/**
 * CountBadge — resumo de uma célula da timeline em escalas grossas (Q.141.J).
 *
 * Em vez de empilhar centenas de cartões num intervalo grande (semana/mês),
 * mostra um badge com o nº de operações. Verde se há realizado, tracejado
 * cinza se só plano. Tooltip separa realizadas/planeadas.
 */
import { memo } from 'react';
import type { ScheduledOp } from '../types';

export const CountBadge = memo(function CountBadge({ ops }: { ops: ScheduledOp[] }) {
  const nAct = ops.filter((o) => o.source === 'actual').length;
  const nPlan = ops.length - nAct;
  const hasActual = nAct > 0;
  return (
    <span
      className="px-1.5 py-0.5 rounded text-[10px] font-semibold tabular-nums"
      style={
        hasActual
          ? { background: 'var(--green-bg)', border: '1px solid var(--green-bd)', color: 'var(--fg-1)' }
          : { background: 'var(--gray-bg)', border: '1px dashed var(--gray-bd)', color: 'var(--fg-2)' }
      }
      title={`${nAct} realizada(s) · ${nPlan} planeada(s)`}
    >
      {ops.length}
    </span>
  );
});

export default CountBadge;
