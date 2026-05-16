/**
 * DispatchPage — Despacho/Expedição (Sprint Q.2 / DE01-DE08)
 * ===========================================================
 *
 * Vertical slice of the dispatch UI from PP1 NELO Plan v4 §7. Three rails:
 *
 *   ┌──────────────────────┬──────────────────────────┬──────────────────┐
 *   │  Left: batch list    │  Center: batch detail    │  Right:          │
 *   │  + status filter     │  + capacity meter        │  suggestions     │
 *   │  + create button     │  + assigned orders       │  (5 types) with  │
 *   │                      │  + freeze/dispatch       │  [ACEITAR]       │
 *   │                      │                          │  [REJEITAR]      │
 *   │                      │                          │  [PORQUÊ?]       │
 *   └──────────────────────┴──────────────────────────┴──────────────────┘
 *
 * Drag-drop wired with `@dnd-kit/core` (Sprint Q.1 dep). Orders dragged
 * between batches trigger `transportApi.assignOrder` (with auto-detach
 * from the previous batch via the unique constraint on the assignment
 * table).
 *
 * Q.21.D — o `<RejectionDialog>` foi removido: o registo de rejeições de
 * sugestão de transporte ainda não tem endpoint, e o dialog antigo só
 * fazia console.info. As sugestões podem ser aceites (acção real) ou
 * ignoradas; o explainer continua a mostrar "SE REJEITAR".
 */

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  DndContext,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  AlertTriangle,
  ArrowRightCircle,
  CheckCircle2,
  ChevronRight,
  Lock,
  Send,
  Truck,
  Wrench,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import {
  DarkBadge,
  DarkButton,
  DarkCard,
  SuggestionExplainer,
} from '../../components/dark';
import {
  transportApi,
  type TransportBatch,
  type TransportBatchStatus,
  type TransportSuggestion,
} from '../../lib/api';

// Q.21.D — REJECTION_CATEGORIES + RejectionDialog removidos. Recolhiam
// categoria/razão de rejeição de uma sugestão de transporte mas o submit
// só fazia console.info — não há endpoint que persista isto (o backend de
// transporte não tem rota de rejeição de sugestão; o /decide do CPO é para
// commits de schedule, outra coisa). Botão que mente → fora.

const STATUS_LABEL: Record<TransportBatchStatus, string> = {
  OPEN: 'Aberto',
  FROZEN: 'Congelado',
  DISPATCHED: 'Expedido',
};

const STATUS_BADGE: Record<TransportBatchStatus, 'success' | 'warning' | 'neutral'> = {
  OPEN: 'success',
  FROZEN: 'warning',
  DISPATCHED: 'neutral',
};

const SUGGESTION_ICON: Record<TransportSuggestion['type'], typeof Truck> = {
  advance_boat: ArrowRightCircle,
  delay_boat: AlertTriangle,
  swap_between_batches: Wrench,
  complete_truck: Truck,
  regroup_by_client: ChevronRight,
};

// ───────────────────────────────────────────────────────────────────────────
// Page
// ───────────────────────────────────────────────────────────────────────────

