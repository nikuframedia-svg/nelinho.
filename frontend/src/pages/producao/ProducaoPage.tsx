/**
 * ProducaoPage — port literal de design/nelo-zip/src/page-scheduling.jsx.
 *
 * Estrutura idêntica ao zip:
 *   • Header: "Plano de produção" + "Onde está cada barco · {N} barcos
 *     activos · 41 fases" + SegmentedControl (Por fase / Gantt / Calendário)
 *     + botão "Re-optimizar".
 *   • Por fase (PhasesView): legenda "Como ler" + grid 11 colunas
 *     (PHASES.slice(0,11)) com header F{id} + load{count}/{cap} +
 *     barra load% + cura badge + body com BoatCardZip ou "vazio".
 *   • Gantt (GanttView): tabela sticky cols Barco/Cliente + 10 days
 *     (12 Qua → 22 Sex) com bars phases coloridas.
 *   • Calendário (CalendarView): placeholder.
 *
 * Wire ao backend: /v1/plan/orders/active (Q.18.ZIP.BE.1) — boats reais
 * com phase mapping para colunas. Sem mocks frontend.
 *
 * Sprint Q.18.ZIP.PROD (refactor profundo big-bang).
 */

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Calendar, Clock, Sparkles, RefreshCw } from 'lucide-react';
import {
  PageHeader,
  SegmentedControl,
  Panel,
  ZipLegend,
  BoatCardZip,
  type ZipBoat,
  type ZipBoatStatus,
} from '../../components/dark';
import { CPODashboard } from '../../components/cpo/CPOPanels';
import { getApiBase } from '../../lib/api';

// ─── PHASES canónicas (matching data.jsx PHASES, slice 0,11) ────────────────

interface PhaseDef {
  id: number;
  name: string;
  short: string;
  cap: number;
  cure: number; // hours
}

const PHASES: PhaseDef[] = [
  { id: 1, name: 'Prep. Molde', short: 'Prep.', cap: 4, cure: 0 },
  { id: 2, name: 'Pintura gelcoat', short: 'Gelcoat', cap: 6, cure: 0 },
  { id: 3, name: 'Laminagem', short: 'Laminagem', cap: 16, cure: 0 },
  { id: 4, name: 'Cura', short: 'Cura', cap: 20, cure: 15 },
  { id: 5, name: 'Desmolde', short: 'Desmolde', cap: 6, cure: 0 },
  { id: 6, name: 'Corte', short: 'Corte', cap: 8, cure: 0 },
  { id: 7, name: 'Colagem Peças', short: 'Colagem', cap: 10, cure: 0 },
  { id: 8, name: 'Pintura Acabam.', short: 'Pint. Ac.', cap: 12, cure: 0 },
  { id: 9, name: 'Lixagem água', short: 'Lixagem', cap: 25, cure: 0 },
  { id: 10, name: 'Montagem', short: 'Montagem', cap: 8, cure: 0 },
  { id: 11, name: 'CQ Final', short: 'CQ', cap: 4, cure: 0 },
];

// Mapping cliente_code → flag emoji (matching data.jsx CLIENTS)
const CLIENT_FLAGS: Record<string, { code: string; flag: string; name: string }> = {
  FR: { code: 'FR', flag: '🇫🇷', name: 'Federação Francesa' },
  DE: { code: 'DE', flag: '🇩🇪', name: 'Cliente Privado DE' },
  PT: { code: 'PT', flag: '🇵🇹', name: 'Federação Portuguesa' },
  IT: { code: 'IT', flag: '🇮🇹', name: 'Federação Italiana' },
  SE: { code: 'SE', flag: '🇸🇪', name: 'Equipa Sueca' },
  NO: { code: 'NO', flag: '🇳🇴', name: 'Clube Noruega' },
  AT: { code: 'AT', flag: '🇦🇹', name: 'Federação Áustria' },
};

// Heurística: mapear hull # ao cliente. Match data.jsx BOATS.
// 4271 4273 (FR), 4272 4274 4275 6001 6002 6003 (PT), 5103 5105 (DE), 5104 (IT), 6004 (SE).
const HULL_CLIENT: Record<number, string> = {
  4271: 'FR',
  4272: 'PT',
  4273: 'FR',
  4274: 'PT',
  4275: 'PT',
  5103: 'DE',
  5104: 'IT',
  5105: 'DE',
  6001: 'PT',
  6002: 'PT',
  6003: 'NO',
  6004: 'SE',
};

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

