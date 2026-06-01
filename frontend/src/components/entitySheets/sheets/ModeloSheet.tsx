/**
 * ModeloSheet — sheet contextual de modelo (Q.116.A + Q.116.B + Q.116.D).
 *
 * Tabs: Fases · Encomendas · Em produção · Drill-down
 * Q.116.B: tab Fases com drag-drop reorder + modal posição alternativa
 * Q.116.D: tab Em produção com instrução de boost + contagem
 */

import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
} from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, ArrowLeftRight } from 'lucide-react';
import { Sheet } from '../../dark/Sheet';
import { SheetError } from '../SheetError';
import { Tabs } from '../../dark/Tabs';
import { DarkBadge } from '../../dark/DarkBadge';
import { DarkButton } from '../../dark/DarkButton';
import { EmptyState } from '../../dark/EmptyState';
import {
  DarkTable,
  DarkTableHead,
  DarkTableBody,
  DarkTableRow,
  DarkTableHeader,
  DarkTableCell,
} from '../../dark/DarkTable';
import { entityKeys } from '../../../lib/api/keys';
import {
  entityApi,
  type ModeloSummary,
  type RoutingTemplateOut,
  type PhaseInTemplate,
  type BoatInProduction,
  type BoatBoostUpsert,
} from '../../../lib/api/entityApi';
import { Clickable } from '../Clickable';
import { useToastContext } from '../../ToastProvider';

export interface ModeloSheetProps {
  modelId: string;
  onClose: () => void;
}

const TABS = [
  { id: 'fases', label: 'Fases' },
  { id: 'encomendas', label: 'Encomendas' },
  { id: 'em-producao', label: 'Em produção' },
  { id: 'drill-down', label: 'Drill-down' },
];

export default function ModeloSheet({ modelId, onClose }: ModeloSheetProps) {
  const [tab, setTab] = useState('fases');

  const { data, isLoading, error } = useQuery({
    queryKey: entityKeys.modelo(modelId),
    queryFn: () => entityApi.modelo(modelId),
  });

  if (isLoading) {
    return (
      <Sheet open={true} onClose={onClose} title="A carregar..." width={720}>
        <div style={{ color: 'var(--fg-2)', fontSize: 14 }}>
          A carregar dados do modelo...
        </div>
      </Sheet>
    );
  }

  if (error || !data) {
    return <SheetError error={error} onClose={onClose} kind="modelo" />;
  }

  const subtitle = `${data.product_type ?? '—'} · ${data.active_orders_count} encomendas activas · ${data.in_production_count} em produção`;

  return (
    <Sheet
      open={true}
      onClose={onClose}
      title={data.model_name}
      subtitle={subtitle}
      width={720}
    >
      <div style={{ borderBottom: '1px solid var(--bd-1)', marginBottom: 16 }}>
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
      </div>

      {tab === 'fases' && (
        <TabFases
          routing={data.routing_template}
          modelId={modelId}
        />
      )}

      {tab === 'encomendas' && (
        <div>
          <div
            style={{
              fontSize: 13,
              color: 'var(--fg-2)',
              marginBottom: 12,
            }}
          >
            Encomendas activas: {data.active_orders_count}
          </div>
          <EmptyState
            title="Q.116.C vai adicionar lista"
            hint="A lista de encomendas deste modelo virá no sub-sprint Q.116.C."
            size="sm"
          />
        </div>
      )}

      {tab === 'em-producao' && (
        <TabEmProducao data={data} />
      )}

      {tab === 'drill-down' && (
        <EmptyState
          title="Q.116.E vai adicionar drill-down"
          hint="Drill-down por fase com top operadores virá no Q.116.E."
          size="sm"
        />
      )}
    </Sheet>
  );
}

// ─── Tab Fases (Q.116.B) ─────────────────────────────────────────────────────

interface TabFasesProps {
  routing: RoutingTemplateOut | null;
  modelId: string;
}

