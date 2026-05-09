/**
 * PlaneamentoPage — porto do nelo (1).zip pages-1.jsx:PlaneamentoPage.
 *
 * 4 tabs (do brief PROMPT_CLAUDE_CODE.md §3.3):
 *   • Atribuição — DragDropPlanner mode='assignment' (Q.4 wired)
 *   • Materiais — MRPPage + InventoryPage (combinados)
 *   • Forecast — ForecastPage existing
 *   • Simulador — TwinPage existing (cenários what-if)
 *
 * Tabs sincronizadas com URL `?tab=...` para deep-linking.
 *
 * Sprint Q.18.ZIP.D.
 */

import { lazy, Suspense, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  CalendarRange,
  Boxes,
  TrendingUp,
  FlaskConical,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { PageHeader, Tabs } from '../../components/dark';
import { SkeletonLoader } from '../../components/ui/Skeleton';

// Lazy imports — cada tab carrega só quando seleccionada
const AllocationsPage = lazy(() =>
  import('../hr/AllocationsPage').then((m) => ({ default: m.AllocationsPage }))
);
const MRPPage = lazy(() =>
  import('../plan/MRPPage').then((m) => ({ default: m.MRPPage }))
);
const InventoryPage = lazy(() =>
  import('../supply/InventoryPage').then((m) => ({ default: m.InventoryPage }))
);
const ForecastPage = lazy(() =>
  import('../supply/ForecastPage').then((m) => ({ default: m.ForecastPage }))
);
const TwinPage = lazy(() =>
  import('../twin/TwinPage').then((m) => ({ default: m.TwinPage }))
);

function askCopilot(query: string) {
  window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
}

const TAB_IDS = ['atribuicao', 'materiais', 'forecast', 'simulador'] as const;
type TabId = (typeof TAB_IDS)[number];

function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

export default function PlaneamentoPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const activeTab: TabId = isTabId(tabFromUrl) ? tabFromUrl : 'atribuicao';

  const tabs = useMemo(
    () => [
      {
        id: 'atribuicao',
        label: 'Atribuição',
        icon: <CalendarRange size={13} />,
      },
      {
        id: 'materiais',
        label: 'Materiais',
        icon: <Boxes size={13} />,
      },
      {
        id: 'forecast',
        label: 'Previsão',
        icon: <TrendingUp size={13} />,
      },
      {
        id: 'simulador',
        label: 'Simulador',
        icon: <FlaskConical size={13} />,
      },
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
        title="Planeamento"
        subtitle="ATRIBUIÇÕES · MRP · FORECAST · CENÁRIOS"
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
                  `Que decisões de planeamento são mais críticas hoje em ${activeTab}?`
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
        <Tabs
          tabs={tabs}
          value={activeTab}
          onChange={handleTabChange}
        />
      </div>

      <div className="px-2 py-4">
        {activeTab === 'atribuicao' && (
          <Suspense fallback={fallback}>
            <AllocationsPage />
          </Suspense>
        )}
        {activeTab === 'materiais' && (
          <Suspense fallback={fallback}>
            <div className="space-y-6">
              <MRPPage />
              <InventoryPage />
            </div>
          </Suspense>
        )}
        {activeTab === 'forecast' && (
          <Suspense fallback={fallback}>
            <ForecastPage />
          </Suspense>
        )}
        {activeTab === 'simulador' && (
          <Suspense fallback={fallback}>
            <TwinPage />
          </Suspense>
        )}
      </div>
    </div>
  );
}
