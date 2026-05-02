/**
 * CEODashboardPage (Sprint H.3)
 * ===============================
 *
 * `/ceo` — the "read in 10 seconds" dashboard. Three big tiles + one
 * sparkline. Everything else is noise here.
 *
 * Primary signal: **€/dia vs the €30-35k NELO target band**. Secondary
 * signal: the 14-day trend. Tertiary: on-target / below / above badge.
 *
 * Backend is fully reused (Sprint Q.5's ``GET /v1/profit/dashboard``);
 * Sprint H didn't need a new endpoint. The only frontend novelty is
 * this layout, the target-band visual, and the SSE wiring that
 * invalidates the query when a new commit lands so the CEO always
 * sees fresh numbers.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceArea,
} from 'recharts';
import {
  AlertTriangle,
  BarChart3,
  Bell,
  CalendarRange,
  CheckCircle2,
  Euro,
  FileDown,
  Target,
  TrendingUp,
  Truck,
  Users,
} from 'lucide-react';
import { DarkPageLayout } from '../layouts';
import { DarkBadge, DarkButton, DarkCard } from '../components/dark';
import { LiveBadge } from '../components/dashboard/LiveBadge';
import { useRealtime } from '../providers/RealtimeProvider';
import {
  ceoDashboardApi,
  profitDashboardApi,
  type ProfitDashboardResponse,
} from '../lib/api';

// ─── Formatting helpers ──────────────────────────────────────────────────

function fmtEur(v: number, opts?: { compact?: boolean }): string {
  if (!Number.isFinite(v)) return '—';
  if (opts?.compact && Math.abs(v) >= 10_000) {
    return `€ ${(v / 1_000).toFixed(1)}k`;
  }
  return v.toLocaleString('pt-PT', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  });
}

function bandColour(
  onTarget: ProfitDashboardResponse['throughput_eur']['on_target'],
) {
  if (onTarget === 'on') return 'text-emerald-300';
  if (onTarget === 'above') return 'text-blue-300';
  return 'text-amber-300';
}

function bandBadge(
  onTarget: ProfitDashboardResponse['throughput_eur']['on_target'],
) {
  if (onTarget === 'on') return { label: 'Dentro da meta', variant: 'success' as const };
  if (onTarget === 'above') return { label: 'Acima da meta', variant: 'info' as const };
  return { label: 'Abaixo da meta', variant: 'warning' as const };
}

// ─── Big-tile primitive ──────────────────────────────────────────────────

interface TileProps {
  label: string;
  value: string;
  subtitle?: string;
  icon: React.ReactNode;
  accent?: 'default' | 'warn' | 'good' | 'info';
}

function Tile({ label, value, subtitle, icon, accent = 'default' }: TileProps) {
  const accentBg = {
    default: 'bg-bg-elevated',
    warn: 'bg-amber-500/10 border-amber-500/30',
    good: 'bg-emerald-500/10 border-emerald-500/30',
    info: 'bg-blue-500/10 border-blue-500/30',
  }[accent];
  return (
    <div
      className={`rounded-xl border border-border-subtle ${accentBg} p-6 flex flex-col justify-between min-h-[160px]`}
    >
      <div className="flex items-center gap-2 text-text-tertiary text-sm">
        {icon}
        <span>{label}</span>
      </div>
      <div className="mt-4">
        <div className="text-4xl font-semibold text-text-white tabular-nums">
          {value}
        </div>
        {subtitle && (
          <div className="text-xs text-text-tertiary mt-2">{subtitle}</div>
        )}
      </div>
    </div>
  );
}

// ─── Trend chart ─────────────────────────────────────────────────────────

interface TrendChartProps {
  data: ProfitDashboardResponse['trend_14d'];
  targetMin: number;
  targetMax: number;
}

function TrendChart({ data, targetMin, targetMax }: TrendChartProps) {
  const shaped = useMemo(
    () =>
      (data ?? []).map((r) => ({
        date: r.date?.slice(5) ?? '', // MM-DD
        throughput: r.throughput_eur ?? 0,
      })),
    [data],
  );
  if (shaped.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-sm text-text-tertiary">
        Sem série temporal ainda.
      </div>
    );
  }
  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={shaped} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: '#9ca3af' }}
            stroke="#374151"
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#9ca3af' }}
            stroke="#374151"
            tickFormatter={(v) => `${Math.round(v / 1000)}k`}
          />
          <Tooltip
            contentStyle={{
              background: '#111827',
              border: '1px solid #374151',
              borderRadius: 8,
              color: '#f9fafb',
            }}
            formatter={(value: number) => fmtEur(value)}
          />
          <ReferenceArea
            y1={targetMin}
            y2={targetMax}
            fill="#10b981"
            fillOpacity={0.08}
            strokeOpacity={0}
          />
          <Line
            type="monotone"
            dataKey="throughput"
            stroke="#38bdf8"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────

export function CEODashboardPage() {
  const queryClient = useQueryClient();
  const realtime = useRealtime();
  const [lastEventAt, setLastEventAt] = useState<Date | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['profit-dashboard'],
    queryFn: () => profitDashboardApi.get(),
    staleTime: 60_000,
  });

  // Sprint Q.5 — 5 secondary tiles fetched in parallel (single useQueries
  // call so React's hooks order stays stable).
  const [otdQ, fpyQ, backlogQ, expeditionsQ, alertsQ] = useQueries({
    queries: [
      {
        queryKey: ['ceo', 'otd'],
        queryFn: () => ceoDashboardApi.otd({ window_days: 30 }),
        staleTime: 5 * 60_000,
      },
      {
        queryKey: ['ceo', 'fpy'],
        queryFn: () => ceoDashboardApi.firstPassYield({ window_days: 30 }),
        staleTime: 5 * 60_000,
      },
      {
        queryKey: ['ceo', 'backlog'],
        queryFn: () => ceoDashboardApi.backlogByClient({ limit: 10 }),
        staleTime: 5 * 60_000,
      },
      {
        queryKey: ['ceo', 'expeditions'],
        queryFn: () => ceoDashboardApi.expeditionsNextNDays({ horizon_days: 7 }),
        staleTime: 60_000,
      },
      {
        queryKey: ['ceo', 'alerts'],
        queryFn: () => ceoDashboardApi.activeAlerts({ limit: 8 }),
        staleTime: 60_000,
      },
    ],
  });

  // SSE-driven invalidation — same debounce pattern as
  // useLiveDashboardRefresh but scoped to this single query.
  const processedLen = useRef(0);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!realtime) return;
    const total = realtime.events.length;
    if (total === processedLen.current) return;
    const fresh = realtime.events.slice(processedLen.current, total);
    processedLen.current = total;
    let refresh = false;
    let latest: Date | null = null;
    for (const ev of fresh) {
      if (
        ev.event_type === 'COGS_CALCULATED' ||
        ev.event_type === 'SCHEDULE_CREATED' ||
        ev.event_type === 'DECISION_EXECUTED'
      ) {
        refresh = true;
        latest = ev.timestamp ? new Date(ev.timestamp) : new Date();
      }
    }
    if (!refresh) return;
    setLastEventAt(latest);
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      queryClient.invalidateQueries({ queryKey: ['profit-dashboard'] });
      debounceTimer.current = null;
    }, 1_500);
  }, [realtime?.events.length, realtime, queryClient]);

  useEffect(
    () => () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    },
    [],
  );

  const throughput = data?.throughput_eur;
  const band = throughput ? bandBadge(throughput.on_target) : null;

  // Sprint Q.9 Onda 3.5 + Q.13.C C.3.4 — Export PDF via the browser's
  // "save as PDF" print pipeline. Plan v4 §9 lists this as a hard
  // requirement; we use window.print() instead of jsPDF so the bundle
  // stays lean (no jspdf + html2canvas → ~400KB saved). The print
  // stylesheet (`@media print` in `index.css`) renders a clean
  // light-theme version of the dashboard with a dated footer.
  //
  // The browser's Save-as-PDF dialog suggests a filename based on
  // `document.title`; we set it transiently here so the saved file is
  // "ProdPlan-CEO-2026-05-02.pdf" (instead of "PP1 - CEO" or
  // whatever the route last set). We restore the original title after
  // the print dispatch returns.
  const handleExportPdf = () => {
    if (typeof window === 'undefined' || typeof window.print !== 'function') {
      return;
    }
    const today = new Date();
    const dd = String(today.getDate()).padStart(2, '0');
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const yyyy = today.getFullYear();
    const dateStr = `${dd}/${mm}/${yyyy}`;
    const fileDate = `${yyyy}-${mm}-${dd}`;

    // Stamp the date on <body> so the @media print footer can read it
    // via attr(data-print-date).
    if (typeof document !== 'undefined' && document.body) {
      document.body.setAttribute('data-print-date', dateStr);
    }

    const previousTitle = typeof document !== 'undefined' ? document.title : '';
    if (typeof document !== 'undefined') {
      document.title = `ProdPlan-CEO-${fileDate}`;
    }

    try {
      window.print();
    } finally {
      // Restore title shortly after — most browsers fire afterprint
      // synchronously but a small timeout covers macOS Safari which
      // is reportedly async.
      setTimeout(() => {
        if (typeof document !== 'undefined') {
          document.title = previousTitle;
          document.body?.removeAttribute('data-print-date');
        }
      }, 500);
    }
  };

  return (
    <DarkPageLayout
      title="CEO"
      subtitle="Throughput €/dia vs meta — leitura em 10 segundos"
      icon={<BarChart3 size={20} />}
      actions={
        <div className="flex items-center gap-2">
          <DarkButton
            variant="secondary"
            size="sm"
            icon={<FileDown size={14} />}
            onClick={handleExportPdf}
          >
            Exportar PDF
          </DarkButton>
          <LiveBadge lastEventAt={lastEventAt} />
        </div>
      }
    >
      {isLoading ? (
        <DarkCard>
          <p className="text-sm text-text-tertiary text-center py-8">
            A carregar…
          </p>
        </DarkCard>
      ) : isError || !throughput ? (
        <DarkCard>
          <p className="text-sm text-text-tertiary text-center py-8">
            Não consegui ler o dashboard. Tenta daqui a pouco.
          </p>
        </DarkCard>
      ) : (
        <>
          {/* 3 tiles — headline first, supporting next */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <Tile
              label="€/dia hoje"
              value={fmtEur(throughput.today)}
              subtitle={
                `Meta ${fmtEur(throughput.target_min, { compact: true })}` +
                ` – ${fmtEur(throughput.target_max, { compact: true })}`
              }
              icon={<Euro size={16} />}
              accent={
                throughput.on_target === 'on'
                  ? 'good'
                  : throughput.on_target === 'above'
                  ? 'info'
                  : 'warn'
              }
            />
            <Tile
              label="Month-to-date"
              value={fmtEur(throughput.mtd)}
              subtitle="Acumulado no mês até hoje"
              icon={<CalendarRange size={16} />}
            />
            <Tile
              label="Year-to-date"
              value={fmtEur(throughput.ytd)}
              subtitle="Acumulado no ano"
              icon={<TrendingUp size={16} />}
            />
          </div>

          {/* Status badge + trend */}
          <DarkCard className="mb-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Target size={16} className={bandColour(throughput.on_target)} />
                <span className="text-sm text-text-secondary">
                  Estado da meta
                </span>
                {band && <DarkBadge variant={band.variant}>{band.label}</DarkBadge>}
              </div>
              <span className="text-xs text-text-tertiary">
                {data.date}
              </span>
            </div>
            <TrendChart
              data={data.trend_14d}
              targetMin={throughput.target_min}
              targetMax={throughput.target_max}
            />
            <p className="text-xs text-text-tertiary mt-2 text-center">
              Banda verde = meta €{throughput.target_min.toLocaleString('pt-PT')}
              –€{throughput.target_max.toLocaleString('pt-PT')}/dia.
              Linha azul = throughput realizado.
            </p>
          </DarkCard>

          {/* Sprint Q.5 — secondary KPI tiles */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <Tile
              label="OTD (30d)"
              value={otdQ.data ? `${otdQ.data.otd_pct.toFixed(1)}%` : '—'}
              subtitle={
                otdQ.data
                  ? `${otdQ.data.on_time}/${otdQ.data.total} no prazo`
                  : 'A calcular…'
              }
              icon={<CheckCircle2 size={16} />}
              accent={
                otdQ.data == null
                  ? 'default'
                  : otdQ.data.otd_pct >= 90
                  ? 'good'
                  : otdQ.data.otd_pct >= 75
                  ? 'info'
                  : 'warn'
              }
            />
            <Tile
              label="First-pass yield (30d)"
              value={fpyQ.data ? `${fpyQ.data.first_pass_yield_pct.toFixed(1)}%` : '—'}
              subtitle={
                fpyQ.data
                  ? `${fpyQ.data.orders_with_rework}/${fpyQ.data.orders_total} c/ retrabalho`
                  : 'A calcular…'
              }
              icon={<Target size={16} />}
              accent={
                fpyQ.data == null
                  ? 'default'
                  : fpyQ.data.first_pass_yield_pct >= 80
                  ? 'good'
                  : fpyQ.data.first_pass_yield_pct >= 60
                  ? 'info'
                  : 'warn'
              }
            />
            <Tile
              label="Backlog (top cliente)"
              value={
                backlogQ.data && backlogQ.data.items[0]
                  ? fmtEur(backlogQ.data.items[0].pending_value_eur, { compact: true })
                  : '—'
              }
              subtitle={
                backlogQ.data && backlogQ.data.items[0]
                  ? `${backlogQ.data.items[0].client_name} · ${backlogQ.data.items[0].pending_orders} OFs`
                  : 'A calcular…'
              }
              icon={<Users size={16} />}
            />
            <Tile
              label="Expedições próx 7d"
              value={expeditionsQ.data ? String(expeditionsQ.data.count) : '—'}
              subtitle={
                expeditionsQ.data
                  ? `${
                      expeditionsQ.data.items.filter((e) => e.risk !== 'ok').length
                    } com risco`
                  : 'A calcular…'
              }
              icon={<Truck size={16} />}
              accent={
                expeditionsQ.data &&
                expeditionsQ.data.items.some((e) => e.risk === 'over_capacity')
                  ? 'warn'
                  : 'default'
              }
            />
          </div>

          {/* Backlog by client table + Active alerts feed (side by side) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <DarkCard>
              <div className="flex items-center gap-2 mb-3">
                <Users size={16} className="text-blue-300" />
                <span className="text-sm text-text-secondary font-medium">
                  Backlog por cliente
                </span>
              </div>
              {backlogQ.isLoading ? (
                <p className="text-xs text-text-tertiary py-3">A carregar…</p>
              ) : backlogQ.data && backlogQ.data.items.length > 0 ? (
                <div className="space-y-1 max-h-64 overflow-auto">
                  {backlogQ.data.items.slice(0, 10).map((row) => (
                    <div
                      key={row.client_name}
                      className="flex items-center justify-between text-xs py-1.5 border-b border-slate-800 last:border-0"
                    >
                      <span className="text-slate-300 truncate flex-1" title={row.client_name}>
                        {row.client_name}
                      </span>
                      <span className="text-slate-400 mx-2">{row.pending_orders}</span>
                      <span className="text-slate-200 font-medium">
                        {fmtEur(row.pending_value_eur, { compact: true })}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-text-tertiary py-3">Sem backlog pendente.</p>
              )}
            </DarkCard>

            <DarkCard>
              <div className="flex items-center gap-2 mb-3">
                <Bell size={16} className="text-amber-300" />
                <span className="text-sm text-text-secondary font-medium">
                  Alertas activos
                </span>
                {alertsQ.data && (
                  <DarkBadge
                    variant={
                      alertsQ.data.by_severity.CRITICAL > 0
                        ? 'danger'
                        : alertsQ.data.by_severity.WARN > 0
                        ? 'warning'
                        : 'success'
                    }
                    size="sm"
                  >
                    {alertsQ.data.count}
                  </DarkBadge>
                )}
              </div>
              {alertsQ.isLoading ? (
                <p className="text-xs text-text-tertiary py-3">A carregar…</p>
              ) : alertsQ.data && alertsQ.data.items.length > 0 ? (
                <div className="space-y-2 max-h-64 overflow-auto">
                  {alertsQ.data.items.map((a) => (
                    <div key={a.id} className="text-xs flex items-start gap-2">
                      <AlertTriangle
                        size={12}
                        className={
                          a.severity === 'CRITICAL'
                            ? 'text-red-400 mt-0.5 flex-shrink-0'
                            : a.severity === 'WARN'
                            ? 'text-amber-400 mt-0.5 flex-shrink-0'
                            : 'text-blue-400 mt-0.5 flex-shrink-0'
                        }
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-slate-200 truncate">{a.title}</p>
                        <p className="text-slate-500 truncate">{a.message_pt}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-emerald-400 py-3">Sem alertas activos.</p>
              )}
            </DarkCard>
          </div>

          {/* Expeditions list */}
          {expeditionsQ.data && expeditionsQ.data.items.length > 0 && (
            <DarkCard className="mb-4">
              <div className="flex items-center gap-2 mb-3">
                <Truck size={16} className="text-teal-300" />
                <span className="text-sm text-text-secondary font-medium">
                  Expedições próximos 7 dias
                </span>
              </div>
              <table className="w-full text-xs">
                <thead className="text-slate-500">
                  <tr>
                    <th className="text-left py-1">Data</th>
                    <th className="text-left py-1">Código</th>
                    <th className="text-left py-1">Estado</th>
                    <th className="text-right py-1">Carga</th>
                    <th className="text-left py-1 pl-2">Risco</th>
                  </tr>
                </thead>
                <tbody>
                  {expeditionsQ.data.items.map((e) => (
                    <tr key={e.batch_id} className="border-t border-slate-800">
                      <td className="py-1 text-slate-300">{e.transport_date}</td>
                      <td className="py-1 text-slate-200">{e.code}</td>
                      <td className="py-1">
                        <DarkBadge
                          variant={
                            e.status === 'DISPATCHED'
                              ? 'neutral'
                              : e.status === 'FROZEN'
                              ? 'warning'
                              : 'success'
                          }
                          size="sm"
                        >
                          {e.status}
                        </DarkBadge>
                      </td>
                      <td className="py-1 text-right text-slate-300">
                        {e.assigned_orders}/{e.truck_capacity_units}
                      </td>
                      <td className="py-1 pl-2">
                        {e.risk === 'over_capacity' && (
                          <span className="text-red-400">⚠ acima</span>
                        )}
                        {e.risk === 'near_capacity' && (
                          <span className="text-amber-400">∼ perto</span>
                        )}
                        {e.risk === 'ok' && (
                          <span className="text-emerald-400">ok</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </DarkCard>
          )}

          <p className="text-xs text-text-tertiary text-center">
            Fonte: {data.source}. Para detalhe operacional ver{' '}
            <a href="/" className="text-accent underline">
              dashboard do gestor
            </a>
            .
          </p>
        </>
      )}
    </DarkPageLayout>
  );
}

export default CEODashboardPage;
