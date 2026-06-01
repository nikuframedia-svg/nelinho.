/**
 * PorFaseView — swimlane gantt por fase de produção (Q.115.K).
 *
 * Extraído de OverallPage.tsx (C1) para ter props uniformes com
 * PorBarcoView / PorPessoaView.
 *
 * Props: {operations, editable, startDate, endDate, onDrop}
 * Converte internamente para onDropPhaseDate que espera (opId, phaseId, date).
 */

import { useMemo, useCallback, memo, type ReactNode } from 'react';
import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
} from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import { EmptyState } from '../../dark';
import { Clickable } from '../../entitySheets';
import { Timeline, buildSlots, dateToSlotIndex } from '../Timeline';
import type { TimelineScale } from '../Timeline';
import type { TimelineLane, TimelineItem } from '../../dark';
import type { ScheduledOp } from '../types';
import type { PlanSelection } from '../selection';
import { opMatchesSelection } from '../selection';
import { OpCard } from './OpCard';
import { DensityCell, DENSITY_THRESHOLD } from './DensityCell';
import { useCellExpand } from '../cellExpand';
import { CountBadge } from './CountBadge';
import { RemoveZone, REMOVE_ZONE_ID } from './RemoveZone';

// ─── Props ────────────────────────────────────────────────────────────────────

interface PorFaseViewProps {
  operations: ScheduledOp[];
  editable: boolean;
  startDate: Date;
  endDate: Date;
  onDrop: (opId: string, newPhase: string, newStartTs: string, newOperatorId?: string) => void;
  /** Q.153.C2 — arrastar uma op para a RemoveZone exclui o barco (order_id). */
  onExclude?: (orderId: string) => void;
  selection?: PlanSelection | null;
  onSelect?: (sel: PlanSelection) => void;
  scale?: TimelineScale;
}

// ─── Droppable slot: fase + dia ───────────────────────────────────────────────

function PhaseDropSlot({
  phaseId,
  slotId,
  ops,
  editable,
  selection,
  onSelect,
  compact = false,
}: {
  phaseId: string;
  slotId: string;
  ops: ScheduledOp[];
  editable: boolean;
  selection?: PlanSelection | null;
  onSelect?: (sel: PlanSelection) => void;
  compact?: boolean;
}) {
  const dropId = `${phaseId}__${slotId}`;
  const { setNodeRef, isOver } = useDroppable({ id: dropId });
  const expand = useCellExpand();

  // Q.141.J — escalas grossas (semana/mês): contagem por célula em vez de
  // milhares de cartões. Verde quando há realizado, neutro quando só plano.
  if (compact) {
    return (
      <div ref={setNodeRef} className="h-full w-full flex items-center justify-center p-0.5">
        {ops.length > 0 && <CountBadge ops={ops} />}
      </div>
    );
  }

  return (
    <div
      ref={setNodeRef}
      className={`h-full w-full flex flex-col gap-0.5 p-0.5 rounded transition ${
        isOver && editable ? 'bg-teal-500/10 ring-1 ring-teal-500/40' : ''
      }`}
    >
      {ops.length > DENSITY_THRESHOLD ? (
        <DensityCell ops={ops} onClick={() => expand?.(ops)} />
      ) : (
        ops.map((op) => {
          const selected = opMatchesSelection(op, selection ?? null);
          const dimmed = !!selection && !selected;
          return (
            <OpCard
              key={op.id}
              op={op}
              editable={editable}
              draggableId={op.id}
              selected={selected}
              dimmed={dimmed}
              onSelect={onSelect}
              primaryLabel={op.order_id}
              showBoost
            />
          );
        })
      )}
    </div>
  );
}

// ─── PorFaseView ──────────────────────────────────────────────────────────────

function renderOpItem(
  item: TimelineItem,
  opsByPhaseSlot: Map<string, ScheduledOp[]>,
  editable: boolean,
  selection: PlanSelection | null,
  onSelect?: (sel: PlanSelection) => void,
  compact = false,
): ReactNode {
  const ops = opsByPhaseSlot.get(item.id) ?? [];
  const [phaseId, slotId] = item.id.split('__slot__');
  return (
    <PhaseDropSlot
      phaseId={phaseId}
      slotId={slotId}
      ops={ops}
      editable={editable}
      selection={selection}
      onSelect={onSelect}
      compact={compact}
    />
  );
}