export default function DispatchPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<'ALL' | TransportBatchStatus>('ALL');
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);

  // ── Queries ────────────────────────────────────────────────────────────
  const { data: batches, isLoading: batchesLoading } = useQuery({
    queryKey: ['transport', 'batches', statusFilter],
    queryFn: () =>
      transportApi.listBatches(
        statusFilter === 'ALL' ? undefined : { status: statusFilter },
      ),
    staleTime: 30_000,
  });

  const selectedBatch = useMemo(
    () => batches?.find((b) => b.id === selectedBatchId) ?? null,
    [batches, selectedBatchId],
  );

  const { data: suggestions, isLoading: suggestionsLoading } = useQuery({
    queryKey: ['transport', 'suggestions', selectedBatchId],
    queryFn: () =>
      selectedBatchId ? transportApi.suggestions(selectedBatchId) : Promise.resolve([]),
    enabled: Boolean(selectedBatchId),
    staleTime: 60_000,
  });

  // ── Mutations ──────────────────────────────────────────────────────────
  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['transport'] });
  };

  const assignMutation = useMutation({
    mutationFn: ({ batchId, orderId }: { batchId: string; orderId: string }) =>
      transportApi.assignOrder(batchId, orderId),
    onSuccess: invalidateAll,
  });

  const removeMutation = useMutation({
    mutationFn: ({ batchId, orderId }: { batchId: string; orderId: string }) =>
      transportApi.removeOrder(batchId, orderId),
    onSuccess: invalidateAll,
  });

  const freezeMutation = useMutation({
    mutationFn: (batchId: string) => transportApi.freeze(batchId),
    onSuccess: invalidateAll,
  });

  const dispatchMutation = useMutation({
    mutationFn: (batchId: string) => transportApi.dispatch(batchId),
    onSuccess: invalidateAll,
  });

  // ── Drag-drop ──────────────────────────────────────────────────────────
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const onDragEnd = (event: DragEndEvent) => {
    const orderId = String(event.active.id);
    const targetBatchId = event.over?.id ? String(event.over.id) : null;
    if (!targetBatchId) return;
    // Idempotent: assign to target. The unique constraint detaches from prior batch.
    assignMutation.mutate({ batchId: targetBatchId, orderId });
  };

  // ── Suggestion handlers ────────────────────────────────────────────────
  const handleAcceptSuggestion = (s: TransportSuggestion) => {
    if (!selectedBatchId) return;
    if (s.type === 'swap_between_batches' && s.target_batch_id) {
      const targetId = s.target_batch_id;
      s.affected_order_ids?.forEach((orderId) => {
        assignMutation.mutate({ batchId: targetId, orderId });
      });
      return;
    }
    if (s.type === 'delay_boat') {
      s.affected_order_ids?.forEach((orderId) => {
        removeMutation.mutate({ batchId: selectedBatchId, orderId });
      });
      return;
    }
    if (s.type === 'complete_truck') {
      s.affected_order_ids?.forEach((orderId) => {
        assignMutation.mutate({ batchId: selectedBatchId, orderId });
      });
      return;
    }
    // advance_boat / regroup_by_client need the operator to choose the
    // target batch first — we just refresh and surface a hint.
    invalidateAll();
  };

  // ───────────────────────────────────────────────────────────────────────
  // Render
  // ───────────────────────────────────────────────────────────────────────

  return (
    <DarkPageLayout
      title="Despacho / Expedição"
      subtitle="Plan v4 §7 — DE01-DE08 · drag-and-drop entre camiões + sugestões com consequências"
      icon={<Truck size={20} />}
    >
      <DndContext sensors={sensors} onDragEnd={onDragEnd}>
        <div className="grid grid-cols-12 gap-4">
          {/* Left rail — batch list */}
          <aside className="col-span-3">
            <DarkCard className="p-3">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs text-slate-400 mr-2">Filtro</span>
                {(['ALL', 'OPEN', 'FROZEN', 'DISPATCHED'] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => setStatusFilter(s)}
                    className={`text-xs px-2 py-1 rounded ${
                      statusFilter === s
                        ? 'bg-teal-500/30 text-teal-300'
                        : 'bg-slate-700/40 text-slate-400 hover:bg-slate-700'
                    }`}
                  >
                    {s === 'ALL' ? 'Todos' : STATUS_LABEL[s]}
                  </button>
                ))}
              </div>
              {batchesLoading ? (
                <p className="text-sm text-slate-500 p-2">A carregar…</p>
              ) : !batches || batches.length === 0 ? (
                <p className="text-sm text-slate-500 p-2">Sem batches.</p>
              ) : (
                <ul className="space-y-2">
                  {batches.map((b) => (
                    <BatchListItem
                      key={b.id}
                      batch={b}
                      selected={b.id === selectedBatchId}
                      onSelect={() => setSelectedBatchId(b.id)}
                    />
                  ))}
                </ul>
              )}
            </DarkCard>
          </aside>

          {/* Center — batch detail */}
          <section className="col-span-6">
            {selectedBatch == null ? (
              <DarkCard className="p-10 text-center">
                <Truck size={48} className="mx-auto mb-3 text-slate-600" />
                <p className="text-slate-500">Selecciona um batch à esquerda.</p>
              </DarkCard>
            ) : (
              <BatchDetail
                batch={selectedBatch}
                onFreeze={() => freezeMutation.mutate(selectedBatch.id)}
                onDispatch={() => dispatchMutation.mutate(selectedBatch.id)}
                onRemoveOrder={(orderId) =>
                  removeMutation.mutate({ batchId: selectedBatch.id, orderId })
                }
              />
            )}
          </section>

          {/* Right rail — suggestions */}
          <aside className="col-span-3">
            <DarkCard className="p-3">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <AlertTriangle size={14} className="text-amber-400" />
                Sugestões
              </h3>
              {!selectedBatchId ? (
                <p className="text-xs text-slate-500">
                  Selecciona um batch para ver sugestões.
                </p>
              ) : suggestionsLoading ? (
                <p className="text-xs text-slate-500">A calcular…</p>
              ) : !suggestions || suggestions.length === 0 ? (
                <p className="text-xs text-slate-500">Sem sugestões. Tudo OK.</p>
              ) : (
                <ul className="space-y-3">
                  {suggestions.map((s, idx) => (
                    <SuggestionCard
                      key={`${s.type}-${idx}`}
                      suggestion={s}
                      onAccept={() => handleAcceptSuggestion(s)}
                    />
                  ))}
                </ul>
              )}
            </DarkCard>
          </aside>
        </div>
      </DndContext>

    </DarkPageLayout>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Sub-components