function TabFases({ routing, modelId }: TabFasesProps) {
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const phases = routing
    ? [...routing.phases].sort((a, b) => a.seq - b.seq)
    : [];

  // IDs para o sortable — usa row `id` se existir, senão `phase_id` como fallback
  // NOTA: fallback phase_id NÃO é o row UUID que o endpoint espera (Q.116.A.fix pendente)
  const hasRowIds = phases.every((p) => p.id != null);
  const toSortableId = (p: PhaseInTemplate) => p.id ?? p.phase_id;

  const [order, setOrder] = useState<string[]>(() => phases.map(toSortableId));
  const [dirty, setDirty] = useState(false);
  const [flexModal, setFlexModal] = useState<PhaseInTemplate | null>(null);

  // Mantém order em sincronia se routing mudar (ex: após invalidate)
  const stableKey = phases.map(toSortableId).join(',');
  const [prevKey, setPrevKey] = useState(stableKey);
  if (stableKey !== prevKey) {
    setOrder(phases.map(toSortableId));
    setDirty(false);
    setPrevKey(stableKey);
  }

  const sensors = useSensors(useSensor(PointerSensor));

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      if (!over || active.id === over.id) return;
      setOrder((prev) => {
        const oldIdx = prev.indexOf(String(active.id));
        const newIdx = prev.indexOf(String(over.id));
        return arrayMove(prev, oldIdx, newIdx);
      });
      setDirty(true);
    },
    [],
  );

  const updateSeqMutation = useMutation({
    mutationFn: () =>
      entityApi.updateTemplateSequence(routing!.id, { phase_order: order }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: entityKeys.modelo(modelId) });
      // Q.153.C3 — CTA: a nova sequência só entra no plano no próximo replan
      // (o CPO lê os templates em state.py:_load_route_templates_db).
      toast.success('Sequência guardada · Replaneie no /overall para o CPO respeitar a nova ordem.');
      setDirty(false);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Erro desconhecido';
      toast.error(`Erro ao guardar sequência: ${msg}`);
    },
  });

  if (routing === null) {
    return (
      <EmptyState
        title="Sem routing definido"
        hint="Este modelo ainda não tem template de routing atribuído."
        size="sm"
      />
    );
  }

  // Mapa para lookup rápido por sortable ID
  const phaseById = new Map(phases.map((p) => [toSortableId(p), p]));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={order} strategy={verticalListSortingStrategy}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {order.map((sid, idx) => {
              const p = phaseById.get(sid);
              if (!p) return null;
              return (
                <SortableFaseRow
                  key={sid}
                  sortableId={sid}
                  phase={p}
                  seqDisplay={idx + 1}
                  disabled={!hasRowIds}
                  onOpenFlexModal={() => setFlexModal(p)}
                />
              );
            })}
          </div>
        </SortableContext>
      </DndContext>

      <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: 4 }}>
        <DarkButton
          variant="primary"
          size="sm"
          disabled={!dirty || !hasRowIds || updateSeqMutation.isPending}
          onClick={() => updateSeqMutation.mutate()}
        >
          {updateSeqMutation.isPending ? 'A guardar...' : 'Guardar ordem'}
        </DarkButton>
      </div>

      {flexModal && (
        <FlexModal
          phase={flexModal}
          allPhases={phases}
          templateId={routing.id}
          modelId={modelId}
          onClose={() => setFlexModal(null)}
        />
      )}
    </div>
  );
}

// ─── Linha sortable de fase ───────────────────────────────────────────────────

interface SortableFaseRowProps {
  sortableId: string;
  phase: PhaseInTemplate;
  seqDisplay: number;
  disabled: boolean;
  onOpenFlexModal: () => void;
}

