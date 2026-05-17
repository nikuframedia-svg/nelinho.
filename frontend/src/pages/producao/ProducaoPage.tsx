/**
 * ProducaoPage — onde está cada barco na fábrica.
 *
 * Estrutura:
 *   • Header: "Plano de produção" + contagem real de barcos/fases +
 *     SegmentedControl (Por fase / Gantt / Calendário / CPO). O botão
 *     "Re-optimizar" abre a tab CPO (onde a re-optimização real vive).
 *   • Por fase (PhasesView): colunas = fases reais presentes nas ordens,
 *     cada uma com a contagem de barcos + BoatCardZip.
 *   • Gantt (GanttView): tabela de barcos activos por expedição (barco ·
 *     fase actual · expedição · estado).
 *   • Calendário (CalendarView): placeholder honesto.
 *
 * Wire ao backend: /v1/plan/orders/active — barcos reais. Sem mocks.
 *
 * Q.21.C — removidos PHASES/HULL_CLIENT/GANTT_DAYS hardcoded (dados de
 * demo do zip). Tudo derivado das ordens reais; sem capacidade nem
 * timeline fabricadas.
 */

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Calendar, Sparkles, RefreshCw } from 'lucide-react';
import {
  PageHeader,
  SegmentedControl,
  Panel,
  ZipLegend,
  BoatCardZip,
  EmptyState,
  ZipStatusBadge,
  type ZipBoat,
  type ZipBoatStatus,
} from '../../components/dark';
import { CPODashboard } from '../../components/cpo/CPOPanels';
import { DragDropPlanner } from '../../components/scheduling/DragDropPlanner';
import { getApiBase } from '../../lib/api';

// ─── Fases derivadas das ordens reais ───────────────────────────────────────
//
// Q.21.C — a lista `PHASES` estava hardcoded com 11 fases (a fábrica tem 41)
// e `cap`/`cure` inventados. Não há endpoint que sirva o catálogo de fases
// com capacidade, por isso derivamos as colunas das fases que realmente
// aparecem nas ordens (`order.phase`). Sem capacidade fabricada: mostramos a
// contagem real de barcos por fase, não uma barra load/cap sobre um
// denominador inventado.

interface PhaseColumn {
  name: string; // nome da fase tal como vem do backend
}

/** Fases distintas presentes nas ordens, pela ordem de primeira aparição. */
function derivePhaseColumns(orders: ActiveOrder[]): PhaseColumn[] {
  const seen = new Set<string>();
  const cols: PhaseColumn[] = [];
  for (const o of orders) {
    const name = (o.phase ?? '').trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    cols.push({ name });
  }
  return cols;
}

// ─── Endpoint backend ───────────────────────────────────────────────────────

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

