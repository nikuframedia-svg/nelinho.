/**
 * QualidadePage — porto do nelo (1).zip pages-2.jsx:QualidadePage.
 *
 * 4 tabs (vs 6 do brief — Erros/Moldes/Retrabalho consolidados em
 * Resumo até endpoints dedicados existirem):
 *   • Resumo      — QualityPage existing (KPIs + Trust + DataSourceNotice)
 *   • Diagnóstico — ExplainPage existing (CausalChain Q.15.D ERRO-TREE
 *                   + Reichenbach + Mill)
 *   • OEE         — OEEPage existing (3-axis quando dados de downtime
 *                   estiverem disponíveis; mostra "bloqueado" entretanto)
 *   • Moldes      — placeholder até endpoint /v1/quality/molds/at-risk
 *                   exposto (deferred)
 *
 * Sprint Q.18.ZIP.G.
 */

import { lazy, Suspense, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ShieldCheck,
  Brain,
  Activity,
  Wrench,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { PageHeader, Tabs, Panel } from '../../components/dark';
import { SkeletonLoader } from '../../components/ui/Skeleton';

const QualityPage = lazy(() =>
  import('../profit/QualityPage').then((m) => ({ default: m.QualityPage }))
);
const ExplainPage = lazy(() =>
  import('../explain/ExplainPage').then((m) => ({ default: m.ExplainPage }))
);
const OEEPage = lazy(() =>
  import('../profit/OEEPage').then((m) => ({ default: m.OEEPage }))
);

function askCopilot(query: string) {
  window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
}

const TAB_IDS = ['resumo', 'diagnostico', 'oee', 'moldes'] as const;
type TabId = (typeof TAB_IDS)[number];

function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

export default function QualidadePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const activeTab: TabId = isTabId(tabFromUrl) ? tabFromUrl : 'resumo';

  const tabs = useMemo(
    () => [
      { id: 'resumo', label: 'Resumo', icon: <ShieldCheck size={13} /> },
      { id: 'diagnostico', label: 'Diagnóstico', icon: <Brain size={13} /> },
      { id: 'oee', label: 'OEE', icon: <Activity size={13} /> },
      { id: 'moldes', label: 'Moldes', icon: <Wrench size={13} /> },
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
        title="Qualidade"
        subtitle="DEFEITOS · RETRABALHO · MOLDES · DIAGNÓSTICO CAUSAL"
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
                askCopilot(
                  `Quais são as causas-raiz mais frequentes na qualidade hoje?`
                )
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
        {activeTab === 'resumo' && (
          <Suspense fallback={fallback}>
            <QualityPage />
          </Suspense>
        )}
        {activeTab === 'diagnostico' && (
          <Suspense fallback={fallback}>
            <ExplainPage />
          </Suspense>
        )}
        {activeTab === 'oee' && (
          <Suspense fallback={fallback}>
            <OEEPage />
          </Suspense>
        )}
        {activeTab === 'moldes' && (
          <Panel title="Moldes em risco" badge="—" flush>
            <div className="px-4 py-12 text-center text-sm text-text-dark-tertiary">
              Endpoint <code className="font-mono text-xs">/v1/quality/molds/at-risk</code> ainda não está exposto.
              <br />
              <span className="text-text-dark-secondary">
                Quando a UI consumir esse dado, esta tab mostrará grid 4×2 cards de moldes com Ciclos/100, próx. manutenção, defeitos.
              </span>
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}
