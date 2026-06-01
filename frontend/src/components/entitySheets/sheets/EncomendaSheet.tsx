/**
 * EncomendaSheet — sheet contextual de encomenda/barco (Q.116.A/C).
 *
 * Tabs: Barcos · Boost · Expedição
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Sheet } from '../../dark/Sheet';
import { SheetError } from '../SheetError';
import { Tabs } from '../../dark/Tabs';
import { DarkBadge } from '../../dark/DarkBadge';
import { DarkButton } from '../../dark/DarkButton';
import { entityKeys } from '../../../lib/api/keys';
import {
  entityApi,
  type EncomendaSummary,
  type OrderBoostUpsert,
  type TransportDateUpsert,
} from '../../../lib/api/entityApi';
import { useToastContext } from '../../ToastProvider';

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
    return <SheetError error={error} onClose={onClose} kind="encomenda" />;
  }

  const subtitle = `${data.product_name} · ${data.customer_name ?? 'sem cliente'} · ${data.status}`;

  // Q.116.G — boost breakdown (backend calcula effective com cap 200 + client_priority)
  const effectiveBoost = data.effective_boost;
  const clientBoost = data.client_boost;
  const orderBoost = data.boost ?? 0;
  const boatBoost = data.boat_boost;
  const isAccelerated = effectiveBoost > 50;

  return (
    <Sheet
      open={true}
      onClose={onClose}
      title={`Encomenda #${data.legacy_id}`}
      subtitle={subtitle}
      width={720}
    >
      {/* Boost breakdown — sempre visível no topo */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 12,
          padding: '8px 10px',
          background: 'var(--bg-2)',
          borderRadius: 6,
        }}
        title={`Cliente: ${clientBoost} + Encomenda: ${orderBoost} + Barco: ${boatBoost} = ${effectiveBoost}`}
      >
        {isAccelerated && (
          <span style={{ fontSize: 16 }}>&#9889;</span>
        )}
        <DarkBadge variant="accent">
          Boost efectivo: {effectiveBoost}/200
        </DarkBadge>
        {isAccelerated && (
          <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>acelerada</span>
        )}
      </div>

      <div style={{ borderBottom: '1px solid var(--bd-1)', marginBottom: 16 }}>
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
      </div>

      {tab === 'barcos' && <TabBarcos data={data} />}

      {tab === 'boost' && <TabBoost data={data} />}

      {tab === 'expedicao' && <TabExpedicao data={data} />}
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

function TabBoost({ data }: { data: EncomendaSummary }) {
  const [boostValue, setBoostValue] = useState(data.boost ?? 0);
  const [boostReason, setBoostReason] = useState(data.boost_reason ?? '');
  const queryClient = useQueryClient();
  const toast = useToastContext();

  const boostMutation = useMutation({
    mutationFn: (body: OrderBoostUpsert) =>
      entityApi.upsertOrderBoost(data.legacy_id, body),
    onSuccess: () => {
      toast.success('Boost aplicado.');
      queryClient.invalidateQueries({ queryKey: entityKeys.encomenda(data.legacy_id) });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Erro a aplicar boost.';
      toast.error(msg);
    },
  });

  const pending = boostMutation.isPending;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ fontSize: 13, color: 'var(--fg-2)' }}>
        Boost actual: <strong style={{ color: 'var(--fg-1)' }}>{data.boost}/100</strong>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <input
            type="range"
            min={0}
            max={100}
            value={boostValue}
            disabled={pending}
            onChange={e => setBoostValue(Number(e.target.value))}
            style={{ flex: 1 }}
          />
          <span
            style={{
              minWidth: 36,
              textAlign: 'right',
              fontVariantNumeric: 'tabular-nums',
              fontSize: 15,
              fontWeight: 600,
            }}
          >
            {boostValue}
          </span>
        </div>

        <textarea
          className="bg-white text-slate-900 placeholder:text-slate-400"
          placeholder="Motivo (opcional)"
          value={boostReason}
          disabled={pending}
          maxLength={2000}
          rows={3}
          onChange={e => setBoostReason(e.target.value)}
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
        onClick={() =>
          boostMutation.mutate({ boost: boostValue, reason: boostReason || null })
        }
      >
        Aplicar boost
      </DarkButton>

      {data.boost_reason && (
        <div
          style={{
            fontSize: 12,
            color: 'var(--fg-2)',
            padding: '8px 10px',
            background: 'var(--bg-2)',
            borderRadius: 6,
          }}
        >
          Motivo guardado: {data.boost_reason}
        </div>
      )}
    </div>
  );
}

