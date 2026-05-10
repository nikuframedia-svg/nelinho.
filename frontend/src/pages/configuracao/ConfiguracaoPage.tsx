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
import { useQuery } from '@tanstack/react-query';
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
import { Q17Dashboard } from '../../components/aprendizagem/Q17Panels';
import { BCamadasDashboard } from '../../components/aprendizagem/BCamadasPanels';
import { CausalDashboard } from '../../components/causal/CausalPanels';
import { CopilotExtrasDashboard } from '../../components/copilot/CopilotExtras';
import { GovernanceDashboard } from '../../components/governance/GovernancePanels';
import { FactoryPulseDashboard } from '../../components/dataproduct/FactoryPulsePanels';

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

const APREND_SUB = ['resumo', 'regras', 'aprendidas', 'q17', 'camadas', 'causal', 'copilot', 'governance', 'dataproduct'] as const;
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

  const [aprendSub, setAprendSub] = useState<AprendSub>('resumo');
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

        {/* Aprendizagem — 4 sub-tabs (Onda 1 Q.17):
            • Resumo (zip page-learning.jsx port literal: regras + pesos)
            • Regras (NL→DSL Q.17 — RegrasPage rica para criar/editar)
            • Aprendidas (Camada 1 — LearnedRulesPage existing)
            • Q.17 Avançado — audit firings + impact + schema + conflitos */}
        {activeTab === 'aprendizagem' && (
          <div>
            <div className="px-4 mb-2">
              <Tabs
                variant="pills"
                tabs={[
                  { id: 'resumo', label: 'Resumo' },
                  { id: 'regras', label: 'Regras (NL→DSL Q.17)' },
                  { id: 'aprendidas', label: 'Regras aprendidas (Camada 1)' },
                  { id: 'q17', label: 'Q.17 Avançado' },
                  { id: 'camadas', label: '4 Camadas Aprendizagem' },
                  { id: 'causal', label: 'Causal/Explain' },
                  { id: 'copilot', label: 'Copilot extras' },
                  { id: 'governance', label: 'Governance/Audit' },
                  { id: 'dataproduct', label: 'Factory data product' },
                ]}
                value={aprendSub}
                onChange={(v) => setAprendSub(v as AprendSub)}
              />
            </div>
            <Suspense fallback={fallback}>
              {aprendSub === 'resumo' ? (
                <AprendizagemZipView />
              ) : aprendSub === 'regras' ? (
                <RegrasPage />
              ) : aprendSub === 'aprendidas' ? (
                <LearnedRulesPage />
              ) : aprendSub === 'q17' ? (
                <div className="px-4">
                  <Q17Dashboard />
                </div>
              ) : aprendSub === 'camadas' ? (
                <div className="px-4">
                  <BCamadasDashboard />
                </div>
              ) : aprendSub === 'causal' ? (
                <div className="px-4">
                  <CausalDashboard />
                </div>
              ) : aprendSub === 'copilot' ? (
                <div className="px-4">
                  <CopilotExtrasDashboard />
                </div>
              ) : aprendSub === 'governance' ? (
                <div className="px-4">
                  <GovernanceDashboard />
                </div>
              ) : (
                <div className="px-4">
                  <FactoryPulseDashboard />
                </div>
              )}
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

// ═══════════════════════════════════════════════════════════════════════════
// AprendizagemZipView — port literal page-extra.jsx PageLearning
// (regras aprendidas + pesos da fitness, side-by-side)
// ═══════════════════════════════════════════════════════════════════════════

interface LearnedRuleApi {
  id: string;
  text?: string;
  rule_text?: string;
  description?: string;
  status?: string;
  confidence?: number;
  basis?: string;
  evidence?: string;
}

interface FitnessWeight {
  key: string;
  default: number;
  learned: number;
}

async function fetchLearnedRules(): Promise<LearnedRuleApi[]> {
  try {
    const resp = await fetch(
      'http://127.0.0.1:8001/v1/governance/preference-rules?limit=20',
      { headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' } },
    );
    if (!resp.ok) return [];
    const data = await resp.json();
    if (Array.isArray(data)) return data;
    return data.items ?? data.rules ?? [];
  } catch {
    return [];
  }
}

async function fetchFitnessWeights(): Promise<FitnessWeight[]> {
  // Endpoint `/v1/governance/learning/weights` — formato pode variar.
  try {
    const resp = await fetch(
      'http://127.0.0.1:8001/v1/governance/learning/weights',
      { headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' } },
    );
    if (!resp.ok) return [];
    const data = await resp.json();
    // Tenta inferir shape — pode ser { weights: { key: value }, defaults: { key: value } }
    if (data?.weights && typeof data.weights === 'object') {
      const defaults = data.defaults ?? {};
      return Object.entries(data.weights).map(([key, learned]) => ({
        key,
        default: Number(defaults[key] ?? 0),
        learned: Number(learned),
      }));
    }
    if (Array.isArray(data)) return data;
    return [];
  } catch {
    return [];
  }
}

function AprendizagemZipView() {
  const rulesQuery = useQuery({
    queryKey: ['aprendizagem-zip', 'rules'],
    queryFn: fetchLearnedRules,
    staleTime: 60_000,
    retry: 0,
  });
  const weightsQuery = useQuery({
    queryKey: ['aprendizagem-zip', 'weights'],
    queryFn: fetchFitnessWeights,
    staleTime: 60_000,
    retry: 0,
  });

  const rules = rulesQuery.data ?? [];
  const weights = weightsQuery.data ?? [];

  return (
    <div className="px-4 space-y-5">
      {/* Explainer */}
      <div
        style={{
          padding: '14px 18px',
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 12,
          fontSize: 13,
          color: 'var(--fg-1)',
          lineHeight: 1.6,
        }}
      >
        <strong style={{ color: 'var(--fg-0)' }}>Transparência total.</strong>{' '}
        Tudo o que o sistema aprendeu está aqui. Pode <strong>aprovar</strong>,{' '}
        <strong>rejeitar</strong>, ou <strong>pausar</strong> qualquer regra. Nada
        é mágico, nada é caixa-preta.
      </div>

      {/* 2-col: Regras + Pesos */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 22 }}>
        {/* Regras aprendidas */}
        <div
          style={{
            background: 'var(--bg-1)',
            border: '1px solid var(--bd-1)',
            borderRadius: 12,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              padding: '18px 22px',
              borderBottom: '1px solid var(--bd-1)',
            }}
          >
            <div className="text-sm font-semibold text-text-dark-primary">
              Regras aprendidas
            </div>
            <div className="text-xs text-text-dark-tertiary mt-0.5">
              Padrões observados nas suas decisões
            </div>
          </div>
          {rulesQuery.isLoading ? (
            <div className="px-4 py-8 text-center text-xs text-text-dark-tertiary">
              A carregar regras…
            </div>
          ) : rules.length === 0 ? (
            <div className="px-4 py-8 text-center text-xs text-text-dark-tertiary">
              Sem regras aprendidas registadas. O sistema aprende observando as
              suas decisões — quando rejeitar/aprovar sugestões consistentemente,
              padrões aparecem aqui.
            </div>
          ) : (
            <div>
              {rules.map((r, i) => {
                const status = (r.status ?? 'active').toLowerCase();
                const isSuggested = status === 'suggested' || status === 'proposed';
                const text = r.text ?? r.rule_text ?? r.description ?? '(sem descrição)';
                const conf = r.confidence ?? null;
                return (
                  <div
                    key={r.id ?? i}
                    style={{
                      padding: '16px 22px',
                      borderBottom:
                        i < rules.length - 1
                          ? '1px solid var(--bd-1)'
                          : 'none',
                    }}
                  >
                    <div className="flex justify-between items-start gap-3">
                      <div style={{ flex: 1 }}>
                        <div className="flex items-center gap-2 mb-1.5">
                          <span
                            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold"
                            style={{
                              background: isSuggested
                                ? 'var(--yellow-bg)'
                                : 'var(--green-bg)',
                              color: isSuggested ? 'var(--yellow)' : 'var(--green)',
                              border: `1px solid ${isSuggested ? 'var(--yellow-bd)' : 'var(--green-bd)'}`,
                            }}
                          >
                            {isSuggested ? '◆ Sugerida' : '● Activa'}
                          </span>
                          {conf !== null ? (
                            <span className="text-[11px] text-text-dark-secondary tabular-nums">
                              Confiança {Math.round(conf * 100)}%
                            </span>
                          ) : null}
                        </div>
                        <div className="text-sm font-medium text-text-dark-primary leading-relaxed">
                          {text}
                        </div>
                        {r.basis || r.evidence ? (
                          <div className="text-xs text-text-dark-secondary mt-1">
                            Base: {r.basis ?? r.evidence}
                          </div>
                        ) : null}
                      </div>
                      <div className="flex gap-2 shrink-0">
                        {isSuggested ? (
                          <>
                            <button
                              type="button"
                              className="px-2.5 py-1 rounded text-xs font-medium"
                              style={{
                                background: 'var(--green)',
                                color: '#fff',
                              }}
                            >
                              Aprovar
                            </button>
                            <button
                              type="button"
                              className="px-2.5 py-1 rounded text-xs text-text-dark-secondary hover:text-text-dark-primary"
                            >
                              Recusar
                            </button>
                          </>
                        ) : (
                          <button
                            type="button"
                            className="px-2.5 py-1 rounded text-xs text-text-dark-secondary hover:text-text-dark-primary"
                          >
                            Pausar
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Pesos da fitness */}
        <div
          style={{
            padding: 22,
            background: 'var(--bg-1)',
            border: '1px solid var(--bd-1)',
            borderRadius: 12,
          }}
        >
          <div className="text-sm font-semibold text-text-dark-primary">
            Pesos da fitness
          </div>
          <div className="text-xs text-text-dark-tertiary mt-0.5 mb-3">
            Como o sistema pondera cada objectivo
          </div>
          <div className="text-[11px] text-text-dark-secondary mb-3 leading-relaxed">
            <strong className="text-text-dark-primary">Default</strong> = padrão
            NELO.{' '}
            <strong style={{ color: 'var(--blue)' }}>Aprendido</strong> = ajustado
            pelas suas decisões.
          </div>
          {weightsQuery.isLoading ? (
            <div className="py-6 text-center text-xs text-text-dark-tertiary">
              A carregar pesos…
            </div>
          ) : weights.length === 0 ? (
            <div className="py-6 text-center text-xs text-text-dark-tertiary">
              Sem pesos aprendidos. Quando o sistema observar suficientes
              decisões, ajusta os pesos automaticamente.
            </div>
          ) : (
            <div className="flex flex-col gap-3.5">
              {weights.map((w) => (
                <div key={w.key}>
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="text-text-dark-secondary">{w.key}</span>
                    <span className="tabular-nums text-text-dark-tertiary">
                      {Math.round(w.default * 100)} →{' '}
                      <span
                        className="font-semibold"
                        style={{ color: 'var(--blue)' }}
                      >
                        {Math.round(w.learned * 100)}%
                      </span>
                    </span>
                  </div>
                  <div
                    style={{
                      position: 'relative',
                      height: 6,
                      background: 'var(--bd-1)',
                      borderRadius: 3,
                    }}
                  >
                    <div
                      style={{
                        position: 'absolute',
                        left: 0,
                        top: 0,
                        bottom: 0,
                        width: `${Math.min(100, w.default * 100 * 2.5)}%`,
                        background: 'var(--bd-3)',
                        borderRadius: 3,
                      }}
                    />
                    <div
                      style={{
                        position: 'absolute',
                        left: 0,
                        top: 0,
                        bottom: 0,
                        width: `${Math.min(100, w.learned * 100 * 2.5)}%`,
                        background: 'var(--blue)',
                        borderRadius: 3,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
