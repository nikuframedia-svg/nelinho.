/**
 * CausalPanels — dashboard causal (Q.60.X).
 *
 * Os 10 painéis foram decompostos para ./panels/ e são re-exportados aqui.
 * Constantes/helpers partilhados em ./causalShared.
 */
import { useState } from 'react';
import { AlertTriangle, Sparkles, ChevronRight } from 'lucide-react';
import { Panel } from '../dark';
import { ErroTreePanel } from './panels/ErroTreePanel';
import { ReichenbachPanel } from './panels/ReichenbachPanel';
import { MillPanel } from './panels/MillPanel';
import { InvestigatePanel } from './panels/InvestigatePanel';
import { NeloDagPanel } from './panels/NeloDagPanel';
import { WorldModelPanel } from './panels/WorldModelPanel';
import { AttributionPanel } from './panels/AttributionPanel';
import { AblationPanel } from './panels/AblationPanel';
import { WhyKpiPanel } from './panels/WhyKpiPanel';
import { PoetiqPanel } from './panels/PoetiqPanel';
export { ErroTreePanel } from './panels/ErroTreePanel';
export { ReichenbachPanel } from './panels/ReichenbachPanel';
export { MillPanel } from './panels/MillPanel';
export { InvestigatePanel } from './panels/InvestigatePanel';
export { NeloDagPanel } from './panels/NeloDagPanel';
export { WorldModelPanel } from './panels/WorldModelPanel';
export { AttributionPanel } from './panels/AttributionPanel';
export { AblationPanel } from './panels/AblationPanel';
export { WhyKpiPanel } from './panels/WhyKpiPanel';
export { PoetiqPanel } from './panels/PoetiqPanel';

const SECTIONS = [
  { id: 'diag', label: 'Diagnostics' },
  { id: 'graph', label: 'NELO_DAG + Attribution' },
  { id: 'why', label: 'Por que?' },
  { id: 'iter', label: 'POETIQ + World-model' },
] as const;
type SectionId = (typeof SECTIONS)[number]['id'];

export function CausalDashboard() {
  const [section, setSection] = useState<SectionId>('diag');

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 px-1">
        <Sparkles size={14} style={{ color: 'var(--fg-3)' }} />
        <div className="flex gap-1 text-xs">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              onClick={() => setSection(s.id)}
              className="rounded-md px-2.5 py-1 transition-colors flex items-center gap-1"
              style={{
                background: section === s.id ? 'var(--bg-3)' : 'transparent',
                color: section === s.id ? 'var(--fg-1)' : 'var(--fg-3)',
              }}
            >
              {s.label}
              {section === s.id && <ChevronRight size={11} />}
            </button>
          ))}
        </div>
        <span className="ml-auto text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Q.18.ZIP.A.Onda4 — D. Causal/Explain
        </span>
      </div>

      {section === 'diag' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <ErroTreePanel />
          <ReichenbachPanel />
          <MillPanel />
          <InvestigatePanel />
        </div>
      )}

      {section === 'graph' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <NeloDagPanel />
          <AttributionPanel />
          <AblationPanel />
        </div>
      )}

      {section === 'why' && (
        <div className="grid grid-cols-1 gap-4">
          <WhyKpiPanel />
          <Panel title="Drawer ExplainDrawer existente" subtitle="Para invocar drawer per-KPI usa o ExplainDrawer já wired em /direcao e /qualidade.">
            <div className="px-3 py-3 text-xs flex items-start gap-2" style={{ color: 'var(--fg-2)' }}>
              <AlertTriangle size={14} style={{ color: 'var(--yellow)' }} />
              <span>
                Componente <code className="font-mono">ExplainDrawer</code> abre em qualquer KPI das pages Direção/OEE/Qualidade.
                Aqui mostra-se apenas o snapshot agregado de 4 KPIs raiz.
              </span>
            </div>
          </Panel>
        </div>
      )}

      {section === 'iter' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <PoetiqPanel />
          <WorldModelPanel />
        </div>
      )}
    </div>
  );
}