export const PorFaseView = memo(function PorFaseView({
  operations,
  editable,
  startDate,
  endDate,
  onDrop,
  onExclude,
  selection,
  onSelect,
  scale = 'day',
}: PorFaseViewProps): ReactNode {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  const slots = buildSlots(scale, startDate, endDate);

  const phases = useMemo(() => {
    const seen = new Map<string, string>();
    for (const op of operations) {
      if (!seen.has(op.phase_id)) seen.set(op.phase_id, op.phase_name ?? op.phase_id);
    }
    return Array.from(seen.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [operations]);

  const lanes: TimelineLane[] = phases.map(([id, label]) => ({
    id,
    label,
    labelNode: (
      <span
        role="button"
        tabIndex={0}
        className="text-left hover:text-[color:var(--accent)] transition-colors cursor-pointer"
        onClick={() => onSelect?.({ kind: 'phase', id })}
        onKeyDown={(e) => e.key === 'Enter' && onSelect?.({ kind: 'phase', id })}
        title={`Filtrar por fase: ${label}`}
      >
        <Clickable kind="fase" id={id}>{label}</Clickable>
      </span>
    ),
  }));

  const opsByPhaseSlot = useMemo(() => {
    const map = new Map<string, ScheduledOp[]>();
    for (const op of operations) {
      const slotIdx = dateToSlotIndex(op.start, startDate, scale);
      const slotId = slotIdx !== null && slotIdx < slots.length
        ? slots[slotIdx]?.id
        : null;
      if (!slotId) continue;
      const key = `${op.phase_id}__slot__${slotId}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(op);
    }
    return map;
  }, [operations, slots, startDate, scale]);

  const items: TimelineItem[] = useMemo(() => {
    const result: TimelineItem[] = [];
    for (const [key, ops] of opsByPhaseSlot.entries()) {
      if (ops.length === 0) continue;
      // Q.146.B — `split('__slot__')` devolve 2 partes; `[a, , c]` lia slotId=undefined
      // → findIndex(-1) → continue → items=[] → grelha vazia. Agora [phaseId, slotId].
      const [phaseId, slotId] = key.split('__slot__');
      const slotIdx = slots.findIndex((s) => s.id === slotId);
      if (slotIdx === -1) continue;
      result.push({
        id: key,
        laneId: phaseId,
        startSlot: slotIdx,
        spanSlots: 1,
      });
    }
    return result;
  }, [opsByPhaseSlot, slots]);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      if (!event.over) return;
      const opId = String(event.active.id);

      // Q.153.C2 — largou na zona de remoção → excluir o barco (order_id).
      if (String(event.over.id) === REMOVE_ZONE_ID) {
        const op = operations.find((o) => o.id === opId);
        if (op?.order_id && onExclude) onExclude(op.order_id);
        return;
      }

      const dropTarget = String(event.over.id);
      const parts = dropTarget.split('__');
      if (parts.length < 2) return;
      const newPhaseId = parts[0];
      const newDate = parts[parts.length - 1];
      const newStartTs = newDate.includes('T') ? newDate : `${newDate}T08:00:00+00:00`;
      onDrop(opId, newPhaseId, newStartTs);
    },
    [onDrop, onExclude, operations],
  );

  if (phases.length === 0) {
    return (
      <EmptyState
        title="Sem fases no plano actual"
        hint="As operações do commit activo não têm fase atribuída."
      />
    );
  }

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      {editable && onExclude && <RemoveZone />}
      <Timeline
        startDate={startDate}
        endDate={endDate}
        scale={scale}
        lanes={lanes}
        items={items}
        slotWidth={72}
        laneHeight={56}
        renderItem={(item) =>
          renderOpItem(item, opsByPhaseSlot, editable, selection ?? null, onSelect, scale !== 'day')
        }
      />
    </DndContext>
  );
});