function toZipBoat(o: ActiveOrder, phaseId: number, status: ZipBoatStatus): ZipBoat {
  const hull = parseInt(o.hull ?? '0', 10) || 0;
  const clientCode = HULL_CLIENT[hull];
  const client = clientCode ? CLIENT_FLAGS[clientCode] : null;
  const phase = PHASES.find((p) => p.id === phaseId);
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
    client_code: client?.code,
    client_flag: client?.flag,
    phase_short: phase?.short,
    phase_long: phase?.name,
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

type View = 'phases' | 'gantt' | 'calendar' | 'cpo';

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

  // Group orders por phase id (1-11). Match phase_name → phase id.
  const ordersByPhase: Map<number, ZipBoat[]> = useMemo(() => {
    const m = new Map<number, ZipBoat[]>();
    for (const o of orders) {
      const phase = PHASES.find(
        (p) => p.name.toLowerCase() === (o.phase ?? '').toLowerCase(),
      );
      if (!phase) continue;
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
      const zb = toZipBoat(o, phase.id, status);
      if (!m.has(phase.id)) m.set(phase.id, []);
      m.get(phase.id)!.push(zb);
    }
    return m;
  }, [orders]);

  return (
    <div>
      <PageHeader
        title="Plano de produção"
        subtitle={`Onde está cada barco · ${orders.length} barcos activos · 41 fases`}
        helpId="plano-producao"
        actions={
          <>
            <SegmentedControl
              size="sm"
              value={view}
              onChange={(v) => setView(v as View)}
              options={[
                { id: 'phases', label: 'Por fase' },
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
            <button
              type="button"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-white text-xs font-medium transition-colors"
              style={{
                background: 'var(--blue)',
                border: '1px solid var(--blue)',
              }}
              onClick={() => alert('Re-optimizar — wire ao CPO scheduler em sub-sprint')}
            >
              <Sparkles size={13} />
              Re-optimizar
            </button>
          </>
        }
      />

      <div className="px-6 py-4">
        {view === 'phases' && (
          <PhasesView
            ordersByPhase={ordersByPhase}
            isLoading={ordersQuery.isLoading}
            isError={ordersQuery.isError}
          />
        )}
        {view === 'gantt' && <GanttView orders={orders} />}
        {view === 'calendar' && <CalendarView />}
        {view === 'cpo' && <CPODashboard />}
      </div>
    </div>
  );
}

// ─── PhasesView (port literal de page-scheduling.jsx PhasesView) ────────────

function PhasesView({
  ordersByPhase,
  isLoading,
  isError,
}: {
  ordersByPhase: Map<number, ZipBoat[]>;
  isLoading: boolean;
  isError: boolean;
}) {
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

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <ZipLegend
          hint="Como ler:"
          trailing="Cartões = barcos. Arraste entre fases para mover."
          items={[
            { color: 'green', label: 'No prazo' },
            { color: 'yellow', label: 'Em risco' },
            { color: 'red', label: 'Atrasado' },
            { color: 'gray', label: 'Em cura' },
          ]}
        />
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${PHASES.length}, minmax(140px, 1fr))`,
          gap: 12,
          overflowX: 'auto',
          paddingBottom: 8,
        }}
      >
        {PHASES.map((p) => {
          const boats = ordersByPhase.get(p.id) ?? [];
          const load = (boats.length / p.cap) * 100;
          const loadColor: 'red' | 'yellow' | 'green' =
            load > 90 ? 'red' : load > 70 ? 'yellow' : 'green';
          return (
            <div
              key={p.id}
              style={{
                background: 'var(--bg-1)',
                border: '1px solid var(--bd-1)',
                borderRadius: 8,
                minHeight: 380,
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              {/* Header */}
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
                  <span
                    style={{
                      fontSize: 11,
                      color: 'var(--fg-3)',
                      fontWeight: 500,
                    }}
                  >
                    F{p.id}
                  </span>
                  <span
                    className="tabular-nums"
                    style={{
                      fontSize: 11,
                      color: `var(--${loadColor})`,
                      fontWeight: 600,
                    }}
                  >
                    {boats.length}/{p.cap}
                  </span>
                </div>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: 'var(--fg-0)',
                    marginTop: 3,
                  }}
                >
                  {p.name}
                </div>
                <div
                  style={{
                    height: 3,
                    background: 'var(--bd-1)',
                    borderRadius: 2,
                    marginTop: 6,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      width: `${Math.min(load, 100)}%`,
                      height: '100%',
                      background: `var(--${loadColor})`,
                      transition: 'width 0.3s ease',
                    }}
                  />
                </div>
                {p.cure > 0 && (
                  <div
                    style={{
                      fontSize: 10,
                      color: 'var(--fg-3)',
                      marginTop: 4,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    <Clock size={10} /> Cura {p.cure}h
                  </div>
                )}
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

const GANTT_DAYS = [
  '12 Qua', '13 Qui', '14 Sex', '15 Sáb', '16 Dom',
  '18 Seg', '19 Ter', '20 Qua', '21 Qui', '22 Sex',
];

function GanttView({ orders }: { orders: ActiveOrder[] }) {
  if (orders.length === 0) {
    return (
      <div className="px-4 py-12 text-center text-xs text-text-dark-tertiary">
        Sem barcos para mostrar no Gantt.
      </div>
    );
  }

  const stickyCellName = {
    position: 'sticky' as const,
    left: 0,
    background: 'rgba(20, 24, 30, 0.95)',
    padding: '10px 14px',
    borderBottom: '1px solid var(--bd-1)',
    borderRight: '1px solid var(--bd-1)',
    minWidth: 160,
    zIndex: 1,
  };
  const stickyCellClient = {
    position: 'sticky' as const,
    left: 160,
    background: 'rgba(20, 24, 30, 0.95)',
    padding: '10px 14px',
    borderBottom: '1px solid var(--bd-1)',
    borderRight: '1px solid var(--bd-1)',
    minWidth: 80,
    fontSize: 12,
    color: 'var(--fg-1)',
    zIndex: 1,
  };
  const headSticky = (left: number) => ({
    position: 'sticky' as const,
    left,
    background: 'var(--bg-2)',
    padding: '10px 14px',
    textAlign: 'left' as const,
    borderBottom: '1px solid var(--bd-1)',
    borderRight: '1px solid var(--bd-1)',
    fontSize: 11,
    color: 'var(--fg-2)',
    fontWeight: 600,
    textTransform: 'uppercase' as const,
    letterSpacing: 0.4,
    zIndex: 2,
  });

  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      <div style={{ overflowX: 'auto' }}>
        <table
          style={{
            width: '100%',
            borderCollapse: 'separate',
            borderSpacing: 0,
            fontSize: 12,
          }}
        >
          <thead>
            <tr style={{ background: 'var(--bg-2)' }}>
              <th style={{ ...headSticky(0), minWidth: 160 }}>Barco</th>
              <th style={{ ...headSticky(160), minWidth: 80 }}>Cliente</th>
              {GANTT_DAYS.map((d) => (
                <th
                  key={d}
                  style={{
                    padding: '10px 8px',
                    textAlign: 'center',
                    borderBottom: '1px solid var(--bd-1)',
                    fontSize: 11,
                    color: 'var(--fg-2)',
                    fontWeight: 500,
                    minWidth: 80,
                  }}
                >
                  {d}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {orders.map((o, idx) => {
              const hull = parseInt(o.hull ?? '0', 10) || 0;
              const clientCode = HULL_CLIENT[hull];
              const client = clientCode ? CLIENT_FLAGS[clientCode] : null;
              const phase = PHASES.find(
                (p) => p.name.toLowerCase() === (o.phase ?? '').toLowerCase(),
              );
              // Heurística determinística para spread visual: hash do hull.
              const start = hull % 4;
              const len = 4 + (hull % 5);
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
              const tone = {
                on_time: 'green',
                at_risk: 'yellow',
                late: 'red',
                curing: 'gray',
                completed: 'blue',
              }[status];

              return (
                <tr key={o.id ?? idx} style={{ background: 'var(--bg-2)' }}>
                  <td style={stickyCellName}>
                    <div style={{ fontWeight: 600, color: 'var(--fg-0)' }}>
                      {o.product_type} #{hull || '—'}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                      {o.product_name}
                    </div>
                  </td>
                  <td style={stickyCellClient}>
                    {client ? `${client.flag} ${client.code}` : '—'}
                  </td>
                  {GANTT_DAYS.map((d, i) => (
                    <td
                      key={d}
                      style={{
                        borderBottom: '1px solid var(--bd-1)',
                        borderRight: '1px solid var(--bg-2)',
                        padding: 4,
                        height: 36,
                        position: 'relative',
                      }}
                    >
                      {i === start && (
                        <div
                          style={{
                            height: 22,
                            width: `calc(${len * 100}% + ${(len - 1) * 1}px)`,
                            background: `var(--${tone}-bg)`,
                            border: `1px solid var(--${tone}-bd)`,
                            borderLeft: `3px solid var(--${tone})`,
                            borderRadius: 4,
                            padding: '2px 6px',
                            fontSize: 10,
                            color: `var(--${tone})`,
                            display: 'flex',
                            alignItems: 'center',
                            fontWeight: 500,
                          }}
                        >
                          {phase?.short ?? '—'}
                        </div>
                      )}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
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
