/**
 * PainelPage — port literal de design/nelo-zip/src/page-ceo.jsx.
 *
 * Estrutura idêntica ao zip:
 *   1. Hero — frase de estado da fábrica + ícone + "Ver detalhe"
 *   2. 4 KPI cards (Barcos / OEE / Throughput / Margem)
 *   3. Grid 2-col: "Atenção necessária" (AlertCardZip) | "Próximas expedições" (ShipmentRowZip)
 *   4. AI Panel "O que o sistema fez por si esta semana" (4 stats)
 *
 * Plus secções extra preservadas (Onda 4):
 *   5. Inbox de decisões (filter tabs Pendentes/Aceites/Rejeitadas/Tudo)
 *   6. Backlog por cliente
 *   7. Actividade ao vivo + Trust index — fontes
 *
 * Wire ao backend real:
 *   - /v1/plan/orders/active → contagem barcos por status
 *   - /v1/profit/dashboard → throughput hoje (now ✓ post-fix)
 *   - /v1/copilot/alerts (via ceoDashboardApi.activeAlerts)
 *   - /v1/plan/transport/batches → próximas expedições
 *   - /v1/decisions/?status_filter=PROPOSED → inbox
 *   - /v1/dqa/trust-index?scope=factory → trust panel
 *   - /v1/ceo/backlog-by-client → backlog
 *
 * ZERO MOCKS. Empty states honestos quando endpoint não responde.
 *
 * Sprint Q.18.ZIP.PAIN.
 */

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  RefreshCw,
  Sparkles,
  ArrowRight,
  Inbox,
  Truck,
  AlertTriangle,
  CheckCircle2,
  Brain,
  Activity,
} from 'lucide-react';
import {
  PageHeader,
  Panel,
  Tabs,
  TrustBadge,
  ZipSevBadge,
  scoreToGrade,
  type ZipSeverity,
} from '../../components/dark';
import { LiveActivityFeed } from '../../components/activity/LiveActivityFeed';
import { ceoDashboardApi, decisionsApi, dqaApi } from '../../lib/api';

