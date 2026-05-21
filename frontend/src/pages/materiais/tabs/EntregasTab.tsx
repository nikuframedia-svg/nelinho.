// MateriaisPage · EntregasTab (Q.60.V). ZERO MOCKS — endpoints reais.
import { useMemo, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Truck, AlertTriangle } from 'lucide-react';
import { Segmented } from '../../../components/dark/Segmented';
import { KPIBig } from '../../../components/dark/KPIBig';
import { EmptyState } from '../../../components/dark/EmptyState';
import { SkeletonLoader } from '../../../components/ui/Skeleton';
import { materiaisApi, type PurchaseOrder } from '../../../components/materiais/materiaisApi';
import { primaryBtn } from '../materiaisShared';

export type EntregasFiltro = 'todas' | 'abertas' | 'atrasadas';

export const ENTREGAS_GRID = '1.5fr 1.7fr 0.9fr 1fr 1fr 0.9fr';

export function EntregasTab(): ReactNode {
  const [filtro, setFiltro] = useState<EntregasFiltro>('abertas');

  const poQuery = useQuery({
    queryKey: ['materiais', 'purchase-orders'],
    queryFn: () => materiaisApi.listPurchaseOrders({ limit: 500 }),
    retry: 0,
  });

  const envelope = poQuery.data;
  const all = useMemo(() => envelope?.items ?? [], [envelope]);

  const filtered = useMemo(() => {
    if (filtro === 'abertas') {
      return all.filter(
        (p) => p.status === 'OPEN' || p.status === 'PARTIAL',
      );
    }
    if (filtro === 'atrasadas') return all.filter((p) => p.is_overdue);
    return all;
  }, [all, filtro]);

  if (poQuery.isLoading) {
    return <SkeletonLoader count={5} />;
  }
  if (poQuery.isError) {
    return (
      <EmptyState
        title="Não foi possível carregar as entregas"
        hint="O endpoint /v1/supply/purchase-orders falhou. Verifica se o backend está a correr."
        icon={<Truck size={28} />}
        action={
          <button type="button" onClick={() => poQuery.refetch()} style={primaryBtn}>
            Tentar novamente
          </button>
        }
      />
    );
  }
  // Mirror nunca sincronizado → empty state honesto (ZERO MOCKS).
  if (envelope && !envelope.data_available) {
    return (
      <EmptyState
        title="Tracking de entregas ainda não sincronizado"
        hint={
          envelope.unavailable_reason ??
          'O mirror supply.purchase_orders nunca foi sincronizado do ERP NELO ' +
            '(MOVIMENTO tipo 9 — pedidos a fornecedor). Corre o ETL purchase_orders ' +
            'para popular esta tab.'
        }
        icon={<Truck size={28} />}
      />
    );
  }
  if (all.length === 0) {
    return (
      <EmptyState
        title="Sem encomendas a fornecedor"
        hint="Não há nenhuma encomenda registada para este tenant."
        icon={<Truck size={28} />}
      />
    );
  }

  const summary = envelope?.summary;

  return (
    <div>
      {summary && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 12,
            marginBottom: 18,
          }}
        >
          <KPIBig
            label="Encomendas abertas"
            value={summary.open}
            context="Por receber (OPEN ou PARTIAL)"
            status={summary.open > 0 ? 'blue' : 'gray'}
          />
          <KPIBig
            label="Atrasadas"
            value={summary.overdue}
            context="ETA já passou e ainda não chegaram"
            status={summary.overdue > 0 ? 'red' : 'green'}
            accent={summary.overdue > 0 ? 'red' : undefined}
          />
          <KPIBig
            label="Recebidas"
            value={summary.received}
            context="Receção completa confirmada"
            status="gray"
          />
          <KPIBig
            label="Qtd. por receber"
            value={summary.total_outstanding_qty.toLocaleString('pt-PT', {
              maximumFractionDigits: 0,
            })}
            context="Soma das quantidades em falta"
            status="gray"
          />
        </div>
      )}

      {envelope?.last_synced_at && (
        <div style={{ fontSize: 10.5, color: 'var(--fg-3)', marginBottom: 12 }}>
          Encomendas sincronizadas do ERP NELO ·{' '}
          {new Date(envelope.last_synced_at).toLocaleString('pt-PT')}
        </div>
      )}

      <div style={{ marginBottom: 12 }}>
        <Segmented
          options={[
            { value: 'abertas', label: 'Abertas' },
            { value: 'atrasadas', label: 'Atrasadas' },
            { value: 'todas', label: 'Todas' },
          ]}
          value={filtro}
          onChange={setFiltro}
        />
      </div>

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
            gridTemplateColumns: ENTREGAS_GRID,
            alignItems: 'center',
            gap: 14,
            padding: '12px 16px',
            borderBottom: '1px solid var(--bd-1)',
            background: 'var(--bg-2)',
            fontSize: 10.5,
            color: 'var(--fg-3)',
            textTransform: 'uppercase',
            letterSpacing: 0.4,
            fontWeight: 600,
          }}
        >
          <div>Fornecedor</div>
          <div>Material</div>
          <div style={{ textAlign: 'right' }}>Encomendado</div>
          <div style={{ textAlign: 'right' }}>Recebido</div>
          <div style={{ textAlign: 'right' }}>ETA</div>
          <div style={{ textAlign: 'right' }}>Estado</div>
        </div>
        {filtered.length === 0 ? (
          <div
            style={{
              padding: '24px 16px',
              fontSize: 12,
              color: 'var(--fg-3)',
              textAlign: 'center',
            }}
          >
            {filtro === 'atrasadas'
              ? 'Nenhuma encomenda atrasada.'
              : filtro === 'abertas'
                ? 'Nenhuma encomenda aberta — tudo recebido.'
                : 'Sem encomendas.'}
          </div>
        ) : (
          filtered.map((po) => <PurchaseOrderRow key={po.id} po={po} />)
        )}
      </div>
    </div>
  );
}