function TabExpedicao({ data }: { data: EncomendaSummary }) {
  const effectiveDateStr = data.transport_date_effective
    ? data.transport_date_effective.slice(0, 10)
    : '';
  const [transportDate, setTransportDate] = useState(effectiveDateStr);
  const [transportReason, setTransportReason] = useState('');
  const queryClient = useQueryClient();
  const toast = useToastContext();

  const transportMutation = useMutation({
    mutationFn: (body: TransportDateUpsert) =>
      entityApi.upsertTransportDate(data.legacy_id, body),
    onSuccess: () => {
      toast.success('Data de transporte actualizada.');
      queryClient.invalidateQueries({ queryKey: entityKeys.encomenda(data.legacy_id) });
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Erro a actualizar transporte.';
      toast.error(msg);
    },
  });

  const pending = transportMutation.isPending;

  const handleApply = () => {
    if (!transportDate) {
      toast.warning('Selecciona uma data antes de aplicar.');
      return;
    }
    transportMutation.mutate({
      transport_date: new Date(transportDate + 'T00:00:00Z').toISOString(),
      reason: transportReason || null,
    });
  };

  const handleClear = () => {
    transportMutation.mutate({
      transport_date: null,
      reason: transportReason || null,
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'auto 1fr',
          gap: '6px 12px',
          fontSize: 13,
          padding: '10px 14px',
          background: 'var(--bg-2)',
          borderRadius: 8,
        }}
      >
        <span style={{ color: 'var(--fg-2)' }}>Transporte ERP:</span>
        <span>{data.transport_date ?? '—'}</span>
        <span style={{ color: 'var(--fg-2)' }}>Transporte efectivo:</span>
        <strong>{data.transport_date_effective ?? '—'}</strong>
        {data.transport_date_override && (
          <>
            <span style={{ color: 'var(--fg-2)' }}>Override actual:</span>
            <span>{data.transport_date_override}</span>
          </>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label style={{ fontSize: 12, color: 'var(--fg-2)', fontWeight: 600 }}>
          Nova data de transporte
        </label>
        <input
          type="date"
          className="bg-white text-slate-900 placeholder:text-slate-400"
          value={transportDate}
          disabled={pending}
          onChange={e => setTransportDate(e.target.value)}
          style={{
            borderRadius: 6,
            border: '1px solid var(--bd-1)',
            padding: '7px 10px',
            fontSize: 13,
            width: '100%',
          }}
        />

        <textarea
          className="bg-white text-slate-900 placeholder:text-slate-400"
          placeholder="Motivo da alteração (opcional)"
          value={transportReason}
          disabled={pending}
          maxLength={2000}
          rows={3}
          onChange={e => setTransportReason(e.target.value)}
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

      <div style={{ display: 'flex', gap: 8 }}>
        <DarkButton
          variant="primary"
          size="sm"
          disabled={pending}
          loading={pending}
          onClick={handleApply}
        >
          Aplicar override
        </DarkButton>

        {data.transport_date_override && (
          <DarkButton
            variant="secondary"
            size="sm"
            disabled={pending}
            onClick={handleClear}
          >
            Remover override
          </DarkButton>
        )}
      </div>
    </div>
  );
}
