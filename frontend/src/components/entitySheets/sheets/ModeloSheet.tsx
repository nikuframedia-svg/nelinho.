/**
 * ModeloSheet — sheet contextual de modelo (Q.116.A, read-only).
 *
 * Tabs: Fases · Encomendas · Em produção · Drill-down
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Sheet } from '../../dark/Sheet';
import { Tabs } from '../../dark/Tabs';
import { DarkBadge } from '../../dark/DarkBadge';
import { EmptyState } from '../../dark/EmptyState';
import { entityKeys } from '../../../lib/api/keys';
import { entityApi, type RoutingTemplateOut } from '../../../lib/api/entityApi';

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
        <TabFases routing={data.routing_template} />
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
        <div>
          <div
            style={{
              fontSize: 13,
              color: 'var(--fg-2)',
              marginBottom: 12,
            }}
          >
            Em produção: {data.in_production_count}
          </div>
          <EmptyState
            title="Q.116.C vai adicionar lista"
            hint="A vista de barcos físicos virá no sub-sprint Q.116.C."
            size="sm"
          />
        </div>
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

function TabFases({ routing }: { routing: RoutingTemplateOut | null }) {
  if (routing === null) {
    return (
      <EmptyState
        title="Sem routing definido"
        hint="Este modelo ainda não tem template de routing atribuído."
        size="sm"
      />
    );
  }

  const phases = [...routing.phases].sort((a, b) => a.seq - b.seq);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {phases.map((p) => (
        <div
          key={p.phase_id}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '8px 12px',
            background: 'var(--bg-2)',
            borderRadius: 8,
            fontSize: 13,
          }}
        >
          <span style={{ color: 'var(--fg-3)', minWidth: 28, textAlign: 'right' }}>
            {p.seq}
          </span>
          <span style={{ flex: 1 }}>{p.phase_name ?? p.phase_id}</span>
          {p.duration_p50_h != null && (
            <span style={{ color: 'var(--fg-2)' }}>{p.duration_p50_h}h</span>
          )}
          {p.can_skip && (
            <DarkBadge variant="neutral" size="sm">
              Opcional
            </DarkBadge>
          )}
        </div>
      ))}
    </div>
  );
}
