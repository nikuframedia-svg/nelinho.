/**
 * LLMPage — /llm · consolidação Chat + KPIs + Regras LLM (Q.115.N)
 * =================================================================
 *
 * Três tabs controladas por ?tab=chat|kpis|regras (default: chat).
 *
 *   chat   → herda CopilotPage directamente (histórico Redis, citações,
 *             pills de modo — zero duplicação de lógica)
 *   kpis   → lista de KPIs com polling 30s + gráfico seleccionado
 *   regras → herda RegrasPage directamente (logic-as-data Q.17)
 *
 * ZERO MOCKS — dados reais de /v1/profit/kpis/snapshot-explained.
 * NÃO remove rotas /copilot e /regras existentes (Q.115.P faz isso).
 */

import { useSearchParams } from 'react-router-dom';
import { BarChart3, MessageSquare, BookOpen } from 'lucide-react';
import CopilotPage from '../copilot/CopilotPage';
import RegrasPage from '../admin/RegrasPage';
import { KPIsTab } from './KPIsTab';

type LLMTab = 'chat' | 'kpis' | 'regras';

const TABS: { id: LLMTab; label: string; icon: React.ReactNode }[] = [
  { id: 'chat', label: 'Chat', icon: <MessageSquare size={14} /> },
  { id: 'kpis', label: 'KPIs', icon: <BarChart3 size={14} /> },
  { id: 'regras', label: 'Regras LLM', icon: <BookOpen size={14} /> },
];

export default function LLMPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const rawTab = searchParams.get('tab') as LLMTab | null;
  const tab: LLMTab = rawTab === 'kpis' || rawTab === 'regras' ? rawTab : 'chat';

  const setTab = (t: LLMTab) => {
    setSearchParams({ tab: t }, { replace: true });
  };

  // Tabs chat e regras delegam completamente para as páginas existentes,
  // que têm o seu próprio DarkPageLayout. A LLMPage não adiciona wrapper
  // extra para evitar layout duplo.
  if (tab === 'chat') {
    return (
      <div className="flex flex-col h-full">
        <TabBar tab={tab} setTab={setTab} />
        <div className="flex-1 min-h-0 overflow-hidden">
          <CopilotPage />
        </div>
      </div>
    );
  }

  if (tab === 'regras') {
    return (
      <div className="flex flex-col h-full">
        <TabBar tab={tab} setTab={setTab} />
        <div className="flex-1 min-h-0 overflow-auto">
          <RegrasPage />
        </div>
      </div>
    );
  }

  // tab === 'kpis'
  return (
    <div className="flex flex-col h-full">
      <TabBar tab={tab} setTab={setTab} />
      <div className="flex-1 min-h-0 overflow-auto">
        <KPIsTab />
      </div>
    </div>
  );
}

// ── TabBar partilhada ────────────────────────────────────────────────────

function TabBar({
  tab,
  setTab,
}: {
  tab: LLMTab;
  setTab: (t: LLMTab) => void;
}) {
  return (
    <div
      className="flex items-center gap-1 border-b border-bd-1 bg-bg-base px-4"
      style={{ minHeight: 44 }}
      role="tablist"
      aria-label="Secções LLM"
    >
      {TABS.map((t) => {
        const active = t.id === tab;
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => setTab(t.id)}
            className={[
              'inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium',
              'border-b-2 -mb-px transition-colors',
              active
                ? 'border-accent text-fg-0'
                : 'border-transparent text-fg-3 hover:text-fg-1',
            ].join(' ')}
          >
            {t.icon}
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