// ───────────────────────────────────────────────────────────────────────────

function BatchListItem({
  batch,
  selected,
  onSelect,
}: {
  batch: TransportBatch;
  selected: boolean;
  onSelect: () => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: batch.id });
  const status = batch.status as TransportBatchStatus;
  return (
    <li
      ref={setNodeRef}
      onClick={onSelect}
      className={`p-2 rounded-lg cursor-pointer border transition ${
        selected
          ? 'bg-teal-500/15 border-teal-500/40'
          : isOver
          ? 'bg-emerald-500/15 border-emerald-500/40'
          : 'bg-slate-800/40 border-slate-700/40 hover:bg-slate-700/40'
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium text-white truncate">{batch.code}</span>
        <DarkBadge variant={STATUS_BADGE[status]} size="sm">
          {STATUS_LABEL[status]}
        </DarkBadge>
      </div>
      <div className="text-xs text-slate-400 flex items-center justify-between">
        <span>{batch.transport_date}</span>
        <span>
          {batch.assigned_orders_count ?? 0}/{batch.truck_capacity_units}
        </span>
      </div>
    </li>
  );
}

function BatchDetail({
  batch,
  onFreeze,
  onDispatch,
  onRemoveOrder,
}: {
  batch: TransportBatch;
  onFreeze: () => void;
  onDispatch: () => void;
  onRemoveOrder: (orderId: string) => void;
}) {
  const status = batch.status as TransportBatchStatus;
  const assigned = batch.assigned_orders_count ?? 0;
  const capacity = batch.truck_capacity_units;
  const ratio = Math.max(0, Math.min(1, assigned / Math.max(1, capacity)));
  const overCapacity = assigned > capacity;

  return (
    <DarkCard className="p-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-white">{batch.code}</h2>
          <p className="text-xs text-slate-400">
            Data {batch.transport_date}
            {batch.destination ? ` · ${batch.destination}` : ''}
            {' · prioridade '}
            {batch.priority}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {status === 'OPEN' && (
            <DarkButton variant="secondary" size="sm" icon={<Lock size={14} />} onClick={onFreeze}>
              Congelar
            </DarkButton>
          )}
          {status === 'FROZEN' && (
            <DarkButton variant="primary" size="sm" icon={<Send size={14} />} onClick={onDispatch}>
              Expedir
            </DarkButton>
          )}
        </div>
      </div>

      {/* Capacity meter */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
          <span>Capacidade</span>
          <span className={overCapacity ? 'text-red-400 font-semibold' : 'text-slate-200'}>
            {assigned}/{capacity}
            {overCapacity && ' · acima do camião'}
          </span>
        </div>
        <div className="w-full h-3 bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              overCapacity ? 'bg-red-500' : ratio > 0.85 ? 'bg-amber-500' : 'bg-emerald-500'
            }`}
            style={{ width: `${Math.min(100, ratio * 100)}%` }}
          />
        </div>
      </div>

      {/* Assigned orders area — drop zone */}
      <BatchOrdersList
        batchId={batch.id}
        assignedCount={assigned}
        readOnly={status !== 'OPEN'}
        onRemoveOrder={onRemoveOrder}
      />
    </DarkCard>
  );
}

