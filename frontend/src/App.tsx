import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ToastProvider } from './components/ToastProvider';
import { ContractDegradedBanner } from './components/ContractDegradedBanner';
import { SkeletonLoader } from './components/ui/Skeleton';
import { CommandPaletteProvider } from './hooks';
import { RealtimeProvider } from './providers/RealtimeProvider';

// Lazy load heavy pages for code splitting
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
// Sprint Q.18.ZIP.shell — 10 páginas standalone matching nelo.html zip (path PT-PT canónicos)
const DirecaoPage = lazy(() => import('./pages/direcao/DirecaoPage'));
const InboxDecisoesPage = lazy(() => import('./pages/inbox/InboxDecisoesPage'));
const PlanoProducaoPage = lazy(() => import('./pages/plano-producao/PlanoProducaoPage'));
const AtribuicaoDiariaPage = lazy(() => import('./pages/atribuicao/AtribuicaoDiariaPage'));
const OEEPageZip = lazy(() => import('./pages/oee/OEEPage'));
const OperadoresPage = lazy(() => import('./pages/operadores/OperadoresPage'));
const AprendizagemPage = lazy(() => import('./pages/aprendizagem/AprendizagemPage'));
const DefinicoesPage = lazy(() => import('./pages/definicoes/DefinicoesPage'));
// Sprint Q.18.ZIP.B — Painel portado do nelo zip (legacy — agora /direcao)
const PainelPage = lazy(() => import('./pages/painel/PainelPage'));
// Sprint Q.18.ZIP.M.0+M.1 — CEO View novo (substitui CEODashboardPage broken)
const CEOView = lazy(() => import('./pages/painel/CEOView'));
// Sprint Q.18.ZIP.C — Producao portada (mapa fabrica + 3 vistas + DragDrop)
const ProducaoPage = lazy(() => import('./pages/producao/ProducaoPage'));
// Sprint Q.18.ZIP.D — Planeamento portado (4 tabs: Atribuicao/Materiais/Forecast/Simulador)
const PlaneamentoPage = lazy(() => import('./pages/planeamento/PlaneamentoPage'));
// Sprint Q.18.ZIP.E — Expedicao portada (wrap DispatchPage Q.2 com PageHeader)
const ExpedicaoPage = lazy(() => import('./pages/expedicao/ExpedicaoPage'));
// Sprint Q.18.ZIP.F — Equipa portada (4 tabs: Lista/Alocacoes/Produtividade/Workforce)
const EquipaPage = lazy(() => import('./pages/equipa/EquipaPage'));
// Sprint Q.18.ZIP.G — Qualidade portada (4 tabs: Resumo/Diagnostico/OEE/Moldes)
const QualidadePage = lazy(() => import('./pages/qualidade/QualidadePage'));
// Sprint Q.18.ZIP.H — Configuracao portada (7 tabs com sub-tabs Aprendizagem/Sistema/DadosMestre)
const ConfiguracaoPage = lazy(() => import('./pages/configuracao/ConfiguracaoPage'));
// Sprint Q.18.ZIP.I — Relatorios portados (5 tabs: KPIs/Custos/Pricing/Cenarios/Export)
const RelatoriosPage = lazy(() => import('./pages/relatorios/RelatoriosPage'));
const RAGIngestPage = lazy(() => import('./pages/admin/RAGIngestPage').then(m => ({ default: m.RAGIngestPage })));
const SettingsPage = lazy(() => import('./pages/admin/SettingsPage').then(m => ({ default: m.SettingsPage })));
const DQAPage = lazy(() => import('./pages/admin/DQAPage').then(m => ({ default: m.DQAPage })));
const AuditTrailPage = lazy(() => import('./pages/admin/AuditTrailPage').then(m => ({ default: m.AuditTrailPage })));
const RBACPage = lazy(() => import('./pages/admin/RBACPage').then(m => ({ default: m.RBACPage })));
// Sprint E.2 — Camada 1 learned-rules review
const LearnedRulesPage = lazy(() => import('./pages/admin/LearnedRulesPage').then(m => ({ default: m.LearnedRulesPage })));
// Sprint Q.17.C — NL→YAML rule authoring (logic-as-data)
const RegrasPage = lazy(() => import('./pages/admin/RegrasPage'));
// Sprint X.3 — cura/secagem editável (Plan v4 §4.7)
const CuraSecagemPage = lazy(() => import('./pages/admin/CuraSecagemPage'));
// Sprint E.1 — CPO Timeline + MAP-Elites alternatives
const TimelinePage = lazy(() => import('./pages/plan/TimelinePage').then(m => ({ default: m.TimelinePage })));
// Sprint Q.2 — Despacho/Expedição
const DispatchPage = lazy(() => import('./pages/dispatch/DispatchPage'));
// Sprint H — 3 Umwelts (Gestor / Operador tablet / CEO)
const CEODashboardPage = lazy(() => import('./pages/CEODashboardPage').then(m => ({ default: m.CEODashboardPage })));
const OperadorPage = lazy(() => import('./pages/OperadorPage').then(m => ({ default: m.OperadorPage })));

