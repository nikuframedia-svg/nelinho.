/**
 * OverallPage — Planeamento (Q.115.K).
 *
 * Página central de replaneamento: timeline −7d/+15d com drag-drop por fase.
 * Drag-drop usa @dnd-kit; drop chama optimistic update local + warning toast
 * (Q.115.C endpoint pendente).
 *
 * Layout: PageHeader (título + toggles) + Timeline scrollable por fase.
 */

import { useMemo, useState, useCallback } from 'react';
import type { ReactNode } from 'react';
import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  useDraggable,
} from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import { useQuery } from '@tanstack/react-query';
import {
  addDays,
  startOfDay,
  format,
} from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { Calendar, GripVertical, AlertTriangle } from 'lucide-react';
import { planKeys } from '../../lib/api/keys';
import { cpoCommitsApi } from '../../lib/api';
import type { CpoCommit } from '../../lib/api';
import { PageHeader, DarkCard, DarkButton, EmptyState } from '../../components/dark';
import { Timeline, buildDaySlots, dateToSlotIndex } from '../../components/overall/Timeline';
import type { TimelineLane, TimelineItem } from '../../components/dark';
import { useToastContext } from '../../components/ToastProvider';

// ─── Constantes ──────────────────────────────────────────────────────────────

const DAYS_PAST = 7;
const DAYS_FUTURE = 15;

// ─── Tipos internos ──────────────────────────────────────────────────────────

interface ScheduledOp {
  id: string;
  phase_id: string;
  phase_name: string;
  order_id?: string;
  product_id?: string;
  operator_name?: string;
  start?: string;
  end?: string;
  status?: string;
}

type ViewMode = 'ver' | 'editar';
type TimelineScale = 'mes' | 'semana' | 'dia';

// ─── Cor por estado ──────────────────────────────────────────────────────────

function statusColor(status?: string): string {
  if (status === 'COMPLETED' || status === 'completed') return 'bg-emerald-500/20 border-emerald-500/40';
  if (status === 'IN_PROGRESS' || status === 'in_progress') return 'bg-teal-500/20 border-teal-500/40';
  return 'bg-slate-700/40 border-slate-600/40';
}

// ─── Op card (draggable) ─────────────────────────────────────────────────────

function OpCardDraggable({ op, editable }: { op: ScheduledOp; editable: boolean }) {
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
      className={`flex items-center gap-1 px-1.5 py-1 rounded border text-[10px] truncate ${statusColor(op.status)} ${editable ? 'cursor-grab active:cursor-grabbing' : 'cursor-default'}`}
      title={`${op.order_id ?? op.id} · ${op.phase_name}`}
    >
      {editable && <GripVertical size={9} className="text-slate-500 flex-shrink-0" />}
      <span className="text-slate-200 truncate font-medium">
        {op.order_id ?? op.id.slice(0, 8)}
      </span>
      {op.operator_name && (
        <span className="text-slate-500 truncate hidden sm:inline">
          · {op.operator_name}
        </span>
      )}
    </div>
  );
}

// ─── Droppable slot: fase + dia ───────────────────────────────────────────────

function PhaseDropSlot({
  phaseId,
  slotId,
  ops,
  editable,
}: {
  phaseId: string;
  slotId: string;
  ops: ScheduledOp[];
  editable: boolean;
}) {
  const dropId = `${phaseId}__${slotId}`;
  const { setNodeRef, isOver } = useDroppable({ id: dropId });

  return (
    <div
      ref={setNodeRef}
      className={`h-full w-full flex flex-col gap-0.5 p-0.5 rounded transition ${
        isOver && editable ? 'bg-teal-500/10 ring-1 ring-teal-500/40' : ''
      }`}
    >
      {ops.map((op) => (
        <OpCardDraggable key={op.id} op={op} editable={editable} />
      ))}
    </div>
  );
}

// ─── Vista por fase: TimelineItem renderer ────────────────────────────────────

function renderOpItem(
  item: TimelineItem,
  opsByPhaseSlot: Map<string, ScheduledOp[]>,
  editable: boolean,
): ReactNode {
  const ops = opsByPhaseSlot.get(item.id) ?? [];
  const [phaseId, slotId] = item.id.split('__slot__');
  return (
    <PhaseDropSlot
      phaseId={phaseId}
      slotId={slotId}
      ops={ops}
      editable={editable}
    />
  );
}

// ─── PorFaseView ─────────────────────────────────────────────────────────────

interface PorFaseViewProps {
  operations: ScheduledOp[];
  editable: boolean;
  startDate: Date;
  endDate: Date;
  onDropPhaseDate: (opId: string, newPhaseId: string, newDate: string) => void;
}

