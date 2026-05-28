/**
 * ClienteSheet — sheet contextual de cliente (Q.116.A, read-only).
 *
 * Tabs: Prioridade · Encomendas · Histórico
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Sheet } from '../../dark/Sheet';
import { Tabs } from '../../dark/Tabs';
import { DarkBadge } from '../../dark/DarkBadge';
import { EmptyState } from '../../dark/EmptyState';
import { entityKeys } from '../../../lib/api/keys';
import { entityApi, type OrderInList } from '../../../lib/api/entityApi';

export interface ClienteSheetProps {
  customerId: string;
  onClose: () => void;
}

const TABS = [
  { id: 'prioridade', label: 'Prioridade' },
  { id: 'encomendas', label: 'Encomendas' },
  { id: 'historico', label: 'Histórico' },
];

type BadgeVariant = 'danger' | 'warning' | 'info' | 'neutral';

function priorityVariant(priority: number): BadgeVariant {
  if (priority === 1) return 'danger';
  if (priority === 2) return 'warning';
  if (priority === 3) return 'info';
  return 'neutral';
}

export default function ClienteSheet({ customerId, onClose }: ClienteSheetProps) {
  const [tab, setTab] = useState('prioridade');

  const { data, isLoading, error } = useQuery({
    queryKey: entityKeys.cliente(customerId),
    queryFn: () => entityApi.cliente(customerId),
  });

  if (isLoading) {
    return (
      <Sheet open={true} onClose={onClose} title="A carregar..." width={720}>
        <div style={{ color: 'var(--fg-2)', fontSize: 14 }}>
          A carregar dados do cliente...
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

  return (
    <Sheet
      open={true}
      onClose={onClose}
      title={data.customer_name ?? customerId}
      subtitle={`${data.active_orders_count} encomendas activas`}
      width={720}
    >
      <div style={{ borderBottom: '1px solid var(--bd-1)', marginBottom: 16 }}>
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
      </div>

      {tab === 'prioridade' && (
        <TabPrioridade priority={data.priority} />
      )}

      {tab === 'encomendas' && (
        <TabEncomendas orders={data.orders} />
      )}

      {tab === 'historico' && (
        <EmptyState
          title="Q.116.D vai adicionar histórico"
          hint="Lead time histórico e revenue virão no Q.116.D."
          size="sm"
        />
      )}
    </Sheet>
  );
}

function TabPrioridade({ priority }: { priority: number | null }) {
  if (priority === null) {
    return (
      <EmptyState
        title="Sem prioridade definida"
        hint="Define a prioridade no sub-sprint Q.116.D (slider 1-5)."
        size="sm"
      />
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '16px 0',
      }}
    >
      <DarkBadge variant={priorityVariant(priority)} size="md">
        Prioridade: {priority} / 5
      </DarkBadge>
    </div>
  );
}

function statusVariant(status: string): 'success' | 'warning' | 'danger' | 'info' | 'neutral' {
  const s = status.toLowerCase();
  if (s === 'concluida' || s === 'completed' || s === 'done') return 'success';
  if (s === 'em_producao' || s === 'in_progress' || s === 'active') return 'info';
  if (s === 'atrasada' || s === 'delayed' || s === 'overdue') return 'danger';
  if (s === 'pendente' || s === 'pending') return 'warning';
  return 'neutral';
}

function TabEncomendas({ orders }: { orders: OrderInList[] }) {
  if (orders.length === 0) {
    return (
      <EmptyState
        title="Sem encomendas"
        hint="Este cliente ainda não tem encomendas registadas."
        size="sm"
      />
    );
  }

  return (
    <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ borderBottom: '1px solid var(--bd-1)', color: 'var(--fg-2)' }}>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 500 }}>#</th>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 500 }}>Produto</th>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 500 }}>Fase actual</th>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 500 }}>Transporte</th>
          <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 500 }}>Estado</th>
        </tr>
      </thead>
      <tbody>
        {orders.map((o, i) => (
          <tr key={i} style={{ borderBottom: '1px solid var(--bd-1)' }}>
            <td style={{ padding: '8px 8px', color: 'var(--fg-2)', fontVariantNumeric: 'tabular-nums' }}>
              {o.legacy_id}
            </td>
            <td style={{ padding: '8px 8px' }}>{o.product_name}</td>
            <td style={{ padding: '8px 8px', color: 'var(--fg-2)' }}>
              {o.current_phase_name}
            </td>
            <td style={{ padding: '8px 8px', color: 'var(--fg-2)', fontVariantNumeric: 'tabular-nums' }}>
              {o.transport_date ?? '—'}
            </td>
            <td style={{ padding: '8px 8px' }}>
              <DarkBadge variant={statusVariant(o.status)} size="sm">
                {o.status}
              </DarkBadge>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
