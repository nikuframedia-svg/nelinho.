/**
 * RelatoriosPage — porto do nelo (1).zip pages-2.jsx:RelatoriosPage.
 *
 * 5 tabs do brief PROMPT_CLAUDE_CODE.md §3.8:
 *   • KPIs       — wrap KPIsPage existing
 *   • Custos     — wrap COGSPage existing
 *   • Pricing    — wrap PricingPage existing
 *   • Cenários   — wrap ScenariosPage existing
 *   • Exportar   — placeholder até endpoint /v1/reports/generate
 *                  (Q.18.ZIP.BE.3 deferred). Mostra lista de templates
 *                  PDF/Excel disponíveis com botão "Em breve".
 *
 * Sprint Q.18.ZIP.I.
 */

import { lazy, Suspense, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  BarChart3,
  Receipt,
  Tag,
  GitBranch,
  Download,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { PageHeader, Tabs, Panel } from '../../components/dark';
import { SkeletonLoader } from '../../components/ui/Skeleton';

const KPIsPage = lazy(() =>
  import('../profit/KPIsPage').then((m) => ({ default: m.KPIsPage }))
);
const COGSPage = lazy(() =>
  import('../profit/COGSPage').then((m) => ({ default: m.COGSPage }))
);
const PricingPage = lazy(() =>
  import('../profit/PricingPage').then((m) => ({ default: m.PricingPage }))
);
const ScenariosPage = lazy(() =>
  import('../profit/ScenariosPage').then((m) => ({ default: m.ScenariosPage }))
);

function askCopilot(query: string) {
  window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
}

const TAB_IDS = ['kpis', 'custos', 'pricing', 'cenarios', 'export'] as const;
type TabId = (typeof TAB_IDS)[number];
function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

type ReportFormat = 'csv' | 'json';

interface ReportTemplate {
  id: 'producao' | 'cliente' | 'qualidade' | 'payroll' | 'cogs' | 'inventario';
  label: string;
  format: ReportFormat;
}

const REPORT_TEMPLATES: ReportTemplate[] = [
  { id: 'producao', label: 'Produção (WIP por fase)', format: 'csv' },
  { id: 'cliente', label: 'Backlog por cliente', format: 'csv' },
  { id: 'qualidade', label: 'Qualidade & retrabalho', format: 'csv' },
  { id: 'payroll', label: 'Payroll', format: 'csv' },
  { id: 'cogs', label: 'COGS detalhado', format: 'csv' },
  { id: 'inventario', label: 'Inventário & ABC', format: 'csv' },
];

interface ReportResponse {
  template_id: string;
  status: 'ready' | 'not_implemented';
  format: ReportFormat;
  filename: string;
  content: string;
  row_count: number;
  generated_at: string;
  message?: string | null;
}

async function generateReport(template_id: string, format: ReportFormat): Promise<ReportResponse> {
  const resp = await fetch('http://127.0.0.1:8001/v1/reports/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-Id': '00000000-0000-0000-0000-000000000001',
    },
    body: JSON.stringify({ template_id, format }),
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

function downloadFile(filename: string, content: string, format: ReportFormat) {
  const mime = format === 'csv' ? 'text/csv;charset=utf-8' : 'application/json';
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function RelatoriosPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const activeTab: TabId = isTabId(tabFromUrl) ? tabFromUrl : 'kpis';

  const tabs = useMemo(
    () => [
      { id: 'kpis', label: 'KPIs', icon: <BarChart3 size={13} /> },
      { id: 'custos', label: 'Custos', icon: <Receipt size={13} /> },
      { id: 'pricing', label: 'Pricing', icon: <Tag size={13} /> },
      { id: 'cenarios', label: 'Cenários', icon: <GitBranch size={13} /> },
      { id: 'export', label: 'Exportar', icon: <Download size={13} /> },
    ],
    []
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

  return (
    <div>
      <PageHeader
        title="Relatórios"
        subtitle="KPIS · CUSTOS · PRICING · CENÁRIOS · EXPORT"
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
              onClick={() =>
                askCopilot('Que relatório devo gerar para o briefing semanal?')
              }
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-500 text-white hover:bg-accent-400 text-xs font-medium transition-colors"
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

      <div className="px-2 py-4">
        {activeTab === 'kpis' && (
          <Suspense fallback={fallback}>
            <KPIsPage />
          </Suspense>
        )}
        {activeTab === 'custos' && (
          <Suspense fallback={fallback}>
            <COGSPage />
          </Suspense>
        )}
        {activeTab === 'pricing' && (
          <Suspense fallback={fallback}>
            <PricingPage />
          </Suspense>
        )}
        {activeTab === 'cenarios' && (
          <Suspense fallback={fallback}>
            <ScenariosPage />
          </Suspense>
        )}
        {activeTab === 'export' && <ExportTab />}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Export tab — wire ao POST /v1/reports/generate (Q.18.ZIP.BE.4)
// ═══════════════════════════════════════════════════════════════════════════════

interface RowState {
  status: 'idle' | 'loading' | 'ready' | 'error' | 'not_implemented';
  message?: string | null;
  rowCount?: number;
  generatedAt?: string;
}

function ExportTab() {
  const [state, setState] = useState<Record<string, RowState>>({});

  const handleGenerate = async (template_id: string, format: ReportFormat) => {
    setState((s) => ({ ...s, [template_id]: { status: 'loading' } }));
    try {
      const resp = await generateReport(template_id, format);
      if (resp.status === 'not_implemented') {
        setState((s) => ({
          ...s,
          [template_id]: {
            status: 'not_implemented',
            message: resp.message,
          },
        }));
        return;
      }
      // ready — auto-download
      downloadFile(resp.filename, resp.content || '', resp.format);
      setState((s) => ({
        ...s,
        [template_id]: {
          status: 'ready',
          rowCount: resp.row_count,
          generatedAt: resp.generated_at,
        },
      }));
    } catch (err) {
      setState((s) => ({
        ...s,
        [template_id]: {
          status: 'error',
          message: err instanceof Error ? err.message : 'Falha ao gerar relatório',
        },
      }));
    }
  };

  return (
    <div className="px-4">
      <Panel title="Templates disponíveis" badge={REPORT_TEMPLATES.length}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {REPORT_TEMPLATES.map((t) => {
            const rs = state[t.id] ?? { status: 'idle' };
            return (
              <div
                key={t.id}
                className="flex flex-col gap-2 p-3 rounded-md bg-dark-900/40 border border-white/[0.06]"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-text-dark-primary">
                      {t.label}
                    </div>
                    <div className="text-[10px] uppercase tracking-wider text-text-dark-tertiary mt-0.5">
                      {t.format}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleGenerate(t.id, t.format)}
                    disabled={rs.status === 'loading'}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-500 text-white hover:bg-accent-400 text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-wait"
                  >
                    <Download size={12} />
                    {rs.status === 'loading' ? 'A gerar…' : 'Gerar'}
                  </button>
                </div>
                {rs.status === 'ready' && (
                  <div className="text-[10px] text-success">
                    ✓ {rs.rowCount} linhas · download iniciado
                  </div>
                )}
                {rs.status === 'not_implemented' && (
                  <div className="text-[10px] text-warning truncate" title={rs.message ?? ''}>
                    Template ainda não wired
                  </div>
                )}
                {rs.status === 'error' && (
                  <div className="text-[10px] text-danger truncate" title={rs.message ?? ''}>
                    Erro: {rs.message}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <div className="mt-4 px-3 py-2 rounded-md bg-primary-500/10 border border-primary-500/30 text-xs text-primary-300">
          Endpoint <code className="font-mono">POST /v1/reports/generate</code> live (Q.18.ZIP.BE.4). Templates <em>producao</em>, <em>cliente</em> e <em>qualidade</em> delegam aos services existentes; restantes retornam <em>not_implemented</em> sem 5xx.
        </div>
      </Panel>
    </div>
  );
}