// PALANTIR-LEVEL PAGES
const DataQualityPage = lazy(() => import('./pages/admin/DataQualityPage').then(m => ({ default: m.DataQualityPage })));
const ToolRegistryPage = lazy(() => import('./pages/admin/ToolRegistryPage').then(m => ({ default: m.ToolRegistryPage })));
const DataIngestionPage = lazy(() => import('./pages/admin/DataIngestionPage').then(m => ({ default: m.DataIngestionPage })));

// Sprint Q.7 Fase 1 — Audit / Health dashboard
const HealthDashboardPage = lazy(() => import('./pages/admin/HealthDashboardPage').then(m => ({ default: m.HealthDashboardPage })));

// Lazy load new module pages
const ExplainPage = lazy(() => import('./pages/explain/ExplainPage').then(m => ({ default: m.ExplainPage })));
const TwinPage = lazy(() => import('./pages/twin/TwinPage').then(m => ({ default: m.TwinPage })));
const SandboxPage = lazy(() => import('./pages/sandbox/SandboxPage').then(m => ({ default: m.SandboxPage })));
const SuggestionsPage = lazy(() => import('./pages/improve/SuggestionsPage').then(m => ({ default: m.SuggestionsPage })));

// NEW: Operations Inbox - Action-oriented exceptions view
const OpsInboxPage = lazy(() => import('./pages/OpsInboxPage').then(m => ({ default: m.OpsInboxPage })));

// NEW: Workforce Operations System - The Killer Feature
const WorkforceDashboard = lazy(() => import('./pages/workforce/WorkforceDashboard').then(m => ({ default: m.WorkforceDashboard })));

// Keep lighter pages as regular imports
import { 
  // CORE
  ProductsPage,
  MachinesPage,
  EmployeesPage,
  OperationsPage,
  RatesPage,
  TenantsPage,
  BOMPage,
  CustomersPage,
  SuppliersPage,
  // PLAN
  SchedulingPage,
  MRPPage,
  CapacityPage,
  // PROFIT
  COGSPage, 
  PricingPage,
  ScenariosPage,
  OEEPage,
  QualityPage,
  KPIsPage,
  // HR
  AllocationsPage,
  PayrollPage,
  ProductivityPage,
  // SUPPLY
  InventoryPage,
  ForecastPage,
  ROPPage,
  ABCPage,
  // SHARED
  DecisionsPage,
} from './pages';

