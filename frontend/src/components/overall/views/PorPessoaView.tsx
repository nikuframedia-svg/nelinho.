/**
 * PorPessoaView — swimlane gantt por operador (Q.115.L).
 *
 * Cada operador é uma swimlane horizontal.
 * Header: {operador_name · skill_principal} + badge afinidade se score > 0.7.
 * Drag op para outro operador → chama onDrop com new_operator_id.
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
import { useQuery } from '@tanstack/react-query';
import { GripVertical } from 'lucide-react';
import { Clickable } from '../../../components/entitySheets';
import { EmptyState } from '../../dark';
import { Timeline, buildDaySlots, dateToSlotIndex } from '../Timeline';
import type { TimelineLane, TimelineItem } from '../../dark';
import { learningAffinitiesApi } from '../../../lib/api/planApi';
import { learningKeys } from '../../../lib/api/keys';
import type { ScheduledOp } from '../types';
import { QualityRiskBadge } from './QualityRiskBadge';

// ─── Tipos ──────────────────────────────────────────────────────────────────

interface PorPessoaViewProps {
  operations: ScheduledOp[];
  editable: boolean;
  startDate: Date;
  endDate: Date;
  onDrop: (opId: string, newPhase: string, newStartTs: string, newOperatorId?: string) => void;
}

// ─── Cor por estado ─────────────────────────────────────────────────────────

function statusBg(status?: string): string {
  if (status === 'COMPLETED' || status === 'completed')
    return 'bg-emerald-500/20 border-emerald-500/40';
  if (status === 'IN_PROGRESS' || status === 'in_progress')
    return 'bg-teal-500/20 border-teal-500/40';
  return 'bg-slate-700/40 border-slate-600/40';
}

// ─── Op card (draggable) ────────────────────────────────────────────────────

function OpCard({ op, editable }: { op: ScheduledOp; editable: boolean }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `pessoa__${op.id}`,
    disabled: !editable,
  });

  return (
    <div
      ref={setNodeRef}
      style={{ opacity: isDragging ? 0.35 : 1 }}
      {...attributes}
      {...listeners}
      className={`flex items-center gap-1 px-1.5 py-1 rounded border text-[10px] truncate ${statusBg(op.status)} ${editable ? 'cursor-grab active:cursor-grabbing' : 'cursor-default'}`}
      title={`${op.order_id ?? op.id} · ${op.phase_name}`}
    >
      {editable && <GripVertical size={9} className="text-slate-500 flex-shrink-0" />}
      <span className="text-slate-200 truncate font-medium">
        {op.order_id
          ? <Clickable kind="encomenda" id={op.order_id}>{op.order_id}</Clickable>
          : op.id.slice(0, 8)}
      </span>
      <span className="text-slate-400 truncate hidden sm:inline">
        · {op.phase_name}
      </span>
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

// ─── Droppable slot por pessoa ───────────────────────────────────────────────

function PessoaDropSlot({
  operadorId,
  slotId,
  ops,
  editable,
}: {
  operadorId: string;
  slotId: string;
  ops: ScheduledOp[];
  editable: boolean;
}) {
  const dropId = `pessoa__${operadorId}__slot__${slotId}`;
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

function renderPessoaItem(
  item: TimelineItem,
  opsByPessoaSlot: Map<string, ScheduledOp[]>,
  editable: boolean,
): ReactNode {
  const ops = opsByPessoaSlot.get(item.id) ?? [];
  // key: pessoa__operadorId__slot__slotId
  const withoutPrefix = item.id.replace(/^pessoa__/, '');
  const [operadorId, , slotId] = withoutPrefix.split('__slot__');
  return (
    <PessoaDropSlot
      operadorId={operadorId ?? ''}
      slotId={slotId ?? ''}
      ops={ops}
      editable={editable}
    />
  );
}

// ─── Componente principal ───────────────────────────────────────────────────

export function PorPessoaView({
  operations,
  editable,
  startDate,
  endDate,
  onDrop,
}: PorPessoaViewProps): ReactNode {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  // Affinidades top-1 por operador para badge
  const { data: affinities } = useQuery({
    queryKey: learningKeys.affinities(),
    queryFn: () => learningAffinitiesApi.list({ top: 200 }),
    staleTime: 60_000,
    retry: false,
  });

  // Mapa operadorId → top affinity (score > 0.7)
  const topAffinity = useMemo(() => {
    const m = new Map<string, { phase_name: string; score: number }>();
    if (!affinities) return m;
    for (const a of affinities) {
      const cur = m.get(a.operator_id);
      if ((!cur || a.score > cur.score) && a.score > 0.7) {
        m.set(a.operator_id, { phase_name: a.phase_name, score: a.score });
      }
    }
    return m;
  }, [affinities]);

  const slots = buildDaySlots(startDate, endDate);

  // Swimlane por operador
  const operadores = useMemo(() => {
    const seen = new Map<string, string>();
    for (const op of operations) {
      const key = op.operator_id ?? op.operator_name ?? 'sem-operador';
      if (!seen.has(key)) {
        seen.set(key, op.operator_name ?? key);
      }
    }
    return Array.from(seen.entries());
  }, [operations]);

  const lanes: TimelineLane[] = useMemo(
    () =>
      operadores.map(([id, name]) => {
        const aff = topAffinity.get(id);
        const label = aff
          ? `${name} · ★ ${aff.phase_name}`
          : name;
        return { id, label };
      }),
    [operadores, topAffinity],
  );

  // (operadorId, slotId) → lista de ops
  const opsByPessoaSlot = useMemo(() => {
    const map = new Map<string, ScheduledOp[]>();
    for (const op of operations) {
      const operadorId = op.operator_id ?? op.operator_name ?? 'sem-operador';
      const slotIdx = dateToSlotIndex(op.start, startDate);
      const slotId =
        slotIdx !== null && slotIdx < slots.length ? slots[slotIdx]?.id : null;
      if (!slotId) continue;
      const key = `pessoa__${operadorId}__slot__${slotId}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(op);
    }
    return map;
  }, [operations, slots, startDate]);

  const items: TimelineItem[] = useMemo(() => {
    const result: TimelineItem[] = [];
    for (const [key, ops] of opsByPessoaSlot.entries()) {
      if (ops.length === 0) continue;
      const withoutPrefix = key.replace(/^pessoa__/, '');
      const slotSplit = withoutPrefix.split('__slot__');
      const laneId = slotSplit[0];
      const slotId = slotSplit[1];
      if (!laneId || !slotId) continue;
      const slotIdx = slots.findIndex((s) => s.id === slotId);
      if (slotIdx === -1) continue;
      result.push({ id: key, laneId, startSlot: slotIdx, spanSlots: 1 });
    }
    return result;
  }, [opsByPessoaSlot, slots]);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      if (!event.over || !editable) return;
      // active.id: pessoa__opId
      const activeId = String(event.active.id);
      const opId = activeId.replace(/^pessoa__/, '');
      // over.id: pessoa__operadorId__slot__slotId
      const dropTarget = String(event.over.id);
      const withoutPrefix = dropTarget.replace(/^pessoa__/, '');
      const slotSplit = withoutPrefix.split('__slot__');
      const newOperadorId = slotSplit[0];
      const newDate = slotSplit[1]; // yyyy-MM-dd

      const op = operations.find((o) => o.id === opId);
      if (!op || !newDate) return;

      onDrop(opId, op.phase_id, `${newDate}T08:00:00+00:00`, newOperadorId);
    },
    [editable, operations, onDrop],
  );

  if (operadores.length === 0) {
    return (
      <EmptyState
        title="Sem operadores no plano actual"
        hint="As operações do commit activo não têm operador atribuído."
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
        renderItem={(item) => renderPessoaItem(item, opsByPessoaSlot, editable)}
      />
    </DndContext>
  );
}
