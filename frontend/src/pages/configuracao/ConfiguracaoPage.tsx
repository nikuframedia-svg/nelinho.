/**
 * ConfiguracaoPage — porto do nelo (1).zip pages-2.jsx:ConfiguracaoPage.
 *
 * 7 tabs canónicas (vs 10 do brief — algumas consolidadas):
 *   • Geral        — wrap SettingsPage (tem tabs internas: scheduling/
 *                    cura/molds/quality/workforce/transport/etc — 13 tabs)
 *   • Aprendizagem — wrap RegrasPage Q.17 NL→DSL + LearnedRulesPage
 *                    Camada 1 (sub-tabs internas)
 *   • Trust        — wrap DQAPage v2 (7 components, 5 gates)
 *   • Acessos      — wrap RBACPage
 *   • Auditoria    — wrap AuditTrailPage
 *   • Sistema      — wrap HealthDashboardPage + RAGIngest + DataIngestion
 *                    + ToolRegistry (sub-tabs internas)
 *   • Dados Mestre — wrap Customers/Suppliers/Machines/Products/BOM/
 *                    Operations/Rates/Tenants (sub-tabs internas)
 *
 * Sprint Q.18.ZIP.H.
 */

import { lazy, Suspense, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Settings,
  Brain,
  Shield,
  Lock,
  FileSearch,
  Server,
  Database,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { PageHeader, Tabs } from '../../components/dark';
import { SkeletonLoader } from '../../components/ui/Skeleton';

// ─── Pages wrapped ───
const SettingsPage = lazy(() =>
  import('../admin/SettingsPage').then((m) => ({ default: m.SettingsPage }))
);
const RegrasPage = lazy(() => import('../admin/RegrasPage'));
const LearnedRulesPage = lazy(() =>
  import('../admin/LearnedRulesPage').then((m) => ({
    default: m.LearnedRulesPage,
  }))
);
const DQAPage = lazy(() =>
  import('../admin/DQAPage').then((m) => ({ default: m.DQAPage }))
);
const RBACPage = lazy(() =>
  import('../admin/RBACPage').then((m) => ({ default: m.RBACPage }))
);
const AuditTrailPage = lazy(() =>
  import('../admin/AuditTrailPage').then((m) => ({ default: m.AuditTrailPage }))
);
const HealthDashboardPage = lazy(() =>
  import('../admin/HealthDashboardPage').then((m) => ({
    default: m.HealthDashboardPage,
  }))
);
const RAGIngestPage = lazy(() =>
  import('../admin/RAGIngestPage').then((m) => ({ default: m.RAGIngestPage }))
);
const DataIngestionPage = lazy(() =>
  import('../admin/DataIngestionPage').then((m) => ({
    default: m.DataIngestionPage,
  }))
);
const ToolRegistryPage = lazy(() =>
  import('../admin/ToolRegistryPage').then((m) => ({
    default: m.ToolRegistryPage,
  }))
);

// Master data
const CustomersPage = lazy(() =>
  import('../core/CustomersPage').then((m) => ({ default: m.CustomersPage }))
);
const SuppliersPage = lazy(() =>
  import('../core/SuppliersPage').then((m) => ({ default: m.SuppliersPage }))
);
const MachinesPage = lazy(() =>
  import('../core/MachinesPage').then((m) => ({ default: m.MachinesPage }))
);
const ProductsPage = lazy(() =>
  import('../core/ProductsPage').then((m) => ({ default: m.ProductsPage }))
);
const BOMPage = lazy(() =>
  import('../core/BOMPage').then((m) => ({ default: m.BOMPage }))
);
const OperationsPage = lazy(() =>
  import('../core/OperationsPage').then((m) => ({ default: m.OperationsPage }))
);
const RatesPage = lazy(() =>
  import('../core/RatesPage').then((m) => ({ default: m.RatesPage }))
);
const TenantsPage = lazy(() =>
  import('../core/TenantsPage').then((m) => ({ default: m.TenantsPage }))
);

function askCopilot(query: string) {
  window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
}

const TAB_IDS = [
  'geral',
  'aprendizagem',
  'trust',
  'acessos',
  'auditoria',
  'sistema',
  'mestre',
] as const;
type TabId = (typeof TAB_IDS)[number];
function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

const APREND_SUB = ['regras', 'aprendidas'] as const;
type AprendSub = (typeof APREND_SUB)[number];

const SISTEMA_SUB = ['saude', 'ingestao', 'rag', 'tools'] as const;
type SistemaSub = (typeof SISTEMA_SUB)[number];

const MESTRE_SUB = [
  'clientes',
  'fornecedores',
  'maquinas',
  'produtos',
  'bom',
  'operacoes',
  'tarifas',
  'tenants',
] as const;
type MestreSub = (typeof MESTRE_SUB)[number];

export default function ConfiguracaoPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const activeTab: TabId = isTabId(tabFromUrl) ? tabFromUrl : 'geral';

  const [aprendSub, setAprendSub] = useState<AprendSub>('regras');
  const [sistemaSub, setSistemaSub] = useState<SistemaSub>('saude');
  const [mestreSub, setMestreSub] = useState<MestreSub>('clientes');

  const tabs = useMemo(
    () => [
      { id: 'geral', label: 'Geral', icon: <Settings size={13} /> },
      { id: 'aprendizagem', label: 'Aprendizagem', icon: <Brain size={13} /> },
      { id: 'trust', label: 'Trust Index', icon: <Shield size={13} /> },
      { id: 'acessos', label: 'Acessos', icon: <Lock size={13} /> },
      { id: 'auditoria', label: 'Auditoria', icon: <FileSearch size={13} /> },
      { id: 'sistema', label: 'Sistema', icon: <Server size={13} /> },
      { id: 'mestre', label: 'Dados Mestre', icon: <Database size={13} /> },
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
        title="Configuração"
        subtitle="GERAL · APRENDIZAGEM · TRUST · ACESSOS · AUDITORIA · SISTEMA · DADOS MESTRE"
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
                askCopilot(`Que regras estão activas hoje na tab ${activeTab}?`)
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
        {/* Geral — wrap SettingsPage que tem 13 tabs próprias */}
        {activeTab === 'geral' && (
          <Suspense fallback={fallback}>
            <SettingsPage />
          </Suspense>
        )}

        {/* Aprendizagem — sub-tabs Regras (NL→DSL Q.17) | Aprendidas (Camada 1) */}
        {activeTab === 'aprendizagem' && (
          <div>
            <div className="px-4 mb-2">
              <Tabs
                variant="pills"
                tabs={[
                  { id: 'regras', label: 'Regras (NL→DSL Q.17)' },
                  { id: 'aprendidas', label: 'Regras aprendidas (Camada 1)' },
                ]}
                value={aprendSub}
                onChange={(v) => setAprendSub(v as AprendSub)}
              />
            </div>
            <Suspense fallback={fallback}>
              {aprendSub === 'regras' ? <RegrasPage /> : <LearnedRulesPage />}
            </Suspense>
          </div>
        )}

        {activeTab === 'trust' && (
          <Suspense fallback={fallback}>
            <DQAPage />
          </Suspense>
        )}

        {activeTab === 'acessos' && (
          <Suspense fallback={fallback}>
            <RBACPage />
          </Suspense>
        )}

        {activeTab === 'auditoria' && (
          <Suspense fallback={fallback}>
            <AuditTrailPage />
          </Suspense>
        )}

        {/* Sistema — sub-tabs Saude | Ingestao | RAG | Tools */}
        {activeTab === 'sistema' && (
          <div>
            <div className="px-4 mb-2">
              <Tabs
                variant="pills"
                tabs={[
                  { id: 'saude', label: 'Saúde' },
                  { id: 'ingestao', label: 'Ingestão' },
                  { id: 'rag', label: 'RAG' },
                  { id: 'tools', label: 'Tools' },
                ]}
                value={sistemaSub}
                onChange={(v) => setSistemaSub(v as SistemaSub)}
              />
            </div>
            <Suspense fallback={fallback}>
              {sistemaSub === 'saude' && <HealthDashboardPage />}
              {sistemaSub === 'ingestao' && <DataIngestionPage />}
              {sistemaSub === 'rag' && <RAGIngestPage />}
              {sistemaSub === 'tools' && <ToolRegistryPage />}
            </Suspense>
          </div>
        )}

        {/* Dados Mestre — sub-tabs */}
        {activeTab === 'mestre' && (
          <div>
            <div className="px-4 mb-2">
              <Tabs
                variant="pills"
                tabs={[
                  { id: 'clientes', label: 'Clientes' },
                  { id: 'fornecedores', label: 'Fornecedores' },
                  { id: 'maquinas', label: 'Máquinas' },
                  { id: 'produtos', label: 'Produtos' },
                  { id: 'bom', label: 'BOM' },
                  { id: 'operacoes', label: 'Operações' },
                  { id: 'tarifas', label: 'Tarifas' },
                  { id: 'tenants', label: 'Tenants' },
                ]}
                value={mestreSub}
                onChange={(v) => setMestreSub(v as MestreSub)}
              />
            </div>
            <Suspense fallback={fallback}>
              {mestreSub === 'clientes' && <CustomersPage />}
              {mestreSub === 'fornecedores' && <SuppliersPage />}
              {mestreSub === 'maquinas' && <MachinesPage />}
              {mestreSub === 'produtos' && <ProductsPage />}
              {mestreSub === 'bom' && <BOMPage />}
              {mestreSub === 'operacoes' && <OperationsPage />}
              {mestreSub === 'tarifas' && <RatesPage />}
              {mestreSub === 'tenants' && <TenantsPage />}
            </Suspense>
          </div>
        )}
      </div>
    </div>
  );
}
