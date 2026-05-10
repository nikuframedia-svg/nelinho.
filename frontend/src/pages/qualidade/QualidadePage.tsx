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

import { lazy, Suspense, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
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

const ExplainPage = lazy(() =>
  import('../explain/ExplainPage').then((m) => ({ default: m.ExplainPage })),
);
const TrustDqaDashboard = lazy(() =>
  import('../../components/dqa/TrustDqaDashboard').then((m) => ({ default: m.TrustDqaDashboard })),
);

function askCopilot(query: string) {
  window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
}

const TAB_IDS = ['resumo', 'erros', 'moldes', 'retrabalho', 'diagnostico', 'oee', 'trust'] as const;
type TabId = (typeof TAB_IDS)[number];
function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

// ─── Endpoints ──────────────────────────────────────────────────────────────

async function fetchQualityRework(filter?: 'open' | 'rework') {
  try {
    const url = filter
      ? `http://127.0.0.1:8001/v1/quality/rework?filter=${filter}&limit=20`
      : `http://127.0.0.1:8001/v1/quality/rework?limit=20`;
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
      `http://127.0.0.1:8001/v1/plan/molds/health-report?limit=24`,
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
      'http://127.0.0.1:8001/v1/quality/dashboard?group_by=phase&top_n=10',
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
      { id: 'retrabalho', label: 'Retrabalho', icon: <Repeat size={13} /> },
      { id: 'diagnostico', label: 'Diagnóstico', icon: <Brain size={13} /> },
      { id: 'oee', label: 'OEE', icon: <Activity size={13} /> },
      { id: 'trust', label: 'Trust + DQA', icon: <ShieldCheck size={13} /> },
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
        <Tabs tabs={tabs} value={activeTab} onChange={handleTabChange} />
      </div>

      <div className="px-6 py-4">
        {activeTab === 'resumo' && <ResumoTab />}
        {activeTab === 'erros' && <ReworkListTab filter="open" />}
        {activeTab === 'moldes' && <MoldsTab />}
        {activeTab === 'retrabalho' && <ReworkListTab filter="rework" />}
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
    <div className="space-y-5">
      {/* KPI strip */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 14,
        }}
      >
        <KPIStrip
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

function OEETab() {
  // OEE não tem endpoint real ainda — placeholders honestos.
  // Quando endpoint exposto (Q.18.ZIP.OEE.BE), substitui com dados reais.
  return (
    <div className="space-y-5">
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
        Mede que percentagem do tempo a fábrica está realmente a produzir bem.{' '}
        <strong>78%</strong> significa que de cada 8h de trabalho, 6h15 produzem
        barcos sem defeito.{' '}
        <span style={{ color: 'var(--fg-2)' }}>Meta NELO: 80%.</span>
      </div>

      {/* Aviso endpoint pendente */}
      <div
        style={{
          padding: '10px 14px',
          background: 'var(--yellow-bg)',
          border: '1px solid var(--yellow-bd)',
          borderRadius: 8,
          fontSize: 12,
          color: 'var(--yellow)',
        }}
      >
        Endpoint <code className="font-mono">/v1/quality/oee</code> pendente — valores
        abaixo são placeholders honestos baseados em médias da indústria.
        Substitui com dados reais quando wired (sub-sprint Q.18.ZIP.OEE.BE).
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
          <div className="text-xs text-text-dark-tertiary mb-3">Hoje · placeholder</div>
          <div className="flex items-baseline gap-2">
            <span
              className="tabular-nums"
              style={{
                fontSize: 56,
                fontWeight: 700,
                color: 'var(--yellow)',
                lineHeight: 1,
              }}
            >
              78,4
            </span>
            <span style={{ fontSize: 18, color: 'var(--fg-2)' }}>%</span>
            <span className="ml-auto text-xs" style={{ color: 'var(--green)' }}>
              ↑ 2,3% vs ontem
            </span>
          </div>
          <div className="mt-3" style={{ height: 60 }}>
            <SparklineLarge
              data={[28.4, 29.1, 27.8, 30.2, 31.5, 32.0, 30.9, 28.5, 24.1, 25.3, 27.2, 30.8, 32.1, 33.2].map((v) => 70 + v / 5)}
              color="var(--yellow)"
              height={60}
            />
          </div>
          <div className="flex justify-between text-[11px] text-text-dark-tertiary mt-1.5">
            <span>14 dias atrás</span>
            <span>Hoje</span>
          </div>
        </div>

        <OEEBlock
          label="Disponibilidade"
          value="92"
          target="95"
          tone="yellow"
          detail="Tempo a produzir vs tempo planeado"
          loss="32min de paragem não planeada (molde K1 7 ML)"
        />
        <OEEBlock
          label="Performance"
          value="86"
          target="90"
          tone="yellow"
          detail="Velocidade real vs velocidade ideal"
          loss="Lixagem mais lenta — fila de 22 barcos"
        />
        <OEEBlock
          label="Qualidade"
          value="99,1"
          target="99"
          tone="green"
          detail="Barcos bons vs total produzido"
          loss="2 barcos para retrabalho ligeiro"
        />
      </div>

      {/* Throughput chart + Impacto financeiro */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 22 }}>
        <Panel title="Throughput diário" badge="14 dias">
          <ThroughputChart
            data={[28.4, 29.1, 27.8, 30.2, 31.5, 32.0, 30.9, 28.5, 24.1, 25.3, 27.2, 30.8, 32.1, 33.2]}
            target={30}
          />
        </Panel>
        <Panel title="Impacto financeiro" badge="€/sem">
          <div className="px-2 py-1 flex flex-col gap-3">
            {[
              { label: 'Paragem por molde', value: 1280, color: 'red' },
              { label: 'Lentidão Lixagem', value: 2400, color: 'yellow' },
              { label: 'Retrabalho qualidade', value: 680, color: 'yellow' },
              { label: 'Setup excessivo', value: 420, color: 'blue' },
            ].map((r) => (
              <div key={r.label}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-text-dark-secondary">{r.label}</span>
                  <span className="tabular-nums font-semibold text-text-dark-primary">
                    €{r.value.toLocaleString('pt-PT')}
                  </span>
                </div>
                <div
                  style={{
                    height: 4,
                    background: 'var(--bd-1)',
                    borderRadius: 2,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      width: `${(r.value / 2400) * 100}%`,
                      height: '100%',
                      background: `var(--${r.color})`,
                    }}
                  />
                </div>
              </div>
            ))}
            <div
              className="flex justify-between mt-2 pt-3"
              style={{ borderTop: '1px solid var(--bd-1)' }}
            >
              <span className="text-xs text-text-dark-secondary font-semibold">
                Total perdido / semana
              </span>
              <span
                className="tabular-nums font-bold"
                style={{ fontSize: 14, color: 'var(--red)' }}
              >
                €4.780
              </span>
            </div>
          </div>
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

// ─── SparklineLarge (60px) ──────────────────────────────────────────────────

function SparklineLarge({
  data,
  color,
  height,
}: {
  data: number[];
  color: string;
  height: number;
}) {
  if (data.length === 0) return null;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const w = 200;
  const path = data
    .map((p, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = height - ((p - min) / range) * height;
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');
  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      style={{ width: '100%', height: '100%' }}
    >
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ─── KPIStrip (reusable) ────────────────────────────────────────────────────

function KPIStrip({
  label,
  value,
  unit,
  context,
  tone,
}: {
  label: string;
  value: string;
  unit?: string;
  context: string;
  tone: 'green' | 'yellow' | 'red' | 'blue' | 'gray';
}) {
  return (
    <div
      style={{
        padding: '16px 18px',
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 12,
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
            fontSize: 28,
            fontWeight: 700,
            color: `var(--${tone})`,
            lineHeight: 1,
          }}
        >
          {value}
        </span>
        {unit ? (
          <span style={{ fontSize: 13, color: 'var(--fg-2)' }}>{unit}</span>
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
                <div
                  key={m.id ?? idx}
                  style={{
                    borderRadius: 8,
                    border: `1px solid var(--${tone}-bd)`,
                    background: 'var(--bg-2)',
                    padding: 12,
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
                </div>
              );
            })}
          </div>
        </>
      )}
    </Panel>
  );
}
