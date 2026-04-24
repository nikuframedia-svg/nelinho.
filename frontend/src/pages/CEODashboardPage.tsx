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
import { useQuery, useQueryClient } from '@tanstack/react-query';
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
  BarChart3,
  Euro,
  TrendingUp,
  Target,
  CalendarRange,
} from 'lucide-react';
import { DarkPageLayout } from '../layouts';
import { DarkCard, DarkBadge } from '../components/dark';
import { LiveBadge } from '../components/dashboard/LiveBadge';
import { useRealtime } from '../providers/RealtimeProvider';
import {
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

  return (
    <DarkPageLayout
      title="CEO"
      subtitle="Throughput €/dia vs meta — leitura em 10 segundos"
      icon={<BarChart3 size={20} />}
      actions={<LiveBadge lastEventAt={lastEventAt} />}
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