function BatchOrdersList({
  batchId,
  assignedCount,
  readOnly,
  onRemoveOrder,
}: {
  batchId: string;
  assignedCount: number;
  readOnly: boolean;
  onRemoveOrder: (orderId: string) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: batchId });
  // Sprint Q.9 Onda 3.3 — real fetch of assigned orders. Replaces the
  // previous Q.4-stub placeholder with a proper draggable card per
  // assignment, backed by the new `GET /v1/plan/transport/batches/
  // {id}/orders` endpoint. Empty list still shows the drop hint.
  const { data, isLoading } = useQuery({
    queryKey: ['transport', 'batch', batchId, 'orders'],
    queryFn: () => transportApi.listOrders(batchId),
    staleTime: 30_000,
  });
  const orders = data?.orders ?? [];

  return (
    <div
      ref={setNodeRef}
      className={`min-h-[120px] rounded-lg border-2 border-dashed p-3 transition ${
        isOver
          ? 'bg-emerald-500/10 border-emerald-500/60'
          : 'bg-slate-800/30 border-slate-700/40'
      }`}
    >
      <div className="flex items-center justify-between mb-2 text-xs text-slate-400">
        <span>Ordens atribuídas ({assignedCount})</span>
        {readOnly && <span className="text-amber-400">só leitura</span>}
      </div>

      {isLoading ? (
        <p className="text-xs text-slate-500 text-center py-6">A carregar…</p>
      ) : orders.length === 0 ? (
        <p className="text-xs text-slate-500 text-center py-6">
          Arrasta aqui ordens de outros batches.
        </p>
      ) : (
        <ul className="space-y-1">
          {orders.map((orderId) => (
            <DraggableOrderCard
              key={orderId}
              orderId={orderId}
              batchId={batchId}
              readOnly={readOnly}
              onRemove={onRemoveOrder}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function DraggableOrderCard({
  orderId,
  batchId,
  readOnly,
  onRemove,
}: {
  orderId: string;
  batchId: string;
  readOnly: boolean;
  onRemove: (orderId: string) => void;
}) {
  // Sprint Q.9 Onda 3.3 — real draggable card. dnd-kit id is the
  // order_id so the parent DispatchPage's `onDragEnd` can resolve
  // `assignOrder(targetBatchId, draggedOrderId)`. The "X" button is
  // the explicit remove path for batches that don't accept drag.
  const { setNodeRef, listeners, attributes, isDragging } = useDraggable({
    id: orderId,
    disabled: readOnly,
    data: { fromBatchId: batchId },
  });
  return (
    <li
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className={`flex items-center justify-between gap-2 px-2 py-1.5 rounded border bg-slate-900/60 border-slate-700/60 text-xs ${
        isDragging ? 'opacity-50' : ''
      } ${readOnly ? '' : 'cursor-grab active:cursor-grabbing'}`}
    >
      <code className="text-slate-200 truncate" title={orderId}>
        {orderId.slice(0, 8)}…
      </code>
      {!readOnly ? (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove(orderId);
          }}
          className="text-slate-500 hover:text-rose-300"
          title="Remover do batch"
        >
          ×
        </button>
      ) : null}
    </li>
  );
}

function SuggestionCard({
  suggestion,
  onAccept,
}: {
  suggestion: TransportSuggestion;
  onAccept: () => void;
}) {
  // Sprint Q.9 Onda 3.3 — replaces the previous collapsible <details>-
  // style block with the canonical <SuggestionExplainer>: 5 boxes
  // (O QUE / PORQUÊ / SE ACEITAR / SE REJEITAR / ALTERNATIVA) so the
  // operator scans the impact in one glance, never having to expand.
  // Plan v4 §7.3 / §8 — "explica sempre".
  const [expanded, setExpanded] = useState(false);
  const Icon = SUGGESTION_ICON[suggestion.type] ?? AlertTriangle;
  return (
    <li className="p-3 rounded-lg bg-slate-800/40 border border-slate-700/40">
      <div className="flex items-start gap-2 mb-3">
        <Icon size={16} className="text-amber-400 mt-0.5 flex-shrink-0" />
        <div className="flex-1">
          <p className="text-sm text-white font-medium">{suggestion.what}</p>
          <p className="text-xs text-slate-400 mt-1">
            {suggestion.why?.slice(0, 80)}
            {suggestion.why && suggestion.why.length > 80 ? '…' : ''}
          </p>
        </div>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-xs text-slate-400 hover:text-white shrink-0"
        >
          {expanded ? 'Ocultar' : 'Detalhe'}
        </button>
      </div>

      {expanded ? (
        <div className="mb-3">
          <SuggestionExplainer
            what={suggestion.what}
            why={suggestion.why ?? '—'}
            ifAccept={suggestion.if_accept ?? '—'}
            ifReject={suggestion.if_reject ?? '—'}
            alternative={suggestion.alternative}
          />
        </div>
      ) : null}

      {/* Q.21.D — só "Aceitar" (acção real: dispara assign/remove
          mutations). "Rejeitar" abria um dialog cujo submit não persistia
          nada — removido. O explainer já mostra "SE REJEITAR". */}
      <div className="flex items-center gap-1">
        <DarkButton
          variant="primary"
          size="sm"
          icon={<CheckCircle2 size={12} />}
          onClick={onAccept}
        >
          Aceitar
        </DarkButton>
      </div>
    </li>
  );
}

