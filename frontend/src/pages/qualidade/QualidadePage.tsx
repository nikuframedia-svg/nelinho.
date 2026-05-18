/**
 * QualidadePage — port literal de design/nelo-zip/src/page-quality.jsx
 * (tab Resumo) + page-oee.jsx (tab OEE).
 *
 * Tabs:
 *   • Resumo      — page-quality.jsx port literal: 4 KPI strip + 2-col
 *                   (Erros recentes / Estado dos moldes).
 *   • Erros       — ReworkListTab filter=open (existing).
 *   • Moldes      — MoldsTab grid (existing, wired BE.3).
 *   • Retrabalho  — ReworkListTab filter=rework (existing).
 *   • Diagnóstico — ExplainPage existing (CausalChain Q.15.D).
 *   • OEE         — page-oee.jsx port literal: explainer + OEE Global +
 *                   3 breakdown cards + Throughput SVG chart + Impacto
 *                   financeiro 4 rows.
 *
 * Wire ao backend real:
 *   - /v1/quality/rework → erros recentes
 *   - /v1/plan/molds/health-report → moldes (BE.3 wired)
 *   - /v1/quality/dashboard → KPIs Resumo
 *
 * ZERO MOCKS. OEE breakdown ainda mostra placeholders honestos
 * (endpoint OEE real pendente).
 *
 * Sprint Q.18.ZIP.QUAL (refactor profundo big-bang).
 */

import { lazy, Suspense, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MoldDefectDrawer } from '../../components/molds/MoldDefectDrawer';
import {
  ShieldCheck,
  Brain,
  Activity,
  Wrench,
  AlertCircle,
  Repeat,
  RefreshCw,
  Sparkles,
  Eye,
  Boxes,
  CheckCircle2,
  Crosshair,
} from 'lucide-react';
import {
  PageHeader,
  Tabs,
  Panel,
  EmptyState,
  ZipSevBadge,
  type ZipSeverity,
} from '../../components/dark';
import { SkeletonLoader } from '../../components/ui/Skeleton';
import {
  defectZonesApi,
  employeesApi,
  getApiBase,
  qualityReworkApi,
  type DefectZoneMapResponse,
  type ReworkCreatePayload,
} from '../../lib/api';

const ExplainPage = lazy(() =>
  import('../explain/ExplainPage').then((m) => ({ default: m.ExplainPage })),
);
const TrustDqaDashboard = lazy(() =>
  import('../../components/dqa/TrustDqaDashboard').then((m) => ({ default: m.TrustDqaDashboard })),
);
const QualityIntelDashboard = lazy(() =>
  import('../../components/quality/QualityIntelPanels').then((m) => ({ default: m.QualityIntelDashboard })),
);

function askCopilot(query: string) {
  window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
}

const TAB_IDS = ['resumo', 'erros', 'moldes', 'zonas', 'retrabalho', 'diagnostico', 'oee', 'trust', 'inteligencia'] as const;
type TabId = (typeof TAB_IDS)[number];
function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

// ─── Endpoints ──────────────────────────────────────────────────────────────

