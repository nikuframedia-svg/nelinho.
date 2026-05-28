/**
 * PorBarcoView — swimlane gantt por barco (Q.115.L).
 *
 * Cada barco (boat_id/order_id) é uma swimlane horizontal.
 * Operações posicionadas pela start_date na timeline.
 * Drag só dentro do mesmo barco (muda start_ts/operator/phase — não troca OF).
 */

import { useMemo, useCallback, type ReactNode } from 'react';
import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
} from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import { GripVertical } from 'lucide-react';
import { EmptyState } from '../../dark';
import { Timeline, buildDaySlots, dateToSlotIndex } from '../Timeline';
import type { TimelineLane, TimelineItem } from '../../dark';
import type { ScheduledOp } from '../types';
import { QualityRiskBadge } from './QualityRiskBadge';

// ─── Tipos internos ────────────────────────────────────────────────────────

interface BoatDropSlotProps {
  boatId: string;
  slotId: string;
  ops: ScheduledOp[];
  editable: boolean;
}

interface PorBarcoViewProps {
  operations: ScheduledOp[];
  editable: boolean;
  startDate: Date;
  endDate: Date;
  onDrop: (opId: string, newPhase: string, newStartTs: string, newOperatorId?: string) => void;
}

// ─── Cor por progresso ─────────────────────────────────────────────────────

function progressBg(status?: string): string {
  if (status === 'COMPLETED' || status === 'completed')
    return 'bg-emerald-500/20 border-emerald-500/40';
  if (status === 'IN_PROGRESS' || status === 'in_progress')
    return 'bg-teal-500/20 border-teal-500/40';
  return 'bg-slate-700/40 border-slate-600/40';
}

// ─── Op card (draggable) ────────────────────────────────────────────────────

function OpCard({ op, editable }: { op: ScheduledOp; editable: boolean }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: op.id,
    disabled: !editable,
  });

  return (
    <div
      ref={setNodeRef}
      style={{ opacity: isDragging ? 0.35 : 1 }}
      {...attributes}
      {...listeners}
      className={`flex items-center gap-1 px-1.5 py-1 rounded border text-[10px] truncate ${progressBg(op.status)} ${editable ? 'cursor-grab active:cursor-grabbing' : 'cursor-default'}`}
      title={`${op.order_id ?? op.id} · ${op.phase_name}${op.operator_name ? ` · ${op.operator_name}` : ''}${op.duration_min ? ` · ${op.duration_min}min` : ''}`}
    >
      {editable && <GripVertical size={9} className="text-slate-500 flex-shrink-0" />}
      <span className="text-slate-200 truncate font-medium">
        {op.phase_name}
      </span>
      {op.operator_name && (
        <span className="text-slate-500 truncate hidden sm:inline">
          · {op.operator_name}
        </span>
      )}
      {op.order_id && op.phase_id && (
        <QualityRiskBadge
          operatorId={op.operator_id ?? ''}
          boatId={op.order_id}
          phaseId={op.phase_id}
        />
      )}
    </div>
  );
}

// ─── Droppable slot por barco ───────────────────────────────────────────────

function BoatDropSlot({ boatId, slotId, ops, editable }: BoatDropSlotProps) {
  const dropId = `boat__${boatId}__${slotId}`;
  const { setNodeRef, isOver } = useDroppable({ id: dropId });

  return (
    <div
      ref={setNodeRef}
      className={`h-full w-full flex flex-col gap-0.5 p-0.5 rounded transition ${
        isOver && editable ? 'bg-teal-500/10 ring-1 ring-teal-500/40' : ''
      }`}
    >
      {ops.map((op) => (
        <OpCard key={op.id} op={op} editable={editable} />
      ))}
    </div>
  );
}

// ─── Render item ────────────────────────────────────────────────────────────

function renderBoatItem(
  item: { id: string; laneId: string; startSlot: number; spanSlots: number },
  opsByBoatSlot: Map<string, ScheduledOp[]>,
  editable: boolean,
): ReactNode {
  const ops = opsByBoatSlot.get(item.id) ?? [];
  const [, boatId, , slotId] = item.id.split('__');
  return (
    <BoatDropSlot
      boatId={boatId}
      slotId={slotId}
      ops={ops}
      editable={editable}
    />
  );
}

// ─── Componente principal ───────────────────────────────────────────────────

export function PorBarcoView({
  operations,
  editable,
  startDate,
  endDate,
  onDrop,
}: PorBarcoViewProps): ReactNode {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  const slots = buildDaySlots(startDate, endDate);

  // Swimlane por barco
  const boats = useMemo(() => {
    const seen = new Map<string, string>();
    for (const op of operations) {
      const boatId = op.order_id ?? op.id;
      if (!seen.has(boatId)) {
        const label = [
          op.order_id ?? op.id,
          op.product_id,
          op.cliente,
        ]
          .filter(Boolean)
          .join(' · ');
        seen.set(boatId, label);
      }
    }
    return Array.from(seen.entries());
  }, [operations]);

  const lanes: TimelineLane[] = boats.map(([id, label]) => ({ id, label }));

  // (boatId, slotId) → lista de ops
  const opsByBoatSlot = useMemo(() => {
    const map = new Map<string, ScheduledOp[]>();
    for (const op of operations) {
      const boatId = op.order_id ?? op.id;
      const slotIdx = dateToSlotIndex(op.start, startDate);
      const slotId =
        slotIdx !== null && slotIdx < slots.length ? slots[slotIdx]?.id : null;
      if (!slotId) continue;
      const key = `boat__${boatId}__slot__${slotId}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(op);
    }
    return map;
  }, [operations, slots, startDate]);

  const items: TimelineItem[] = useMemo(() => {
    const result: TimelineItem[] = [];
    for (const [key, ops] of opsByBoatSlot.entries()) {
      if (ops.length === 0) continue;
      const parts = key.split('__slot__');
      const slotId = parts[1];
      const laneId = parts[0].replace('boat__', '');
      const slotIdx = slots.findIndex((s) => s.id === slotId);
      if (slotIdx === -1) continue;
      result.push({ id: key, laneId, startSlot: slotIdx, spanSlots: 1 });
    }
    return result;
  }, [opsByBoatSlot, slots]);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      if (!event.over || !editable) return;
      const opId = String(event.active.id);
      // dropId: boat__boatId__slotId
      const dropTarget = String(event.over.id);
      const parts = dropTarget.split('__');
      if (parts.length < 3) return;
      const newDate = parts[parts.length - 1]; // slotId = yyyy-MM-dd

      // Encontra a op para saber a fase
      const op = operations.find((o) => o.id === opId);
      if (!op) return;

      // Drag dentro do barco: mantém phase, muda start_ts
      onDrop(opId, op.phase_id, `${newDate}T08:00:00+00:00`);
    },
    [editable, operations, onDrop],
  );

  if (boats.length === 0) {
    return (
      <EmptyState
        title="Sem barcos no plano actual"
        hint="As operações do commit activo não têm order_id atribuído."
      />
    );
  }

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <Timeline
        startDate={startDate}
        endDate={endDate}
        scale="day"
        lanes={lanes}
        items={items}
        slotWidth={72}
        laneHeight={56}
        renderItem={(item) => renderBoatItem(item, opsByBoatSlot, editable)}
      />
    </DndContext>
  );
}
