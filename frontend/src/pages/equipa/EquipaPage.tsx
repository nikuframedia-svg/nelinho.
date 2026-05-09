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
  AlertTriangle,
  FlaskConical,
  GraduationCap,
  RefreshCw,
  Sparkles,
  Info,
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

const TAB_IDS = [
  'lista',
  'alocacoes',
  'produtividade',
  'risco',
  'simulador',
  'formacao',
] as const;
type TabId = (typeof TAB_IDS)[number];

function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

/** Banner explicando que Risco/Simulador/Formação partilham o
 *  WorkforceDashboard até endpoints dedicados (Q.18.ZIP.BE.2) existirem. */
function FocusBanner({ focus }: { focus: 'risco' | 'simulador' | 'formacao' }) {
  const labels = {
    risco: {
      title: 'Tab Risco',
      hint: 'Painel completo abaixo: foca em RiskHeatmap (skill × operador) + SPOFs + DependencyGraph + CascadeImpact.',
    },
    simulador: {
      title: 'Tab Simulador',
      hint: 'Painel completo abaixo: foca em WorkforceSimulator (what-if ausência) + ScenarioComparisonMatrix.',
    },
    formacao: {
      title: 'Tab Formação',
      hint: 'Painel completo abaixo: foca em TrainingRecommendation (planos sugeridos por skill gap).',
    },
  };
  const f = labels[focus];
  return (
    <div className="mx-2 mb-3 flex items-start gap-2 px-3 py-2 rounded-md bg-primary-500/5 border border-primary-500/20">
      <Info size={14} className="shrink-0 mt-0.5 text-primary-300" />
      <div className="flex-1 text-xs">
        <span className="font-semibold text-primary-300">{f.title}</span>
        <span className="text-text-dark-secondary"> · {f.hint}</span>
        <div className="text-[10px] text-text-dark-tertiary mt-1">
          Decomposição em endpoints dedicados (
          <code className="font-mono">/v1/workforce/risks/spof</code>,
          <code className="font-mono">/simulate/absence</code>,
          <code className="font-mono">/training/suggestions</code>) ainda não wired
          (Q.18.ZIP.BE.2 deferred).
        </div>
      </div>
    </div>
  );
}

export default function EquipaPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const activeTab: TabId = isTabId(tabFromUrl) ? tabFromUrl : 'lista';

  const tabs = useMemo(
    () => [
      { id: 'lista', label: 'Lista', icon: <Users size={13} /> },
      { id: 'alocacoes', label: 'Alocações', icon: <CalendarRange size={13} /> },
      { id: 'produtividade', label: 'Produtividade', icon: <TrendingUp size={13} /> },
      { id: 'risco', label: 'Risco', icon: <AlertTriangle size={13} /> },
      { id: 'simulador', label: 'Simulador', icon: <FlaskConical size={13} /> },
      { id: 'formacao', label: 'Formação', icon: <GraduationCap size={13} /> },
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
        {activeTab === 'risco' && (
          <>
            <FocusBanner focus="risco" />
            <Suspense fallback={fallback}>
              <WorkforceDashboard />
            </Suspense>
          </>
        )}
        {activeTab === 'simulador' && (
          <>
            <FocusBanner focus="simulador" />
            <Suspense fallback={fallback}>
              <WorkforceDashboard />
            </Suspense>
          </>
        )}
        {activeTab === 'formacao' && (
          <>
            <FocusBanner focus="formacao" />
            <Suspense fallback={fallback}>
              <WorkforceDashboard />
            </Suspense>
          </>
        )}
      </div>
    </div>
  );
}