function SortableFaseRow({
  sortableId,
  phase,
  seqDisplay,
  disabled,
  onOpenFlexModal,
}: SortableFaseRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: sortableId, disabled });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '8px 12px',
    background: 'var(--bg-2)',
    borderRadius: 8,
    fontSize: 13,
    cursor: disabled ? 'default' : 'grab',
  };

  return (
    <div ref={setNodeRef} style={style}>
      <span
        {...attributes}
        {...listeners}
        style={{
          color: disabled ? 'var(--fg-3)' : 'var(--fg-2)',
          cursor: disabled ? 'not-allowed' : 'grab',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        <GripVertical size={14} />
      </span>

      <span style={{ color: 'var(--fg-3)', minWidth: 28, textAlign: 'right' }}>
        {seqDisplay}
      </span>

      <span style={{ flex: 1 }}>
        {phase.phase_name ?? phase.phase_id}
      </span>

      {phase.duration_p50_h != null && (
        <span style={{ color: 'var(--fg-2)' }}>{phase.duration_p50_h}h</span>
      )}

      {phase.can_skip && (
        <DarkBadge variant="neutral" size="sm">
          Opcional
        </DarkBadge>
      )}

      {phase.is_flexible && (
        <span
          title={
            phase.allowed_predecessors && phase.allowed_predecessors.length > 0
              ? `Após: ${phase.allowed_predecessors.join(', ')}`
              : 'Posição alternativa'
          }
        >
          <DarkBadge variant="info" size="sm">
            Pos. alternativa
          </DarkBadge>
        </span>
      )}

      <button
        onClick={onOpenFlexModal}
        title="Configurar posição alternativa"
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--fg-2)',
          padding: '2px 4px',
          borderRadius: 4,
          display: 'flex',
          alignItems: 'center',
        }}
      >
        <ArrowLeftRight size={13} />
      </button>
    </div>
  );
}

// ─── Modal posição alternativa ────────────────────────────────────────────────

interface FlexModalProps {
  phase: PhaseInTemplate;
  allPhases: PhaseInTemplate[];
  templateId: string;
  modelId: string;
  onClose: () => void;
}

function FlexModal({ phase, allPhases, templateId, modelId, onClose }: FlexModalProps) {
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const [isFlexible, setIsFlexible] = useState(phase.is_flexible ?? false);
  const [selected, setSelected] = useState<Set<string>>(
    new Set(phase.allowed_predecessors ?? []),
  );

  const hasRowId = phase.id != null;

  const setFlexMutation = useMutation({
    mutationFn: () =>
      entityApi.setPhaseFlexible(templateId, phase.id!, {
        is_flexible: isFlexible,
        allowed_predecessors: [...selected],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: entityKeys.modelo(modelId) });
      toast.success('Posição alternativa actualizada.');
      onClose();
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Erro desconhecido';
      toast.error(`Erro ao guardar: ${msg}`);
    },
  });

  const others = allPhases.filter((p) => p.phase_id !== phase.phase_id);

  const toggleSelected = (phaseId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(phaseId)) next.delete(phaseId);
      else next.add(phaseId);
      return next;
    });
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 12,
          padding: 24,
          width: 420,
          maxWidth: '90vw',
        }}
      >
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>
          Posição alternativa: {phase.phase_name ?? phase.phase_id}
        </div>

        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            marginBottom: 16,
            cursor: hasRowId ? 'pointer' : 'not-allowed',
            fontSize: 13,
          }}
        >
          <input
            type="checkbox"
            checked={isFlexible}
            disabled={!hasRowId}
            onChange={(e) => setIsFlexible(e.target.checked)}
            style={{ width: 16, height: 16 }}
          />
          Esta fase pode ocorrer após várias outras
        </label>

        {isFlexible && others.length > 0 && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
              marginBottom: 16,
              maxHeight: 200,
              overflowY: 'auto',
            }}
          >
            <div style={{ fontSize: 12, color: 'var(--fg-2)', marginBottom: 4 }}>
              Predecessores permitidos:
            </div>
            {others.map((p) => (
              <label
                key={p.phase_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: 13,
                  cursor: hasRowId ? 'pointer' : 'not-allowed',
                }}
              >
                <input
                  type="checkbox"
                  checked={selected.has(p.phase_id)}
                  disabled={!hasRowId}
                  onChange={() => toggleSelected(p.phase_id)}
                  style={{ width: 14, height: 14 }}
                />
                {p.phase_name ?? p.phase_id}
              </label>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <DarkButton variant="ghost" size="sm" onClick={onClose}>
            Cancelar
          </DarkButton>
          <DarkButton
            variant="primary"
            size="sm"
            disabled={!hasRowId || setFlexMutation.isPending}
            onClick={() => setFlexMutation.mutate()}
          >
            {setFlexMutation.isPending ? 'A guardar...' : 'Guardar'}
          </DarkButton>
        </div>
      </div>
    </div>
  );
}

// ─── Tab Em produção (Q.116.G) ───────────────────────────────────────────────

