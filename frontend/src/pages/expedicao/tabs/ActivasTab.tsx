// ExpedicaoPage · ActivasTab (Q.60.S → Q.143.C). ZERO MOCKS — endpoints reais.
import { Flag, DownloadCloud, Loader2 } from 'lucide-react';
import { DarkBadge, DarkCard, EmptyState } from '../../../components/dark';
import { type TransportBatch } from '../../../lib/api';
import { shortDate } from '../expedicaoShared';

function statusBadge(status: string) {
  if (status === 'FROZEN') return <DarkBadge variant="warning" size="sm">congelado</DarkBadge>;
  if (status === 'DISPATCHED') return <DarkBadge variant="success" size="sm">expedido</DarkBadge>;
  return <DarkBadge variant="info" size="sm">aberto</DarkBadge>;
}

function CapacityBar({ used, total }: { used: number; total: number }) {
  const pct = total > 0 ? Math.min(100, Math.round((used / total) * 100)) : 0;
  const tone = pct >= 90 ? 'bg-emerald-400' : pct >= 50 ? 'bg-teal-400' : 'bg-amber-400/80';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded-full bg-white/[0.08] overflow-hidden">
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular-nums text-xs text-text-dark-secondary">{used}/{total}</span>
    </div>
  );
}

export function ActivasTab({
  batches,
  isLoading,
  isError,
  onSync,
  isSyncing,
}: {
  batches: TransportBatch[];
  isLoading: boolean;
  isError: boolean;
  onSync?: () => void;
  isSyncing?: boolean;
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
        title="Sem camiões agendados"
        hint="Sincroniza do ERP para criar os camiões a partir das ordens reais (data de transporte)."
        icon={<Flag size={32} />}
        action={
          onSync ? (
            <button
              type="button"
              onClick={onSync}
              disabled={isSyncing}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-teal-500/15 text-teal-200 hover:bg-teal-500/25 border border-teal-400/25 text-xs font-medium transition-colors disabled:opacity-60"
            >
              {isSyncing ? <Loader2 size={13} className="animate-spin" /> : <DownloadCloud size={13} />}
              {isSyncing ? 'A sincronizar…' : 'Sincronizar do ERP'}
            </button>
          ) : undefined
        }
      />
    );
  }

  const sorted = [...batches].sort(
    (a, b) =>
      new Date(a.transport_date).getTime() - new Date(b.transport_date).getTime(),
  );

  return (
    <DarkCard className="p-0 overflow-hidden">
      <div className="grid grid-cols-[1.4fr_1.2fr_auto_auto_auto] gap-x-4 items-center px-4 py-2.5 border-b border-white/[0.06] bg-white/[0.02] text-[10px] uppercase tracking-wide text-text-dark-tertiary font-semibold">
        <span>Camião</span>
        <span>Destino</span>
        <span>Data</span>
        <span>Capacidade</span>
        <span>Estado</span>
      </div>
      {sorted.map((b) => (
        <div
          key={b.id}
          className="grid grid-cols-[1.4fr_1.2fr_auto_auto_auto] gap-x-4 items-center px-4 py-2.5 border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02] transition-colors"
        >
          <span className="text-sm font-medium text-text-dark-primary truncate">{b.code}</span>
          <span className="text-xs text-text-dark-secondary truncate">{b.destination ?? '—'}</span>
          <span className="tabular-nums text-xs text-text-dark-secondary">{shortDate(b.transport_date)}</span>
          <CapacityBar used={b.assigned_orders_count ?? 0} total={b.truck_capacity_units} />
          <span>{statusBadge(b.status)}</span>
        </div>
      ))}
    </DarkCard>
  );
}
