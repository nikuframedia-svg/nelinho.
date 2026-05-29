/**
 * KPIsTab — tab KPIs da LLMPage (Q.115.N)
 * =========================================
 *
 * Layout 2 colunas: lista à esquerda (1/3) + detalhe à direita (2/3).
 * Dados de GET /v1/profit/kpis/snapshot-explained, polling 30s.
 * Gráfico de tendência: GET /v1/profit/kpis/{name}/history (Q.117.D),
 * alimentado pelo snapshot diário (profit.kpi_snapshot). Enquanto não
 * houver ≥2 dias, mostra empty state honesto — nunca pontos inventados.
 *
 * ZERO MOCKS.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart3, RefreshCw, AlertTriangle, TrendingUp, Sparkles } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkButton, DarkBadge } from '../../components/dark';
import { LineChart } from '../../components/charts';
import { kpisApi } from '../../lib/api';
import { profitKeys } from '../../lib/api/keys';
import { OtdHeatmap } from './OtdHeatmap';

// ── Tipos locais (espelham snapshot-explained) ───────────────────────────

interface KPIValue {
  value: number | null;
  reason?: string | null;
  citations?: Array<{ label: string }>;
}

interface KPISnapshot {
  updated_at?: string;
  quality_fpy?: KPIValue;
  rework_rate?: KPIValue;
  orders_total?: KPIValue;
  orders_in_progress?: KPIValue;
  orders_completed?: KPIValue;
  [key: string]: unknown;
}

interface KPIItem {
  name: string;
  label: string;
  value: number | null;
  unit: string;
  status: 'ok' | 'aviso' | 'alerta' | 'sem-dados';
}

function resolveStatus(name: string, value: number | null): KPIItem['status'] {
  if (value === null) return 'sem-dados';
  if (name === 'rework_rate') return value > 5 ? 'alerta' : value > 2 ? 'aviso' : 'ok';
  if (name === 'quality_fpy') return value < 90 ? 'alerta' : value < 95 ? 'aviso' : 'ok';
  return 'ok';
}

const STATUS_VARIANT: Record<KPIItem['status'], 'success' | 'warning' | 'danger' | 'neutral'> = {
  ok: 'success',
  aviso: 'warning',
  alerta: 'danger',
  'sem-dados': 'neutral',
};

const STATUS_LABEL: Record<KPIItem['status'], string> = {
  ok: 'Ok',
  aviso: 'Aviso',
  alerta: 'Fora de banda',
  'sem-dados': 'Sem dados',
};

const KPI_META: Record<string, { label: string; unit: string }> = {
  quality_fpy: { label: 'Qualidade (FPY)', unit: '%' },
  rework_rate: { label: 'Taxa de retrabalho', unit: '%' },
  orders_total: { label: 'Total de ordens', unit: '' },
  orders_in_progress: { label: 'Ordens em curso', unit: '' },
  orders_completed: { label: 'Ordens concluídas', unit: '' },
};

function snapshotToList(snapshot: KPISnapshot): KPIItem[] {
  return Object.entries(KPI_META).map(([name, meta]) => {
    const entry = snapshot[name] as KPIValue | undefined;
    const value = entry?.value ?? null;
    return {
      name,
      label: meta.label,
      value,
      unit: meta.unit,
      status: resolveStatus(name, value),
    };
  });
}

// ── Componente principal ─────────────────────────────────────────────────

export function KPIsTab() {
  const [selected, setSelected] = useState<string | null>(null);

  const snapshotQuery = useQuery({
    queryKey: ['kpis', 'snapshot-explained', 'llm-tab'],
    queryFn: () => kpisApi.getSnapshotExplained(),
    refetchInterval: 30_000,
    refetchOnWindowFocus: false,
  });

  const raw = snapshotQuery.data?.snapshot as KPISnapshot | undefined;
  const items: KPIItem[] = raw ? snapshotToList(raw) : [];
  const selectedItem = items.find((k) => k.name === selected) ?? null;

  const lastUpdated = raw?.updated_at
    ? new Date(raw.updated_at as string).toLocaleString('pt-PT')
    : null;

  return (
    <DarkPageLayout
      breadcrumbs={[{ label: 'Sistema' }, { label: 'LLM' }, { label: 'KPIs' }]}
      title="KPIs"
      subtitle="Indicadores calculados a partir da base de dados · actualização a cada 30s"
      icon={<BarChart3 className="h-6 w-6" />}
    >
      {/* Estado de erro */}
      {snapshotQuery.isError && (
        <DarkCard className="mb-5 border-danger/30 bg-danger/5">
          <div className="flex items-center gap-3">
            <AlertTriangle size={18} className="text-danger shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-fg-1">Falha ao carregar KPIs</p>
              <p className="text-xs text-fg-3 mt-0.5">
                {(snapshotQuery.error as Error)?.message ?? 'Erro desconhecido'}
              </p>
            </div>
            <DarkButton variant="ghost" icon={<RefreshCw size={13} />} onClick={() => snapshotQuery.refetch()}>
              Tentar novamente
            </DarkButton>
          </div>
        </DarkCard>
      )}

      {lastUpdated && (
        <p className="text-xs text-fg-3 mb-4">
          Última actualização: {lastUpdated}
        </p>
      )}

      {/* Layout 2 colunas */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-4">
        {/* Esquerda — lista KPIs */}
        <div>
          <p className="text-[10.5px] uppercase tracking-wide font-semibold text-fg-3 mb-2">
            KPIs disponíveis
          </p>

          {snapshotQuery.isLoading ? (
            <DarkCard className="text-center py-10">
              <p className="text-sm text-fg-3">A carregar KPIs…</p>
            </DarkCard>
          ) : items.length === 0 ? (
            <DarkCard className="text-center py-10">
              <BarChart3 className="h-8 w-8 text-fg-3 mx-auto mb-2" />
              <p className="text-sm text-fg-2">Sem KPIs calculados.</p>
              <p className="text-xs text-fg-3 mt-1">
                Os KPIs são calculados a partir das ordens de fabrico. Verifica que há dados no ERP.
              </p>
            </DarkCard>
          ) : (
            <div className="flex flex-col gap-1.5">
              {items.map((kpi) => {
                const active = selected === kpi.name;
                return (
                  <button
                    key={kpi.name}
                    type="button"
                    onClick={() => setSelected(active ? null : kpi.name)}
                    className={[
                      'w-full text-left rounded-lg border transition-colors px-3 py-2.5',
                      active
                        ? 'border-accent bg-bg-3'
                        : 'border-bd-1 bg-bg-1 hover:border-bd-2',
                    ].join(' ')}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-fg-1 truncate">{kpi.label}</span>
                      <DarkBadge variant={STATUS_VARIANT[kpi.status]}>
                        {STATUS_LABEL[kpi.status]}
                      </DarkBadge>
                    </div>
                    <div className="mt-1 flex items-baseline gap-1">
                      {kpi.value !== null ? (
                        <>
                          <span className="text-xl font-bold text-fg-0">
                            {kpi.value.toFixed(kpi.unit === '%' ? 1 : 0)}
                          </span>
                          {kpi.unit && (
                            <span className="text-xs text-fg-3">{kpi.unit}</span>
                          )}
                        </>
                      ) : (
                        <span className="text-sm text-fg-3">— sem dados</span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Direita — detalhe / gráfico */}
        <div>
          <p className="text-[10.5px] uppercase tracking-wide font-semibold text-fg-3 mb-2">
            Detalhe
          </p>
          {selectedItem ? (
            <KPIDetail kpi={selectedItem} />
          ) : (
            <DarkCard className="text-center py-16">
              <BarChart3 className="h-10 w-10 text-fg-3 mx-auto mb-3" />
              <h3 className="text-base font-medium text-fg-1 mb-1">
                Selecciona um KPI
              </h3>
              <p className="text-sm text-fg-2">
                Vês aqui o histórico e o contexto do indicador seleccionado.
              </p>
            </DarkCard>
          )}
        </div>
      </div>

      {/* Q.118.K — mapa de calor OTD (produto × semana) */}
      <OtdHeatmap />
    </DarkPageLayout>
  );
}

// ── Componente de detalhe ────────────────────────────────────────────────

function KPIDetail({ kpi }: { kpi: KPIItem }) {
  // Q.117.D — série histórica real de GET /v1/profit/kpis/{name}/history.
  const historyQuery = useQuery({
    queryKey: profitKeys.kpiHistory(kpi.name, 30),
    queryFn: () => kpisApi.getHistory(kpi.name, 30),
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  });

  // Pontos com valor (saltamos dias sem dados — nunca inventamos um zero).
  const chartData = (historyQuery.data?.points ?? [])
    .filter((p): p is { date: string; value: number } => p.value !== null)
    .map((p) => ({
      name: new Date(p.date).toLocaleDateString('pt-PT', { day: '2-digit', month: '2-digit' }),
      value: p.value,
    }));

  return (
    <DarkCard>
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h3 className="text-base font-semibold text-fg-0">{kpi.label}</h3>
          <div className="flex items-baseline gap-1.5 mt-1">
            {kpi.value !== null ? (
              <>
                <span className="text-2xl font-bold text-fg-0">
                  {kpi.value.toFixed(kpi.unit === '%' ? 1 : 0)}
                </span>
                {kpi.unit && <span className="text-sm text-fg-3">{kpi.unit}</span>}
              </>
            ) : (
              <span className="text-lg text-fg-3">— sem dados</span>
            )}
          </div>
        </div>
        <DarkBadge variant={STATUS_VARIANT[kpi.status]}>
          {STATUS_LABEL[kpi.status]}
        </DarkBadge>
      </div>

      {/* Q.118.O — investigar a causa via copiloto (caminho diagnostic/causal) */}
      <div className="mb-4">
        <DarkButton
          variant="ghost"
          icon={<Sparkles size={13} />}
          onClick={() =>
            window.dispatchEvent(
              new CustomEvent('copilot:open', {
                detail: {
                  query:
                    kpi.value !== null
                      ? `Porque está a ${kpi.label} em ${kpi.value.toFixed(kpi.unit === '%' ? 1 : 0)}${kpi.unit}? Investiga a causa.`
                      : `Porque é que a ${kpi.label} não tem dados? Investiga.`,
                },
              }),
            )
          }
        >
          Investigar (porquê?)
        </DarkButton>
      </div>

      {/* Gráfico de tendência (últimos 30 dias) */}
      <div className="mb-1">
        <p className="text-[10.5px] uppercase tracking-wide font-semibold text-fg-3 mb-2">
          Tendência (30 dias)
        </p>
      </div>

      {historyQuery.isLoading ? (
        <div
          className="rounded-lg border border-bd-1 bg-bg-1 flex items-center justify-center"
          style={{ minHeight: 200 }}
        >
          <p className="text-sm text-fg-3">A carregar histórico…</p>
        </div>
      ) : chartData.length >= 2 ? (
        <div className="rounded-lg border border-bd-1 bg-bg-1 p-2">
          <LineChart
            data={chartData}
            height={200}
            color={kpi.status === 'alerta' ? '#ef4444' : kpi.status === 'aviso' ? '#f59e0b' : '#14b8a6'}
            showGrid
            showArea
          />
        </div>
      ) : (
        <div
          className="rounded-lg border border-dashed border-bd-2 bg-bg-1 flex flex-col items-center justify-center gap-2 py-10 px-6 text-center"
          style={{ minHeight: 200 }}
        >
          <TrendingUp className="h-8 w-8 text-fg-3" />
          <p className="text-sm font-medium text-fg-2">Histórico a acumular</p>
          <p className="text-xs text-fg-3 max-w-xs leading-relaxed">
            A tendência aparece quando houver pelo menos 2 dias de dados. O
            snapshot diário corre às 00:45 (UTC) — volta amanhã para ver a curva.
          </p>
        </div>
      )}
    </DarkCard>
  );
}
