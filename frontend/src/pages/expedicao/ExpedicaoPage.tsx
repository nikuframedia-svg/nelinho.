/**
 * ExpedicaoPage — Q.18.ZIP.M.3.
 *
 * Substitui o wrap simples por composição:
 *   • SegmentedControl 2 vistas: 3 rails (port do zip) | Lotes (DispatchPage Q.2)
 *   • Vista 3-rails: Hoje / Amanhã / Esta semana com shipment-card
 *     listadas via transportApi.listBatches() agrupadas por data
 *   • Vista Lotes preserva DispatchPage Q.2 (drag-drop + RejectionDialog)
 *
 * Sem retirar funcionalidade Q.2 — apenas adiciona a vista do zip.
 *
 * Sprint Q.18.ZIP.M.3.
 */

import { lazy, Suspense, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Calendar,
  Layers,
  RefreshCw,
  Sparkles,
  Truck,
  Eye,
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';
import {
  PageHeader,
  SegmentedControl,
  Panel,
  EmptyState,
} from '../../components/dark';
import { SkeletonLoader } from '../../components/ui/Skeleton';
import { transportApi, type TransportBatch } from '../../lib/api';

const DispatchPage = lazy(() => import('../dispatch/DispatchPage'));

function askCopilot(query: string) {
  window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
}

// ─── Helpers ──────────────────────────────────────────────────────────────

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}
function isoOffset(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

interface RailGroups {
  hoje: TransportBatch[];
  amanha: TransportBatch[];
  semana: TransportBatch[];
}

function groupBatches(batches: TransportBatch[] | undefined): RailGroups {
  const today = isoToday();
  const tomorrow = isoOffset(1);
  const weekEnd = isoOffset(7);
  const result: RailGroups = { hoje: [], amanha: [], semana: [] };
  if (!batches) return result;
  for (const b of batches) {
    const d = b.transport_date?.slice(0, 10);
    if (!d) continue;
    if (d === today) result.hoje.push(b);
    else if (d === tomorrow) result.amanha.push(b);
    else if (d > tomorrow && d <= weekEnd) result.semana.push(b);
  }
  return result;
}

function statusBadgeColor(status: string): string {
  if (status === 'DISPATCHED') return 'bg-success/15 text-success border-success/40';
  if (status === 'FROZEN') return 'bg-primary-500/15 text-primary-300 border-primary-500/40';
  return 'bg-warning/15 text-warning border-warning/40';
}
function statusLabel(status: string): string {
  if (status === 'DISPATCHED') return 'Despachado';
  if (status === 'FROZEN') return 'Congelado';
  return 'Aberto';
}

// ─── Shipment card (one batch in a rail) ──────────────────────────────────

function ShipmentCard({ batch }: { batch: TransportBatch }) {
  const cap = batch.truck_capacity_units ?? 0;
  const assigned = batch.assigned_orders_count ?? 0;
  const utilization = cap > 0 ? Math.min(1, assigned / cap) : 0;
  const overload = utilization > 1;
  const utilizationColor = overload
    ? 'bg-danger'
    : utilization >= 0.8
    ? 'bg-warning'
    : utilization >= 0.5
    ? 'bg-success'
    : 'bg-primary-500';
  return (
    <div
      className="flex flex-col gap-2 p-3 rounded-md border border-white/[0.06] bg-dark-800/60 hover:bg-dark-700/60 transition-colors cursor-pointer"
      title={`Lote ${batch.code}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Truck size={14} className="shrink-0 text-text-dark-tertiary" />
          <span className="text-sm font-semibold text-text-dark-primary truncate font-mono">
            {batch.code}
          </span>
        </div>
        <span
          className={`inline-flex items-center text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded border ${statusBadgeColor(batch.status)}`}
        >
          {statusLabel(batch.status)}
        </span>
      </div>

      {batch.destination ? (
        <div className="text-xs text-text-dark-secondary truncate">
          → {batch.destination}
        </div>
      ) : null}

      <div className="flex items-center justify-between gap-2 text-[10px] text-text-dark-tertiary tabular-nums">
        <span>{batch.transport_date}</span>
        <span>
          cap. {assigned}/{cap}
        </span>
      </div>

      <div className="h-1 bg-dark-900 rounded-full overflow-hidden">
        <div
          className={`h-full ${utilizationColor} transition-all duration-300`}
          style={{ width: `${Math.min(100, utilization * 100)}%` }}
        />
      </div>

      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          className="inline-flex items-center gap-1 text-[10px] text-text-dark-tertiary hover:text-text-dark-secondary"
          onClick={() => askCopilot(`Porquê é que o lote ${batch.code} foi proposto?`)}
        >
          <Sparkles size={10} />
          Porquê?
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-1 text-[10px] text-text-dark-tertiary hover:text-text-dark-secondary"
        >
          <Eye size={10} />
          Detalhe
        </button>
      </div>
    </div>
  );
}

// ─── Single rail (a column) ───────────────────────────────────────────────

function Rail({
  title,
  count,
  items,
  emptyMessage,
}: {
  title: string;
  count: number;
  items: TransportBatch[];
  emptyMessage: string;
}) {
  return (
    <div className="flex flex-col gap-2 min-w-0">
      <div className="flex items-center gap-2 px-2 py-1">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-text-dark-tertiary">
          {title}
        </div>
        <span className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-white/[0.06] text-[10px] font-bold text-text-dark-secondary tabular-nums">
          {count}
        </span>
      </div>
      <div className="flex flex-col gap-2 min-h-[120px]">
        {items.length === 0 ? (
          <div className="px-3 py-6 text-center text-[11px] text-text-dark-tertiary border border-dashed border-white/[0.06] rounded-md">
            {emptyMessage}
          </div>
        ) : (
          items.map((b) => <ShipmentCard key={b.id} batch={b} />)
        )}
      </div>
    </div>
  );
}

// ─── 3-rails view ─────────────────────────────────────────────────────────

function ThreeRailsView({ refreshKey }: { refreshKey: number }) {
  const batchesQuery = useQuery({
    queryKey: ['expedicao', 'batches-7d', refreshKey],
    queryFn: () =>
      transportApi.listBatches({
        from_date: isoToday(),
        to_date: isoOffset(7),
      }),
    staleTime: 30_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  const groups = useMemo(() => groupBatches(batchesQuery.data), [batchesQuery.data]);
  const total =
    groups.hoje.length + groups.amanha.length + groups.semana.length;

  if (batchesQuery.isLoading) {
    return (
      <Panel title="Lotes próximos 7 dias" badge="…" flush>
        <div className="px-4 py-8 text-center text-xs text-text-dark-tertiary">
          A carregar lotes…
        </div>
      </Panel>
    );
  }
  if (batchesQuery.isError) {
    return (
      <Panel title="Lotes próximos 7 dias" badge="—" flush>
        <EmptyState
          title="Endpoint /v1/plan/transport/batches indisponível"
          hint="Backend pode estar a falhar. Tenta a vista Lotes (DispatchPage Q.2) ou atualiza."
          mascot={false}
          icon={<AlertTriangle size={32} />}
          size="sm"
        />
      </Panel>
    );
  }
  if (total === 0) {
    return (
      <Panel title="Lotes próximos 7 dias" badge="0" flush>
        <EmptyState
          title="Sem lotes de transporte agendados"
          hint="Cria um novo lote ou usa a vista Lotes para gerir."
          mascot
          size="md"
        />
      </Panel>
    );
  }

  return (
    <Panel title="Lotes próximos 7 dias" badge={total} flush>
      <div className="px-3 pb-3 grid grid-cols-1 md:grid-cols-3 gap-4">
        <Rail
          title="Hoje"
          count={groups.hoje.length}
          items={groups.hoje}
          emptyMessage="Sem lotes para hoje"
        />
        <Rail
          title="Amanhã"
          count={groups.amanha.length}
          items={groups.amanha}
          emptyMessage="Sem lotes para amanhã"
        />
        <Rail
          title="Esta semana"
          count={groups.semana.length}
          items={groups.semana}
          emptyMessage="Sem lotes para os próximos dias"
        />
      </div>
    </Panel>
  );
}

// ─── Suggestions panel (top) ──────────────────────────────────────────────

function SuggestionsBanner({ refreshKey }: { refreshKey: number }) {
  // transportApi.suggestions é Q.18.ZIP.M.3 — sub-utilizado.
  // Não está exposto em transportApi por nome; vou tentar o endpoint
  // directamente. Se falhar (404), banner não renderiza.
  const sugQuery = useQuery({
    queryKey: ['expedicao', 'suggestions', refreshKey],
    queryFn: async () => {
      try {
        const resp = await fetch('http://127.0.0.1:8001/v1/plan/transport/suggestions', {
          headers: {
            'X-Tenant-Id': '00000000-0000-0000-0000-000000000001',
          },
        });
        if (!resp.ok) return null;
        return (await resp.json()) as any;
      } catch {
        return null;
      }
    },
    staleTime: 60_000,
    retry: 0,
  });

  if (sugQuery.isLoading || sugQuery.isError || !sugQuery.data) return null;
  const items: any[] = Array.isArray(sugQuery.data)
    ? sugQuery.data
    : sugQuery.data.suggestions ?? sugQuery.data.items ?? [];
  if (items.length === 0) return null;

  const first = items[0];
  return (
    <div className="flex items-start gap-3 p-3 rounded-md border border-primary-500/30 bg-primary-500/5">
      <Sparkles size={18} className="shrink-0 mt-0.5 text-primary-300" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] uppercase tracking-wider text-primary-300 font-semibold">
            Sugestão CPO
          </span>
          {first.type ? (
            <span className="text-[10px] text-text-dark-tertiary">
              · {first.type}
            </span>
          ) : null}
        </div>
        <div className="text-sm font-medium text-text-dark-primary mt-0.5">
          {first.what ?? first.title ?? '(sem título)'}
        </div>
        {first.why ? (
          <div className="text-xs text-text-dark-secondary mt-1">{first.why}</div>
        ) : null}
      </div>
      <button
        type="button"
        className="shrink-0 inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-primary-500/15 text-primary-300 hover:bg-primary-500/25 text-xs font-medium transition-colors"
      >
        Ver todas <ArrowRight size={12} />
      </button>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════════════════════

type View = 'rails' | 'lotes';

export default function ExpedicaoPage() {
  const [view, setView] = useState<View>('rails');
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div>
      <PageHeader
        title="Expedição"
        subtitle="LOTES DE TRANSPORTE · CALENDÁRIO 7 DIAS · DRAG-DROP COM IMPACTO"
        actions={
          <>
            <SegmentedControl
              size="sm"
              value={view}
              onChange={(v) => setView(v as View)}
              options={[
                { id: 'rails', label: '3 rails', icon: <Calendar size={12} /> },
                { id: 'lotes', label: 'Lotes', icon: <Layers size={12} /> },
              ]}
            />
            <button
              type="button"
              onClick={() => setRefreshKey((k) => k + 1)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
            >
              <RefreshCw size={13} />
              Atualizar
            </button>
            <button
              type="button"
              onClick={() => askCopilot('Como otimizar as expedições da próxima semana?')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-500 text-white hover:bg-accent-400 text-xs font-medium transition-colors"
            >
              <Sparkles size={13} />
              Pedir ao Copilot
            </button>
          </>
        }
      />

      <div className="px-6 py-4 space-y-4">
        <SuggestionsBanner refreshKey={refreshKey} />

        {view === 'rails' && <ThreeRailsView refreshKey={refreshKey} />}
        {view === 'lotes' && (
          <Panel
            title="Lotes (drag-drop Q.2)"
            badge={
              <span className="inline-flex items-center gap-1 text-[10px]">
                <CheckCircle2 size={10} /> Q.2 wired
              </span>
            }
            flush
            bodyClassName="p-0"
          >
            <Suspense
              fallback={
                <div className="p-8">
                  <SkeletonLoader count={5} />
                </div>
              }
            >
              <DispatchPage />
            </Suspense>
          </Panel>
        )}
      </div>
    </div>
  );
}