async function fetchActiveOrders(): Promise<ActiveOrder[]> {
  // Q.21.A — base URL via api.ts (concorda com VITE_API_URL).
  const resp = await fetch(
    `${getApiBase()}/v1/plan/orders/active?limit=500`,
    { headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' } },
  );
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

// ─── Map ActiveOrder → ZipBoat ──────────────────────────────────────────────
//
// Q.21.C — sem `HULL_CLIENT` (mapa heurístico hull→cliente que era dados de
// demo). O endpoint /v1/plan/orders/active não devolve cliente, por isso o
// cartão não mostra bandeira — `client_*` ficam undefined e o BoatCardZip
// lida com isso. A fase vem directa da ordem.

function toZipBoat(o: ActiveOrder, status: ZipBoatStatus): ZipBoat {
  const hull = parseInt(o.hull ?? '0', 10) || 0;
  // dx (days to ship) — derive da transport_date
  let dx: number | undefined;
  if (o.transport_date) {
    const t = new Date(o.transport_date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    dx = Math.max(0, Math.round((t.getTime() - today.getTime()) / (1000 * 60 * 60 * 24)));
  }
  return {
    id: hull,
    short: o.product_type || '—',
    model: o.product_name,
    phase_short: o.phase ?? undefined,
    phase_long: o.phase ?? undefined,
    status,
    workers: [],
    dx,
    transport: o.transport_date ?? undefined,
    mold: null,
  };
}

// Status heuristic — derive from dx + phase
function deriveStatus(dx: number | undefined, phaseName: string | null): ZipBoatStatus {
  if (phaseName === 'Cura') return 'curing';
  if (dx === undefined) return 'on_time';
  if (dx <= 0) return 'late';
  if (dx <= 2) return 'at_risk';
  return 'on_time';
}

// ─── Page ───────────────────────────────────────────────────────────────────

type View = 'phases' | 'reorg' | 'gantt' | 'calendar' | 'cpo';

export default function ProducaoPage() {
  const [view, setView] = useState<View>('phases');
  const [refreshKey, setRefreshKey] = useState(0);

  const ordersQuery = useQuery({
    queryKey: ['producao', 'orders-active', refreshKey],
    queryFn: fetchActiveOrders,
    staleTime: 30_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  const orders = ordersQuery.data ?? [];

  // Q.21.C — colunas = fases reais presentes nas ordens (não 11 hardcoded).
  const phaseColumns = useMemo(() => derivePhaseColumns(orders), [orders]);

  // Agrupa barcos pela fase (string) tal como vem do backend.
  const ordersByPhase: Map<string, ZipBoat[]> = useMemo(() => {
    const m = new Map<string, ZipBoat[]>();
    for (const o of orders) {
      const phaseName = (o.phase ?? '').trim();
      if (!phaseName) continue;
      const dx = o.transport_date
        ? Math.max(
            0,
            Math.round(
              (new Date(o.transport_date).getTime() -
                new Date().setHours(0, 0, 0, 0)) /
                (1000 * 60 * 60 * 24),
            ),
          )
        : undefined;
      const status = deriveStatus(dx, o.phase);
      const zb = toZipBoat(o, status);
      if (!m.has(phaseName)) m.set(phaseName, []);
      m.get(phaseName)!.push(zb);
    }
    return m;
  }, [orders]);

  return (
    <div>
      <PageHeader
        title="Plano de produção"
        subtitle={`Onde está cada barco · ${orders.length} barcos activos · ${phaseColumns.length} fases activas`}
        helpId="plano-producao"
        actions={
          <>
            <SegmentedControl
              size="sm"
              value={view}
              onChange={(v) => setView(v as View)}
              options={[
                { id: 'phases', label: 'Por fase' },
                { id: 'reorg', label: 'Reorganizar' },
                { id: 'gantt', label: 'Gantt' },
                { id: 'calendar', label: 'Calendário' },
                { id: 'cpo', label: 'CPO' },
              ]}
            />
            <button
              type="button"
              onClick={() => setRefreshKey((k) => k + 1)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
              title="Actualizar dados"
            >
              <RefreshCw size={13} />
              Atualizar
            </button>
            {/* Q.21.C — a re-optimização real (POST /v1/plan/cpo/schedule)
                vive no CPOReoptimizerCard da tab CPO. Este botão levava só
                a um alert(); agora abre essa tab em vez de mentir. */}
            <button
              type="button"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-white text-xs font-medium transition-colors"
              style={{
                background: 'var(--blue)',
                border: '1px solid var(--blue)',
              }}
              onClick={() => setView('cpo')}
            >
              <Sparkles size={13} />
              Re-optimizar
            </button>
          </>
        }
      />

      <div className="px-6 py-4 page-enter">
        {view === 'phases' && (
          <PhasesView
            phaseColumns={phaseColumns}
            ordersByPhase={ordersByPhase}
            isLoading={ordersQuery.isLoading}
            isError={ordersQuery.isError}
          />
        )}
        {/* Q.31.D — drag-drop que PERSISTE: arrastar uma operação entre
            fases/operadores faz preview e o "Aplicar" grava via apply-move
            (ScheduleCommit). O componente já existia, isolado em
            /plan/scheduling — aqui fica alcançável do menu principal. */}
        {view === 'reorg' && <DragDropPlanner />}
        {view === 'gantt' && <GanttView orders={orders} />}
        {view === 'calendar' && <CalendarView />}
        {view === 'cpo' && <CPODashboard />}
      </div>
    </div>
  );
}

// ─── PhasesView (port literal de page-scheduling.jsx PhasesView) ────────────

function PhasesView({
  phaseColumns,
  ordersByPhase,
  isLoading,
  isError,
}: {
  phaseColumns: PhaseColumn[];
  ordersByPhase: Map<string, ZipBoat[]>;
  isLoading: boolean;
  isError: boolean;
}) {
  // Q.23.E — a fase com mais barcos acumulados é o gargalo. Hooks antes
  // de qualquer early return.
  const bottleneckPhase = useMemo(() => {
    let best: string | null = null;
    let max = 1; // só marca se houver acumulação real (>=2 barcos)
    for (const p of phaseColumns) {
      const n = (ordersByPhase.get(p.name) ?? []).length;
      if (n > max) { max = n; best = p.name; }
    }
    return best;
  }, [phaseColumns, ordersByPhase]);

  if (isLoading) {
    return (
      <div className="px-4 py-12 text-center text-xs text-text-dark-tertiary">
        A carregar barcos…
      </div>
    );
  }
  if (isError) {
    return (
      <div className="px-4 py-12 text-center text-xs text-danger">
        Erro a carregar /v1/plan/orders/active. Backend offline?
      </div>
    );
  }
  if (phaseColumns.length === 0) {
    return (
      <EmptyState
        title="Sem barcos em produção"
        hint="O endpoint /v1/plan/orders/active não devolveu ordens com fase atribuída. Verifica se a sincronização do ERP correu."
        size="md"
      />
    );
  }

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <ZipLegend
          hint="Como ler:"
          trailing="Cartões = barcos. Cada coluna é uma fase activa."
          items={[
            { color: 'green', label: 'No prazo' },
            { color: 'yellow', label: 'Em risco' },
            { color: 'red', label: 'Atrasado' },
            { color: 'gray', label: 'Em cura' },
          ]}
        />
      </div>

      <div
        className="page-enter"
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${phaseColumns.length}, minmax(140px, 1fr))`,
          gap: 12,
          overflowX: 'auto',
          paddingBottom: 8,
        }}
      >
        {phaseColumns.map((p) => {
          const boats = ordersByPhase.get(p.name) ?? [];
          const isBottleneck = p.name === bottleneckPhase;
          return (
            <div
              key={p.name}
              style={{
                background: 'var(--bg-1)',
                border: `1px solid ${isBottleneck ? 'var(--orange-bd)' : 'var(--bd-1)'}`,
                borderRadius: 8,
                minHeight: 380,
                display: 'flex',
                flexDirection: 'column',
                boxShadow: isBottleneck ? '0 0 0 1px var(--orange-bd)' : undefined,
              }}
            >
              {/* Header — Q.21.C: contagem real de barcos. Sem barra
                  load/cap (a capacidade por fase não é exposta por nenhum
                  endpoint e não se inventa um denominador). */}
              <div
                style={{
                  padding: '10px 12px',
                  borderBottom: '1px solid var(--bd-1)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'baseline',
                  }}
                >
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: 'var(--fg-0)',
                    }}
                  >
                    {p.name}
                  </div>
                  <span
                    className="tabular-nums"
                    style={{
                      fontSize: 11,
                      color: isBottleneck ? 'var(--orange)' : 'var(--fg-2)',
                      fontWeight: 600,
                    }}
                  >
                    {boats.length} barco{boats.length !== 1 ? 's' : ''}
                  </span>
                </div>
                {isBottleneck ? (
                  <div
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      color: 'var(--orange)',
                      marginTop: 4,
                    }}
                  >
                    ● Gargalo — mais barcos acumulados
                  </div>
                ) : null}
              </div>

              {/* Body */}
              <div
                style={{
                  padding: 8,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                  flex: 1,
                }}
              >
                {boats.length === 0 ? (
                  <div
                    style={{
                      flex: 1,
                      display: 'grid',
                      placeItems: 'center',
                      fontSize: 11,
                      color: 'var(--fg-3)',
                      border: '1px dashed var(--bd-2)',
                      borderRadius: 6,
                      minHeight: 60,
                    }}
                  >
                    vazio
                  </div>
                ) : (
                  boats.map((b) => <BoatCardZip key={b.id} boat={b} compact />)
                )}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

// ─── GanttView (port literal page-scheduling.jsx GanttView) ─────────────────

// Q.21.C — o GanttView original tinha datas fixas (`GANTT_DAYS`) e barras
// posicionadas por `hull % 4` / `hull % 5` — um Gantt decorativo fabricado.
// O endpoint /v1/plan/orders/active não devolve início/fim de fase por dia,
// por isso mostramos uma tabela só com dados reais (barco · fase actual ·
// expedição · estado), em vez de inventar uma timeline.

// Q.23.E — cor do left-border de estado por linha (padrão AlertCardZip).
const GANTT_STATUS_BAR: Record<ZipBoatStatus, string> = {
  on_time: 'var(--green)',
  at_risk: 'var(--yellow)',
  late: 'var(--red)',
  curing: 'var(--blue)',
  completed: 'var(--green)',
};

function GanttView({ orders }: { orders: ActiveOrder[] }) {
  if (orders.length === 0) {
    return (
      <EmptyState
        title="Sem barcos para mostrar"
        hint="O endpoint /v1/plan/orders/active não devolveu ordens activas."
        size="md"
      />
    );
  }

  const sorted = [...orders].sort((a, b) => {
    const ta = a.transport_date ? new Date(a.transport_date).getTime() : Infinity;
    const tb = b.transport_date ? new Date(b.transport_date).getTime() : Infinity;
    return ta - tb;
  });

  return (
    <Panel
      title="Barcos activos por expedição"
      badge={`${orders.length} barcos`}
      flush
    >
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="border-b border-white/[0.06]">
            <tr className="text-left text-[10px] uppercase tracking-wider text-text-dark-tertiary">
              <th className="px-3 py-2">Barco</th>
              <th className="px-3 py-2">Modelo</th>
              <th className="px-3 py-2">Fase actual</th>
              <th className="px-3 py-2">Expedição</th>
              <th className="px-3 py-2">Estado</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((o, idx) => {
              const hull = parseInt(o.hull ?? '0', 10) || 0;
              const dx = o.transport_date
                ? Math.max(
                    0,
                    Math.round(
                      (new Date(o.transport_date).getTime() -
                        new Date().setHours(0, 0, 0, 0)) /
                        (1000 * 60 * 60 * 24),
                    ),
                  )
                : undefined;
              const status = deriveStatus(dx, o.phase);
              return (
                <tr
                  key={o.id ?? idx}
                  className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors"
                  style={{ boxShadow: `inset 3px 0 0 0 ${GANTT_STATUS_BAR[status]}` }}
                >
                  <td className="px-3 py-2 font-medium text-text-dark-primary">
                    {o.product_type} #{hull || '—'}
                  </td>
                  <td className="px-3 py-2 text-text-dark-secondary">
                    {o.product_name}
                  </td>
                  <td className="px-3 py-2 text-text-dark-secondary">
                    {o.phase ?? '—'}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-text-dark-secondary">
                    {o.transport_date
                      ? `${o.transport_date.slice(8, 10)}/${o.transport_date.slice(5, 7)}`
                      : '—'}
                    {dx !== undefined ? ` · D−${dx}` : ''}
                  </td>
                  <td className="px-3 py-2">
                    <ZipStatusBadge status={status} size="sm" />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

// ─── CalendarView (placeholder estilo zip) ─────────────────────────────────

function CalendarView() {
  return (
    <Panel title="Vista de calendário" flush>
      <div className="px-4 py-12 text-center">
        <Calendar size={32} className="mx-auto mb-3 text-text-dark-tertiary" />
        <div className="text-sm text-text-dark-secondary">Vista de calendário</div>
        <div className="text-xs text-text-dark-tertiary mt-1">
          Mostrará expedições e milestones por mês
        </div>
      </div>
    </Panel>
  );
}
