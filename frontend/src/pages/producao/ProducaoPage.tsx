/**
 * ProducaoPage — porto da Produção do nelo (1).zip pages-1.jsx:ProducaoPage.
 *
 * 3 vistas alternáveis via SegmentedControl (do brief PROMPT_CLAUDE_CODE.md):
 *   • Por fase  — colunas Kanban PhaseColumn (uma por fase) + count real
 *                 de bottlenecks. Drag-drop por enquanto desactivado até
 *                 endpoint /v1/plan/production/boats existir (BE.* deferred).
 *   • Gantt     — usa GanttChart Q.18.UI.A (visualização temporal)
 *   • Tabela    — wrap DragDropPlanner Q.4 existing (já tem drag-drop
 *                 wired ao schedulePreviewApi com ConsequenceBlock real)
 *
 * Capacity bar overview no topo mostra carga por fase via getBottlenecks()
 * — pages-1.jsx:293-307 do zip.
 *
 * ZERO MOCKS: usa factoryApi.getWIP() + getBottlenecks() reais; empty
 * states explícitos onde dados faltarem.
 *
 * Sprint Q.18.ZIP.C.
 */

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Layers,
  Calendar,
  Table as TableIcon,
  Filter,
  RefreshCw,
  Sparkles,
  AlertTriangle,
} from 'lucide-react';
import {
  PageHeader,
  SegmentedControl,
  PhaseColumn,
  Panel,
  GanttChart,
  BoatCard,
  type GanttRow,
} from '../../components/dark';
import { factoryApi, type BottleneckData, type WIPData } from '../../lib/factoryApi';

interface ActiveOrder {
  id: string;
  hull: string | null;
  product_name: string;
  product_type: string;
  phase: string | null;
  status: string;
  created_date: string | null;
  transport_date: string | null;
}