function PorFaseView({
  operations,
  editable,
  startDate,
  endDate,
  onDropPhaseDate,
}: PorFaseViewProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  const slots = buildDaySlots(startDate, endDate);

  // Agrupa fases únicas (preserva ordem de aparecimento)
  const phases = useMemo(() => {
    const seen = new Map<string, string>();
    for (const op of operations) {
      if (!seen.has(op.phase_id)) seen.set(op.phase_id, op.phase_name ?? op.phase_id);
    }
    return Array.from(seen.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [operations]);

  const lanes: TimelineLane[] = phases.map(([id, label]) => ({ id, label }));

  // Para cada (phaseId, slotId): lista de ops que começam nesse dia
  const opsByPhaseSlot = useMemo(() => {
    const map = new Map<string, ScheduledOp[]>();
    for (const op of operations) {
      const slotIdx = dateToSlotIndex(op.start, startDate);
      const slotId = slotIdx !== null && slotIdx < slots.length
        ? slots[slotIdx]?.id
        : null;
      if (!slotId) continue;
      const key = `${op.phase_id}__slot__${slotId}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(op);
    }
    return map;
  }, [operations, slots, startDate]);

  // TimelineItems: um item por (fase, slot) que tem ops
  const items: TimelineItem[] = useMemo(() => {
    const result: TimelineItem[] = [];
    for (const [key, ops] of opsByPhaseSlot.entries()) {
      if (ops.length === 0) continue;
      const [phaseId, , slotId] = key.split('__slot__');
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
      const dropTarget = String(event.over.id); // phaseId__slotId
      const parts = dropTarget.split('__');
      if (parts.length < 2) return;
      const newPhaseId = parts[0];
      const newDate = parts[parts.length - 1]; // slotId é yyyy-MM-dd
      onDropPhaseDate(opId, newPhaseId, newDate);
    },
    [onDropPhaseDate],
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
      <Timeline
        startDate={startDate}
        endDate={endDate}
        scale="day"
        lanes={lanes}
        items={items}
        slotWidth={72}
        laneHeight={56}
        renderItem={(item) => renderOpItem(item, opsByPhaseSlot, editable)}
      />
    </DndContext>
  );
}

// ─── Componente principal ─────────────────────────────────────────────────────

export default function OverallPage(): ReactNode {
  const toast = useToastContext();

  const today = startOfDay(new Date());
  const [windowStart, setWindowStart] = useState(() => addDays(today, -DAYS_PAST));
  const [windowEnd, setWindowEnd] = useState(() => addDays(today, DAYS_FUTURE));
  const [scale, setScale] = useState<TimelineScale>('dia');
  const [mode, setMode] = useState<ViewMode>('ver');

  // Optimistic local overrides: opId → { phase_id, start }
  const [localOverrides, setLocalOverrides] = useState<
    Map<string, { phase_id: string; start: string }>
  >(new Map());

  // ── Query ──────────────────────────────────────────────────────────────────
  const { data: commits, isLoading, isError, refetch } = useQuery({
    queryKey: planKeys.scheduleCurrent(),
    queryFn: () => cpoCommitsApi.list({ limit: 1 }),
    refetchInterval: 30_000,
    refetchOnWindowFocus: false,
  });

  const latestCommit: CpoCommit | undefined = commits?.[0];

  const { data: commitDetail, isLoading: detailLoading } = useQuery({
    queryKey: [...planKeys.scheduleCurrent(), latestCommit?.commit_sha256 ?? 'none'],
    queryFn: () =>
      latestCommit
        ? cpoCommitsApi.get(latestCommit.commit_sha256, { include_operations: true })
        : Promise.resolve(null),
    enabled: Boolean(latestCommit),
    refetchInterval: 30_000,
    refetchOnWindowFocus: false,
  });

  // ── Operações com overrides locais ─────────────────────────────────────────
  const operations: ScheduledOp[] = useMemo(() => {
    if (!commitDetail?.operations) return [];
    return commitDetail.operations.map((op: Record<string, any>) => {
      const override = localOverrides.get(String(op.id ?? op.operation_id ?? ''));
      return {
        id: String(op.id ?? op.operation_id ?? ''),
        phase_id: override?.phase_id ?? String(op.phase_id ?? op.phase_name ?? 'UNKNOWN'),
        phase_name: String(op.phase_name ?? op.phase_id ?? 'UNKNOWN'),
        order_id: op.order_id ? String(op.order_id) : undefined,
        product_id: op.product_id ? String(op.product_id) : undefined,
        operator_name: op.operator_name ? String(op.operator_name) : undefined,
        start: override?.start ?? op.start,
        end: op.end,
        status: op.status,
      } satisfies ScheduledOp;
    });
  }, [commitDetail, localOverrides]);

  // ── Handler drag-drop ──────────────────────────────────────────────────────
  const handleDropPhaseDate = useCallback(
    (opId: string, newPhaseId: string, newDate: string) => {
      // Optimistic local update
      setLocalOverrides((prev) => {
        const next = new Map(prev);
        next.set(opId, { phase_id: newPhaseId, start: newDate });
        return next;
      });

      toast.warning('Endpoint Q.115.C pendente — guardando localmente. Rollback em 3s.');

      // Rollback após 3s (Q.115.C ainda não existe)
      setTimeout(() => {
        setLocalOverrides((prev) => {
          const next = new Map(prev);
          next.delete(opId);
          return next;
        });
      }, 3_000);
    },
    [toast],
  );

  // ── Reset window ───────────────────────────────────────────────────────────
  const resetToToday = useCallback(() => {
    const t = startOfDay(new Date());
    setWindowStart(addDays(t, -DAYS_PAST));
    setWindowEnd(addDays(t, DAYS_FUTURE));
  }, []);

  // ── Janela no título ───────────────────────────────────────────────────────
  const windowLabel = `${format(windowStart, 'd MMM', { locale: ptBR })} – ${format(windowEnd, 'd MMM', { locale: ptBR })}`;

  // ─── Render loading/error/empty ─────────────────────────────────────────────
  const loadingAny = isLoading || detailLoading;

  return (
    <div className="flex flex-col h-full" style={{ minHeight: 0 }}>
      <PageHeader
        title="Planeamento"
        subtitle={windowLabel}
        icon={<Calendar size={18} />}
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            {/* Toggle escala */}
            <div className="flex items-center gap-0.5 rounded-lg border border-slate-700 p-0.5 bg-slate-800">
              {(['dia', 'semana', 'mes'] as TimelineScale[]).map((s) => (
                <button
                  key={s}
                  onClick={() => setScale(s)}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition ${
                    scale === s
                      ? 'bg-teal-600 text-white'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {s === 'dia' ? 'Dia' : s === 'semana' ? 'Semana' : 'Mês'}
                </button>
              ))}
            </div>

            {/* Botão Hoje */}
            <DarkButton variant="secondary" size="sm" onClick={resetToToday}>
              Hoje
            </DarkButton>

            {/* Toggle Ver / Editar */}
            <DarkButton
              size="sm"
              variant={mode === 'editar' ? 'primary' : 'secondary'}
              onClick={() => setMode((m) => (m === 'ver' ? 'editar' : 'ver'))}
            >
              {mode === 'ver' ? 'Editar' : 'A editar'}
            </DarkButton>
          </div>
        }
      />

      <div className="flex-1 overflow-auto p-6 space-y-4">
        {/* Banner drag-drop activo */}
        {mode === 'editar' && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300">
            <AlertTriangle size={13} className="flex-shrink-0" />
            Modo editar activo. Arrastar operação para outra fase/dia actualiza o estado local
            apenas (Q.115.C pendente — sem persistência real).
          </div>
        )}

        {/* Estado de carregamento */}
        {loadingAny && (
          <DarkCard className="p-6 text-center text-slate-400 text-sm">
            A carregar plano actual…
          </DarkCard>
        )}

        {/* Estado de erro */}
        {!loadingAny && isError && (
          <EmptyState
            title="Erro ao carregar plano"
            hint="Não foi possível obter o schedule commit actual."
            action={
              <DarkButton size="sm" onClick={() => refetch()}>
                Tentar novamente
              </DarkButton>
            }
          />
        )}

        {/* Sem commit activo */}
        {!loadingAny && !isError && !latestCommit && (
          <EmptyState
            title="Sem plano activo"
            hint="Use Decisões para aprovar o primeiro plano ou corre POST /v1/plan/cpo/schedule."
          />
        )}

        {/* Sem operações no commit */}
        {!loadingAny && !isError && latestCommit && commitDetail && operations.length === 0 && (
          <EmptyState
            title="Plano sem operações"
            hint="O commit activo não contém operações. Gera um novo plano no CPO."
          />
        )}

        {/* Vista por fase */}
        {!loadingAny && !isError && operations.length > 0 && (
          <DarkCard className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-white">
                Por fase
              </h2>
              <span className="text-xs text-slate-500">
                {operations.length} operações · commit{' '}
                <code className="text-slate-400">
                  {latestCommit?.short_sha}
                </code>
              </span>
            </div>
            <PorFaseView
              operations={operations}
              editable={mode === 'editar'}
              startDate={windowStart}
              endDate={windowEnd}
              onDropPhaseDate={handleDropPhaseDate}
            />
          </DarkCard>
        )}
      </div>
    </div>
  );
}
