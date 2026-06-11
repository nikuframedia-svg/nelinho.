/**
 * PorBarcoView — swimlane gantt por barco (Q.115.L).
 *
 * Cada barco (boat_id/order_id) é uma swimlane horizontal.
 * Operações posicionadas pela start_date na timeline.
 * Drag só dentro do mesmo barco (muda start_ts/operator/phase — não troca OF).
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
import { Timeline, buildSlots, dateToSlotIndex, dateToSpanSlots } from '../Timeline';
import type { TimelineScale } from '../Timeline';
import { CountBadge } from './CountBadge';
import type { TimelineLane, TimelineItem } from '../../dark';
import type { ScheduledOp } from '../types';
import type { PlanSelection } from '../selection';
import { opMatchesSelection } from '../selection';
import { OpCard } from './OpCard';
import { DensityCell, DENSITY_THRESHOLD } from './DensityCell';
import { useCellExpand } from '../cellExpand';
import { RemoveZone, REMOVE_ZONE_ID } from './RemoveZone';
import { sortOpsChrono } from './sortOps';

// ─── Tipos internos ────────────────────────────────────────────────────────

interface BoatDropSlotProps {
  boatId: string;
  slotId: string;
  ops: ScheduledOp[];
  editable: boolean;
  selection?: PlanSelection | null;
  onSelect?: (sel: PlanSelection) => void;
  compact?: boolean;
}

interface PorBarcoViewProps {
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

// ─── Droppable slot por barco ───────────────────────────────────────────────

function BoatDropSlot({ boatId, slotId, ops, editable, selection, onSelect, compact = false }: BoatDropSlotProps) {
  const dropId = `boat__${boatId}__${slotId}`;
  const { setNodeRef, isOver } = useDroppable({ id: dropId });
  const expand = useCellExpand();

  // Q.173.AE — CountBadge com onClick drill-down em escalas semana/mês.
  if (compact) {
    return (
      <div ref={setNodeRef} className="h-full w-full flex items-center justify-center p-0.5">
        {ops.length > 0 && <CountBadge ops={ops} onClick={expand ? () => expand(ops) : undefined} />}
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
              primaryLabel={op.phase_name}
              showQuality
            />
          );
        })
      )}
    </div>
  );
}

// ─── Render item ────────────────────────────────────────────────────────────

function renderBoatItem(
  item: { id: string; laneId: string; startSlot: number; spanSlots: number },
  opsByBoatSlot: Map<string, ScheduledOp[]>,
  editable: boolean,
  selection: PlanSelection | null,
  onSelect?: (sel: PlanSelection) => void,
  compact = false,
): ReactNode {
  const ops = opsByBoatSlot.get(item.id) ?? [];
  const [, boatId, , slotId] = item.id.split('__');
  return (
    <BoatDropSlot
      boatId={boatId}
      slotId={slotId}
      ops={ops}
      editable={editable}
      selection={selection}
      onSelect={onSelect}
      compact={compact}
    />
  );
}

// ─── Componente principal ───────────────────────────────────────────────────

export const PorBarcoView = memo(function PorBarcoView({
  operations,
  editable,
  startDate,
  endDate,
  onDrop,
  onExclude,
  selection,
  onSelect,
  scale = 'day',
}: PorBarcoViewProps): ReactNode {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  const slots = buildSlots(scale, startDate, endDate);

  // Swimlane por barco
  const boats = useMemo(() => {
    const seen = new Map<string, { label: string; productId?: string }>();
    for (const op of operations) {
      const boatId = op.order_id ?? op.id;
      if (!seen.has(boatId)) {
        // Q.173.AF — nome real do modelo (o código OF_P_ID cru era ilegível,
        // auditoria 2026-06-11); o código continua disponível no tooltip.
        const label = [
          op.order_id ?? op.id,
          op.product_name ?? op.product_id,
          op.cliente,
        ]
          .filter(Boolean)
          .join(' · ');
        seen.set(boatId, { label, productId: op.product_id });
      }
    }
    return Array.from(seen.entries());
  }, [operations]);

  // Q.133 — clicar no barco abre o detalhe: o MODELO (que tem o editor de
  // fases + posicao alternativa) quando ha product_id; senao a encomenda.
  const lanes: TimelineLane[] = boats.map(([id, { label, productId }]) => ({
    id,
    label,
    labelNode: (
      <Clickable
        kind={productId ? 'modelo' : 'encomenda'}
        id={productId ?? id}
        className="text-left font-mono tabular-nums"
      >
        {label}
      </Clickable>
    ),
  }));

  // (boatId, slotId) → lista de ops
  const opsByBoatSlot = useMemo(() => {
    const map = new Map<string, ScheduledOp[]>();
    for (const op of operations) {
      const boatId = op.order_id ?? op.id;
      const slotIdx = dateToSlotIndex(op.start, startDate, scale);
      const slotId =
        slotIdx !== null && slotIdx < slots.length ? slots[slotIdx]?.id : null;
      if (!slotId) continue;
      const key = `boat__${boatId}__slot__${slotId}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(op);
    }
    // Q.164.D — dentro de cada célula, ordem cronológica (= sequência de fases).
    for (const list of map.values()) sortOpsChrono(list);
    return map;
  }, [operations, slots, startDate, scale]);

  const items: TimelineItem[] = useMemo(() => {
    const result: TimelineItem[] = [];
    for (const [key, ops] of opsByBoatSlot.entries()) {
      if (ops.length === 0) continue;
      const parts = key.split('__slot__');
      const slotId = parts[1];
      const laneId = parts[0].replace('boat__', '');
      const slotIdx = slots.findIndex((s) => s.id === slotId);
      if (slotIdx === -1) continue;
      // Q.173.AE — spanSlots real: máximo das ops da célula.
      const span = Math.max(
        1,
        ...ops.map((op) =>
          dateToSpanSlots(op.start, op.end, op.duration_min, startDate, scale, slots.length),
        ),
      );
      result.push({ id: key, laneId, startSlot: slotIdx, spanSlots: span });
    }
    return result;
  }, [opsByBoatSlot, slots, startDate, scale]);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      if (!event.over || !editable) return;
      const opId = String(event.active.id);
      const op = operations.find((o) => o.id === opId);
      if (!op) return;

      // Q.153.C2 — largou na zona de remoção → excluir o barco (order_id).
      if (String(event.over.id) === REMOVE_ZONE_ID) {
        if (op.order_id && onExclude) onExclude(op.order_id);
        return;
      }

      // dropId: boat__boatId__slotId
      const dropTarget = String(event.over.id);
      const parts = dropTarget.split('__');
      if (parts.length < 3) return;
      const newDate = parts[parts.length - 1]; // slotId = yyyy-MM-dd

      // Drag dentro do barco: mantém phase, muda start_ts
      onDrop(opId, op.phase_id, `${newDate}T08:00:00+00:00`);
    },
    [editable, operations, onDrop, onExclude],
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
      {editable && onExclude && <RemoveZone />}
      <Timeline
        startDate={startDate}
        endDate={endDate}
        scale={scale}
        lanes={lanes}
        items={items}
        slotWidth={72}
        laneHeight={56}
        renderItem={(item) => renderBoatItem(item, opsByBoatSlot, editable, selection ?? null, onSelect, scale !== 'day')}
      />
    </DndContext>
  );
});