export function PurchaseOrderRow({ po }: { po: PurchaseOrder }): ReactNode {
  const statusLabel: Record<string, string> = {
    OPEN: 'Aberta',
    PARTIAL: 'Parcial',
    RECEIVED: 'Recebida',
    CANCELLED: 'Cancelada',
  };
  const statusColour =
    po.status === 'RECEIVED'
      ? 'var(--green)'
      : po.status === 'CANCELLED'
        ? 'var(--fg-3)'
        : po.is_overdue
          ? 'var(--red)'
          : 'var(--yellow)';

  const etaText = po.eta
    ? new Date(po.eta).toLocaleDateString('pt-PT', {
        day: '2-digit',
        month: '2-digit',
        year: '2-digit',
      })
    : '—';
  const etaSub =
    po.days_to_eta === null || po.days_to_eta === undefined
      ? null
      : po.is_overdue
        ? `${Math.abs(po.days_to_eta)}d em atraso`
        : po.days_to_eta === 0
          ? 'hoje'
          : `em ${po.days_to_eta}d`;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: ENTREGAS_GRID,
        alignItems: 'center',
        gap: 14,
        padding: '11px 16px',
        borderBottom: '1px solid var(--bd-1)',
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 12.5, color: 'var(--fg-0)', fontWeight: 500 }}>
          {po.supplier_name}
        </div>
        <div style={{ fontSize: 10.5, color: 'var(--fg-3)', marginTop: 3 }}>
          {po.po_number ?? `mov. ${po.erp_movement_id ?? '—'}`}
        </div>
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 12, color: 'var(--fg-1)' }}>
          {po.product_name ?? po.product_code}
        </div>
        <div style={{ fontSize: 10.5, color: 'var(--fg-3)', marginTop: 3 }}>
          {po.product_code}
        </div>
      </div>
      <div
        className="tabular"
        style={{ fontSize: 12, color: 'var(--fg-1)', textAlign: 'right' }}
      >
        {po.qty_ordered.toLocaleString('pt-PT', { maximumFractionDigits: 1 })}{' '}
        <span style={{ fontSize: 10, color: 'var(--fg-3)' }}>
          {po.unit_of_measure}
        </span>
      </div>
      <div
        className="tabular"
        style={{
          fontSize: 12,
          textAlign: 'right',
          fontWeight: 600,
          color:
            po.qty_outstanding > 0 ? 'var(--orange)' : 'var(--green)',
        }}
      >
        {po.qty_received.toLocaleString('pt-PT', { maximumFractionDigits: 1 })}
        {po.qty_outstanding > 0 && (
          <div style={{ fontSize: 10, color: 'var(--fg-3)', fontWeight: 400 }}>
            faltam{' '}
            {po.qty_outstanding.toLocaleString('pt-PT', {
              maximumFractionDigits: 1,
            })}
          </div>
        )}
      </div>
      <div style={{ textAlign: 'right' }}>
        <div
          className="tabular"
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: po.is_overdue ? 'var(--red)' : 'var(--fg-1)',
          }}
        >
          {etaText}
        </div>
        {etaSub && (
          <div
            style={{
              fontSize: 10,
              color: po.is_overdue ? 'var(--red)' : 'var(--fg-3)',
            }}
          >
            {etaSub}
          </div>
        )}
      </div>
      <div style={{ textAlign: 'right' }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            fontSize: 10.5,
            fontWeight: 600,
            color: statusColour,
          }}
        >
          {po.is_overdue && po.status !== 'RECEIVED' && (
            <AlertTriangle size={11} />
          )}
          {statusLabel[po.status] ?? po.status}
        </span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB · FORNECEDORES
// ═══════════════════════════════════════════════════════════════════════════
