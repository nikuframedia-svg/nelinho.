// ExpedicaoPage · ActivasTab (Q.60.S). ZERO MOCKS — endpoints reais.
import { Flag } from 'lucide-react';
import { EmptyState } from '../../../components/dark';
import { type TransportBatch } from '../../../lib/api';
import { shortDate } from '../expedicaoShared';
import { RowTag } from './listaComponents';

export function ActivasTab({
  batches,
  isLoading,
  isError,
}: {
  batches: TransportBatch[];
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading) {
    return (
      <div className="px-4 py-12 text-center text-xs text-text-dark-tertiary">
        A carregar encomendas…
      </div>
    );
  }
  if (isError) {
    return (
      <div className="px-4 py-12 text-center text-xs text-danger">
        Erro a carregar /v1/plan/transport/batches.
      </div>
    );
  }
  if (batches.length === 0) {
    return (
      <EmptyState
        title="Sem encomendas activas"
        hint="Não há camiões agendados de momento."
        icon={<Flag size={32} />}
      />
    );
  }

  const sorted = [...batches].sort(
    (a, b) =>
      new Date(a.transport_date).getTime() - new Date(b.transport_date).getTime(),
  );

  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1.4fr 1fr 120px 120px 120px',
          alignItems: 'center',
          padding: '12px 18px',
          borderBottom: '1px solid var(--bd-1)',
          background: 'var(--bg-2)',
          fontSize: 10.5,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
        }}
      >
        <div>Camião</div>
        <div>Destino</div>
        <div>Data</div>
        <div>Capacidade</div>
        <div>Estado</div>
      </div>
      {sorted.map((b, i) => (
        <div
          key={b.id}
          style={{
            display: 'grid',
            gridTemplateColumns: '1.4fr 1fr 120px 120px 120px',
            alignItems: 'center',
            padding: '12px 18px',
            borderBottom:
              i < sorted.length - 1 ? '1px solid var(--bd-1)' : 'none',
          }}
        >
          <div style={{ fontSize: 12.5, color: 'var(--fg-0)', fontWeight: 500 }}>
            {b.code}
          </div>
          <div style={{ fontSize: 12, color: 'var(--fg-2)' }}>
            {b.destination ?? '—'}
          </div>
          <div className="tabular" style={{ fontSize: 12, color: 'var(--fg-1)' }}>
            {shortDate(b.transport_date)}
          </div>
          <div className="tabular" style={{ fontSize: 12, color: 'var(--fg-1)' }}>
            {b.assigned_orders_count ?? 0}/{b.truck_capacity_units}
          </div>
          <div>
            <RowTag tone={b.status === 'OPEN' ? 'neutral' : 'green'}>
              {b.status === 'OPEN'
                ? 'aberto'
                : b.status === 'FROZEN'
                  ? 'congelado'
                  : 'expedido'}
            </RowTag>
          </div>
        </div>
      ))}
    </div>
  );
}
