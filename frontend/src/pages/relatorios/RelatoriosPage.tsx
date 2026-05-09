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

import { lazy, Suspense, useMemo } from 'react';
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

const REPORT_TEMPLATES = [
  { id: 'producao', label: 'Produção mensal', format: 'PDF' },
  { id: 'cliente', label: 'Por cliente', format: 'PDF' },
  { id: 'qualidade', label: 'Qualidade & retrabalho', format: 'Excel' },
  { id: 'payroll', label: 'Payroll', format: 'Excel' },
  { id: 'cogs', label: 'COGS detalhado', format: 'Excel' },
  { id: 'inventario', label: 'Inventário & ABC', format: 'Excel' },
];

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
        {activeTab === 'export' && (
          <div className="px-4">
            <Panel title="Templates disponíveis" badge={REPORT_TEMPLATES.length}>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {REPORT_TEMPLATES.map((t) => (
                  <div
                    key={t.id}
                    className="flex items-center justify-between gap-2 p-3 rounded-md bg-dark-900/40 border border-white/[0.06]"
                  >
                    <div>
                      <div className="text-sm font-medium text-text-dark-primary">
                        {t.label}
                      </div>
                      <div className="text-[10px] uppercase tracking-wider text-text-dark-tertiary mt-0.5">
                        {t.format}
                      </div>
                    </div>
                    <button
                      type="button"
                      disabled
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-dark-700 text-text-dark-tertiary text-xs font-medium opacity-50 cursor-not-allowed border border-white/[0.06]"
                      title="Endpoint /v1/reports/generate em desenvolvimento"
                    >
                      <Download size={12} />
                      Gerar
                    </button>
                  </div>
                ))}
              </div>
              <div className="mt-4 px-3 py-2 rounded-md bg-warning/10 border border-warning/30 text-xs text-warning">
                Endpoint <code className="font-mono">POST /v1/reports/generate</code> em desenvolvimento (Q.18.ZIP.BE.3 deferred). Geração de relatórios fica disponível quando criado.
              </div>
            </Panel>
          </div>
        )}
      </div>
    </div>
  );
}