function App() {
  return (
    <ErrorBoundary>
      <CommandPaletteProvider>
        <ToastProvider>
          {/* Sprint D.2 — single shared SSE connection for the whole app.
              Components read via useRealtimeType(type, handler). */}
          <RealtimeProvider>
          <BrowserRouter>
            {/* Contract Degraded Banner - shows when API version mismatch */}
            <ContractDegradedBanner />
                
                <Routes>
                <Route path="/" element={<Layout />}>
                  {/* Sprint Q.18.ZIP.shell — / redireciona para /direcao matching zip nelo.html */}
                  <Route index element={<Navigate to="/direcao" replace />} />

                  {/* ── 10 páginas standalone matching zip ── */}
                  <Route path="direcao" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <DirecaoPage />
                    </Suspense>
                  } />
                  <Route path="inbox" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <InboxDecisoesPage />
                    </Suspense>
                  } />
                  <Route path="plano-producao" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <PlanoProducaoPage />
                    </Suspense>
                  } />
                  <Route path="atribuicao" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <AtribuicaoDiariaPage />
                    </Suspense>
                  } />
                  <Route path="oee" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <OEEPageZip />
                    </Suspense>
                  } />
                  <Route path="operadores" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <OperadoresPage />
                    </Suspense>
                  } />
                  <Route path="aprendizagem" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <AprendizagemPage />
                    </Suspense>
                  } />
                  <Route path="regras" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <RegrasPage />
                    </Suspense>
                  } />
                  <Route path="definicoes" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <DefinicoesPage />
                    </Suspense>
                  } />

                  {/* Legacy /painel + Painel-old para debug — agora redirecionam */}
                  <Route path="painel" element={<Navigate to="/direcao" replace />} />
                  <Route path="painel-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <PainelPage />
                    </Suspense>
                  } />
                  {/* Acesso ao Dashboard antigo via path explícito (debug/comparação) */}
                  <Route path="dashboard-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <Dashboard />
                    </Suspense>
                  } />
                  
                  {/* Q.21.E — a rota `inbox` está declarada acima (linha
                      ~138) a servir o InboxDecisoesPage. A 2ª declaração
                      que estava aqui (Navigate to /painel?tab=inbox) era
                      código morto: o react-router usa sempre a 1ª. O
                      OpsInboxPage legacy continua acessível via /inbox-legacy. */}
                  <Route path="inbox-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <OpsInboxPage />
                    </Suspense>
                  } />

                  {/* Sprint H — 3 Umwelts */}
                  <Route path="gestor" element={<Navigate to="/" replace />} />
                  {/* Q.18.ZIP.M.0+M.1 — CEO View novo (CEODashboardPage legacy
                      em /ceo-legacy). Usa endpoints individuais (otd, fpy,
                      alerts, expeditions) com graceful degradation em vez do
                      /v1/profit/dashboard que devolve 500. */}
                  <Route path="ceo" element={<Navigate to="/direcao" replace />} />
                  <Route path="ceo-view-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={3} /></div>}>
                      <CEOView />
                    </Suspense>
                  } />
                  <Route path="ceo-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={3} /></div>}>
                      <CEODashboardPage />
                    </Suspense>
                  } />
                  <Route path="operador" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={3} /></div>}>
                      <OperadorPage />
                    </Suspense>
                  } />
                  
                  {/* ── Q.18.ZIP Onda 5 — legacy redirects ───────────────
                      Bookmarks antigos continuam a funcionar mas levam para
                      a página portada equivalente. Páginas legacy ainda
                      acessíveis via -legacy suffix para debug/comparação. */}

                  {/* CORE Master Data → /configuracao tab "Dados Mestre" */}
                  <Route path="core">
                    <Route path="products" element={<Navigate to="/configuracao?tab=dados-mestre&sub=products" replace />} />
                    <Route path="machines" element={<Navigate to="/configuracao?tab=dados-mestre&sub=machines" replace />} />
                    <Route path="employees" element={<Navigate to="/equipa?tab=lista" replace />} />
                    <Route path="operations" element={<Navigate to="/configuracao?tab=dados-mestre&sub=operations" replace />} />
                    <Route path="rates" element={<Navigate to="/configuracao?tab=dados-mestre&sub=rates" replace />} />
                    <Route path="tenants" element={<Navigate to="/configuracao?tab=dados-mestre&sub=tenants" replace />} />
                    <Route path="bom" element={<Navigate to="/configuracao?tab=dados-mestre&sub=bom" replace />} />
                    <Route path="customers" element={<Navigate to="/configuracao?tab=dados-mestre&sub=customers" replace />} />
                    <Route path="suppliers" element={<Navigate to="/configuracao?tab=dados-mestre&sub=suppliers" replace />} />
                  </Route>

                  {/* PLAN Production → /producao | /planeamento */}
                  <Route path="plan">
                    <Route path="scheduling" element={<Navigate to="/producao" replace />} />
                    <Route path="mrp" element={<Navigate to="/planeamento?tab=materiais" replace />} />
                    <Route path="capacity" element={<Navigate to="/producao?view=fase" replace />} />
                    <Route path="timeline" element={<Navigate to="/painel" replace />} />
                    <Route path="dispatch" element={<Navigate to="/expedicao" replace />} />
                  </Route>

                  {/* PROFIT → /relatorios + /qualidade */}
                  <Route path="profit">
                    <Route path="oee" element={<Navigate to="/qualidade?tab=oee" replace />} />
                    <Route path="quality" element={<Navigate to="/qualidade?tab=resumo" replace />} />
                    <Route path="cogs" element={<Navigate to="/relatorios?tab=custos" replace />} />
                    <Route path="pricing" element={<Navigate to="/relatorios?tab=pricing" replace />} />
                    <Route path="scenarios" element={<Navigate to="/relatorios?tab=cenarios" replace />} />
                    <Route path="kpis" element={<Navigate to="/relatorios?tab=kpis" replace />} />
                  </Route>

                  {/* HR → /equipa */}
                  <Route path="hr">
                    <Route path="allocations" element={<Navigate to="/equipa?tab=alocacoes" replace />} />
                    <Route path="payroll" element={<Navigate to="/relatorios?tab=kpis" replace />} />
                    <Route path="productivity" element={<Navigate to="/equipa?tab=produtividade" replace />} />
                  </Route>

                  {/* SUPPLY → /planeamento + /relatorios */}
                  <Route path="supply">
                    <Route path="inventory" element={<Navigate to="/planeamento?tab=materiais" replace />} />
                    <Route path="forecast" element={<Navigate to="/planeamento?tab=forecast" replace />} />
                    <Route path="rop" element={<Navigate to="/planeamento?tab=materiais" replace />} />
                    <Route path="abc" element={<Navigate to="/relatorios?tab=custos" replace />} />
                  </Route>

                  {/* WORKFORCE → /equipa Risco/Simulador/Formação */}
                  <Route path="workforce">
                    <Route index element={<Navigate to="/equipa?tab=risco" replace />} />
                    <Route path="risk" element={<Navigate to="/equipa?tab=risco" replace />} />
                    <Route path="simulator" element={<Navigate to="/equipa?tab=simulador" replace />} />
                    <Route path="training" element={<Navigate to="/equipa?tab=formacao" replace />} />
                  </Route>

                  {/* SHARED + diagnóstico/sandbox */}
                  <Route path="decisions" element={<Navigate to="/painel?tab=inbox" replace />} />
                  <Route path="explain" element={<Navigate to="/qualidade?tab=diagnostico" replace />} />
                  <Route path="explain/:metricId" element={<Navigate to="/qualidade?tab=diagnostico" replace />} />
                  <Route path="twin" element={<Navigate to="/planeamento?tab=simulador" replace />} />
                  <Route path="sandbox" element={<Navigate to="/planeamento?tab=simulador" replace />} />
                  <Route path="suggestions" element={<Navigate to="/painel?tab=inbox" replace />} />

                  {/* Legacy reachable para debug — usar com cuidado */}
                  <Route path="core-legacy">
                    <Route path="products" element={<ProductsPage />} />
                    <Route path="machines" element={<MachinesPage />} />
                    <Route path="employees" element={<EmployeesPage />} />
                    <Route path="operations" element={<OperationsPage />} />
                    <Route path="rates" element={<RatesPage />} />
                    <Route path="tenants" element={<TenantsPage />} />
                    <Route path="bom" element={<BOMPage />} />
                    <Route path="customers" element={<CustomersPage />} />
                    <Route path="suppliers" element={<SuppliersPage />} />
                  </Route>
                  <Route path="plan-legacy">
                    <Route path="scheduling" element={<SchedulingPage />} />
                    <Route path="mrp" element={<MRPPage />} />
                    <Route path="capacity" element={<CapacityPage />} />
                    <Route path="timeline" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <TimelinePage />
                      </Suspense>
                    } />
                    <Route path="dispatch" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <DispatchPage />
                      </Suspense>
                    } />
                  </Route>
                  <Route path="profit-legacy">
                    <Route path="oee" element={<OEEPage />} />
                    <Route path="quality" element={<QualityPage />} />
                    <Route path="cogs" element={<COGSPage />} />
                    <Route path="pricing" element={<PricingPage />} />
                    <Route path="scenarios" element={<ScenariosPage />} />
                    <Route path="kpis" element={<KPIsPage />} />
                  </Route>
                  <Route path="hr-legacy">
                    <Route path="allocations" element={<AllocationsPage />} />
                    <Route path="payroll" element={<PayrollPage />} />
                    <Route path="productivity" element={<ProductivityPage />} />
                  </Route>
                  <Route path="supply-legacy">
                    <Route path="inventory" element={<InventoryPage />} />
                    <Route path="forecast" element={<ForecastPage />} />
                    <Route path="rop" element={<ROPPage />} />
                    <Route path="abc" element={<ABCPage />} />
                  </Route>
                  <Route path="workforce-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <WorkforceDashboard />
                    </Suspense>
                  } />
                  <Route path="decisions-legacy" element={<DecisionsPage />} />
                  <Route path="explain-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <ExplainPage />
                    </Suspense>
                  } />
                  <Route path="twin-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <TwinPage />
                    </Suspense>
                  } />
                  <Route path="sandbox-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <SandboxPage />
                    </Suspense>
                  } />
                  <Route path="suggestions-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <SuggestionsPage />
                    </Suspense>
                  } />
                  
                  {/* Sprint Q.18.UI.A — novos paths PT-PT.
                      Por agora redirect para a versão antiga; cada Q.18.UI.X
                      vai substituir o redirect pela página nativa.
                      Nota Q.18.ZIP.B: /painel já é nativo acima — esta entrada
                      é redundante (mantida só por defesa caso alguém tire). */}
                  {/* ── Legacy paths PT-PT antigos → redirect para novos zip ── */}
                  <Route path="producao" element={<Navigate to="/plano-producao" replace />} />
                  <Route path="planeamento" element={<Navigate to="/plano-producao" replace />} />
                  <Route path="equipa" element={<Navigate to="/operadores" replace />} />
                  <Route path="relatorios" element={<Navigate to="/oee" replace />} />
                  <Route path="configuracao" element={<Navigate to="/aprendizagem" replace />} />

                  {/* /qualidade + /expedicao mantêm path canónico zip */}
                  <Route path="qualidade" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <QualidadePage />
                    </Suspense>
                  } />
                  <Route path="expedicao" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <ExpedicaoPage />
                    </Suspense>
                  } />

                  {/* Páginas legacy acessíveis via -legacy para debug/comparação */}
                  <Route path="producao-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <ProducaoPage />
                    </Suspense>
                  } />
                  <Route path="planeamento-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <PlaneamentoPage />
                    </Suspense>
                  } />
                  <Route path="equipa-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <EquipaPage />
                    </Suspense>
                  } />
                  <Route path="relatorios-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <RelatoriosPage />
                    </Suspense>
                  } />
                  <Route path="configuracao-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <ConfiguracaoPage />
                    </Suspense>
                  } />

                  {/* Legacy routes - redirect to new structure */}
                  <Route path="products" element={<Navigate to="/core/products" replace />} />
                  <Route path="machines" element={<Navigate to="/core/machines" replace />} />
                  
                  {/* Settings → /configuracao tab "Scheduling" (port da SettingsPage) */}
                  <Route path="settings" element={<Navigate to="/configuracao?tab=scheduling" replace />} />
                  <Route path="settings-legacy" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <SettingsPage />
                    </Suspense>
                  } />

                  {/* Admin → /configuracao com tab apropriada */}
                  <Route path="admin">
                    <Route path="rag-ingest" element={<Navigate to="/configuracao?tab=sistema&sub=rag" replace />} />
                    <Route path="dqa" element={<Navigate to="/configuracao?tab=trust" replace />} />
                    <Route path="audit-trail" element={<Navigate to="/configuracao?tab=sistema&sub=audit" replace />} />
                    <Route path="rbac" element={<Navigate to="/configuracao?tab=sistema&sub=rbac" replace />} />
                    <Route path="learned-rules" element={<Navigate to="/configuracao?tab=aprendizagem&sub=learned" replace />} />
                    <Route path="regras" element={<Navigate to="/configuracao?tab=aprendizagem&sub=regras" replace />} />
                    <Route path="cura-secagem" element={<Navigate to="/configuracao?tab=cura" replace />} />
                    <Route path="data-quality" element={<Navigate to="/configuracao?tab=trust" replace />} />
                    <Route path="tool-registry" element={<Navigate to="/configuracao?tab=sistema&sub=tools" replace />} />
                    <Route path="data-ingestion" element={<Navigate to="/configuracao?tab=sistema&sub=ingestion" replace />} />
                    <Route path="health" element={<Navigate to="/configuracao?tab=sistema&sub=health" replace />} />
                  </Route>

                  {/* Admin legacy reachable via -legacy para debug/comparação */}
                  <Route path="admin-legacy">
                    <Route path="rag-ingest" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <RAGIngestPage />
                      </Suspense>
                    } />
                    <Route path="dqa" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <DQAPage />
                      </Suspense>
                    } />
                    <Route path="audit-trail" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <AuditTrailPage />
                      </Suspense>
                    } />
                    <Route path="rbac" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <RBACPage />
                      </Suspense>
                    } />
                    <Route path="learned-rules" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <LearnedRulesPage />
                      </Suspense>
                    } />
                    <Route path="regras" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <RegrasPage />
                      </Suspense>
                    } />
                    <Route path="cura-secagem" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <CuraSecagemPage />
                      </Suspense>
                    } />
                    <Route path="data-quality" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <DataQualityPage />
                      </Suspense>
                    } />
                    <Route path="tool-registry" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <ToolRegistryPage />
                      </Suspense>
                    } />
                    <Route path="data-ingestion" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <DataIngestionPage />
                      </Suspense>
                    } />
                    <Route path="health" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <HealthDashboardPage />
                      </Suspense>
                    } />
                  </Route>
                  
                  {/* Fallback */}
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
                </Routes>
          </BrowserRouter>
          </RealtimeProvider>
        </ToastProvider>
      </CommandPaletteProvider>
    </ErrorBoundary>
  );
}

export default App;
