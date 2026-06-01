/**
 * OpCard — card de operação reutilizável nas 4 vistas (C1).
 *
 * Props:
 *   op          — ScheduledOp
 *   editable    — activa cursor-grab e useDraggable
 *   draggableId — id passado ao useDraggable (cada vista usa o seu prefixo)
 *   selected    — ring de acento
 *   dimmed      — opacity reduzida (outra op está seleccionada)
 *   onSelect    — callback quando se clica no card (não no Clickable)
 *   primaryLabel— texto principal (ex: order_id para Fase, phase_name para Barco)
 *   showBoost   — mostra badge ⚡acelerada (Fase)
 *   showQuality — mostra QualityRiskBadge (Barco / Pessoa)
 */

import { memo } from 'react';
import { useDraggable } from '@dnd-kit/core';
import { GripVertical } from 'lucide-react';
import { Clickable } from '../../entitySheets';
import { QualityRiskBadge } from './QualityRiskBadge';
import type { ScheduledOp } from '../types';
import type { PlanSelection } from '../selection';

// ─── Cor por estado ───────────────────────────────────────────────────────────

function statusStyle(status?: string): React.CSSProperties {
  if (status === 'COMPLETED' || status === 'completed')
    return { background: 'var(--green-bg)', borderColor: 'var(--green-bd)' };
  if (status === 'IN_PROGRESS' || status === 'in_progress')
    return { background: 'var(--teal-bg)', borderColor: 'var(--teal-bd)' };
  return { background: 'var(--gray-bg)', borderColor: 'var(--gray-bd)' };
}

// Q.141.H — Realizado (actual, sólido verde) vs Planeado (plan, tracejado).
function cardStyle(op: ScheduledOp): React.CSSProperties {
  if (op.source === 'actual')
    return { background: 'var(--green-bg)', borderColor: 'var(--green-bd)', borderStyle: 'solid' };
  return { ...statusStyle(op.status), borderStyle: 'dashed' };
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface OpCardProps {
  op: ScheduledOp;
  editable: boolean;
  draggableId: string;
  selected: boolean;
  dimmed: boolean;
  onSelect?: (sel: PlanSelection) => void;
  primaryLabel?: string;
  showBoost?: boolean;
  showQuality?: boolean;
}

// ─── Componente ───────────────────────────────────────────────────────────────

export const OpCard = memo(function OpCard({
  op,
  editable,
  draggableId,
  selected,
  dimmed,
  onSelect,
  primaryLabel,
  showBoost = false,
  showQuality = false,
}: OpCardProps) {
  // Q.141.I — o passado (actuals) é read-only; só o plano futuro é arrastável.
  const effectiveEditable = editable && op.source !== 'actual';
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: draggableId,
    disabled: !effectiveEditable,
  });

  const isAccelerated = showBoost && (op.effective_boost ?? 0) > 50;

  const selectionStyle: React.CSSProperties = selected
    ? { boxShadow: '0 0 0 1.5px var(--accent)', transition: 'box-shadow 140ms, opacity 140ms' }
    : { transition: 'box-shadow 140ms, opacity 140ms' };

  const opacityStyle: React.CSSProperties = isDragging
    ? { opacity: 0.35 }
    : dimmed
    ? { opacity: 0.32 }
    : { opacity: 1 };

  function handleClick(e: React.MouseEvent) {
    // Não intercepta cliques em links/Clickable
    if ((e.target as HTMLElement).closest('a, button[data-clickable]')) return;
    onSelect?.({ kind: 'op', id: op.id });
  }

  return (
    <div
      ref={setNodeRef}
      style={{ ...selectionStyle, ...opacityStyle, ...cardStyle(op) }}
      {...attributes}
      {...listeners}
      onClick={handleClick}
      className={[
        'relative flex items-center gap-1 px-1.5 py-1 rounded border text-[10px] truncate',
        effectiveEditable ? 'cursor-grab active:cursor-grabbing' : 'cursor-default',
        onSelect ? 'hover:ring-1 hover:ring-[color:var(--accent)]/40' : '',
      ].join(' ')}
      title={`${op.order_id ?? op.id} · ${op.phase_name}${isAccelerated ? ` · Acelerada (boost ${op.effective_boost})` : ''}${op.operator_name ? ` · ${op.operator_name}` : ''}`}
    >
      {effectiveEditable && <GripVertical size={9} className="flex-shrink-0" style={{ color: 'var(--fg-3)' }} />}

      <span className="truncate font-medium font-mono tabular-nums" style={{ color: 'var(--fg-1)' }}>
        {op.order_id ? (
          <Clickable kind="encomenda" id={op.order_id}>
            {primaryLabel ?? op.order_id}
          </Clickable>
        ) : (
          <span className="font-mono">{(primaryLabel ?? op.id).slice(0, 8)}</span>
        )}
      </span>

      {op.operator_name && (
        <span className="truncate hidden sm:inline" style={{ color: 'var(--fg-3)' }}>
          · {op.operator_name}
        </span>
      )}

      {showQuality && op.order_id && op.phase_id && (
        <QualityRiskBadge
          operatorId={op.operator_id ?? ''}
          boatId={op.order_id}
          phaseId={op.phase_id}
        />
      )}

      {isAccelerated && (
        <span
          className="absolute -top-1 -right-1 text-[8px] leading-none px-0.5 py-0 rounded bg-amber-400 text-amber-900 font-bold"
          aria-label={`Acelerada (boost ${op.effective_boost})`}
        >
          ⚡
        </span>
      )}
    </div>
  );
});
