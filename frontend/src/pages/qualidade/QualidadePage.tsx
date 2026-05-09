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
} from 'lucide-react';
import { PageHeader, Tabs, Panel, EmptyState } from '../../components/dark';
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

const TAB_IDS = [
  'resumo',
  'erros',
  'moldes',
  'retrabalho',
  'diagnostico',
  'oee',
] as const;
type TabId = (typeof TAB_IDS)[number];

function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

// ─── Fetch helpers para tabs Erros/Retrabalho ─────────────────────────────

async function fetchQualityRework(filter: 'open' | 'rework') {
  try {
    const resp = await fetch(
      `http://127.0.0.1:8001/v1/quality/rework?filter=${filter}&limit=20`,
      { headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' } }
    );
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

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
        {activeTab === 'erros' && <ReworkListTab filter="open" />}
        {activeTab === 'moldes' && <MoldsTab />}
        {activeTab === 'retrabalho' && <ReworkListTab filter="rework" />}
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
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Tabs novas Q.18.ZIP Onda 4
// ═══════════════════════════════════════════════════════════════════════════════

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
          title={`Endpoint /v1/quality/rework indisponível`}
          hint={
            isReworkTab
              ? 'Quando wired, esta tab listará retrabalhos em curso (Hull/Defeito/Custo/Tempo extra/Atribuído/Estado).'
              : 'Quando wired, esta tab listará defeitos abertos (DEF id/Hull/Fase/Tipo/Severidade/OP/Aberto há/Estado).'
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
                <th className="px-3 py-2">Aberto há</th>
                <th className="px-3 py-2">Estado</th>
              </tr>
            </thead>
            <tbody>
              {items.slice(0, 20).map((r, idx) => (
                <tr
                  key={r.id ?? idx}
                  className="border-b border-white/[0.04] hover:bg-white/[0.02]"
                >
                  <td className="px-3 py-2 font-mono text-text-dark-primary">{r.id ?? '—'}</td>
                  <td className="px-3 py-2 text-text-dark-secondary">{r.hull ?? r.order_id ?? '—'}</td>
                  <td className="px-3 py-2 text-text-dark-secondary">{r.phase ?? '—'}</td>
                  <td className="px-3 py-2 text-text-dark-secondary">{r.type ?? r.defect_type ?? '—'}</td>
                  <td className="px-3 py-2">
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border bg-warning/15 text-warning border-warning/40">
                      {r.severity ?? '—'}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-text-dark-tertiary">{r.opened_ago ?? '—'}</td>
                  <td className="px-3 py-2 text-text-dark-secondary">{r.status ?? '—'}</td>
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
  return (
    <Panel title="Moldes em risco" badge="—" flush>
      <EmptyState
        title="Cards moldes com ciclos/100, manutenção, defeitos"
        hint={
          'Endpoint /v1/quality/molds/at-risk ainda não está exposto (Q.18.ZIP.BE.3 deferred). ' +
          'Quando wired, mostra grid 4×2 cards de moldes com taxa erro semana, ciclos/100, próx. manutenção e barra defeitos.'
        }
        mascot
        size="md"
      />
    </Panel>
  );
}
