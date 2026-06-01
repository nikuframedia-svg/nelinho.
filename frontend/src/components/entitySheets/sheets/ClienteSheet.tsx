/**
 * ClienteSheet — sheet contextual de cliente (Q.116.A/D).
 *
 * Tabs: Prioridade · Encomendas · Histórico
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Sheet } from '../../dark/Sheet';
import { SheetError } from '../SheetError';
import { Tabs } from '../../dark/Tabs';
import { DarkBadge } from '../../dark/DarkBadge';
import { DarkButton } from '../../dark/DarkButton';
import { EmptyState } from '../../dark/EmptyState';
import { entityKeys, clientPriorityKeys } from '../../../lib/api/keys';
import { entityApi, type OrderInList } from '../../../lib/api/entityApi';
import { clientPriorityApi } from '../../../lib/api/platformApi';
import { useToastContext } from '../../ToastProvider';

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
    return <SheetError error={error} onClose={onClose} kind="cliente" />;
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
        <TabPrioridade
          customerId={customerId}
          priority={data.priority}
          priorityReason={(data as any).priority_reason as string | null ?? null}
        />
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

function TabPrioridade({
  customerId,
  priority,
  priorityReason,
}: {
  customerId: string;
  priority: number | null;
  priorityReason: string | null;
}) {
  const [sliderValue, setSliderValue] = useState(priority ?? 3);
  const [reason, setReason] = useState('');
  const queryClient = useQueryClient();
  const toast = useToastContext();

  const clientBoost = (6 - sliderValue) * 20;

  const mutation = useMutation({
    mutationFn: () =>
      clientPriorityApi.update(customerId, {
        prioridade: sliderValue,
        razao: reason || undefined,
      }),
    onSuccess: () => {
      toast.success('Prioridade aplicada.');
      queryClient.invalidateQueries({ queryKey: entityKeys.cliente(customerId) });
      queryClient.invalidateQueries({ queryKey: clientPriorityKeys.all });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Erro a aplicar prioridade.';
      toast.error(msg);
    },
  });

  const pending = mutation.isPending;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {priority !== null && (
        <div
          style={{
            fontSize: 12,
            color: 'var(--fg-2)',
            padding: '8px 10px',
            background: 'var(--bg-2)',
            borderRadius: 6,
          }}
        >
          Prioridade actual: <strong style={{ color: 'var(--fg-1)' }}>{priority}</strong>
          {priorityReason && <span> · motivo: &lsquo;{priorityReason}&rsquo;</span>}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <input
            type="range"
            min={1}
            max={5}
            step={1}
            value={sliderValue}
            disabled={pending}
            onChange={e => setSliderValue(Number(e.target.value))}
            style={{ flex: 1 }}
          />
          <DarkBadge variant={priorityVariant(sliderValue)} size="md">
            Prioridade {sliderValue} / 5
          </DarkBadge>
        </div>

        <div style={{ fontSize: 12, color: 'var(--fg-2)' }}>
          Cliente boost:{' '}
          <strong style={{ color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums' }}>
            {clientBoost}
          </strong>
        </div>

        <textarea
          className="bg-white text-slate-900 placeholder:text-slate-400"
          placeholder="Motivo (opcional)"
          value={reason}
          disabled={pending}
          maxLength={2000}
          rows={3}
          onChange={e => setReason(e.target.value)}
          style={{
            width: '100%',
            borderRadius: 6,
            border: '1px solid var(--bd-1)',
            padding: '8px 10px',
            fontSize: 13,
            resize: 'vertical',
          }}
        />
      </div>

      <DarkButton
        variant="primary"
        size="sm"
        disabled={pending}
        loading={pending}
        onClick={() => mutation.mutate()}
      >
        Aplicar prioridade
      </DarkButton>
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
