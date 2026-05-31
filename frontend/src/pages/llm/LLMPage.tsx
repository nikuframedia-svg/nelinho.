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
import { BarChart3, MessageSquare, BookOpen, BellRing } from 'lucide-react';
import { Tabs } from '../../components/dark';
import CopilotPage from '../copilot/CopilotPage';
import RegrasPage from '../admin/RegrasPage';
import { KPIsTab } from './KPIsTab';
import { AlertasTab } from './AlertasTab';

type LLMTab = 'chat' | 'kpis' | 'regras' | 'alertas';

const TABS: { id: LLMTab; label: string; icon: React.ReactNode }[] = [
  { id: 'chat', label: 'Chat', icon: <MessageSquare size={14} /> },
  { id: 'kpis', label: 'KPIs', icon: <BarChart3 size={14} /> },
  { id: 'alertas', label: 'Alertas', icon: <BellRing size={14} /> },
  { id: 'regras', label: 'Regras LLM', icon: <BookOpen size={14} /> },
];

export default function LLMPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const rawTab = searchParams.get('tab') as LLMTab | null;
  const tab: LLMTab =
    rawTab === 'kpis' || rawTab === 'regras' || rawTab === 'alertas' ? rawTab : 'chat';

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

  if (tab === 'alertas') {
    return (
      <div className="flex flex-col h-full">
        <TabBar tab={tab} setTab={setTab} />
        <div className="flex-1 min-h-0 overflow-auto">
          <AlertasTab />
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

// ── TabBar partilhada — usa o componente Tabs canónico (Q.123) ─────────────
// Antes era uma reimplementação bespoke do underline; agora delega no <Tabs>
// partilhado para consistência visual/acessibilidade com as outras páginas.

function TabBar({
  tab,
  setTab,
}: {
  tab: LLMTab;
  setTab: (t: LLMTab) => void;
}) {
  return (
    <div className="border-b border-bd-1 bg-bg-base px-4 shrink-0">
      <Tabs tabs={TABS} value={tab} onChange={(id) => setTab(id as LLMTab)} />
    </div>
  );
}