async function fetchActiveOrders(): Promise<ActiveOrder[] | null> {
  try {
    const resp = await fetch(
      'http://127.0.0.1:8001/v1/plan/orders/active?limit=500',
      { headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' } }
    );
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// FASES NELO (canónicas — extraídas do brief PP1_NELO_PLANO_v4.md §3.1)
// ═══════════════════════════════════════════════════════════════════════════════

interface PhaseDef {
  id: string;
  name: string;
  capacity: number;
  curing_hours?: number;
}

const PHASES: PhaseDef[] = [
  { id: 'prep_molde', name: 'Prep. Molde', capacity: 4 },
  { id: 'pintura_gelcoat', name: 'Pintura gelcoat', capacity: 3 },
  { id: 'laminagem', name: 'Laminagem', capacity: 6 },
  { id: 'cura', name: 'Cura', capacity: 8, curing_hours: 15 },
  { id: 'desmolde', name: 'Desmolde', capacity: 4 },
  { id: 'corte', name: 'Corte', capacity: 4 },
  { id: 'colagem_pecas', name: 'Colagem Peças', capacity: 5 },
  { id: 'pintura_acab', name: 'Pintura Acab.', capacity: 3 },
  { id: 'lixagem_agua', name: 'Lixagem água', capacity: 4 },
  { id: 'lixagem_seco', name: 'Lixagem seco', capacity: 4 },
  { id: 'cq_montagem', name: 'CQ Montagem', capacity: 2 },
  { id: 'montagem', name: 'Montagem', capacity: 5 },
  { id: 'cq_final', name: 'CQ Final', capacity: 2 },
  { id: 'embalagem', name: 'Embalagem', capacity: 3 },
];

// ═══════════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

interface PhaseRow {
  phase: PhaseDef;
  count: number;
  orders: ActiveOrder[];
  is_bottleneck: boolean;
  backlog_hours: number;
}

function buildPhaseRows(
  bottlenecks: BottleneckData | undefined | null,
  ordersByPhase: Map<string, ActiveOrder[]>
): PhaseRow[] {
  const byId = new Map<string, { is_bottleneck: boolean; backlog_hours: number }>();
  if (bottlenecks?.bottlenecks) {
    for (const b of bottlenecks.bottlenecks) {
      const matchPhase = PHASES.find(
        (p) =>
          p.name.toLowerCase() === b.fase_nome?.toLowerCase() ||
          p.id === b.fase_id
      );
      const key = matchPhase?.id ?? b.fase_id;
      byId.set(key, {
        is_bottleneck: b.is_critical,
        backlog_hours: b.backlog_hours,
      });
    }
  }
  return PHASES.map((p) => {
    const ordersHere = ordersByPhase.get(p.id) ?? [];
    const fromBottleneck = byId.get(p.id);
    // Preferimos o count REAL de orders (Q.18.ZIP.BE.1).
    // Fallback: aproximação via backlog_hours / 8h.
    const realCount = ordersHere.length;
    const approxCount = fromBottleneck
      ? Math.max(0, Math.round(fromBottleneck.backlog_hours / 8))
      : 0;
    return {
      phase: p,
      count: realCount > 0 ? realCount : approxCount,
      orders: ordersHere,
      is_bottleneck: fromBottleneck?.is_bottleneck ?? false,
      backlog_hours: fromBottleneck?.backlog_hours ?? 0,
    };
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// COPILOT TRIGGER
// ═══════════════════════════════════════════════════════════════════════════════

function askCopilot(query: string) {
  window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
}

// ═══════════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════════

type View = 'phases' | 'gantt' | 'table';

export default function ProducaoPage() {
  const [view, setView] = useState<View>('phases');
  const [refreshKey, setRefreshKey] = useState(0);

  const wipQuery = useQuery({
    queryKey: ['producao', 'wip', refreshKey],
    queryFn: () => factoryApi.getWIP(),
    staleTime: 30_000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const bottlenecksQuery = useQuery({
    queryKey: ['producao', 'bottlenecks', refreshKey],
    queryFn: () => factoryApi.getBottlenecks(),
    staleTime: 30_000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  // Q.18.ZIP.BE.1 — barcos reais por fase (popula PhaseColumn cards)
  const ordersQuery = useQuery({
    queryKey: ['producao', 'orders-active', refreshKey],
    queryFn: () => fetchActiveOrders(),
    staleTime: 30_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  const ordersByPhase: Map<string, ActiveOrder[]> = useMemo(() => {
    const m = new Map<string, ActiveOrder[]>();
    const list = ordersQuery.data ?? [];
    for (const o of list) {
      // Mapear current_phase_name ao id canónico
      const matchPhase = PHASES.find(
        (p) => p.name.toLowerCase() === (o.phase ?? '').toLowerCase()
      );
      const key = matchPhase?.id ?? 'unknown';
      if (!m.has(key)) m.set(key, []);
      m.get(key)!.push(o);
    }
    return m;
  }, [ordersQuery.data]);

  const phaseRows = useMemo(
    () => buildPhaseRows(bottlenecksQuery.data?.data, ordersByPhase),
    [bottlenecksQuery.data, ordersByPhase]
  );

  const totalBoats = (wipQuery.data?.data as WIPData | undefined)?.open_orders ?? 0;
  const totalHours = (wipQuery.data?.data as WIPData | undefined)?.total_hours_pending ?? 0;

  // ─── Gantt rows derivadas (best effort sem endpoint dedicado) ───
  const ganttRows: GanttRow[] = useMemo(() => {
    return phaseRows
      .filter((r) => r.count > 0)
      .slice(0, 12)
      .map((r, idx) => ({
        id: r.phase.id,
        label: r.phase.name,
        sub_label: `${r.count} barcos · ${r.backlog_hours.toFixed(0)}h`,
        bars: [
          {
            idx: 0,
            label: r.phase.name,
            start_hours: idx * 4,
            duration_hours: Math.min(48, Math.max(2, r.backlog_hours / r.count)),
            kind: 'work' as const,
            status: r.is_bottleneck ? 'at_risk' : 'on_time',
            detail: `Backlog ${r.backlog_hours.toFixed(0)}h · capacity ${r.phase.capacity}`,
          },
        ],
      }));
  }, [phaseRows]);

  return (
    <div>
      <PageHeader
        title="Produção"
        subtitle={`MAPA AO VIVO · ${totalBoats || '—'} BARCOS ACTIVOS · ${totalHours.toFixed(0)} h PENDENTES`}
        actions={
          <>
            <SegmentedControl
              size="sm"
              value={view}
              onChange={(v) => setView(v as View)}
              options={[
                { id: 'phases', label: 'Por fase', icon: <Layers size={12} /> },
                { id: 'gantt', label: 'Gantt', icon: <Calendar size={12} /> },
                { id: 'table', label: 'Tabela', icon: <TableIcon size={12} /> },
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
              disabled
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-dark-700 text-text-dark-tertiary border border-white/[0.08] text-xs font-medium opacity-50 cursor-not-allowed"
            >
              <Filter size={13} />
              Filtros
            </button>
            <button
              type="button"
              onClick={() => askCopilot('Como está a produção neste momento? Há gargalos críticos?')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-500 text-white hover:bg-accent-400 text-xs font-medium transition-colors"
            >
              <Sparkles size={13} />
              Pedir ao Copilot
            </button>
          </>
        }
      />

      <div className="px-6 py-4 space-y-4">
        {/* ═══ Capacity bar overview — todas as fases num glance ═══ */}
        <Panel title="Carga por fase" badge={`${PHASES.length} fases`} flush>
          {bottlenecksQuery.isLoading ? (
            <div className="px-4 py-4 text-xs text-text-dark-tertiary">
              A carregar carga…
            </div>
          ) : bottlenecksQuery.isError ? (
            <div className="px-4 py-4 text-xs text-danger">
              Erro a obter bottlenecks. Backend offline?
            </div>
          ) : (
            <div className="px-4 py-3 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
              {phaseRows.map((r) => {
                const ratio = r.phase.capacity > 0 ? r.count / r.phase.capacity : 0;
                const overload = ratio > 1;
                const barColor = overload
                  ? 'bg-danger'
                  : ratio > 0.8
                  ? 'bg-warning'
                  : ratio > 0
                  ? 'bg-success'
                  : 'bg-dark-600';
                return (
                  <div key={r.phase.id} className="flex flex-col gap-1">
                    <div className="flex items-center justify-between gap-1 text-[10px]">
                      <span className="text-text-dark-secondary truncate">
                        {r.phase.name}
                      </span>
                      <span className="text-text-dark-tertiary tabular-nums shrink-0">
                        {r.count}/{r.phase.capacity}
                      </span>
                    </div>
                    <div className="h-1 bg-dark-900 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${barColor} transition-all duration-300`}
                        style={{ width: `${Math.min(100, ratio * 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Panel>

        {/* ═══ Vista activa ═══ */}
        {view === 'phases' && (
          <PhasesView
            phaseRows={phaseRows}
            loading={bottlenecksQuery.isLoading || ordersQuery.isLoading}
            ordersAvailable={!ordersQuery.isError && ordersQuery.data !== null}
          />
        )}
        {view === 'gantt' && (
          <Panel title="Plano semanal" badge={`${ganttRows.length} fases`} flush>
            {ganttRows.length === 0 ? (
              <EmptyView text="Sem operações para mostrar no Gantt." />
            ) : (
              <div className="p-2">
                <GanttChart
                  rows={ganttRows}
                  start_date={new Date()}
                  total_hours={56}
                  px_per_hour={10}
                />
              </div>
            )}
          </Panel>
        )}
        {view === 'table' && <TableView />}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PhasesView — colunas Kanban (1 por fase) com PhaseColumn primitive
// ═══════════════════════════════════════════════════════════════════════════════

function PhasesView({
  phaseRows,
  loading,
  ordersAvailable,
}: {
  phaseRows: PhaseRow[];
  loading: boolean;
  ordersAvailable: boolean;
}) {
  if (loading) {
    return (
      <div className="px-4 py-12 text-center text-text-dark-tertiary text-sm">
        A carregar mapa de fases…
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Aviso só quando endpoint /v1/plan/orders/active não responde
          (degraded). Quando funciona mas devolve []  → mostra colunas
          com EmptyState "Sem barcos activos". */}
      {!ordersAvailable && (
        <div className="mx-2 flex items-start gap-2 px-3 py-2 rounded-md bg-warning/5 border border-warning/20">
          <AlertTriangle size={14} className="shrink-0 mt-0.5 text-warning" />
          <div className="flex-1 text-xs">
            <span className="font-semibold text-warning">Endpoint /v1/plan/orders/active indisponível</span>
            <span className="text-text-dark-secondary">
              {' '}— Cards de barcos por fase ficam vazios. Counts mostrados são aproximação via bottlenecks.
            </span>
            <div className="text-[10px] text-text-dark-tertiary mt-1">
              Para drag-drop funcional → vista <strong>Tabela</strong> (DragDropPlanner Q.4 wired ao schedulePreviewApi).
            </div>
          </div>
        </div>
      )}

      <div className="overflow-x-auto pb-2">
        <div className="flex gap-3 min-w-max">
          {phaseRows.map((r) => (
            <PhaseColumn
              key={r.phase.id}
              phase_id={r.phase.id}
              phase_name={r.phase.name}
              count={r.count}
              capacity={r.phase.capacity}
              current_load={r.count}
              curing_hours={r.phase.curing_hours}
              is_bottleneck={r.is_bottleneck}
            >
              {r.orders.length > 0 ? (
                <div className="space-y-2">
                  {r.orders.slice(0, 8).map((o) => (
                    <BoatCard
                      key={o.id}
                      order_id={parseInt(o.hull ?? '0', 10) || 0}
                      model={o.product_name}
                      model_short={o.product_type || '—'}
                      phase={o.phase ?? r.phase.name}
                      status={r.is_bottleneck ? 'at_risk' : 'on_time'}
                      transport_date={o.transport_date ?? undefined}
                    />
                  ))}
                  {r.orders.length > 8 && (
                    <div className="text-[10px] text-text-dark-tertiary text-center py-1">
                      +{r.orders.length - 8} mais
                    </div>
                  )}
                </div>
              ) : r.count === 0 ? (
                <div className="text-[10px] text-text-dark-tertiary text-center py-4">
                  Sem barcos
                </div>
              ) : (
                <div className="text-[10px] text-text-dark-tertiary text-center py-3">
                  {r.count} barco{r.count !== 1 ? 's' : ''} estimado{r.count !== 1 ? 's' : ''}
                  <div className="mt-1 text-text-dark-secondary">
                    Detalhe → vista <strong>Tabela</strong>
                  </div>
                </div>
              )}
            </PhaseColumn>
          ))}
        </div>
      </div>
    </div>
  );
}

function EmptyView({ text }: { text: string }) {
  return (
    <div className="px-4 py-12 text-center text-text-dark-tertiary text-sm">
      {text}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TableView — embebe DragDropPlanner Q.4 existing (já wired a schedulePreviewApi)
// ═══════════════════════════════════════════════════════════════════════════════

function TableView() {
  // Lazy-import dinâmico para evitar carregar o bundle pesado se o utilizador
  // só usa a vista "Por fase" ou "Gantt".
  const [Planner, setPlanner] = useState<React.ComponentType | null>(null);
  useMemo(() => {
    import('../../components/scheduling/DragDropPlanner')
      .then((mod) => setPlanner(() => mod.DragDropPlanner ?? mod.default))
      .catch(() => setPlanner(null));
    return null;
  }, []);

  if (!Planner) {
    return (
      <Panel title="Planeamento drag-drop" flush>
        <div className="px-4 py-12 text-center text-text-dark-tertiary text-sm">
          A carregar planner…
        </div>
      </Panel>
    );
  }

  return (
    <Panel title="Planeamento drag-drop · Q.4" flush bodyClassName="p-2">
      <Planner />
    </Panel>
  );
}
