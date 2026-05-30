/**
 * KPIsTab — tab KPIs da LLMPage (Q.R: ligada ao Cube)
 * ===================================================
 *
 * Mostra as MEASURES REAIS do Cube (operações NELO via marts) em vez do
 * caminho legacy /v1/profit/kpis/* (quase vazio). Fonte:
 * GET /api/copilot/cube/dashboard-dev (determinístico, sem LLM).
 *
 * Cards (valor actual) + gráficos (séries). Degradação honesta: uma measure
 * cujo mart ainda não está populado mostra "sem dados" — nunca valores inventados.
 *
 * ZERO MOCKS.
 */

import { useQuery } from '@tanstack/react-query';
import { BarChart3, RefreshCw, AlertTriangle, Sparkles, Database } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkButton, DarkBadge } from '../../components/dark';
import { LineChart, BarChart } from '../../components/charts';
import { cubeApi } from '../../lib/api';
import type { CubeDashboardCard, CubeDashboardChart } from '../../lib/api';
import { OtdHeatmap } from './OtdHeatmap';

// ── Formatação ────────────────────────────────────────────────────────────

function formatValue(card: CubeDashboardCard): string {
  if (card.value === null) return '—';
  const v = card.value;
  if (card.unit === '%') return `${(v * 100).toFixed(2)}%`; // ratio measure → %
  if (card.unit === '€') return `${v.toLocaleString('pt-PT', { maximumFractionDigits: 0 })} €`;
  return Number.isInteger(v)
    ? v.toLocaleString('pt-PT')
    : v.toLocaleString('pt-PT', { maximumFractionDigits: 2 });
}

const COLORS = ['#4ea7c1', '#7bb274', '#c9a72a', '#b97fc9', '#d6845a', '#5aa9d6'];

// ── Componente principal ─────────────────────────────────────────────────

export function KPIsTab() {
  const dashQuery = useQuery({
    queryKey: ['cube', 'dashboard-dev'],
    queryFn: () => cubeApi.dashboard(),
    refetchInterval: 60_000,
    refetchOnWindowFocus: false,
  });

  const cards = dashQuery.data?.cards ?? [];
  const charts = dashQuery.data?.charts ?? [];

  return (
    <DarkPageLayout
      breadcrumbs={[{ label: 'Sistema' }, { label: 'LLM' }, { label: 'KPIs' }]}
      title="KPIs"
      subtitle="Indicadores reais do Cube (operações NELO) · actualização a cada 60s"
      icon={<BarChart3 className="h-6 w-6" />}
      actions={
        <DarkButton
          variant="ghost"
          icon={<RefreshCw size={13} className={dashQuery.isFetching ? 'animate-spin' : ''} />}
          onClick={() => dashQuery.refetch()}
        >
          Actualizar
        </DarkButton>
      }
    >
      {/* Estado de erro global */}
      {dashQuery.isError && (
        <DarkCard className="mb-5 border-danger/30 bg-danger/5">
          <div className="flex items-center gap-3">
            <AlertTriangle size={18} className="text-danger shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-fg-1">Falha ao carregar o dashboard do Cube</p>
              <p className="text-xs text-fg-3 mt-0.5">
                {(dashQuery.error as Error)?.message ?? 'Erro desconhecido'}
              </p>
            </div>
            <DarkButton variant="ghost" icon={<RefreshCw size={13} />} onClick={() => dashQuery.refetch()}>
              Tentar novamente
            </DarkButton>
          </div>
        </DarkCard>
      )}

      {/* Cards */}
      <p className="text-[10.5px] uppercase tracking-wide font-semibold text-fg-3 mb-2">
        Indicadores
      </p>
      {dashQuery.isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 mb-7">
          {Array.from({ length: 7 }).map((_, i) => (
            <DarkCard key={i} className="h-[92px] animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 mb-7">
          {cards.map((card) => (
            <KpiCard key={card.key} card={card} />
          ))}
        </div>
      )}

      {/* Gráficos */}
      <p className="text-[10.5px] uppercase tracking-wide font-semibold text-fg-3 mb-2">
        Gráficos
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-7">
        {dashQuery.isLoading
          ? Array.from({ length: 4 }).map((_, i) => (
              <DarkCard key={i} className="h-[260px] animate-pulse" />
            ))
          : charts.map((chart, i) => <ChartCard key={chart.key} chart={chart} color={COLORS[i % COLORS.length]} />)}
      </div>

      {/* Q.118.K — mapa de calor OTD (produto × semana) */}
      <OtdHeatmap />
    </DarkPageLayout>
  );
}

// ── Card de KPI ──────────────────────────────────────────────────────────

function KpiCard({ card }: { card: CubeDashboardCard }) {
  const hasData = card.status === 'ok' && card.value !== null;

  return (
    <DarkCard className="relative group">
      <div className="flex items-start justify-between gap-2 mb-1">
        <span className="text-xs font-medium text-fg-2 leading-tight">{card.label}</span>
        {!hasData && <DarkBadge variant="neutral">sem dados</DarkBadge>}
      </div>
      <div className="flex items-baseline gap-1 mt-1.5">
        {hasData ? (
          <span className="text-2xl font-bold text-fg-0 tabular-nums">{formatValue(card)}</span>
        ) : (
          <span className="text-sm text-fg-3">—</span>
        )}
      </div>
      <button
        type="button"
        title="Investigar a causa via copiloto"
        className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-fg-3 hover:text-accent"
        onClick={() =>
          window.dispatchEvent(
            new CustomEvent('copilot:open', {
              detail: {
                query: hasData
                  ? `Porque está a ${card.label} em ${formatValue(card)}? Investiga a causa.`
                  : `Porque é que a ${card.label} não tem dados? Investiga.`,
              },
            }),
          )
        }
      >
        <Sparkles size={14} />
      </button>
    </DarkCard>
  );
}

// ── Card de gráfico ──────────────────────────────────────────────────────

function ChartCard({ chart, color }: { chart: CubeDashboardChart; color: string }) {
  const data = chart.series
    .filter((p): p is { x: string; y: number } => p.y !== null)
    .map((p) => ({ name: p.x, value: p.y }));

  return (
    <DarkCard>
      <div className="flex items-center justify-between gap-2 mb-3">
        <h3 className="text-sm font-semibold text-fg-1">{chart.label}</h3>
        {chart.status !== 'ok' && <DarkBadge variant="neutral">sem dados</DarkBadge>}
      </div>
      {data.length > 0 ? (
        <div className="rounded-lg border border-bd-1 bg-bg-1 p-2">
          {chart.kind === 'line' ? (
            <LineChart data={data} height={220} color={color} showGrid showArea />
          ) : (
            <BarChart data={data} height={220} color={color} showGrid />
          )}
        </div>
      ) : (
        <div
          className="rounded-lg border border-dashed border-bd-2 bg-bg-1 flex flex-col items-center justify-center gap-2 text-center px-6"
          style={{ minHeight: 220 }}
        >
          <Database className="h-7 w-7 text-fg-3" />
          <p className="text-sm font-medium text-fg-2">Sem dados para este indicador</p>
          <p className="text-xs text-fg-3 max-w-xs leading-relaxed">
            O mart correspondente ainda não está populado. Corre o ETL (mirror NELO +
            setup_marts) para ver a série.
          </p>
        </div>
      )}
    </DarkCard>
  );
}
