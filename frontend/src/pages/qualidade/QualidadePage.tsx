/**
 * QualidadePage — página "Qualidade" (shell · Q.60.Q).
 *
 * As 10 tabs foram decompostas para ./tabs/. Tipos partilhados em
 * ./qualidadeTypes; hooks, primitivas e constantes em ./qualidadeShared.
 * ZERO MOCKS — cada tab liga a endpoints reais (ver cada ficheiro).
 */
import { useMemo } from 'react';
import {
  ShieldCheck, AlertCircle, Wrench, Repeat, Brain,
  Activity, Layers, Target, Euro, RefreshCw,
} from 'lucide-react';
import { PageHeader, Tabs } from '../../components/dark';
import { useTabRouting } from '../../hooks/useTabRouting';
import { ResumoTab } from './tabs/ResumoTab';
import { PredicoesTab } from './tabs/PredicoesTab';
import { MapaTab } from './tabs/MapaTab';
import { ErrosTab } from './tabs/ErrosTab';
import { MoldesTab } from './tabs/MoldesTab';
import { RetrabalhoTab } from './tabs/RetrabalhoTab';
import { AderenciaTab } from './tabs/AderenciaTab';
import { DiagnosticoTab } from './tabs/DiagnosticoTab';
import { OeeTab } from './tabs/OeeTab';
import { CustosTab } from './tabs/CustosTab';

const TAB_IDS = [
  'resumo', 'predicoes', 'mapa', 'erros', 'moldes',
  'retrabalho', 'aderencia', 'diagnostico', 'oee', 'custos',
] as const;
type TabId = (typeof TAB_IDS)[number];

export default function QualidadePage() {
  const { activeTab, setTab } = useTabRouting(TAB_IDS, 'resumo');

  const tabs = useMemo(
    () => [
      { id: 'resumo', label: 'Resumo', icon: <ShieldCheck size={13} /> },
      { id: 'predicoes', label: 'Predições', icon: <Brain size={13} /> },
      { id: 'mapa', label: 'Mapa do casco', icon: <Layers size={13} /> },
      { id: 'erros', label: 'Erros', icon: <AlertCircle size={13} /> },
      { id: 'moldes', label: 'Moldes', icon: <Wrench size={13} /> },
      { id: 'retrabalho', label: 'Retrabalho', icon: <Repeat size={13} /> },
      { id: 'aderencia', label: 'Aderência', icon: <Target size={13} /> },
      { id: 'diagnostico', label: 'Diagnóstico', icon: <Brain size={13} /> },
      { id: 'oee', label: 'OEE', icon: <Activity size={13} /> },
      { id: 'custos', label: 'Custos vs Ganhos', icon: <Euro size={13} /> },
    ],
    [],
  );

  return (
    <div>
      <PageHeader
        icon={<ShieldCheck size={18} />}
        title="Qualidade"
        subtitle="Erros, retrabalho, OEE, diagnóstico causal · ROI de cada acção"
        actions={
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="inline-flex items-center gap-1.5 text-text-dark-secondary hover:text-text-dark-primary transition-colors"
            style={{
              padding: '6px 12px', height: 32, background: 'var(--bg-2)',
              border: '1px solid var(--bd-2)', borderRadius: 9, fontSize: 12.5,
            }}
          >
            <RefreshCw size={13} />
            Atualizar
          </button>
        }
      />

      <div style={{ padding: '8px 28px 0 28px' }}>
        <Tabs
          tabs={tabs}
          value={activeTab}
          onChange={(id) => setTab(id as TabId)}
          sticky
        />
      </div>

      <div style={{ padding: '20px 28px' }} className="page-enter">
        {activeTab === 'resumo' && <ResumoTab />}
        {activeTab === 'predicoes' && <PredicoesTab />}
        {activeTab === 'mapa' && <MapaTab />}
        {activeTab === 'erros' && <ErrosTab />}
        {activeTab === 'moldes' && <MoldesTab />}
        {activeTab === 'retrabalho' && <RetrabalhoTab />}
        {activeTab === 'aderencia' && <AderenciaTab />}
        {activeTab === 'diagnostico' && <DiagnosticoTab />}
        {activeTab === 'oee' && <OeeTab />}
        {activeTab === 'custos' && <CustosTab />}
      </div>
    </div>
  );
}
