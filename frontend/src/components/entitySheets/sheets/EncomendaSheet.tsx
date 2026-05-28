/**
 * EncomendaSheet — sheet contextual de encomenda/barco (Q.116.A, read-only).
 *
 * Tabs: Barcos · Boost · Expedição
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Sheet } from '../../dark/Sheet';
import { Tabs } from '../../dark/Tabs';
import { DarkBadge } from '../../dark/DarkBadge';
import { EmptyState } from '../../dark/EmptyState';
import { entityKeys } from '../../../lib/api/keys';
import { entityApi, type EncomendaSummary } from '../../../lib/api/entityApi';

export interface EncomendaSheetProps {
  workOrderId: string;
  onClose: () => void;
}

const TABS = [
  { id: 'barcos', label: 'Barcos' },
  { id: 'boost', label: 'Boost' },
  { id: 'expedicao', label: 'Expedição' },
];

export default function EncomendaSheet({ workOrderId, onClose }: EncomendaSheetProps) {
  const [tab, setTab] = useState('barcos');

  const { data, isLoading, error } = useQuery({
    queryKey: entityKeys.encomenda(workOrderId),
    queryFn: () => entityApi.encomenda(workOrderId),
  });

  if (isLoading) {
    return (
      <Sheet open={true} onClose={onClose} title="A carregar..." width={720}>
        <div style={{ color: 'var(--fg-2)', fontSize: 14 }}>
          A carregar dados da encomenda...
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

  const subtitle = `${data.product_name} · ${data.customer_name ?? 'sem cliente'} · ${data.status}`;

  return (
    <Sheet
      open={true}
      onClose={onClose}
      title={`Encomenda #${data.legacy_id}`}
      subtitle={subtitle}
      width={720}
    >
      <div style={{ borderBottom: '1px solid var(--bd-1)', marginBottom: 16 }}>
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
      </div>

      {tab === 'barcos' && <TabBarcos data={data} />}

      {tab === 'boost' && (
        <EmptyState
          title="Q.116.C vai adicionar boost"
          hint="Slider de boost 0-100 vem no Q.116.C."
          size="sm"
        />
      )}

      {tab === 'expedicao' && <TabExpedicao transportDate={data.transport_date} />}
    </Sheet>
  );
}

function TabBarcos({ data }: { data: EncomendaSummary }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div
        style={{
          padding: '12px 14px',
          background: 'var(--bg-2)',
          borderRadius: 8,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        <div style={{ fontSize: 15, fontWeight: 600 }}>
          #{data.legacy_id} &nbsp;
          <span style={{ color: 'var(--fg-2)', fontWeight: 400 }}>
            {data.product_name}
          </span>
          {data.product_type && (
            <span style={{ color: 'var(--fg-3)', fontSize: 13 }}>
              {' '}({data.product_type})
            </span>
          )}
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'auto 1fr',
            gap: '4px 12px',
            fontSize: 13,
          }}
        >
          <span style={{ color: 'var(--fg-2)' }}>Criada</span>
          <span>{data.created_date ?? '—'}</span>
          <span style={{ color: 'var(--fg-2)' }}>Transporte</span>
          <span>{data.transport_date ?? '—'}</span>
          <span style={{ color: 'var(--fg-2)' }}>Concluída</span>
          <span>{data.completed_date ?? '—'}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
          <span style={{ fontSize: 13, color: 'var(--fg-2)' }}>Fase actual:</span>
          <DarkBadge variant="info">{data.current_phase_name}</DarkBadge>
        </div>
      </div>

      <div>
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--fg-2)',
            marginBottom: 8,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          Histórico de fases
        </div>

        {data.phase_history.length === 0 ? (
          <div style={{ color: 'var(--fg-2)', fontSize: 13 }}>
            Histórico de fases não disponível (Q.44.Z pending).
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {data.phase_history.map((ph, i) => (
              <div
                key={i}
                style={{
                  fontSize: 13,
                  padding: '6px 10px',
                  background: 'var(--bg-2)',
                  borderRadius: 6,
                  display: 'flex',
                  gap: 8,
                  alignItems: 'center',
                }}
              >
                <span style={{ flex: 1 }}>{ph.phase_name}</span>
                <span style={{ color: 'var(--fg-2)', fontVariantNumeric: 'tabular-nums' }}>
                  {ph.start_at ?? '—'} → {ph.end_at ?? '—'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TabExpedicao({ transportDate }: { transportDate?: string | null }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div
        style={{
          padding: '10px 14px',
          background: 'var(--bg-2)',
          borderRadius: 8,
          fontSize: 13,
          display: 'flex',
          gap: 10,
          alignItems: 'center',
        }}
      >
        <span style={{ color: 'var(--fg-2)' }}>Transporte previsto:</span>
        <span>{transportDate ?? 'sem data'}</span>
      </div>
      <EmptyState
        title="Q.116.C vai permitir alterar"
        hint="Edição da data de transporte vem no Q.116.C."
        size="sm"
      />
    </div>
  );
}
