/**
 * DirecaoPage — port literal de design/nelo-zip/src/page-ceo.jsx (PageCEO).
 *
 * Hero "A fábrica está {NO PLANO|EM RISCO|EM ATRASO}" + 4 KPIs + 2-col
 * Atenção necessária + Próximas expedições + AI panel "O que o sistema
 * fez por si esta semana".
 *
 * Standalone (sem Inbox embutida — Inbox vive em /inbox).
 *
 * Sprint Q.18.ZIP.shell.
 */

import { lazy, Suspense, useMemo, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Building2,
  RefreshCw,
  Sparkles,
  ArrowRight,
  Truck,
  AlertTriangle,
  CheckCircle2,
  Brain,
  Activity,
  Euro,
} from 'lucide-react';
import { PageHeader, Tabs, ZipSevBadge, EmptyState, type ZipSeverity } from '../../components/dark';
import { SkeletonLoader } from '../../components/ui/Skeleton';
import { ReportExportButton } from '../../components/reports/ReportExportButton';
import { useUmwelt } from '../../lib/umwelt';

const ProfitDashboard = lazy(() =>
  import('../../components/profit/ProfitPanels').then((m) => ({ default: m.ProfitDashboard })),
);
import { ceoDashboardApi, decisionsApi } from '../../lib/api';

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

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const TENANT_HEADER = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };

async function fetchActiveOrders(): Promise<ActiveOrder[]> {
  const resp = await fetch(
    `${API_BASE}/v1/plan/orders/active?limit=500`,
    { headers: TENANT_HEADER },
  );
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

async function fetchProfitDashboard() {
  try {
    const resp = await fetch(`${API_BASE}/v1/profit/dashboard`, {
      headers: TENANT_HEADER,
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

async function fetchTransportBatches() {
  try {
    const resp = await fetch(
      `${API_BASE}/v1/plan/transport/batches?limit=20`,
      { headers: TENANT_HEADER },
    );
    if (!resp.ok) return [];
    return await resp.json();
  } catch {
    return [];
  }
}

function deriveStatus(transport_date: string | null, phase: string | null): string {
  if (phase === 'Cura') return 'curing';
  if (!transport_date) return 'on_time';
  const dx = Math.round(
    (new Date(transport_date).getTime() - new Date().setHours(0, 0, 0, 0)) /
      (1000 * 60 * 60 * 24),
  );
  if (dx < 0) return 'late';
  if (dx <= 2) return 'at_risk';
  return 'on_time';
}

function relativeTime(iso?: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 60000;
  if (diff < 1) return 'agora';
  if (diff < 60) return `há ${Math.round(diff)} min`;
  if (diff < 60 * 24) return `há ${Math.round(diff / 60)}h`;
  return `há ${Math.round(diff / (60 * 24))} dias`;
}

function shipmentDayLabel(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  const days = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
  return days[d.getDay()];
}

export default function DirecaoPage() {
  const navigate = useNavigate();
  const [refreshKey, setRefreshKey] = useState(0);
  const [tab, setTab] = useState<'resumo' | 'profit'>('resumo');
  const { isReadOnly } = useUmwelt();

  const ordersQuery = useQuery({
    queryKey: ['direcao', 'orders', refreshKey],
    queryFn: fetchActiveOrders,
    staleTime: 30_000,
    retry: 0,
  });
  const profitQuery = useQuery({
    queryKey: ['direcao', 'profit', refreshKey],
    queryFn: fetchProfitDashboard,
    staleTime: 60_000,
    retry: 0,
  });
  const alertsQuery = useQuery({
    queryKey: ['direcao', 'alerts', refreshKey],
    queryFn: () => ceoDashboardApi.activeAlerts({ limit: 8 }),
    staleTime: 30_000,
    retry: 1,
  });
  const transportQuery = useQuery({
    queryKey: ['direcao', 'transport', refreshKey],
    queryFn: fetchTransportBatches,
    staleTime: 60_000,
    retry: 0,
  });
  const oeeQuery = useQuery({
    queryKey: ['direcao', 'oee', refreshKey],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/v1/profit/oee`, { headers: TENANT_HEADER });
      return r.ok ? r.json() : null;
    },
    staleTime: 5 * 60_000,
    retry: 0,
  });

  const orders = ordersQuery.data ?? [];
  const totalActive = orders.length;
  const ordersWithStatus = useMemo(
    () => orders.map((o) => ({ ...o, _status: deriveStatus(o.transport_date, o.phase) })),
    [orders],
  );
  const onTime = ordersWithStatus.filter((o) => o._status === 'on_time').length;
  const atRisk = ordersWithStatus.filter((o) => o._status === 'at_risk').length;
  const late = ordersWithStatus.filter((o) => o._status === 'late').length;

  const throughputToday = profitQuery.data?.throughput_eur?.today ?? null;
  const throughputTrend = profitQuery.data?.trend_14d?.map((p: any) => p.eur) ?? [];

  const alertsItems = useMemo<any[]>(() => {
    const data: any = alertsQuery.data;
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.items)) return data.items;
    if (Array.isArray(data.alerts)) return data.alerts;
    return [];
  }, [alertsQuery.data]);

  const transportBatches = transportQuery.data ?? [];

  const hero = (() => {
    if (totalActive === 0)
      return {
        tone: 'gray' as const,
        Icon: Activity,
        head: 'Sem barcos activos',
        sub: 'Nenhuma ordem em produção neste momento.',
      };
    if (late > 0)
      return {
        tone: 'red' as const,
        Icon: AlertTriangle,
        head: 'em atraso',
        sub: `${late} ${late === 1 ? 'barco atrasado' : 'barcos atrasados'} · ${atRisk} em risco · ${onTime} no prazo. Há decisões a aguardar a sua aprovação.`,
      };
    if (atRisk > 0)
      return {
        tone: 'yellow' as const,
        Icon: AlertTriangle,
        head: 'em risco',
        sub: `${atRisk} ${atRisk === 1 ? 'barco em risco' : 'barcos em risco'} · ${onTime} no prazo. Vamos cumprir as próximas expedições com margem apertada.`,
      };
    return {
      tone: 'green' as const,
      Icon: CheckCircle2,
      head: 'no plano',
      sub: `${onTime} dos ${totalActive} barcos no prazo. Sem alertas críticos. Continuar a executar.`,
    };
  })();

  return (
    <div>
      <PageHeader
        icon={<Building2 size={20} />}
        title="Bom dia, Luis."
        subtitle="Resumo do dia"
        helpId="direcao"
        actions={
          <>
            <button
              type="button"
              onClick={() => setRefreshKey((k) => k + 1)}
              className="inline-flex items-center gap-1.5 text-text-dark-secondary hover:text-text-dark-primary transition-colors"
              style={{
                padding: '6px 12px',
                height: 32,
                background: 'var(--bg-2)',
                border: '1px solid var(--bd-1)',
                borderRadius: 'var(--r-md)',
                fontSize: 12,
              }}
            >
              <RefreshCw size={13} />
              Actualizar
            </button>
            <ReportExportButton defaultTemplate="producao" />
            {!isReadOnly && (
            <button
              type="button"
              onClick={() => navigate('/inbox')}
              className="inline-flex items-center gap-1.5 text-white font-medium transition-colors"
              style={{
                padding: '6px 12px',
                height: 32,
                background: 'var(--blue)',
                border: '1px solid var(--blue)',
                borderRadius: 'var(--r-md)',
                fontSize: 12,
              }}
            >
              <Sparkles size={13} />
              Sugestões
            </button>
            )}
          </>
        }
      />

      <div className="px-7 pt-2">
        <Tabs
          tabs={[
            { id: 'resumo', label: 'Resumo do dia', icon: <Building2 size={13} /> },
            { id: 'profit', label: 'Profit Intelligence', icon: <Euro size={13} /> },
          ]}
          value={tab}
          onChange={(id) => setTab(id as 'resumo' | 'profit')}
        />
      </div>

      {tab === 'profit' && (
        <div style={{ padding: '24px 28px' }}>
          <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
            <ProfitDashboard />
          </Suspense>
        </div>
      )}

      {tab === 'resumo' && (
      <div style={{ padding: '24px 28px' }} className="space-y-5">
        {/* Hero */}
        <div
          className="flex items-center"
          style={{
            padding: '22px 26px',
            background: 'var(--bg-1)',
            border: '1px solid var(--bd-1)',
            borderRadius: 'var(--r-lg)',
            gap: 18,
          }}
        >
          <div
            className={`grid place-items-center shrink-0 ${hero.tone === 'red' || hero.tone === 'yellow' ? 'animate-pulse motion-reduce:animate-none' : ''}`}
            style={{
              width: 44,
              height: 44,
              background: `var(--${hero.tone}-bg)`,
              border: `1px solid var(--${hero.tone}-bd)`,
              color: `var(--${hero.tone})`,
              borderRadius: 'var(--r-md)',
              boxShadow:
                hero.tone === 'red'
                  ? '0 0 24px oklch(0.50 0.14 25 / 0.45)'
                  : hero.tone === 'yellow'
                    ? '0 0 24px oklch(0.50 0.12 80 / 0.45)'
                    : undefined,
            }}
            aria-label={`Estado: ${hero.head}`}
          >
            <hero.Icon size={22} />
          </div>
          <div style={{ flex: 1 }}>
            <div
              className="text-text-dark-primary"
              style={{ fontSize: 18, fontWeight: 500, lineHeight: 1.4 }}
            >
              A fábrica está{' '}
              <span style={{ color: `var(--${hero.tone})`, fontWeight: 600 }}>
                {hero.head}
              </span>
              .
            </div>
            <div
              className="text-text-dark-tertiary"
              style={{ fontSize: 13, marginTop: 6 }}
            >
              {hero.sub}
            </div>
          </div>
          <button
            type="button"
            onClick={() => navigate('/plano-producao')}
            className="inline-flex items-center gap-1.5 font-medium transition-colors"
            style={{
              padding: '8px 12px',
              background: 'var(--blue-bg)',
              color: 'var(--blue)',
              border: '1px solid var(--blue-bd)',
              borderRadius: 'var(--r-md)',
              fontSize: 12,
            }}
          >
            Ver detalhe <ArrowRight size={14} />
          </button>
        </div>

        {/* 4 KPIs */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 14,
          }}
        >
          <KPICardZip
            label="Barcos em produção"
            value={totalActive.toString()}
            unit=""
            context={`${onTime} no prazo · ${atRisk} em risco · ${late} atrasados`}
            tone={late > 0 ? 'red' : atRisk > 0 ? 'yellow' : 'green'}
            onClick={() => navigate('/plano-producao')}
          />
          <KPICardZip
            label="OEE da fábrica"
            value={
              oeeQuery.data?.overall
                ? Math.round(oeeQuery.data.overall.oee * 100).toString()
                : '—'
            }
            unit="%"
            context={
              oeeQuery.data?.overall
                ? `Disp ${Math.round(oeeQuery.data.overall.availability * 100)}% · `
                  + `Perf ${Math.round(oeeQuery.data.overall.performance * 100)}% · `
                  + `Qual ${Math.round(oeeQuery.data.overall.quality * 100)}% `
                  + `(${oeeQuery.data.overall.sample_size} ops)`
                : oeeQuery.isLoading ? 'A carregar…' : 'Sem dados de OEE'
            }
            tone={
              !oeeQuery.data?.overall ? 'gray'
                : oeeQuery.data.overall.oee >= 0.60 ? 'green'
                : oeeQuery.data.overall.oee >= 0.40 ? 'yellow'
                : 'red'
            }
            onClick={() => navigate('/qualidade?tab=oee')}
          />
          <KPICardZip
            label="Throughput hoje"
            value={throughputToday !== null ? Math.round(throughputToday).toString() : '—'}
            unit="€"
            context={
              throughputToday !== null
                ? 'Receita reconhecida hoje · /v1/profit/dashboard'
                : 'Sem dados de revenue hoje'
            }
            tone={throughputToday !== null && throughputToday > 0 ? 'green' : 'gray'}
            sparkline={throughputTrend}
            onClick={() => navigate('/oee')}
          />
          <KPICardZip
            label="Margem por barco"
            value="—"
            unit="€"
            context="Calculado em sub-sprint dedicado"
            tone="gray"
          />
        </div>

        {/* Grid 2-col: Atenção + Expedições */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 22 }}>
          <CardWithHeader
            icon={<AlertTriangle size={16} />}
            iconTone="orange"
            title="Atenção necessária"
            subtitle={`${alertsItems.length} ${alertsItems.length === 1 ? 'alerta activo' : 'alertas activos'} · ordenados por urgência`}
            action={
              <button
                type="button"
                onClick={() => navigate('/inbox')}
                className="inline-flex items-center gap-1 text-text-dark-secondary hover:text-text-dark-primary"
                style={{ fontSize: 12 }}
              >
                Ver inbox <ArrowRight size={12} />
              </button>
            }
          >
            {alertsQuery.isLoading ? (
              <div className="py-6 text-center text-text-dark-tertiary" style={{ fontSize: 12 }}>
                A carregar alertas…
              </div>
            ) : alertsItems.length === 0 ? (
              <EmptyState
                size="sm"
                title="Sem alertas activos"
                hint="Tudo calmo no chão de fábrica. Os turnos seguem o plano."
              />
            ) : (
              <div className="flex flex-col" style={{ gap: 10 }}>
                {alertsItems.slice(0, 5).map((a, idx) => (
                  <AlertCardZip key={a.alert_id ?? idx} alert={a} />
                ))}
              </div>
            )}
          </CardWithHeader>

          <CardWithHeader
            icon={<Truck size={16} />}
            iconTone="blue"
            title="Próximas expedições"
            subtitle="Estado dos próximos camiões"
            action={
              <button
                type="button"
                onClick={() => navigate('/expedicao')}
                className="inline-flex items-center gap-1 text-text-dark-secondary hover:text-text-dark-primary"
                style={{ fontSize: 12 }}
              >
                Ver tudo <ArrowRight size={12} />
              </button>
            }
          >
            {transportQuery.isLoading ? (
              <div className="py-6 text-center text-text-dark-tertiary" style={{ fontSize: 12 }}>
                A carregar expedições…
              </div>
            ) : transportBatches.length === 0 ? (
              <EmptyState
                size="sm"
                title="Sem expedições agendadas"
                hint="Quando houver camiões para carregar, aparecem aqui ordenados por data."
              />
            ) : (
              <div className="flex flex-col" style={{ gap: 12 }}>
                {transportBatches.slice(0, 3).map((s: any) => (
                  <ShipmentRowZip key={s.id ?? s.code} shipment={s} />
                ))}
              </div>
            )}
          </CardWithHeader>
        </div>

        {/* AI Panel */}
        <AIPanel />
      </div>
      )}
    </div>
  );
}

// ─── KPICardZip (port atoms.jsx KPICard) ────────────────────────────────────

function KPICardZip({
  label,
  value,
  unit,
  context,
  tone,
  sparkline,
  onClick,
}: {
  label: string;
  value: string;
  unit: string;
  context: string;
  tone: 'green' | 'yellow' | 'red' | 'gray' | 'blue';
  sparkline?: number[];
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      style={{
        padding: '16px 18px',
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'background 0.12s, border-color 0.12s',
      }}
    >
      <div
        className="text-text-dark-tertiary uppercase font-medium"
        style={{ fontSize: 11, letterSpacing: '0.4px', marginBottom: 8 }}
      >
        {label}
      </div>
      <div className="flex items-baseline gap-1 tabular-nums">
        <span
          style={{
            fontSize: 32,
            fontWeight: 700,
            color: `var(--${tone})`,
            lineHeight: 1,
          }}
        >
          {value}
        </span>
        {unit ? (
          <span style={{ fontSize: 14, color: 'var(--fg-2)' }}>{unit}</span>
        ) : null}
      </div>
      {sparkline && sparkline.length > 0 ? (
        <div style={{ marginTop: 10, height: 24 }}>
          <SparklineMini points={sparkline} color={`var(--${tone})`} />
        </div>
      ) : null}
      <div
        className="text-text-dark-tertiary"
        style={{ fontSize: 11, marginTop: 8, lineHeight: 1.4 }}
      >
        {context}
      </div>
    </div>
  );
}

function SparklineMini({ points, color }: { points: number[]; color: string }) {
  if (points.length === 0) return null;
  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const range = max - min || 1;
  const w = 100;
  const h = 24;
  const path = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * w;
      const y = h - ((p - min) / range) * h;
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
      <path d={path} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ─── CardWithHeader (port atoms.jsx Card + CardHeader) ──────────────────────

function CardWithHeader({
  icon,
  iconTone,
  title,
  subtitle,
  action,
  children,
}: {
  icon: ReactNode;
  iconTone: 'orange' | 'blue' | 'green' | 'red' | 'purple' | 'yellow';
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div
      style={{
        padding: 20,
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
      }}
    >
      <div className="flex items-start justify-between mb-3" style={{ gap: 12 }}>
        <div className="flex items-center" style={{ gap: 10 }}>
          <div
            className="grid place-items-center"
            style={{
              width: 32,
              height: 32,
              background: `var(--${iconTone}-bg)`,
              color: `var(--${iconTone})`,
              border: `1px solid var(--${iconTone}-bd)`,
              borderRadius: 'var(--r-md)',
            }}
          >
            {icon}
          </div>
          <div>
            <div className="text-text-dark-primary font-semibold leading-tight" style={{ fontSize: 14 }}>
              {title}
            </div>
            {subtitle ? (
              <div className="text-text-dark-tertiary" style={{ fontSize: 12, marginTop: 2 }}>
                {subtitle}
              </div>
            ) : null}
          </div>
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

// ─── AlertCardZip ───────────────────────────────────────────────────────────

function AlertCardZip({ alert }: { alert: any }) {
  const sev: ZipSeverity =
    alert.severity === 'critical' ||
    alert.severity === 'high' ||
    alert.severity === 'medium' ||
    alert.severity === 'low'
      ? alert.severity
      : 'medium';
  const sevColor =
    sev === 'critical' ? 'red' : sev === 'high' ? 'orange' : sev === 'medium' ? 'yellow' : 'blue';

  return (
    <div
      style={{
        padding: '12px 14px',
        background: 'var(--bg-2)',
        border: '1px solid var(--bd-1)',
        borderLeft: `3px solid var(--${sevColor})`,
        borderRadius: 'var(--r-md)',
      }}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <ZipSevBadge severity={sev} size="sm" />
        <span className="text-text-dark-tertiary" style={{ fontSize: 10 }}>
          {relativeTime(alert.created_at)}
        </span>
      </div>
      <div className="text-text-dark-primary font-medium" style={{ fontSize: 14 }}>
        {alert.title ?? alert.message ?? '(Sem título)'}
      </div>
      {alert.detail || alert.description ? (
        <div className="text-text-dark-secondary" style={{ fontSize: 12, marginTop: 4 }}>
          {alert.detail ?? alert.description}
        </div>
      ) : null}
      {alert.cause ? (
        <div
          className="text-text-dark-secondary"
          style={{
            fontSize: 12,
            marginTop: 6,
            paddingLeft: 12,
            borderLeft: '2px solid var(--bd-2)',
          }}
        >
          <strong className="text-text-dark-primary">Causa:</strong> {alert.cause}
        </div>
      ) : null}
    </div>
  );
}

// ─── ShipmentRowZip ─────────────────────────────────────────────────────────

function ShipmentRowZip({ shipment }: { shipment: any }) {
  const transport = shipment.transport_date ?? shipment.date;
  const total = shipment.truck_capacity_units ?? shipment.total ?? 50;
  const ready = shipment.ready ?? 0;
  const in_prod = shipment.in_prod ?? 0;
  const at_risk = shipment.at_risk ?? 0;
  const pct = total > 0 ? Math.round((ready / total) * 100) : 0;
  const tone = at_risk > 0 ? 'yellow' : pct === 100 ? 'green' : 'blue';
  const day = transport ? shipmentDayLabel(transport) : '—';
  const dayShort = transport ? `${transport.slice(8, 10)}/${transport.slice(5, 7)}` : '—';

  return (
    <div
      style={{
        padding: '12px 14px',
        background: 'var(--bg-2)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-md)',
      }}
    >
      <div className="flex items-baseline justify-between gap-2 mb-1">
        <div className="flex items-baseline gap-2">
          <span className="text-text-dark-primary font-semibold" style={{ fontSize: 13 }}>
            {day}
          </span>
          <span className="text-text-dark-tertiary tabular-nums" style={{ fontSize: 11 }}>
            {dayShort}
          </span>
        </div>
        <span
          className="font-semibold tabular-nums"
          style={{ fontSize: 13, color: `var(--${tone})` }}
        >
          {ready}/{total}
        </span>
      </div>
      <div className="text-text-dark-secondary mb-2" style={{ fontSize: 12 }}>
        {shipment.destination ?? shipment.client ?? '—'}
      </div>
      <div
        style={{
          height: 5,
          background: 'var(--bg-3)',
          borderRadius: 3,
          overflow: 'hidden',
          display: 'flex',
        }}
      >
        <div style={{ width: `${pct}%`, background: 'var(--green)' }} />
        {in_prod > 0 ? (
          <div style={{ width: `${(in_prod / total) * 100}%`, background: 'var(--blue)' }} />
        ) : null}
        {at_risk > 0 ? (
          <div style={{ width: `${(at_risk / total) * 100}%`, background: 'var(--yellow)' }} />
        ) : null}
      </div>
      <div className="flex gap-3 mt-2 text-text-dark-tertiary" style={{ fontSize: 11 }}>
        <span>
          ●{' '}
          <span style={{ color: 'var(--green)' }}>
            {ready} pronto{ready !== 1 ? 's' : ''}
          </span>
        </span>
        {in_prod > 0 ? (
          <span>
            ● <span style={{ color: 'var(--blue)' }}>{in_prod} em produção</span>
          </span>
        ) : null}
        {at_risk > 0 ? (
          <span>
            ● <span style={{ color: 'var(--yellow)' }}>{at_risk} em risco</span>
          </span>
        ) : null}
      </div>
    </div>
  );
}

// ─── AIPanel ────────────────────────────────────────────────────────────────

function AIPanel() {
  const decisionsQuery = useQuery({
    queryKey: ['direcao', 'ai-stats'],
    queryFn: async () => {
      const fetchTotal = async (status?: string) => {
        try {
          const r: any = await decisionsApi.list({ status, page_size: 1 });
          return r?.total ?? 0;
        } catch {
          return 0;
        }
      };
      const [proposed, executed, rejected] = await Promise.all([
        fetchTotal('PROPOSED'),
        fetchTotal('EXECUTED'),
        fetchTotal('REJECTED'),
      ]);
      const total = proposed + executed + rejected;
      return { total, executed, rejected, proposed };
    },
    staleTime: 60_000,
    retry: 0,
  });
  const stats = decisionsQuery.data ?? { total: 0, executed: 0, rejected: 0, proposed: 0 };
  const acceptanceRate = stats.total > 0 ? Math.round((stats.executed / stats.total) * 100) : 0;

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
        className="flex items-center"
        style={{
          padding: '18px 22px',
          borderBottom: '1px solid var(--bd-1)',
          gap: 10,
        }}
      >
        <div
          className="grid place-items-center"
          style={{
            width: 32,
            height: 32,
            background: 'var(--purple-bg)',
            color: 'var(--purple)',
            border: '1px solid var(--purple-bd)',
            borderRadius: 'var(--r-md)',
          }}
        >
          <Brain size={16} />
        </div>
        <div>
          <div className="text-text-dark-primary font-semibold" style={{ fontSize: 14 }}>
            O que o sistema fez por si esta semana
          </div>
          <div className="text-text-dark-tertiary" style={{ fontSize: 12, marginTop: 2 }}>
            O assistente é uma proposta — você decide sempre
          </div>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)' }}>
        {[
          { value: stats.total.toString(), label: 'Sugestões geradas', sub: 'Plano, atribuição, qualidade' },
          { value: stats.executed.toString(), label: 'Aceites por si', sub: `${acceptanceRate}% — ${acceptanceRate >= 70 ? 'boa concordância' : 'baixa concordância'}` },
          { value: stats.rejected.toString(), label: 'Rejeitadas', sub: 'O sistema aprendeu com cada uma' },
          { value: '—', label: 'Poupança estimada', sub: 'Calculado em sub-sprint cost service' },
        ].map((s, i) => (
          <div
            key={i}
            style={{
              padding: '20px 22px',
              borderRight: i < 3 ? '1px solid var(--bd-1)' : 'none',
            }}
          >
            <div
              className="tabular-nums text-text-dark-primary"
              style={{ fontSize: 28, fontWeight: 700, lineHeight: 1 }}
            >
              {s.value}
            </div>
            <div
              className="text-text-dark-secondary font-medium"
              style={{ fontSize: 12, marginTop: 6 }}
            >
              {s.label}
            </div>
            <div className="text-text-dark-tertiary" style={{ fontSize: 11, marginTop: 3 }}>
              {s.sub}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