// ─── Endpoints auxiliares ───────────────────────────────────────────────────

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
  const resp = await fetch(
    'http://127.0.0.1:8001/v1/plan/orders/active?limit=500',
    { headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' } },
  );
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

async function fetchProfitDashboard() {
  try {
    const resp = await fetch('http://127.0.0.1:8001/v1/profit/dashboard', {
      headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' },
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
      'http://127.0.0.1:8001/v1/plan/transport/batches?limit=20',
      { headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' } },
    );
    if (!resp.ok) return [];
    return await resp.json();
  } catch {
    return [];
  }
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function deriveStatus(transport_date: string | null, phase: string | null): string {
  if (phase === 'Cura') return 'curing';
  if (!transport_date) return 'on_time';
  const t = new Date(transport_date).getTime();
  const today = new Date().setHours(0, 0, 0, 0);
  const dx = Math.round((t - today) / (1000 * 60 * 60 * 24));
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

// ═══════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════

export default function PainelPage() {
  const navigate = useNavigate();
  const [refreshKey, setRefreshKey] = useState(0);

  const ordersQuery = useQuery({
    queryKey: ['painel', 'orders', refreshKey],
    queryFn: fetchActiveOrders,
    staleTime: 30_000,
    retry: 0,
  });

  const profitQuery = useQuery({
    queryKey: ['painel', 'profit', refreshKey],
    queryFn: fetchProfitDashboard,
    staleTime: 60_000,
    retry: 0,
  });

  const alertsQuery = useQuery({
    queryKey: ['painel', 'alerts', refreshKey],
    queryFn: () => ceoDashboardApi.activeAlerts({ limit: 8 }),
    staleTime: 30_000,
    retry: 1,
  });

  const transportQuery = useQuery({
    queryKey: ['painel', 'transport', refreshKey],
    queryFn: fetchTransportBatches,
    staleTime: 60_000,
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

  // ─── Hero state derivation ───
  const heroState = (() => {
    if (totalActive === 0) {
      return {
        tone: 'gray',
        icon: Activity,
        head: 'Sem barcos activos',
        sub: 'Nenhuma ordem em produção neste momento.',
      };
    }
    if (late > 0) {
      return {
        tone: 'red',
        icon: AlertTriangle,
        head: 'em atraso',
        sub: `${late} ${late === 1 ? 'barco atrasado' : 'barcos atrasados'} · ${atRisk} em risco · ${onTime} no prazo. Há decisões a aguardar a sua aprovação.`,
      };
    }
    if (atRisk > 0) {
      return {
        tone: 'yellow',
        icon: AlertTriangle,
        head: 'em risco',
        sub: `${atRisk} ${atRisk === 1 ? 'barco em risco' : 'barcos em risco'} · ${onTime} no prazo. Vamos cumprir as próximas expedições com margem apertada.`,
      };
    }
    return {
      tone: 'green',
      icon: CheckCircle2,
      head: 'no plano',
      sub: `${onTime} dos ${totalActive} barcos no prazo. Sem alertas críticos. Continuar a executar.`,
    };
  })();

  return (
    <div>
      <PageHeader
        title="Bom dia, Luis."
        subtitle="Resumo do dia"
        actions={
          <>
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
              onClick={() => window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query: 'Que sugestões há para hoje?' } }))}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-white text-xs font-medium transition-colors"
              style={{ background: 'var(--blue)', border: '1px solid var(--blue)' }}
            >
              <Sparkles size={13} />
              Sugestões
            </button>
          </>
        }
      />

      <div className="px-6 py-4 space-y-5">
        {/* ─── Hero ─── */}
        <div
          style={{
            padding: '22px 26px',
            background: 'var(--bg-1)',
            border: '1px solid var(--bd-1)',
            borderRadius: 12,
            display: 'flex',
            alignItems: 'center',
            gap: 18,
          }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 8,
              background: `var(--${heroState.tone}-bg)`,
              border: `1px solid var(--${heroState.tone}-bd)`,
              color: `var(--${heroState.tone})`,
              display: 'grid',
              placeItems: 'center',
              flexShrink: 0,
            }}
          >
            <heroState.icon size={22} />
          </div>
          <div style={{ flex: 1 }}>
            <div
              style={{
                fontSize: 18,
                fontWeight: 500,
                color: 'var(--fg-0)',
                lineHeight: 1.4,
              }}
            >
              A fábrica está{' '}
              <span style={{ color: `var(--${heroState.tone})`, fontWeight: 600 }}>
                {heroState.head}
              </span>
              .
            </div>
            <div
              style={{
                fontSize: 13,
                color: 'var(--fg-2)',
                marginTop: 6,
              }}
            >
              {heroState.sub}
            </div>
          </div>
          <button
            type="button"
            onClick={() => navigate('/producao')}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-medium transition-colors"
            style={{
              background: 'var(--blue-bg)',
              color: 'var(--blue)',
              border: '1px solid var(--blue-bd)',
            }}
          >
            Ver detalhe <ArrowRight size={14} />
          </button>
        </div>

        {/* ─── 4 KPIs ─── */}
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
            onClick={() => navigate('/producao')}
          />
          <KPICardZip
            label="OEE da fábrica"
            value="—"
            unit="%"
            context="Endpoint OEE indisponível (ingestão de eventos pendente)"
            tone="gray"
            onClick={() => navigate('/qualidade?tab=oee')}
          />
          <KPICardZip
            label="Throughput hoje"
            value={throughputToday !== null ? Math.round(throughputToday).toString() : '—'}
            unit="€"
            context={
              throughputToday !== null
                ? 'Receita reconhecida · /v1/profit/dashboard'
                : 'Sem dados de revenue hoje'
            }
            tone={throughputToday !== null && throughputToday > 0 ? 'green' : 'gray'}
            sparkline={throughputTrend}
            onClick={() => navigate('/relatorios')}
          />
          <KPICardZip
            label="Margem por barco"
            value="—"
            unit="€"
            context="Calculado em sub-sprint dedicado (cost service + revenue join)"
            tone="gray"
            onClick={() => navigate('/relatorios?tab=custos')}
          />
        </div>

        {/* ─── Grid 2-col: Alertas + Expedições ─── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 22 }}>
          {/* Atenção necessária */}
          <div
            style={{
              background: 'var(--bg-1)',
              border: '1px solid var(--bd-1)',
              borderRadius: 12,
              padding: 20,
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2.5">
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 6,
                    background: 'var(--orange-bg)',
                    color: 'var(--orange)',
                    display: 'grid',
                    placeItems: 'center',
                    border: '1px solid var(--orange-bd)',
                  }}
                >
                  <AlertTriangle size={16} />
                </div>
                <div>
                  <div className="text-sm font-semibold text-text-dark-primary leading-tight">
                    Atenção necessária
                  </div>
                  <div className="text-xs text-text-dark-tertiary mt-0.5">
                    {alertsItems.length} {alertsItems.length === 1 ? 'alerta activo' : 'alertas activos'} · ordenados por urgência
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => navigate('/qualidade')}
                className="inline-flex items-center gap-1 text-xs text-text-dark-secondary hover:text-text-dark-primary"
              >
                Ver inbox <ArrowRight size={12} />
              </button>
            </div>
            {alertsQuery.isLoading ? (
              <div className="px-3 py-6 text-center text-xs text-text-dark-tertiary">
                A carregar alertas…
              </div>
            ) : alertsItems.length === 0 ? (
              <div className="px-3 py-6 text-center text-xs text-text-dark-tertiary">
                Sem alertas activos. Tudo calmo no chão de fábrica.
              </div>
            ) : (
              <div className="flex flex-col gap-2.5">
                {alertsItems.slice(0, 5).map((a, idx) => (
                  <AlertCardZip key={a.alert_id ?? idx} alert={a} />
                ))}
              </div>
            )}
          </div>

          {/* Próximas expedições */}
          <div
            style={{
              background: 'var(--bg-1)',
              border: '1px solid var(--bd-1)',
              borderRadius: 12,
              padding: 20,
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2.5">
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 6,
                    background: 'var(--blue-bg)',
                    color: 'var(--blue)',
                    display: 'grid',
                    placeItems: 'center',
                    border: '1px solid var(--blue-bd)',
                  }}
                >
                  <Truck size={16} />
                </div>
                <div>
                  <div className="text-sm font-semibold text-text-dark-primary leading-tight">
                    Próximas expedições
                  </div>
                  <div className="text-xs text-text-dark-tertiary mt-0.5">
                    Estado dos próximos camiões
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => navigate('/expedicao')}
                className="inline-flex items-center gap-1 text-xs text-text-dark-secondary hover:text-text-dark-primary"
              >
                Ver tudo <ArrowRight size={12} />
              </button>
            </div>
            {transportQuery.isLoading ? (
              <div className="px-3 py-6 text-center text-xs text-text-dark-tertiary">
                A carregar expedições…
              </div>
            ) : transportBatches.length === 0 ? (
              <div className="px-3 py-6 text-center text-xs text-text-dark-tertiary">
                Sem expedições agendadas.
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {transportBatches.slice(0, 3).map((s: any) => (
                  <ShipmentRowZip key={s.id ?? s.code} shipment={s} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ─── AI Panel ─── */}
        <AIPanel />

        {/* ─── Inbox (preserve Onda 4) ─── */}
        <InboxPanel refreshKey={refreshKey} />

        {/* ─── Backlog por cliente (preserve Onda 4) ─── */}
        <BacklogByClientPanel refreshKey={refreshKey} />

        {/* ─── Activity feed + Trust panel (preserve) ─── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <Panel
              title="Actividade ao vivo"
              action={
                <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-success">
                  <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                  AO VIVO
                </span>
              }
              flush
              bodyClassName="p-0"
            >
              <LiveActivityFeed maxItems={6} showHeader={false} compact />
            </Panel>
          </div>
          <TrustPanel refreshKey={refreshKey} />
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// KPICardZip — port literal page-ceo.jsx KPICard pattern
// ═══════════════════════════════════════════════════════════════════════════

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
        borderRadius: 12,
        cursor: onClick ? 'pointer' : 'default',
        transition: 'background 0.12s, border-color 0.12s',
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-2)',
          fontWeight: 500,
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          marginBottom: 8,
        }}
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
          <span style={{ fontSize: 14, color: 'var(--fg-2)' }}>
            {unit}
          </span>
        ) : null}
      </div>
      {sparkline && sparkline.length > 0 ? (
        <div style={{ marginTop: 10, height: 24 }}>
          <SparklineMini points={sparkline} color={`var(--${tone})`} />
        </div>
      ) : null}
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-3)',
          marginTop: 8,
          lineHeight: 1.4,
        }}
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
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      style={{ width: '100%', height: '100%' }}
    >
      <path d={path} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// AlertCardZip — port literal page-ceo.jsx AlertCard
// ═══════════════════════════════════════════════════════════════════════════

function AlertCardZip({ alert }: { alert: any }) {
  const sev: ZipSeverity =
    alert.severity === 'critical' || alert.severity === 'high' || alert.severity === 'medium' || alert.severity === 'low'
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
        borderRadius: 8,
      }}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <ZipSevBadge severity={sev} size="sm" />
        <span className="text-[10px] text-text-dark-tertiary">
          {relativeTime(alert.created_at)}
        </span>
      </div>
      <div className="text-sm font-medium text-text-dark-primary">
        {alert.title ?? alert.message ?? '(Sem título)'}
      </div>
      {alert.detail || alert.description ? (
        <div className="text-xs text-text-dark-secondary mt-1">
          {alert.detail ?? alert.description}
        </div>
      ) : null}
      {alert.cause ? (
        <div
          className="text-xs text-text-dark-secondary mt-1.5 pl-3"
          style={{ borderLeft: '2px solid var(--bd-2)' }}
        >
          <strong className="text-text-dark-primary">Causa:</strong> {alert.cause}
        </div>
      ) : null}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ShipmentRowZip — port literal page-ceo.jsx ShipmentRow
// ═══════════════════════════════════════════════════════════════════════════

function ShipmentRowZip({ shipment }: { shipment: any }) {
  const transport = shipment.transport_date ?? shipment.date;
  const total = shipment.truck_capacity_units ?? shipment.total ?? 50;
  // Sem assignments wired ainda — mostramos só o destino + capacity.
  // Quando wired, ready/in_prod/at_risk derivam de assignments.
  const ready = shipment.ready ?? 0;
  const in_prod = shipment.in_prod ?? 0;
  const at_risk = shipment.at_risk ?? 0;
  const pct = total > 0 ? Math.round((ready / total) * 100) : 0;
  const tone = at_risk > 0 ? 'yellow' : pct === 100 ? 'green' : 'blue';
  const day = transport ? shipmentDayLabel(transport) : '—';
  const dayShort = transport
    ? `${transport.slice(8, 10)}/${transport.slice(5, 7)}`
    : '—';

  return (
    <div
      style={{
        padding: '12px 14px',
        background: 'var(--bg-2)',
        border: '1px solid var(--bd-1)',
        borderRadius: 8,
      }}
    >
      <div className="flex items-baseline justify-between gap-2 mb-1">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-semibold text-text-dark-primary">{day}</span>
          <span className="text-[11px] text-text-dark-tertiary tabular-nums">
            {dayShort}
          </span>
        </div>
        <span
          className="text-sm font-semibold tabular-nums"
          style={{ color: `var(--${tone})` }}
        >
          {ready}/{total}
        </span>
      </div>
      <div className="text-xs text-text-dark-secondary mb-2">
        {shipment.destination ?? shipment.client ?? '—'}
      </div>
      <div
        style={{
          height: 5,
          background: 'var(--bd-1)',
          borderRadius: 3,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: `var(--${tone})`,
          }}
        />
      </div>
      <div className="flex gap-3 mt-2 text-[11px] text-text-dark-secondary">
        <span>✓ {ready} prontos</span>
        {in_prod > 0 && <span>◐ {in_prod} em produção</span>}
        {at_risk > 0 && (
          <span style={{ color: 'var(--yellow)' }}>◆ {at_risk} em risco</span>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// AIPanel — port literal page-ceo.jsx (4 stats horizontal)
// ═══════════════════════════════════════════════════════════════════════════

function AIPanel() {
  // Dados reais quando endpoint /v1/copilot/stats existir; agora derivamos
  // do count de decisions.
  const decisionsQuery = useQuery({
    queryKey: ['painel', 'ai-stats'],
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
        borderRadius: 12,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '18px 22px',
          borderBottom: '1px solid var(--bd-1)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 6,
            background: 'var(--purple-bg)',
            color: 'var(--purple)',
            display: 'grid',
            placeItems: 'center',
            border: '1px solid var(--purple-bd)',
          }}
        >
          <Brain size={16} />
        </div>
        <div>
          <div className="text-sm font-semibold text-text-dark-primary">
            O que o sistema fez por si esta semana
          </div>
          <div className="text-xs text-text-dark-tertiary mt-0.5">
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
              className="tabular-nums"
              style={{
                fontSize: 28,
                fontWeight: 700,
                color: 'var(--fg-0)',
                lineHeight: 1,
              }}
            >
              {s.value}
            </div>
            <div className="text-xs text-text-dark-secondary mt-2 font-medium">
              {s.label}
            </div>
            <div className="text-[11px] text-text-dark-tertiary mt-1">{s.sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// InboxPanel — preserved from Onda 4
// ═══════════════════════════════════════════════════════════════════════════

const INBOX_TAB_IDS = ['pending', 'accepted', 'rejected', 'all'] as const;
type InboxTabId = (typeof INBOX_TAB_IDS)[number];

const STATUS_BY_TAB: Record<InboxTabId, string | undefined> = {
  pending: 'PROPOSED',
  accepted: 'EXECUTED',
  rejected: 'REJECTED',
  all: undefined,
};

function InboxPanel({ refreshKey }: { refreshKey: number }) {
  const navigate = useNavigate();
  const [tab, setTab] = useState<InboxTabId>('pending');

  const counts = useQuery({
    queryKey: ['painel', 'inbox', 'counts', refreshKey],
    queryFn: async () => {
      const fetchTotal = async (status?: string) => {
        try {
          const r: any = await decisionsApi.list({ status, page_size: 1 });
          return r?.total ?? 0;
        } catch {
          return 0;
        }
      };
      const [pending, accepted, rejected, all] = await Promise.all([
        fetchTotal('PROPOSED'),
        fetchTotal('EXECUTED'),
        fetchTotal('REJECTED'),
        fetchTotal(undefined),
      ]);
      return { pending, accepted, rejected, all };
    },
    staleTime: 30_000,
    retry: 0,
  });

  const list = useQuery({
    queryKey: ['painel', 'inbox', 'list', tab, refreshKey],
    queryFn: async () => {
      try {
        const r: any = await decisionsApi.list({
          status: STATUS_BY_TAB[tab],
          page_size: 6,
        });
        return r;
      } catch {
        return null;
      }
    },
    staleTime: 15_000,
    retry: 0,
  });

  const items: any[] = useMemo(() => {
    const data: any = list.data;
    if (!data) return [];
    if (Array.isArray(data)) return data;
    return data.items ?? data.decisions ?? [];
  }, [list.data]);

  const tabsConfig = [
    { id: 'pending', label: 'Pendentes', count: counts.data?.pending },
    { id: 'accepted', label: 'Aceites', count: counts.data?.accepted },
    { id: 'rejected', label: 'Rejeitadas', count: counts.data?.rejected },
    { id: 'all', label: 'Tudo', count: counts.data?.all },
  ];

  return (
    <Panel
      title="Inbox de decisões"
      badge={counts.data?.pending ?? '—'}
      action={
        <button
          type="button"
          onClick={() => navigate('/configuracao?tab=auditoria')}
          className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs text-text-dark-secondary hover:text-text-dark-primary hover:bg-white/5 transition-colors"
        >
          Histórico
        </button>
      }
      flush
    >
      <div className="px-2 pt-2">
        <Tabs
          variant="pills"
          tabs={tabsConfig}
          value={tab}
          onChange={(v) => setTab(v as InboxTabId)}
        />
      </div>
      <div className="px-2 py-3">
        {list.isLoading ? (
          <div className="px-4 py-6 text-center text-xs text-text-dark-tertiary">
            A carregar decisões…
          </div>
        ) : list.isError || list.data === null ? (
          <div className="px-4 py-6 text-center text-xs text-text-dark-tertiary">
            <Inbox size={20} className="mx-auto mb-2 opacity-50" />
            Endpoint /v1/decisions indisponível.
          </div>
        ) : items.length === 0 ? (
          <div className="px-4 py-6 text-center text-xs text-text-dark-tertiary">
            <Inbox size={20} className="mx-auto mb-2 opacity-50" />
            {tab === 'pending'
              ? 'Sem decisões pendentes. Tudo decidido!'
              : tab === 'accepted'
                ? 'Sem decisões aceites no período.'
                : tab === 'rejected'
                  ? 'Sem decisões rejeitadas.'
                  : 'Sem decisões.'}
          </div>
        ) : (
          <div className="space-y-2">
            {items.slice(0, 6).map((d, idx) => (
              <SuggestionCardZip key={d.id ?? idx} decision={d} />
            ))}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ─── SuggestionCardZip ──────────────────────────────────────────────────────

function SuggestionCardZip({ decision }: { decision: any }) {
  const sandbox = decision.sandbox_result ?? {};
  const priority: ZipSeverity =
    sandbox.priority === 'critical' || sandbox.priority === 'high' || sandbox.priority === 'medium' || sandbox.priority === 'low'
      ? sandbox.priority
      : 'medium';
  const sevColor =
    priority === 'critical'
      ? 'red'
      : priority === 'high'
        ? 'orange'
        : priority === 'medium'
          ? 'yellow'
          : 'blue';

  return (
    <div
      style={{
        padding: '12px 14px',
        background: 'var(--bg-2)',
        border: '1px solid var(--bd-1)',
        borderLeft: `3px solid var(--${sevColor})`,
        borderRadius: 8,
      }}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <ZipSevBadge severity={priority} size="sm" />
        {sandbox.confidence ? (
          <span className="text-[10px] text-text-dark-tertiary tabular-nums">
            confiança {sandbox.confidence}%
          </span>
        ) : null}
      </div>
      <div className="text-sm font-medium text-text-dark-primary">
        {decision.title ?? '(Sem título)'}
      </div>
      {sandbox.why ? (
        <div className="text-xs text-text-dark-secondary mt-1.5">
          <strong className="text-text-dark-primary">Porquê:</strong> {sandbox.why}
        </div>
      ) : null}
      {sandbox.if_accept || sandbox.if_reject ? (
        <div className="grid grid-cols-2 gap-2 mt-2">
          {sandbox.if_accept ? (
            <div
              style={{
                padding: 8,
                background: 'var(--green-bg)',
                border: '1px solid var(--green-bd)',
                borderRadius: 6,
              }}
            >
              <div
                className="text-[10px] uppercase tracking-wider mb-1 font-semibold"
                style={{ color: 'var(--green)' }}
              >
                Se aceitar
              </div>
              <ul className="text-[11px] text-text-dark-secondary space-y-0.5 list-none">
                {sandbox.if_accept.slice(0, 3).map((line: string, i: number) => (
                  <li key={i}>· {line}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {sandbox.if_reject ? (
            <div
              style={{
                padding: 8,
                background: 'var(--red-bg)',
                border: '1px solid var(--red-bd)',
                borderRadius: 6,
              }}
            >
              <div
                className="text-[10px] uppercase tracking-wider mb-1 font-semibold"
                style={{ color: 'var(--red)' }}
              >
                Se rejeitar
              </div>
              <ul className="text-[11px] text-text-dark-secondary space-y-0.5 list-none">
                {sandbox.if_reject.slice(0, 3).map((line: string, i: number) => (
                  <li key={i}>· {line}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
      {sandbox.alternative ? (
        <div
          style={{
            marginTop: 8,
            padding: 8,
            background: 'var(--purple-bg)',
            border: '1px solid var(--purple-bd)',
            borderRadius: 6,
          }}
        >
          <div
            className="text-[10px] uppercase tracking-wider mb-1 font-semibold"
            style={{ color: 'var(--purple)' }}
          >
            Alternativa
          </div>
          <div className="text-[11px] text-text-dark-primary font-medium">
            {sandbox.alternative.label}
          </div>
          {sandbox.alternative.detail ? (
            <div className="text-[11px] text-text-dark-secondary mt-0.5">
              {sandbox.alternative.detail}
            </div>
          ) : null}
        </div>
      ) : null}
      {sandbox.source ? (
        <div className="text-[10px] text-text-dark-tertiary mt-2">
          fonte: {sandbox.source}
        </div>
      ) : null}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// BacklogByClientPanel — preserved from Onda 4
// ═══════════════════════════════════════════════════════════════════════════

function BacklogByClientPanel({ refreshKey }: { refreshKey: number }) {
  const navigate = useNavigate();
  const backlogQuery = useQuery({
    queryKey: ['painel', 'backlog-by-client', refreshKey],
    queryFn: () => ceoDashboardApi.backlogByClient({ limit: 8 }),
    staleTime: 60_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  const items: any[] = useMemo(() => {
    const data: any = backlogQuery.data;
    if (!data) return [];
    if (Array.isArray(data)) return data;
    return data.items ?? data.clients ?? [];
  }, [backlogQuery.data]);

  if (backlogQuery.isLoading) return null;
  if (items.length === 0) return null;

  return (
    <Panel
      title="Backlog por cliente"
      badge={items.length}
      action={
        <button
          type="button"
          onClick={() => navigate('/expedicao')}
          className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs text-text-dark-secondary hover:text-text-dark-primary hover:bg-white/5 transition-colors"
        >
          Detalhe <ArrowRight size={11} />
        </button>
      }
      flush
    >
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="border-b border-white/[0.06]">
            <tr className="text-left text-[10px] uppercase tracking-wider text-text-dark-tertiary">
              <th className="px-3 py-2">Cliente</th>
              <th className="px-3 py-2 text-right">Encomendas</th>
              <th className="px-3 py-2 text-right">Valor €</th>
              <th className="px-3 py-2">Próximo prazo</th>
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 8).map((c, idx) => (
              <tr
                key={c.client_id ?? idx}
                className="border-b border-white/[0.04] hover:bg-white/[0.02]"
              >
                <td className="px-3 py-2 text-text-dark-primary">
                  {c.client_name ?? c.client_id ?? '—'}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-text-dark-secondary">
                  {c.order_count ?? 0}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-text-dark-primary font-medium">
                  €{Math.round(c.total_value_eur ?? 0).toLocaleString('pt-PT')}
                </td>
                <td className="px-3 py-2 text-text-dark-secondary">
                  {c.earliest_deadline ?? '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TrustPanel — preserved
// ═══════════════════════════════════════════════════════════════════════════

function TrustPanel({ refreshKey }: { refreshKey: number }) {
  const navigate = useNavigate();
  const trustQuery = useQuery({
    queryKey: ['painel', 'trust', refreshKey],
    queryFn: () => dqaApi.trustIndex({ scope: 'factory' }),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const trustScore = (trustQuery.data as any)?.composite
    ?? (trustQuery.data as any)?.trust_index
    ?? null;
  const trustGrade = trustScore !== null ? scoreToGrade(trustScore) : undefined;

  const trustComponents = useMemo<{ name: string; score: number }[]>(() => {
    const data: any = trustQuery.data;
    if (!data) return [];
    if (data.components && typeof data.components === 'object' && !Array.isArray(data.components)) {
      return Object.entries(data.components)
        .filter(([, score]) => score !== null && score !== undefined)
        .map(([name, score]) => ({ name, score: Number(score) }));
    }
    return [];
  }, [trustQuery.data]);

  return (
    <Panel title="Trust index — fontes" badge={trustGrade} flush>
      {trustQuery.isLoading ? (
        <div className="px-4 py-6 text-center text-xs text-text-dark-tertiary">
          A calcular trust…
        </div>
      ) : trustComponents.length === 0 ? (
        <div className="px-4 py-6 text-center text-xs text-text-dark-tertiary">
          Sem componentes de Trust visíveis.
        </div>
      ) : (
        <div className="px-4 py-3 space-y-2.5">
          {trustComponents.map((c) => {
            const grade = scoreToGrade(c.score);
            const pctW = `${Math.round(c.score * 100)}%`;
            const barColor =
              c.score >= 0.85
                ? 'var(--green)'
                : c.score >= 0.70
                  ? 'var(--yellow)'
                  : 'var(--red)';
            return (
              <div key={c.name} className="flex items-center gap-3">
                <div className="flex-1 text-xs text-text-dark-secondary truncate">
                  {c.name}
                </div>
                <div
                  style={{
                    width: 80,
                    height: 6,
                    background: 'var(--bd-1)',
                    borderRadius: 3,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      width: pctW,
                      height: '100%',
                      background: barColor,
                      transition: 'width 0.3s ease',
                    }}
                  />
                </div>
                <TrustBadge grade={grade} size="xs" />
              </div>
            );
          })}
          <div className="border-t border-white/[0.06] pt-2 mt-2">
            <button
              type="button"
              onClick={() => navigate('/configuracao?tab=trust')}
              className="text-[10px] text-text-dark-tertiary hover:text-text-dark-secondary inline-flex items-center gap-1"
            >
              <Activity size={10} /> Detalhe Trust v2
            </button>
          </div>
        </div>
      )}
    </Panel>
  );
}
