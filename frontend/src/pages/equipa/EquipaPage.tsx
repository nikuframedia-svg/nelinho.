/**
 * EquipaPage — porto do nelo (1).zip pages-2.jsx:EquipaPage.
 *
 * 4 tabs (do brief PROMPT_CLAUDE_CODE.md §3.5 + WorkforceDashboard
 * cobre Risco/Simulador/Formação internamente via activeView):
 *   • Lista         — EmployeesPage (Q.3 wired ao backend real)
 *   • Alocações     — AllocationsPage existing
 *   • Produtividade — ProductivityPage existing
 *   • Workforce     — WorkforceDashboard existing (Heatmap + Graph +
 *                     Scenarios + Simulator + Training — tudo num só
 *                     componente já composto, Q.X palantir)
 *
 * Brief sugere 6 tabs separadas (Lista/Alocações/Produtividade/Risco/
 * Simulador/Formação) — Risco/Simulador/Formação ficam DENTRO da tab
 * Workforce até decomposição em sub-sprints futuros (cada um precisa
 * de endpoint dedicado: /v1/workforce/risks/spof,
 * /v1/workforce/simulate/absence, /v1/workforce/training/suggestions).
 *
 * Sprint Q.18.ZIP.F.
 */

import { lazy, Suspense, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Users,
  CalendarRange,
  TrendingUp,
  Activity,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { PageHeader, Tabs } from '../../components/dark';
import { SkeletonLoader } from '../../components/ui/Skeleton';

const EmployeesPage = lazy(() =>
  import('../core/EmployeesPage').then((m) => ({ default: m.EmployeesPage }))
);
const AllocationsPage = lazy(() =>
  import('../hr/AllocationsPage').then((m) => ({ default: m.AllocationsPage }))
);
const ProductivityPage = lazy(() =>
  import('../hr/ProductivityPage').then((m) => ({ default: m.ProductivityPage }))
);
const WorkforceDashboard = lazy(() =>
  import('../workforce/WorkforceDashboard').then((m) => ({
    default: m.WorkforceDashboard,
  }))
);

function askCopilot(query: string) {
  window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
}

const TAB_IDS = ['lista', 'alocacoes', 'produtividade', 'workforce'] as const;
type TabId = (typeof TAB_IDS)[number];

function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

export default function EquipaPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const activeTab: TabId = isTabId(tabFromUrl) ? tabFromUrl : 'lista';

  const tabs = useMemo(
    () => [
      { id: 'lista', label: 'Lista', icon: <Users size={13} /> },
      {
        id: 'alocacoes',
        label: 'Alocações',
        icon: <CalendarRange size={13} />,
      },
      {
        id: 'produtividade',
        label: 'Produtividade',
        icon: <TrendingUp size={13} />,
      },
      {
        id: 'workforce',
        label: 'Risco · Simulador · Formação',
        icon: <Activity size={13} />,
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
        title="Equipa"
        subtitle="OPERADORES · ALOCAÇÕES · PRODUTIVIDADE · RISCO"
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
                askCopilot(`Que sinais de risco há na equipa hoje (tab ${activeTab})?`)
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
        {activeTab === 'lista' && (
          <Suspense fallback={fallback}>
            <EmployeesPage />
          </Suspense>
        )}
        {activeTab === 'alocacoes' && (
          <Suspense fallback={fallback}>
            <AllocationsPage />
          </Suspense>
        )}
        {activeTab === 'produtividade' && (
          <Suspense fallback={fallback}>
            <ProductivityPage />
          </Suspense>
        )}
        {activeTab === 'workforce' && (
          <Suspense fallback={fallback}>
            <WorkforceDashboard />
          </Suspense>
        )}
      </div>
    </div>
  );
}