interface TabEmProducaoProps {
  data: ModeloSummary;
}

function TabEmProducao({ data }: TabEmProducaoProps) {
  const boats = data.in_production_boats;

  if (boats.length === 0) {
    return (
      <EmptyState
        title="Sem barcos em produção"
        hint={`Não há barcos do modelo ${data.model_name} actualmente em produção.`}
        size="sm"
      />
    );
  }

  return (
    <DarkTable>
      <DarkTableHead>
        <DarkTableRow>
          <DarkTableHeader>#</DarkTableHeader>
          <DarkTableHeader>Fase actual</DarkTableHeader>
          <DarkTableHeader>Cliente</DarkTableHeader>
          <DarkTableHeader>Transporte</DarkTableHeader>
          <DarkTableHeader>Boost</DarkTableHeader>
          <DarkTableHeader></DarkTableHeader>
        </DarkTableRow>
      </DarkTableHead>
      <DarkTableBody>
        {boats.map((b) => (
          <BoatRow key={b.legacy_id} boat={b} modelId={data.model_id} />
        ))}
      </DarkTableBody>
    </DarkTable>
  );
}

interface BoatRowProps {
  boat: BoatInProduction;
  modelId: string;
}

function BoatRow({ boat, modelId }: BoatRowProps) {
  const [showBoostModal, setShowBoostModal] = useState(false);

  return (
    <DarkTableRow>
      <DarkTableCell>
        <Clickable kind="encomenda" id={boat.legacy_id}>
          #{boat.legacy_id}
        </Clickable>
      </DarkTableCell>
      <DarkTableCell>
        <Clickable kind="fase" id={boat.current_phase_name}>
          {boat.current_phase_name}
        </Clickable>
      </DarkTableCell>
      <DarkTableCell>{boat.customer_name ?? '—'}</DarkTableCell>
      <DarkTableCell mono>{boat.transport_date ?? '—'}</DarkTableCell>
      <DarkTableCell>
        <DarkBadge variant={boat.effective_boost > 50 ? 'accent' : 'neutral'}>
          {boat.effective_boost}/200
        </DarkBadge>
      </DarkTableCell>
      <DarkTableCell>
        <DarkButton
          variant="ghost"
          size="sm"
          onClick={() => setShowBoostModal(true)}
        >
          Acelerar
        </DarkButton>
        {showBoostModal && (
          <BoostModal
            boat={boat}
            modelId={modelId}
            onClose={() => setShowBoostModal(false)}
          />
        )}
      </DarkTableCell>
    </DarkTableRow>
  );
}

interface BoostModalProps {
  boat: BoatInProduction;
  modelId: string;
  onClose: () => void;
}

function BoostModal({ boat, modelId, onClose }: BoostModalProps) {
  const toast = useToastContext();
  const queryClient = useQueryClient();
  const [boostValue, setBoostValue] = useState(boat.effective_boost > 100 ? 100 : boat.effective_boost);

  const boostMutation = useMutation({
    mutationFn: (body: BoatBoostUpsert) =>
      entityApi.upsertBoatBoost(String(boat.legacy_id), body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: entityKeys.modelo(modelId) });
      toast.success('Boost de barco aplicado.');
      onClose();
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Erro a aplicar boost.';
      toast.error(msg);
    },
  });

  const pending = boostMutation.isPending;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 12,
          padding: 24,
          width: 360,
          maxWidth: '90vw',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        <div style={{ fontSize: 15, fontWeight: 600 }}>
          Acelerar barco #{boat.legacy_id}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <input
            type="range"
            min={0}
            max={100}
            value={boostValue}
            disabled={pending}
            onChange={(e) => setBoostValue(Number(e.target.value))}
            style={{ flex: 1 }}
          />
          <span style={{ minWidth: 36, textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontSize: 15, fontWeight: 600 }}>
            {boostValue}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <DarkButton variant="ghost" size="sm" onClick={onClose} disabled={pending}>
            Cancelar
          </DarkButton>
          <DarkButton
            variant="primary"
            size="sm"
            disabled={pending}
            loading={pending}
            onClick={() => boostMutation.mutate({ boost: boostValue })}
          >
            Aplicar boost
          </DarkButton>
        </div>
      </div>
    </div>
  );
}
