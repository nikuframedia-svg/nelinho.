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
import { Tabs } from '../../dark/Tabs';
import { DarkBadge } from '../../dark/DarkBadge';
import { DarkButton } from '../../dark/DarkButton';
import { EmptyState } from '../../dark/EmptyState';
import { entityKeys } from '../../../lib/api/keys';
import {
  entityApi,
  type RoutingTemplateOut,
  type PhaseInTemplate,
} from '../../../lib/api/entityApi';
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
    return (
      <Sheet open={true} onClose={onClose} title="Erro" width={720}>
        <div style={{ color: 'var(--danger, #ef4444)', fontSize: 14 }}>
          Erro ao carregar dados:{' '}
          {error instanceof Error ? error.message : 'Erro desconhecido'}
        </div>
      </Sheet>
    );
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
        <TabEmProducao
          inProductionCount={data.in_production_count}
          modelName={data.model_name}
        />
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
      toast.success('Sequência guardada.');
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
      {!hasRowIds && (
        <div
          style={{
            padding: '8px 12px',
            background: 'var(--warning-bg, rgba(234,179,8,0.1))',
            border: '1px solid var(--warning, #ca8a04)',
            borderRadius: 8,
            fontSize: 12,
            color: 'var(--warning, #ca8a04)',
          }}
        >
          Reordenação desactivada: IDs de linha em falta (Q.116.A.fix pendente).
        </div>
      )}

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

        {!hasRowId && (
          <div
            style={{
              padding: '8px 12px',
              background: 'var(--warning-bg, rgba(234,179,8,0.1))',
              border: '1px solid var(--warning, #ca8a04)',
              borderRadius: 8,
              fontSize: 12,
              color: 'var(--warning, #ca8a04)',
              marginBottom: 16,
            }}
          >
            Edição desactivada: ID de linha em falta (Q.116.A.fix pendente).
          </div>
        )}

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

// ─── Tab Em produção (Q.116.D) ────────────────────────────────────────────────

interface TabEmProducaoProps {
  inProductionCount: number;
  modelName: string;
}

function TabEmProducao({ inProductionCount, modelName }: TabEmProducaoProps) {
  if (inProductionCount === 0) {
    return (
      <EmptyState
        title="Nenhum barco em produção"
        hint={`Não há barcos do modelo ${modelName} actualmente em produção.`}
        size="sm"
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '12px 16px',
          background: 'var(--bg-2)',
          borderRadius: 8,
        }}
      >
        <DarkBadge variant="info">{inProductionCount}</DarkBadge>
        <span style={{ fontSize: 13 }}>
          barco{inProductionCount !== 1 ? 's' : ''} em produção
        </span>
      </div>

      <div
        style={{
          padding: '14px 16px',
          background: 'var(--bg-2)',
          border: '1px solid var(--bd-1)',
          borderRadius: 8,
          fontSize: 13,
          color: 'var(--fg-2)',
          lineHeight: 1.6,
        }}
      >
        <div style={{ fontWeight: 600, color: 'var(--fg-1)', marginBottom: 8 }}>
          Como acelerar um barco deste modelo
        </div>
        <ol style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <li>
            Abre a vista <strong>Por barco</strong> em{' '}
            <a href="/overall?view=barco" style={{ color: 'var(--accent)' }}>
              /overall
            </a>
          </li>
          <li>Clica na encomenda do barco que queres acelerar</li>
          <li>No tab <strong>Boost</strong> da EncomendaSheet, usa o slider 0–100</li>
        </ol>
        <div style={{ marginTop: 12, fontSize: 12, color: 'var(--fg-3)' }}>
          Q.116.G: lista detalhada de barcos em produção por modelo (pendente).
        </div>
      </div>
    </div>
  );
}
