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
// Sprint Q.18.ZIP.B — Painel portado do nelo zip (substitui Dashboard como rota /)
const PainelPage = lazy(() => import('./pages/painel/PainelPage'));
// Sprint Q.18.ZIP.C — Producao portada (mapa fabrica + 3 vistas + DragDrop)
const ProducaoPage = lazy(() => import('./pages/producao/ProducaoPage'));
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
                  {/* Sprint Q.18.ZIP.B — / serve PainelPage (porto do nelo zip).
                      Dashboard.tsx mantém-se no disco até cleanup Q.18.ZIP.K
                      mas já não é renderizado pela rota canónica. */}
                  <Route index element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <PainelPage />
                    </Suspense>
                  } />
                  <Route path="painel" element={
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
                  
                  {/* NEW: Operations Inbox - Action-oriented exceptions */}
                  <Route path="inbox" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <OpsInboxPage />
                    </Suspense>
                  } />

                  {/* Sprint H — 3 Umwelts */}
                  <Route path="gestor" element={<Navigate to="/" replace />} />
                  <Route path="ceo" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={3} /></div>}>
                      <CEODashboardPage />
                    </Suspense>
                  } />
                  <Route path="operador" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={3} /></div>}>
                      <OperadorPage />
                    </Suspense>
                  } />
                  
                  {/* CORE Module - Master Data */}
                  <Route path="core">
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
                  
                  {/* PLAN Module - Production Planning */}
                  <Route path="plan">
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
                  
                  {/* PROFIT Module - Cost & Pricing */}
                  <Route path="profit">
                    <Route path="oee" element={<OEEPage />} />
                    <Route path="quality" element={<QualityPage />} />
                    <Route path="cogs" element={<COGSPage />} />
                    <Route path="pricing" element={<PricingPage />} />
                    <Route path="scenarios" element={<ScenariosPage />} />
                    <Route path="kpis" element={<KPIsPage />} />
                  </Route>
                  
                  {/* HR Module - Human Resources */}
                  <Route path="hr">
                    <Route path="allocations" element={<AllocationsPage />} />
                    <Route path="payroll" element={<PayrollPage />} />
                    <Route path="productivity" element={<ProductivityPage />} />
                  </Route>
                  
                  {/* SUPPLY Module - Supply Chain Planning */}
                  <Route path="supply">
                    <Route path="inventory" element={<InventoryPage />} />
                    <Route path="forecast" element={<ForecastPage />} />
                    <Route path="rop" element={<ROPPage />} />
                    <Route path="abc" element={<ABCPage />} />
                  </Route>
                  
                  {/* WORKFORCE Module - Decision OS for Workforce Operations (KILLER FEATURE) */}
                  <Route path="workforce">
                    <Route index element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <WorkforceDashboard />
                      </Suspense>
                    } />
                    <Route path="risk" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <WorkforceDashboard />
                      </Suspense>
                    } />
                    <Route path="simulator" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <WorkforceDashboard />
                      </Suspense>
                    } />
                    <Route path="training" element={
                      <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                        <WorkforceDashboard />
                      </Suspense>
                    } />
                  </Route>
                  
                  {/* SHARED Module - Decision Intelligence Platform */}
                  <Route path="decisions" element={<DecisionsPage />} />
                  
                  {/* NEW MODULES - Explain, Twin, Sandbox, Suggestions */}
                  <Route path="explain" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <ExplainPage />
                    </Suspense>
                  } />
                  <Route path="explain/:metricId" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <ExplainPage />
                    </Suspense>
                  } />
                  <Route path="twin" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <TwinPage />
                    </Suspense>
                  } />
                  <Route path="sandbox" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <SandboxPage />
                    </Suspense>
                  } />
                  <Route path="suggestions" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <SuggestionsPage />
                    </Suspense>
                  } />
                  
                  {/* Sprint Q.18.UI.A — novos paths PT-PT.
                      Por agora redirect para a versão antiga; cada Q.18.UI.X
                      vai substituir o redirect pela página nativa.
                      Nota Q.18.ZIP.B: /painel já é nativo acima — esta entrada
                      é redundante (mantida só por defesa caso alguém tire). */}
                  {/* /painel removido daqui — agora rota nativa acima */}
                  {/* Q.18.ZIP.C — /producao agora nativa */}
                  <Route path="producao" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <ProducaoPage />
                    </Suspense>
                  } />
                  <Route path="planeamento" element={<Navigate to="/plan/scheduling" replace />} />
                  <Route path="expedicao" element={<Navigate to="/plan/dispatch" replace />} />
                  <Route path="equipa" element={<Navigate to="/core/employees" replace />} />
                  <Route path="qualidade" element={<Navigate to="/profit/quality" replace />} />
                  <Route path="relatorios" element={<Navigate to="/" replace />} />
                  <Route path="configuracao" element={<Navigate to="/settings" replace />} />

                  {/* Legacy routes - redirect to new structure */}
                  <Route path="products" element={<Navigate to="/core/products" replace />} />
                  <Route path="machines" element={<Navigate to="/core/machines" replace />} />
                  
                  {/* Settings */}
                  <Route path="settings" element={
                    <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
                      <SettingsPage />
                    </Suspense>
                  } />
                  
                  {/* Admin routes */}
                  <Route path="admin">
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