// Q.21.A/B — base URL via api.ts (concorda com VITE_API_URL).
async function fetchQualityRework(filter?: 'open' | 'rework') {
  try {
    const url = filter
      ? `${getApiBase()}/v1/quality/rework?filter=${filter}&limit=20`
      : `${getApiBase()}/v1/quality/rework?limit=20`;
    const resp = await fetch(url, {
      headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' },
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

async function fetchMoldsHealthReport() {
  try {
    const resp = await fetch(
      `${getApiBase()}/v1/plan/molds/health-report?limit=24`,
      { headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' } },
    );
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

async function fetchQualityDashboard() {
  try {
    const resp = await fetch(
      `${getApiBase()}/v1/quality/dashboard?group_by=phase&top_n=10`,
      { headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' } },
    );
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════

export default function QualidadePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const activeTab: TabId = isTabId(tabFromUrl) ? tabFromUrl : 'resumo';

  const tabs = useMemo(
    () => [
      { id: 'resumo', label: 'Resumo', icon: <ShieldCheck size={13} /> },
      { id: 'erros', label: 'Erros', icon: <AlertCircle size={13} /> },
      { id: 'moldes', label: 'Moldes', icon: <Wrench size={13} /> },
      { id: 'zonas', label: 'Zonas', icon: <Crosshair size={13} /> },
      { id: 'retrabalho', label: 'Retrabalho', icon: <Repeat size={13} /> },
      { id: 'diagnostico', label: 'Diagnóstico', icon: <Brain size={13} /> },
      { id: 'oee', label: 'OEE', icon: <Activity size={13} /> },
      { id: 'trust', label: 'Trust + DQA', icon: <ShieldCheck size={13} /> },
      { id: 'inteligencia', label: 'Inteligência', icon: <Brain size={13} /> },
    ],
    [],
  );

  const handleTabChange = (id: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', id);
    setSearchParams(next, { replace: true });
  };

  const fallback = (
    <div className="p-8">
      <SkeletonLoader count={5} />
    </div>
  );

  const titleByTab = (tab: TabId) =>
    tab === 'oee'
      ? 'OEE — Eficácia da fábrica'
      : tab === 'diagnostico'
        ? 'Diagnóstico causal'
        : 'Qualidade & Defeitos';
  const subtitleByTab = (tab: TabId) =>
    tab === 'oee'
      ? 'Disponibilidade × Performance × Qualidade · 14 dias'
      : tab === 'diagnostico'
        ? 'Causal chains · ERRO-TREE · Reichenbach · Mill'
        : 'Erros recentes · estado dos moldes · padrões aprendidos';

  return (
    <div>
      <PageHeader
        title={titleByTab(activeTab)}
        subtitle={subtitleByTab(activeTab)}
        helpId={activeTab === 'oee' ? 'oee' : 'qualidade'}
        actions={
          <>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
            >
              <RefreshCw size={13} />
              Atualizar
            </button>
            <button
              type="button"
              onClick={() => askCopilot(`Quais são as causas-raiz mais frequentes na qualidade hoje?`)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-white text-xs font-medium transition-colors"
              style={{ background: 'var(--blue)', border: '1px solid var(--blue)' }}
            >
              <Sparkles size={13} />
              Pedir ao Copilot
            </button>
          </>
        }
      />

      <div className="px-6 pt-2">
        <Tabs tabs={tabs} value={activeTab} onChange={handleTabChange} sticky />
      </div>

      <div className="px-6 py-4">
        {activeTab === 'resumo' && <ResumoTab />}
        {activeTab === 'erros' && <ReworkListTab filter="open" />}
        {activeTab === 'moldes' && <MoldsTab />}
        {activeTab === 'zonas' && <ZonasTab />}
        {activeTab === 'retrabalho' && (
          <div className="space-y-4">
            <NovoRetrabalhoForm />
            <ReworkListTab filter="rework" />
          </div>
        )}
        {activeTab === 'diagnostico' && (
          <Suspense fallback={fallback}>
            <ExplainPage />
          </Suspense>
        )}
        {activeTab === 'oee' && <OEETab />}
        {activeTab === 'trust' && (
          <Suspense fallback={fallback}>
            <TrustDqaDashboard />
          </Suspense>
        )}
        {activeTab === 'inteligencia' && (
          <Suspense fallback={fallback}>
            <QualityIntelDashboard />
          </Suspense>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ResumoTab — port literal page-quality.jsx
// ═══════════════════════════════════════════════════════════════════════════

function ResumoTab() {
  const reworkQuery = useQuery({
    queryKey: ['qualidade', 'rework', 'all'],
    queryFn: () => fetchQualityRework(),
    staleTime: 60_000,
    retry: 0,
  });
  const moldsQuery = useQuery({
    queryKey: ['qualidade', 'molds-health'],
    queryFn: fetchMoldsHealthReport,
    staleTime: 60_000,
    retry: 0,
  });
  const dashboardQuery = useQuery({
    queryKey: ['qualidade', 'dashboard'],
    queryFn: fetchQualityDashboard,
    staleTime: 60_000,
    retry: 0,
  });

  const reworkItems: any[] = useMemo(() => {
    const data: any = reworkQuery.data;
    if (!data) return [];
    if (Array.isArray(data)) return data;
    return data.items ?? data.reworks ?? [];
  }, [reworkQuery.data]);

  const moldsItems: any[] = useMemo(() => {
    const data: any = moldsQuery.data;
    if (!data) return [];
    if (Array.isArray(data)) return data;
    return data.items ?? [];
  }, [moldsQuery.data]);

  // KPIs derivados
  const totalErrors = reworkItems.length;
  const totalCostEur = reworkItems.reduce(
    (sum, r) => sum + (Number(r.cost_estimate_eur) || 0),
    0,
  );
  const dashboardItems = dashboardQuery.data?.items ?? [];
  const totalOps = dashboardItems.reduce(
    (sum: number, it: any) => sum + (Number(it.total_ops) || 0),
    0,
  );
  const defectRate = totalOps > 0 ? (totalErrors / totalOps) * 100 : null;

  return (
    <div className="space-y-5 page-enter">
      {/* KPI strip — Q.23.G: 1 hero (taxa de defeito) + 3 compactos */}
      <div
        className="page-enter"
        style={{
          display: 'grid',
          gridTemplateColumns: '1.6fr 1fr 1fr 1fr',
          gap: 14,
        }}
      >
        <KPIStrip
          hero
          label="Taxa de defeito"
          value={defectRate !== null ? defectRate.toFixed(1) : '—'}
          unit="%"
          context={
            defectRate !== null
              ? `${totalErrors} erros em ${totalOps.toLocaleString('pt-PT')} operações`
              : 'Sem operações registadas para baseline'
          }
          tone={defectRate === null ? 'gray' : defectRate < 3 ? 'green' : defectRate < 6 ? 'yellow' : 'red'}
        />
        <KPIStrip
          label="Erros activos"
          value={totalErrors.toString()}
          context={
            totalErrors === 0
              ? 'Sem rework registado'
              : 'Ordenados por gravidade abaixo'
          }
          tone={totalErrors === 0 ? 'green' : totalErrors < 5 ? 'yellow' : 'red'}
        />
        <KPIStrip
          label="Custo de retrabalho"
          value={totalCostEur > 0 ? `€${Math.round(totalCostEur).toLocaleString('pt-PT')}` : '€0'}
          context="Soma cost_estimate_eur dos rework registados"
          tone={totalCostEur === 0 ? 'green' : totalCostEur < 1000 ? 'yellow' : 'red'}
        />
        <KPIStrip
          label="Moldes críticos"
          value={moldsItems.filter((m) => m.health?.risk_category === 'red').length.toString()}
          context={`${moldsItems.length} moldes monitorizados (BE.3)`}
          tone={
            moldsItems.filter((m) => m.health?.risk_category === 'red').length > 0
              ? 'red'
              : 'green'
          }
        />
      </div>

      {/* 2-col: Erros recentes + Moldes */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 22 }}>
        {/* Erros recentes */}
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
                background: 'var(--orange-bg)',
                color: 'var(--orange)',
                display: 'grid',
                placeItems: 'center',
                border: '1px solid var(--orange-bd)',
              }}
            >
              <AlertCircle size={16} />
            </div>
            <div>
              <div className="text-sm font-semibold text-text-dark-primary">
                Erros recentes
              </div>
              <div className="text-xs text-text-dark-tertiary mt-0.5">
                Últimas 24h · ordenados por gravidade
              </div>
            </div>
          </div>
          {reworkQuery.isLoading ? (
            <div className="px-4 py-8 text-center text-xs text-text-dark-tertiary">
              A carregar erros…
            </div>
          ) : reworkItems.length === 0 ? (
            <div className="px-4 py-8 text-center text-xs text-text-dark-tertiary">
              Sem erros recentes — tudo limpo.
            </div>
          ) : (
            <div>
              {reworkItems.slice(0, 8).map((e: any, i: number) => {
                const sev: ZipSeverity =
                  (e.context?.severity as ZipSeverity) ??
                  (e.severity as ZipSeverity) ??
                  'medium';
                return (
                  <div
                    key={e.id ?? i}
                    style={{
                      padding: '12px 22px',
                      borderBottom:
                        i < Math.min(reworkItems.length, 8) - 1
                          ? '1px solid var(--bd-1)'
                          : 'none',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 14,
                    }}
                  >
                    <ZipSevBadge severity={sev} size="sm" />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        className="text-sm font-medium text-text-dark-primary truncate"
                        title={`${e.of_id ?? ''} · ${e.error_description ?? e.error_code}`}
                      >
                        {e.of_id ? `#${e.of_id}` : ''} ·{' '}
                        {e.error_description ?? e.error_code}
                      </div>
                      <div className="text-[11px] text-text-dark-secondary mt-0.5">
                        {e.phase_id_causer ?? '—'}
                        {e.cost_estimate_eur
                          ? ` · €${Math.round(Number(e.cost_estimate_eur)).toLocaleString('pt-PT')}`
                          : ''}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs text-text-dark-secondary hover:text-text-dark-primary hover:bg-white/5"
                    >
                      <Eye size={12} /> Ver
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Moldes */}
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
                background: 'var(--blue-bg)',
                color: 'var(--blue)',
                display: 'grid',
                placeItems: 'center',
                border: '1px solid var(--blue-bd)',
              }}
            >
              <Boxes size={16} />
            </div>
            <div>
              <div className="text-sm font-semibold text-text-dark-primary">
                Estado dos moldes
              </div>
              <div className="text-xs text-text-dark-tertiary mt-0.5">
                Score 0-100 + risco · /v1/plan/molds/health-report
              </div>
            </div>
          </div>
          {moldsQuery.isLoading ? (
            <div className="px-4 py-8 text-center text-xs text-text-dark-tertiary">
              A carregar moldes…
            </div>
          ) : moldsItems.length === 0 ? (
            <div className="px-4 py-8 text-center text-xs text-text-dark-tertiary">
              Sem moldes registados.
            </div>
          ) : (
            <div>
              {moldsItems.slice(0, 6).map((m: any, i: number) => {
                const health = m.health ?? {};
                const score = health.score_0_100 ?? null;
                const risk = health.risk_category ?? 'green';
                const tone = risk === 'red' ? 'red' : risk === 'yellow' ? 'yellow' : 'green';
                const cycles = health.components ?? {};
                const uses = cycles.cycles_used ?? null;
                const max = cycles.cycles_max ?? null;
                const errWeek = cycles.err_rate_week;
                const errNormal = cycles.err_rate_normal;
                const pct =
                  uses !== null && max !== null && max > 0
                    ? Math.min(100, (uses / max) * 100)
                    : score !== null
                      ? 100 - score
                      : 0;
                return (
                  <div
                    key={m.id ?? i}
                    style={{
                      padding: '12px 22px',
                      borderBottom:
                        i < Math.min(moldsItems.length, 6) - 1
                          ? '1px solid var(--bd-1)'
                          : 'none',
                    }}
                  >
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium text-text-dark-primary">
                        {m.name ?? m.mold_code}
                      </span>
                      <span
                        className="text-xs tabular-nums"
                        style={{ color: `var(--${tone})` }}
                      >
                        {uses !== null && max !== null ? `${uses}/${max}` : `score ${score}/100`}
                      </span>
                    </div>
                    <div
                      style={{
                        height: 4,
                        background: 'var(--bd-1)',
                        borderRadius: 2,
                        marginTop: 6,
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
                    <div className="flex justify-between text-[11px] text-text-dark-secondary mt-1.5">
                      {errWeek !== undefined ? (
                        <span>
                          Erro:{' '}
                          <span
                            className="tabular-nums font-semibold"
                            style={{ color: `var(--${tone})` }}
                          >
                            {Math.round(Number(errWeek) * 100)}%
                          </span>{' '}
                          esta semana{' '}
                          <span className="text-text-dark-tertiary">
                            (normal {Math.round(Number(errNormal ?? 0) * 100)}%)
                          </span>
                        </span>
                      ) : (
                        <span className="text-text-dark-tertiary">
                          Score {score}/100
                        </span>
                      )}
                      {risk === 'red' ? (
                        <span style={{ color: 'var(--red)' }}>● Manutenção</span>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// OEETab — port literal page-oee.jsx
// ═══════════════════════════════════════════════════════════════════════════

// Q.21.A/B — base URL via api.ts (concorda com VITE_API_URL).
const TENANT_OEE = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };

interface OEEItem {
  group_value: string | null;
  availability: number;
  performance: number;
  quality: number;
  oee: number;
  sample_size: number;
  sample_excluded: number;
}
interface OEEResponse {
  date_from: string;
  date_to: string;
  group_by: string;
  overall: OEEItem;
  breakdown: OEEItem[];
}

async function fetchOEE(group_by?: string): Promise<OEEResponse | null> {
  const qs = group_by ? `?group_by=${group_by}` : '';
  try {
    const r = await fetch(`${getApiBase()}/v1/profit/oee${qs}`, { headers: TENANT_OEE });
    return r.ok ? r.json() : null;
  } catch { return null; }
}

// Throughput diário real (€/dia) — GET /v1/profit/dashboard devolve
// `trend_14d` (14 pontos densificados) + targets. Q.21.B substitui o
// array de 14 números que estava hardcoded.
interface ThroughputDashboard {
  throughput_eur: { target_min: number; target_max: number };
  trend_14d: Array<{ date: string; eur: number }>;
}

async function fetchThroughputDashboard(): Promise<ThroughputDashboard | null> {
  try {
    const r = await fetch(`${getApiBase()}/v1/profit/dashboard`, { headers: TENANT_OEE });
    return r.ok ? r.json() : null;
  } catch { return null; }
}

function toneFor(oee: number): 'green' | 'yellow' | 'red' {
  return oee >= 0.60 ? 'green' : oee >= 0.40 ? 'yellow' : 'red';
}

function OEETab() {
  const overallQuery = useQuery({
    queryKey: ['oee', 'overall'],
    queryFn: () => fetchOEE(),
    staleTime: 5 * 60_000,
  });
  const byPhaseQuery = useQuery({
    queryKey: ['oee', 'phase'],
    queryFn: () => fetchOEE('phase'),
    staleTime: 5 * 60_000,
  });
  const byTypeQuery = useQuery({
    queryKey: ['oee', 'product_type'],
    queryFn: () => fetchOEE('product_type'),
    staleTime: 5 * 60_000,
  });
  const throughputQuery = useQuery({
    queryKey: ['oee', 'throughput-14d'],
    queryFn: fetchThroughputDashboard,
    staleTime: 5 * 60_000,
    retry: 0,
  });

  const overall = overallQuery.data?.overall;
  const phases = byPhaseQuery.data?.breakdown ?? [];
  const types = byTypeQuery.data?.breakdown ?? [];
  // Throughput diário real, em milhares de € (€28.4K → 28.4). A meta é o
  // limite inferior da banda NELO (target_min) na mesma escala.
  const throughput = throughputQuery.data;
  const throughputData = (throughput?.trend_14d ?? []).map((p) => p.eur / 1000);
  const throughputTarget = throughput
    ? throughput.throughput_eur.target_min / 1000
    : 0;
  const worstPhases = phases.slice(0, 8);
  const bestTypes = types.filter((t) => t.sample_size >= 5).sort((a, b) => b.oee - a.oee).slice(0, 10);
  const worstTypes = types.filter((t) => t.sample_size >= 5).sort((a, b) => a.oee - b.oee).slice(0, 5);

  return (
    <div className="space-y-5 page-enter">
      {/* Explainer */}
      <div
        style={{
          padding: '14px 18px',
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 12,
          fontSize: 13,
          color: 'var(--fg-1)',
          lineHeight: 1.6,
        }}
      >
        <strong style={{ color: 'var(--fg-0)' }}>O que é OEE?</strong>{' '}
        Mede que percentagem do tempo a fábrica está realmente a produzir bem.
        Calculado em tempo real a partir das operações executadas em <code>OF_FP</code>{' '}
        (janela: 30 dias).{' '}
        <span style={{ color: 'var(--fg-2)' }}>
          Meta NELO: 60%+ (world-class: 85%+).
        </span>
      </div>

      {/* OEE breakdown — 4 cards (1.4fr 1fr 1fr 1fr) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1.4fr 1fr 1fr 1fr',
          gap: 14,
        }}
      >
        {/* OEE Global */}
        <div
          style={{
            padding: 22,
            background: 'var(--bg-1)',
            border: '1px solid var(--bd-1)',
            borderRadius: 12,
          }}
        >
          <div className="text-sm font-semibold text-text-dark-primary mb-1">
            OEE Global
          </div>
          <div className="text-xs text-text-dark-tertiary mb-3">
            {overall
              ? `${overall.sample_size.toLocaleString('pt-PT')} ops · 30 dias`
              : overallQuery.isLoading ? 'A carregar…' : 'sem dados'}
          </div>
          <div className="flex items-baseline gap-2">
            <span
              className="tabular-nums"
              style={{
                fontSize: 56,
                fontWeight: 700,
                color: overall ? `var(--${toneFor(overall.oee)})` : 'var(--fg-3)',
                lineHeight: 1,
              }}
            >
              {overall ? (overall.oee * 100).toFixed(1).replace('.', ',') : '—'}
            </span>
            <span style={{ fontSize: 18, color: 'var(--fg-2)' }}>%</span>
          </div>
          {overall && (
            <div className="mt-3 text-xs text-text-dark-tertiary">
              Excluídos {overall.sample_excluded} outliers
            </div>
          )}
        </div>

        <OEEBlock
          label="Disponibilidade"
          value={overall ? Math.round(overall.availability * 100).toString() : '—'}
          target="—"
          tone={overall ? toneFor(overall.availability) : 'blue'}
          detail="Tempo a produzir vs tempo planeado"
          loss={overall && overall.availability >= 0.99 ? 'Cap a 100% (paralelismo de operadores)' : undefined}
        />
        <OEEBlock
          label="Performance"
          value={overall ? Math.round(overall.performance * 100).toString() : '—'}
          target="—"
          tone={overall ? toneFor(overall.performance) : 'blue'}
          detail="Velocidade real vs standard"
          loss={overall && overall.performance < 0.6 ? 'Acabamento + Pintura lentos vs PRODF_TEMPO' : undefined}
        />
        <OEEBlock
          label="Qualidade"
          value={overall ? Math.round(overall.quality * 100).toString() : '—'}
          target="—"
          tone={overall ? toneFor(overall.quality) : 'blue'}
          detail="First-pass yield (OFFP_PROBS_* sem registo)"
          loss={overall && overall.quality < 0.95 ? `${((1 - overall.quality) * overall.sample_size).toFixed(0)} ops com problema inline` : undefined}
        />
      </div>

      {/* Worst phases + best types */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 22 }}>
        <Panel title="Piores fases por OEE" badge={`${phases.length} fases`}>
          <div className="flex flex-col" style={{ gap: 8 }}>
            {worstPhases.length === 0 ? (
              <div className="text-xs text-text-dark-tertiary py-2">A carregar…</div>
            ) : worstPhases.map((p) => (
              <div key={p.group_value} className="flex items-center" style={{ gap: 12, padding: '6px 8px', borderRadius: 6, background: 'var(--bg-0)' }}>
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-text-dark-primary truncate">{p.group_value}</div>
                  <div className="text-[10px] text-text-dark-tertiary">{p.sample_size} ops</div>
                </div>
                <div className="tabular-nums font-semibold" style={{ fontSize: 14, color: `var(--${toneFor(p.oee)})`, minWidth: 56, textAlign: 'right' }}>
                  {(p.oee * 100).toFixed(1)}%
                </div>
                <div className="flex flex-col" style={{ gap: 1, fontSize: 9, color: 'var(--fg-2)', minWidth: 100, textAlign: 'right' }}>
                  <span>Pf {Math.round(p.performance * 100)}%</span>
                  <span>Ql {Math.round(p.quality * 100)}%</span>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="OEE por tipo de produto" badge={`${types.length} tipos`}>
          <div className="flex flex-col" style={{ gap: 6 }}>
            <div className="text-[10px] uppercase text-text-dark-tertiary mb-1">Piores (≥5 ops)</div>
            {worstTypes.length === 0 ? (
              <div className="text-xs text-text-dark-tertiary py-2">A carregar…</div>
            ) : worstTypes.map((t) => (
              <div key={t.group_value} className="flex items-center justify-between text-xs" style={{ padding: '4px 6px' }}>
                <span className="text-text-dark-primary truncate" style={{ maxWidth: 160 }}>{t.group_value}</span>
                <span className="tabular-nums font-semibold" style={{ color: `var(--${toneFor(t.oee)})` }}>
                  {(t.oee * 100).toFixed(0)}%
                </span>
              </div>
            ))}
            <div className="text-[10px] uppercase text-text-dark-tertiary mt-3 mb-1">Melhores (≥5 ops)</div>
            {bestTypes.slice(0, 5).map((t) => (
              <div key={t.group_value} className="flex items-center justify-between text-xs" style={{ padding: '4px 6px' }}>
                <span className="text-text-dark-primary truncate" style={{ maxWidth: 160 }}>{t.group_value}</span>
                <span className="tabular-nums font-semibold" style={{ color: `var(--${toneFor(t.oee)})` }}>
                  {(t.oee * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {/* Throughput chart + Impacto financeiro */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 22 }}>
        <Panel title="Throughput diário" badge="14 dias">
          {throughputQuery.isLoading ? (
            <div className="px-4 py-8 text-center text-xs text-text-dark-tertiary">
              A carregar throughput…
            </div>
          ) : throughputData.length === 0 ? (
            <EmptyState
              title="Sem throughput registado"
              hint="O endpoint /v1/profit/dashboard não devolveu série de receita. Verifica se há order_revenue para os últimos 14 dias."
              size="sm"
            />
          ) : (
            <ThroughputChart data={throughputData} target={throughputTarget} />
          )}
        </Panel>
        <Panel title="Impacto financeiro" badge="€/sem">
          {/* Q.21.B — os 4 valores € + total €4.780 eram hardcoded (ZERO
              MOCKS). Não há endpoint que decomponha o custo de perda por
              causa, por isso mostramos um EmptyState honesto em vez de
              números fabricados. Wire quando o backend o servir. */}
          <EmptyState
            title="Decomposição de perdas indisponível"
            hint="Ainda não há endpoint que atribua o custo de perda às causas (paragem de molde, lentidão de fase, retrabalho). O custo de retrabalho real está no separador Retrabalho."
            size="sm"
          />
        </Panel>
      </div>
    </div>
  );
}

// ─── OEEBlock ───────────────────────────────────────────────────────────────

function OEEBlock({
  label,
  value,
  target,
  tone,
  detail,
  loss,
}: {
  label: string;
  value: string;
  target: string;
  tone: 'green' | 'yellow' | 'red' | 'blue';
  detail: string;
  loss?: string;
}) {
  return (
    <div
      style={{
        padding: 22,
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 12,
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-2)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
        }}
      >
        {label}
      </div>
      <div className="flex items-baseline gap-1 mt-2">
        <span
          className="tabular-nums"
          style={{
            fontSize: 32,
            fontWeight: 700,
            color: `var(--${tone})`,
            lineHeight: 1,
          }}
        >
          {value}
        </span>
        <span style={{ fontSize: 14, color: 'var(--fg-2)' }}>%</span>
      </div>
      <div className="text-[11px] text-text-dark-tertiary mt-1">Meta: {target}%</div>
      <div className="text-xs text-text-dark-secondary mt-2.5 leading-relaxed">
        {detail}
      </div>
      {loss ? (
        <div
          style={{
            marginTop: 10,
            padding: '8px 10px',
            background: 'var(--bg-2)',
            borderRadius: 6,
            borderLeft: `2px solid var(--${tone})`,
            fontSize: 11,
            color: 'var(--fg-1)',
          }}
        >
          <strong
            className="text-text-dark-tertiary"
            style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.4 }}
          >
            Maior perda:
          </strong>
          <div className="mt-0.5">{loss}</div>
        </div>
      ) : null}
    </div>
  );
}

// ─── ThroughputChart (port literal page-oee.jsx) ────────────────────────────

function ThroughputChart({ data, target }: { data: number[]; target: number }) {
  const w = 600;
  const h = 200;
  const pad = { l: 32, r: 12, t: 12, b: 28 };
  const cw = w - pad.l - pad.r;
  const ch = h - pad.t - pad.b;
  const max = Math.max(...data, target) * 1.1;
  const dx = cw / (data.length - 1);

  return (
    <div className="px-2 py-1">
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 200 }}>
        {/* grid */}
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <line
            key={t}
            x1={pad.l}
            x2={w - pad.r}
            y1={pad.t + ch * (1 - t)}
            y2={pad.t + ch * (1 - t)}
            stroke="var(--bd-1)"
            strokeDasharray={t === 0 ? '0' : '2 3'}
          />
        ))}
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <text
            key={t}
            x={pad.l - 6}
            y={pad.t + ch * (1 - t) + 3}
            fontSize="9"
            fill="var(--fg-3)"
            textAnchor="end"
          >
            {Math.round(max * t)}
          </text>
        ))}
        {/* target line */}
        <line
          x1={pad.l}
          x2={w - pad.r}
          y1={pad.t + ch * (1 - target / max)}
          y2={pad.t + ch * (1 - target / max)}
          stroke="var(--green)"
          strokeWidth="1.2"
          strokeDasharray="3 3"
        />
        <text
          x={w - pad.r - 4}
          y={pad.t + ch * (1 - target / max) - 4}
          fontSize="9"
          fill="var(--green)"
          textAnchor="end"
        >
          Meta {target}
        </text>
        {/* line */}
        <path
          d={data
            .map(
              (v, i) =>
                `${i === 0 ? 'M' : 'L'} ${pad.l + i * dx} ${pad.t + ch * (1 - v / max)}`,
            )
            .join(' ')}
          fill="none"
          stroke="var(--blue)"
          strokeWidth="2"
        />
        {/* dots */}
        {data.map((v, i) => (
          <circle
            key={i}
            cx={pad.l + i * dx}
            cy={pad.t + ch * (1 - v / max)}
            r="3"
            fill="var(--blue)"
          />
        ))}
        {/* x-axis */}
        {data.map((_, i) =>
          i % 2 === 0 ? (
            <text
              key={i}
              x={pad.l + i * dx}
              y={h - 8}
              fontSize="9"
              fill="var(--fg-3)"
              textAnchor="middle"
            >
              D−{data.length - 1 - i}
            </text>
          ) : null,
        )}
      </svg>
    </div>
  );
}

// ─── KPIStrip (reusable) ────────────────────────────────────────────────────

function KPIStrip({
  label,
  value,
  unit,
  context,
  tone,
  hero = false,
}: {
  label: string;
  value: string;
  unit?: string;
  context: string;
  tone: 'green' | 'yellow' | 'red' | 'blue' | 'gray';
  /** Q.23.G — variante destacada: valor maior, atmosfera, profundidade. */
  hero?: boolean;
}) {
  return (
    <div
      style={{
        padding: hero ? '20px 24px' : '16px 18px',
        background: hero ? 'var(--atmosphere-card), var(--bg-1)' : 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 12,
        boxShadow: hero ? 'var(--shadow-2)' : undefined,
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-2)',
          fontWeight: 500,
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div className="flex items-baseline gap-1 tabular-nums">
        <span
          style={{
            fontSize: hero ? 44 : 28,
            fontWeight: 700,
            color: `var(--${tone})`,
            lineHeight: 1,
            letterSpacing: hero ? '-0.02em' : undefined,
          }}
        >
          {value}
        </span>
        {unit ? (
          <span style={{ fontSize: hero ? 16 : 13, color: 'var(--fg-2)' }}>{unit}</span>
        ) : null}
      </div>
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-3)',
          marginTop: 6,
          lineHeight: 1.4,
        }}
      >
        {context}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// NovoRetrabalhoForm — Q.30.D: lançar retrabalho (POST /v1/quality/rework)
// ═══════════════════════════════════════════════════════════════════════════

const REWORK_ERROR_CODES: Array<{ code: string; label: string }> = [
  { code: 'RESIN_BUBBLE', label: 'Bolha na resina' },
  { code: 'PAINT_SCRATCH', label: 'Risco na pintura' },
  { code: 'COLAGEM_FAIL', label: 'Falha na colagem' },
  { code: 'LAMINATE_DEFECT', label: 'Defeito de laminagem' },
  { code: 'DIMENSION_OFF', label: 'Dimensão fora de tolerância' },
  { code: 'OTHER', label: 'Outro' },
];

const ROOT_CAUSE_CATEGORIES = [
  'Erro de operador',
  'Molde danificado',
  'Material defeituoso',
  'Procedimento incorreto',
  'Equipamento',
  'Outro',
];

const FIELD_CLASS =
  'w-full px-3 py-2 rounded-md bg-dark-700 border border-white/10 text-sm ' +
  'text-text-dark-primary placeholder:text-text-dark-tertiary focus:outline-none ' +
  'focus:ring-2 focus:ring-accent-500/40 focus:border-accent-500/60';

function NovoRetrabalhoForm() {
  const queryClient = useQueryClient();
  const [ofId, setOfId] = useState('');
  const [errorCode, setErrorCode] = useState('');
  const [phaseCauser, setPhaseCauser] = useState('');
  const [rootCause, setRootCause] = useState('');
  const [costEur, setCostEur] = useState('');
  const [description, setDescription] = useState('');
  const [causerEmployeeId, setCauserEmployeeId] = useState('');
  const [savedBanner, setSavedBanner] = useState(false);

  // Picker de operador — degrada para vazio se a lista não responder.
  const employeesQuery = useQuery({
    queryKey: ['qualidade', 'rework-employees'],
    queryFn: () => employeesApi.list({ limit: 200 }),
    staleTime: 5 * 60_000,
    retry: false,
  });
  const employees: Array<{ id: string; label: string }> = useMemo(() => {
    const raw = (employeesQuery.data as any)?.data ?? employeesQuery.data;
    if (!Array.isArray(raw)) return [];
    return raw
      .map((e: any) => {
        const id = e.id ?? e.employee_id;
        if (!id) return null;
        const name =
          [e.first_name, e.last_name].filter(Boolean).join(' ') ||
          e.full_name ||
          e.name ||
          String(id).slice(0, 8);
        return { id: String(id), label: name };
      })
      .filter(Boolean) as Array<{ id: string; label: string }>;
  }, [employeesQuery.data]);

  const mutation = useMutation({
    mutationFn: (payload: ReworkCreatePayload) => qualityReworkApi.create(payload),
    onSuccess: () => {
      setSavedBanner(true);
      setTimeout(() => setSavedBanner(false), 3_000);
      setOfId('');
      setErrorCode('');
      setPhaseCauser('');
      setRootCause('');
      setCostEur('');
      setDescription('');
      setCauserEmployeeId('');
      queryClient.invalidateQueries({ queryKey: ['qualidade', 'rework'] });
    },
  });

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!ofId.trim() || !errorCode) return;
    const cost = Number(costEur);
    const payload: ReworkCreatePayload = {
      of_id: ofId.trim(),
      error_code: errorCode,
      detected_at: new Date().toISOString(),
      phase_id_causer: phaseCauser.trim() || undefined,
      root_cause_category: rootCause || undefined,
      error_description: description.trim() || undefined,
      causer_employee_id: causerEmployeeId || undefined,
      cost_estimate_eur:
        costEur.trim() !== '' && Number.isFinite(cost) ? cost : undefined,
    };
    mutation.mutate(payload);
  }

  const disabled = !ofId.trim() || !errorCode || mutation.isPending;

  return (
    <Panel title="Registar novo retrabalho" badge="QA01">
      <form onSubmit={handleSubmit} className="space-y-3 p-1">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <label className="block">
            <span className="text-xs text-text-dark-secondary">Ordem (OF) *</span>
            <input
              type="text"
              value={ofId}
              onChange={(e) => setOfId(e.target.value.toUpperCase())}
              placeholder="OF-12345"
              className={`mt-1 ${FIELD_CLASS}`}
              required
            />
          </label>
          <label className="block">
            <span className="text-xs text-text-dark-secondary">Tipo de defeito *</span>
            <select
              value={errorCode}
              onChange={(e) => setErrorCode(e.target.value)}
              className={`mt-1 ${FIELD_CLASS}`}
              required
            >
              <option value="">Escolher…</option>
              {REWORK_ERROR_CODES.map((e) => (
                <option key={e.code} value={e.code}>
                  {e.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-text-dark-secondary">Fase onde ocorreu</span>
            <input
              type="text"
              value={phaseCauser}
              onChange={(e) => setPhaseCauser(e.target.value)}
              placeholder="Ex: Laminagem"
              className={`mt-1 ${FIELD_CLASS}`}
            />
          </label>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <label className="block">
            <span className="text-xs text-text-dark-secondary">Causa-raiz</span>
            <select
              value={rootCause}
              onChange={(e) => setRootCause(e.target.value)}
              className={`mt-1 ${FIELD_CLASS}`}
            >
              <option value="">Escolher…</option>
              {ROOT_CAUSE_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-text-dark-secondary">Operador responsável</span>
            <select
              value={causerEmployeeId}
              onChange={(e) => setCauserEmployeeId(e.target.value)}
              className={`mt-1 ${FIELD_CLASS}`}
              disabled={employees.length === 0}
            >
              <option value="">
                {employees.length === 0 ? 'Lista indisponível' : '— sem atribuir —'}
              </option>
              {employees.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-text-dark-secondary">Custo estimado €</span>
            <input
              type="number"
              inputMode="decimal"
              min={0}
              value={costEur}
              onChange={(e) => setCostEur(e.target.value)}
              placeholder="0"
              className={`mt-1 ${FIELD_CLASS}`}
            />
          </label>
        </div>
        <label className="block">
          <span className="text-xs text-text-dark-secondary">Descrição (opcional)</span>
          <textarea
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Ex: bolha de 3 mm no pavilhão lateral direito"
            className={`mt-1 ${FIELD_CLASS} resize-none`}
          />
        </label>

        {savedBanner ? (
          <div className="flex items-center gap-2 text-xs text-success bg-success/10 border border-success/30 rounded-md px-3 py-2">
            <CheckCircle2 size={14} /> Retrabalho registado.
          </div>
        ) : null}
        {mutation.isError ? (
          <div className="text-xs text-danger" role="alert">
            Não foi possível registar o retrabalho. Tenta outra vez.
          </div>
        ) : null}

        <button
          type="submit"
          disabled={disabled}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-white text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          style={{ background: 'var(--blue)', border: '1px solid var(--blue)' }}
        >
          <Repeat size={14} />
          {mutation.isPending ? 'A registar…' : 'Registar retrabalho'}
        </button>
      </form>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ReworkListTab + MoldsTab — preserved from Onda 4
// ═══════════════════════════════════════════════════════════════════════════

function ReworkListTab({ filter }: { filter: 'open' | 'rework' }) {
  const isReworkTab = filter === 'rework';
  const reworkQuery = useQuery({
    queryKey: ['qualidade', 'rework', filter],
    queryFn: () => fetchQualityRework(filter),
    staleTime: 30_000,
    retry: 0,
  });

  const items: any[] = useMemo(() => {
    const data: any = reworkQuery.data;
    if (!data) return [];
    if (Array.isArray(data)) return data;
    return data.items ?? data.reworks ?? [];
  }, [reworkQuery.data]);

  const title = isReworkTab ? 'Retrabalho em curso' : 'Erros abertos';

  return (
    <Panel title={title} badge={items.length || '—'} flush>
      {reworkQuery.isLoading ? (
        <div className="px-4 py-6 text-center text-xs text-text-dark-tertiary">
          A carregar…
        </div>
      ) : reworkQuery.isError || reworkQuery.data === null ? (
        <EmptyState
          title="Endpoint /v1/quality/rework indisponível"
          hint={
            isReworkTab
              ? 'Quando wired, esta tab listará retrabalhos em curso.'
              : 'Quando wired, esta tab listará defeitos abertos.'
          }
          mascot
          size="md"
        />
      ) : items.length === 0 ? (
        <EmptyState
          title={isReworkTab ? 'Sem retrabalho em curso' : 'Sem erros abertos'}
          hint="Tudo limpo no chão de fábrica."
          mascot
          size="sm"
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="border-b border-white/[0.06]">
              <tr className="text-left text-[10px] uppercase tracking-wider text-text-dark-tertiary">
                <th className="px-3 py-2">ID</th>
                <th className="px-3 py-2">Hull</th>
                <th className="px-3 py-2">Fase</th>
                <th className="px-3 py-2">Tipo</th>
                <th className="px-3 py-2">Severidade</th>
                <th className="px-3 py-2">Custo €</th>
                <th className="px-3 py-2">Estado</th>
              </tr>
            </thead>
            <tbody>
              {items.slice(0, 20).map((r, idx) => (
                <tr
                  key={r.id ?? idx}
                  className="border-b border-white/[0.04] hover:bg-white/[0.02]"
                >
                  <td className="px-3 py-2 font-mono text-text-dark-primary">
                    {(r.id ?? '—').toString().slice(0, 8)}
                  </td>
                  <td className="px-3 py-2 text-text-dark-secondary">{r.of_id ?? '—'}</td>
                  <td className="px-3 py-2 text-text-dark-secondary">
                    {r.phase_id_causer ?? '—'}
                  </td>
                  <td className="px-3 py-2 text-text-dark-secondary">
                    {r.error_description ?? r.error_code ?? '—'}
                  </td>
                  <td className="px-3 py-2">
                    <ZipSevBadge
                      severity={(r.context?.severity as ZipSeverity) ?? 'medium'}
                      size="sm"
                    />
                  </td>
                  <td className="px-3 py-2 tabular-nums text-text-dark-secondary">
                    {r.cost_estimate_eur ? `€${Math.round(Number(r.cost_estimate_eur))}` : '—'}
                  </td>
                  <td className="px-3 py-2 text-text-dark-secondary">
                    {r.resolved_at ? 'Resolvido' : 'Aberto'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function MoldsTab() {
  const moldsQuery = useQuery({
    queryKey: ['qualidade', 'molds', 'health-report'],
    queryFn: () => fetchMoldsHealthReport(),
    staleTime: 60_000,
    retry: 0,
  });

  const [drawer, setDrawer] = useState<{ id: string | null; code?: string }>({ id: null });

  const items: any[] = useMemo(() => {
    const data: any = moldsQuery.data;
    if (!data) return [];
    if (Array.isArray(data)) return data;
    return data.items ?? [];
  }, [moldsQuery.data]);

  const reds = items.filter((m) => m.health?.risk_category === 'red').length;
  const yellows = items.filter((m) => m.health?.risk_category === 'yellow').length;

  return (
    <Panel title="Moldes — health report" badge={items.length || '—'} flush>
      {moldsQuery.isLoading ? (
        <div className="px-4 py-6 text-center text-xs text-text-dark-tertiary">
          A carregar moldes…
        </div>
      ) : moldsQuery.isError || moldsQuery.data === null ? (
        <EmptyState
          title="Endpoint /v1/plan/molds/health-report indisponível"
          hint="Quando wired, mostra grid de moldes com score de saúde."
          mascot
          size="md"
        />
      ) : items.length === 0 ? (
        <EmptyState
          title="Sem moldes registados"
          hint="O endpoint respondeu mas devolveu lista vazia."
          mascot
          size="sm"
        />
      ) : (
        <>
          <div className="px-4 py-2 border-b border-white/[0.06] flex items-center gap-3 text-[11px] text-text-dark-tertiary">
            <span>
              <span className="font-semibold text-danger">{reds}</span> red
            </span>
            <span>
              <span className="font-semibold text-warning">{yellows}</span> yellow
            </span>
            <span className="ml-auto">{items.length} moldes</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 p-3">
            {items.slice(0, 24).map((m, idx) => {
              const score = m.health?.score_0_100 ?? 100;
              const cat = m.health?.risk_category ?? 'green';
              const tone = cat === 'red' ? 'red' : cat === 'yellow' ? 'yellow' : 'green';
              return (
                <button
                  key={m.id ?? idx}
                  type="button"
                  onClick={() => setDrawer({ id: m.id ?? m.mold_id ?? null, code: m.mold_code })}
                  style={{
                    borderRadius: 8,
                    border: `1px solid var(--${tone}-bd)`,
                    background: 'var(--bg-2)',
                    padding: 12,
                    textAlign: 'left',
                    cursor: 'pointer',
                  }}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="min-w-0">
                      <div className="text-xs font-mono text-text-dark-primary truncate">
                        {m.mold_code ?? '—'}
                      </div>
                      <div className="text-[10px] text-text-dark-tertiary truncate">
                        {m.model_id ?? '—'}
                      </div>
                    </div>
                    <span
                      className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold"
                      style={{
                        background: `var(--${tone}-bg)`,
                        color: `var(--${tone})`,
                        border: `1px solid var(--${tone}-bd)`,
                      }}
                    >
                      {cat}
                    </span>
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span
                      className="text-2xl font-semibold tabular-nums"
                      style={{ color: `var(--${tone})` }}
                    >
                      {score}
                    </span>
                    <span className="text-[10px] text-text-dark-tertiary">/100</span>
                  </div>
                  <div
                    style={{
                      marginTop: 8,
                      height: 6,
                      background: 'var(--bd-1)',
                      borderRadius: 3,
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${score}%`,
                        background: `var(--${tone})`,
                      }}
                    />
                  </div>
                </button>
              );
            })}
          </div>
        </>
      )}
      <MoldDefectDrawer
        open={!!drawer.id}
        moldId={drawer.id}
        moldCode={drawer.code}
        onClose={() => setDrawer({ id: null })}
      />
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ZonasTab — F11 / Q.46.C: mapa de defeitos do barco por zona do casco
// ═══════════════════════════════════════════════════════════════════════════
//
// Heatmap / Pareto de retrabalho por zona do casco. Diz *onde* no barco a
// fábrica falha, não só *quanto*. Lê GET /v1/quality/defect-zones, que
// agrega `rework_entry.location_zone` (Q.46.A, vindo de OFCH_LOCAL).
// ZERO MOCKS — estados loading / erro / vazio explícitos.

function zoneTone(sharePct: number): 'red' | 'yellow' | 'green' {
  return sharePct >= 25 ? 'red' : sharePct >= 10 ? 'yellow' : 'green';
}

function ZonasTab() {
  const zonesQuery = useQuery<DefectZoneMapResponse>({
    queryKey: ['qualidade', 'defect-zones'],
    queryFn: () => defectZonesApi.zoneMap({ top_n: 30 }),
    staleTime: 60_000,
    retry: 0,
  });

  if (zonesQuery.isLoading) {
    return (
      <Panel title="Mapa de defeitos por zona" badge="F11">
        <div className="px-4 py-8 text-center text-xs text-text-dark-tertiary">
          A carregar zonas…
        </div>
      </Panel>
    );
  }

  if (zonesQuery.isError) {
    return (
      <Panel title="Mapa de defeitos por zona" badge="F11" flush>
        <EmptyState
          title="Endpoint /v1/quality/defect-zones indisponível"
          hint="Quando wired, esta aba mostra o Pareto de defeitos por zona do casco."
          mascot
          size="md"
        />
      </Panel>
    );
  }

  const data = zonesQuery.data;
  const zones = data?.zones ?? [];
  const maxEvents = zones.length > 0 ? zones[0].events : 0;

  return (
    <div className="space-y-5 page-enter">
      {/* Explainer */}
      <div
        style={{
          padding: '14px 18px',
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 12,
          fontSize: 13,
          color: 'var(--fg-1)',
          lineHeight: 1.6,
        }}
      >
        <strong style={{ color: 'var(--fg-0)' }}>Mapa de defeitos por zona.</strong>{' '}
        Mostra em que zona do casco os defeitos foram marcados — diz <em>onde</em>{' '}
        no barco a fábrica falha, não só quanto. Vem de <code>OFCH_LOCAL</code>{' '}
        (a localização registada na checklist de qualidade).
      </div>

      {/* KPI strip — total / com zona / sem zona / cobertura */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr 1fr',
          gap: 14,
        }}
      >
        <KPIStrip
          label="Eventos de retrabalho"
          value={(data?.total_events ?? 0).toLocaleString('pt-PT')}
          context="Janela de 90 dias"
          tone="blue"
        />
        <KPIStrip
          label="Zonas distintas"
          value={(data?.distinct_zones ?? 0).toString()}
          context="Zonas do casco com defeito marcado"
          tone="blue"
        />
        <KPIStrip
          label="Eventos sem zona"
          value={(data?.events_without_zone ?? 0).toLocaleString('pt-PT')}
          context="Sem localização registada na checklist"
          tone={(data?.events_without_zone ?? 0) > 0 ? 'yellow' : 'green'}
        />
        <KPIStrip
          label="Cobertura de zona"
          value={(data?.zone_coverage_pct ?? 0).toFixed(1)}
          unit="%"
          context={
            (data?.zone_coverage_pct ?? 0) < 50
              ? 'Cobertura baixa — o Pareto é parcial'
              : 'Fracção dos eventos com zona marcada'
          }
          tone={
            (data?.zone_coverage_pct ?? 0) >= 75
              ? 'green'
              : (data?.zone_coverage_pct ?? 0) >= 40
                ? 'yellow'
                : 'red'
          }
        />
      </div>

      {/* Heatmap / Pareto por zona */}
      <Panel title="Pareto de defeitos por zona" badge={`${zones.length} zonas`} flush>
        {zones.length === 0 ? (
          <EmptyState
            title="Sem defeitos com zona registada"
            hint={
              (data?.total_events ?? 0) > 0
                ? 'Há retrabalho na janela, mas nenhum tem zona do casco marcada (OFCH_LOCAL).'
                : 'Sem retrabalho registado na janela de 90 dias.'
            }
            mascot
            size="sm"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b border-white/[0.06]">
                <tr className="text-left text-[10px] uppercase tracking-wider text-text-dark-tertiary">
                  <th className="px-3 py-2">Zona do casco</th>
                  <th className="px-3 py-2">Eventos</th>
                  <th className="px-3 py-2" style={{ minWidth: 160 }}>
                    Quota
                  </th>
                  <th className="px-3 py-2">Cumulativo</th>
                  <th className="px-3 py-2">Custo €</th>
                  <th className="px-3 py-2">Horas</th>
                  <th className="px-3 py-2">Ordens</th>
                </tr>
              </thead>
              <tbody>
                {zones.map((z) => {
                  const tone = zoneTone(z.share_pct);
                  const barPct =
                    maxEvents > 0 ? (z.events / maxEvents) * 100 : 0;
                  return (
                    <tr
                      key={z.zone}
                      className="border-b border-white/[0.04] hover:bg-white/[0.02]"
                    >
                      <td className="px-3 py-2 text-text-dark-primary font-medium">
                        {z.zone}
                      </td>
                      <td className="px-3 py-2 tabular-nums text-text-dark-secondary">
                        {z.events.toLocaleString('pt-PT')}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          <div
                            style={{
                              flex: 1,
                              height: 6,
                              background: 'var(--bd-1)',
                              borderRadius: 3,
                              overflow: 'hidden',
                            }}
                          >
                            <div
                              style={{
                                width: `${barPct}%`,
                                height: '100%',
                                background: `var(--${tone})`,
                              }}
                            />
                          </div>
                          <span
                            className="tabular-nums"
                            style={{ color: `var(--${tone})`, minWidth: 44, textAlign: 'right' }}
                          >
                            {z.share_pct.toFixed(1)}%
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-2 tabular-nums text-text-dark-tertiary">
                        {z.cumulative_pct.toFixed(1)}%
                      </td>
                      <td className="px-3 py-2 tabular-nums text-text-dark-secondary">
                        {z.cost_estimate_eur > 0
                          ? `€${Math.round(z.cost_estimate_eur).toLocaleString('pt-PT')}`
                          : '—'}
                      </td>
                      <td className="px-3 py-2 tabular-nums text-text-dark-secondary">
                        {z.hours_lost > 0 ? z.hours_lost.toFixed(1) : '—'}
                      </td>
                      <td className="px-3 py-2 tabular-nums text-text-dark-secondary">
                        {z.affected_orders}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
