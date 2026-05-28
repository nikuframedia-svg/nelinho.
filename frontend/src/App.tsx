import { lazy, Suspense, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ToastProvider } from './components/ToastProvider';
import { ContractDegradedBanner } from './components/ContractDegradedBanner';
import { SkeletonLoader } from './components/ui/Skeleton';
import { CommandPaletteProvider } from './hooks';
import { RealtimeProvider } from './providers/RealtimeProvider';

/**
 * App router — Q.52.S (Onda 2 da reconstrução NELO).
 *
 * 19 páginas do design + 5 órfãs preservadas. Estrutura:
 *   PRINCIPAL  → painel · planeamento · fabrica · expedicao · equipa ·
 *                qualidade · materiais · simulacoes · regras · aprendi ·
 *                copilot · configuracao
 *   ESPECIAIS  → direcao (Direção) · operador (tablet, fullscreen)
 *   SISTEMA    → inbox · relatorios · dados-mestre · saude · rbac
 *
 * `/operador` e `/login` vivem FORA do <Layout> (sem sidebar/topbar).
 * Todos os paths legados redirecionam para os canónicos novos.
 */

// ── Páginas standalone (fora do Layout) ──────────────────────────────
const LoginPage = lazy(() => import('./pages/login/LoginPage'));
// Q.52.Q — vista tablet do operador, fullscreen sem sidebar.
const OperadorTabletPage = lazy(() => import('./pages/operadores/OperadorTabletPage'));

// ── 12 páginas principais do design ──────────────────────────────────
const PainelDiarioPage = lazy(() => import('./pages/painel/PainelDiarioPage'));
const PlaneamentoPage = lazy(() => import('./pages/planeamento/PlaneamentoPage'));
const FabricaPage = lazy(() => import('./pages/producao/FabricaPage'));
const ExpedicaoPage = lazy(() => import('./pages/expedicao/ExpedicaoPage'));
const EquipaPage = lazy(() => import('./pages/equipa/EquipaPage'));
const QualidadePage = lazy(() => import('./pages/qualidade/QualidadePage'));
const MateriaisPage = lazy(() => import('./pages/materiais/MateriaisPage'));
const SimulacoesPage = lazy(() => import('./pages/simulacoes/SimulacoesPage'));
const RegrasPage = lazy(() => import('./pages/admin/RegrasPage'));
const AprendiPage = lazy(() => import('./pages/aprendi/AprendiPage'));
const CopilotPage = lazy(() => import('./pages/copilot/CopilotPage'));
const ConfiguracaoPage = lazy(() => import('./pages/configuracao/ConfiguracaoPage'));

// ── Q.53 — página de Custos dedicada (COGS · pricing · margem · cenários) ──
const CustosPage = lazy(() => import('./pages/custos/CustosPage'));

// ── 2 vistas especiais ───────────────────────────────────────────────
const DirecaoPage = lazy(() => import('./pages/direcao/DirecaoPage'));

// ── Q.53 — páginas de Sistema novas ──────────────────────────────────
const ConexaoErpPage = lazy(() => import('./pages/conexao-erp/ConexaoErpPage'));
const LigacoesPage = lazy(() => import('./pages/ligacoes/LigacoesPage'));

// ── 5 páginas órfãs preservadas (Q.52.R) ─────────────────────────────
const InboxDecisoesPage = lazy(() => import('./pages/inbox/InboxDecisoesPage'));
// ── Q.115.J — Decisões estilo Tinder ────────────────────────────────
const DecisoesPage = lazy(() => import('./pages/decisoes/DecisoesPage'));
const RelatoriosPage = lazy(() => import('./pages/relatorios/RelatoriosPage'));
const HealthDashboardPage = lazy(() =>
  import('./pages/admin/HealthDashboardPage').then((m) => ({ default: m.HealthDashboardPage })),
);
const RBACPage = lazy(() =>
  import('./pages/admin/RBACPage').then((m) => ({ default: m.RBACPage })),
);

// ── Q.115.N — Página LLM consolidada (Chat + KPIs + Regras LLM) ──────
const LLMPage = lazy(() => import('./pages/llm/LLMPage'));

// ── Q.115.O — Página Configurações consolidada (6 tabs) ───────────────
const ConfiguracoesPage = lazy(() => import('./pages/configuracoes/ConfiguracoesPage'));

// ── Q.115.K — Página Overall (Planeamento com timeline + drag-drop) ───
const OverallPage = lazy(() => import('./pages/overall/OverallPage'));

// ── Pesquisa global (Q.52.S) ─────────────────────────────────────────
const SearchResultsPage = lazy(() => import('./pages/search/SearchResultsPage'));

/** Wrapper Suspense uniforme para páginas lazy. */
function Lazy({ children, count = 5 }: { children: ReactNode; count?: number }): ReactNode {
  return (
    <Suspense fallback={<div className="p-8"><SkeletonLoader count={count} /></div>}>
      {children}
    </Suspense>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <CommandPaletteProvider>
        <ToastProvider>
          {/* Sprint D.2 — uma só ligação SSE partilhada para toda a app. */}
          <RealtimeProvider>
            <BrowserRouter>
              <ContractDegradedBanner />

              <Routes>
                {/* ── Standalone (fora do Layout, sem sidebar) ── */}
                <Route path="/login" element={<Lazy count={3}><LoginPage /></Lazy>} />
                {/* Q.52.Q — tablet do operador em ecrã inteiro. */}
                <Route path="/operador" element={<Lazy count={3}><OperadorTabletPage /></Lazy>} />

                <Route path="/" element={<Layout />}>
                  {/* Raiz → Painel diário. */}
                  <Route index element={<Navigate to="/painel" replace />} />

                  {/* ── Páginas principais (Q.53: + Custos) ── */}
                  <Route path="painel" element={<Lazy><PainelDiarioPage /></Lazy>} />
                  <Route path="planeamento" element={<Lazy><PlaneamentoPage /></Lazy>} />
                  <Route path="fabrica" element={<Lazy><FabricaPage /></Lazy>} />
                  <Route path="expedicao" element={<Lazy><ExpedicaoPage /></Lazy>} />
                  <Route path="equipa" element={<Lazy><EquipaPage /></Lazy>} />
                  <Route path="qualidade" element={<Lazy><QualidadePage /></Lazy>} />
                  <Route path="materiais" element={<Lazy><MateriaisPage /></Lazy>} />
                  <Route path="simulacoes" element={<Lazy><SimulacoesPage /></Lazy>} />
                  <Route path="custos" element={<Lazy><CustosPage /></Lazy>} />
                  <Route path="regras" element={<Lazy><RegrasPage /></Lazy>} />
                  <Route path="aprendi" element={<Lazy><AprendiPage /></Lazy>} />
                  <Route path="copilot" element={<Lazy count={3}><CopilotPage /></Lazy>} />
                  {/* Q.115.N — página LLM consolidada (Chat + KPIs + Regras LLM) */}
                  <Route path="llm" element={<Lazy count={3}><LLMPage /></Lazy>} />
                  {/* Q.115.K — Planeamento Overall (timeline + drag-drop por fase) */}
                  <Route path="overall" element={<Lazy count={4}><OverallPage /></Lazy>} />
                  <Route path="configuracao" element={<Lazy><ConfiguracaoPage /></Lazy>} />
                  {/* Q.115.O — página Configurações consolidada (6 tabs) */}
                  <Route path="configuracoes" element={<Lazy><ConfiguracoesPage /></Lazy>} />

                  {/* ── Vista especial: Direção ── */}
                  <Route path="direcao" element={<Lazy><DirecaoPage /></Lazy>} />

                  {/* ── Grupo Sistema (Q.53: + Conexão ERP, Ligações) ── */}
                  <Route path="inbox" element={<Lazy><InboxDecisoesPage /></Lazy>} />
                  {/* Q.115.J — página de decisões estilo Tinder */}
                  <Route path="decisoes" element={<Lazy><DecisoesPage /></Lazy>} />
                  <Route path="relatorios" element={<Lazy><RelatoriosPage /></Lazy>} />
                  <Route
                    path="dados-mestre"
                    element={<Navigate to="/configuracao?tab=dados-mestre" replace />}
                  />
                  <Route path="saude" element={<Lazy><HealthDashboardPage /></Lazy>} />
                  <Route path="rbac" element={<Lazy><RBACPage /></Lazy>} />
                  {/* Q.53 — estado da ligação à API do ERP NELO + saúde do realtime */}
                  <Route path="conexao-erp" element={<Lazy><ConexaoErpPage /></Lazy>} />
                  <Route path="ligacoes" element={<Lazy><LigacoesPage /></Lazy>} />

                  {/* ── Pesquisa global ── */}
                  <Route path="pesquisa" element={<Lazy count={4}><SearchResultsPage /></Lazy>} />

                  {/* ════════ Redirects de paths legados ════════
                      Bookmarks antigos continuam a funcionar e levam
                      à página canónica nova equivalente. */}

                  {/* Painéis / dashboards antigos */}
                  <Route path="ceo" element={<Navigate to="/direcao" replace />} />
                  <Route path="gestor" element={<Navigate to="/painel" replace />} />
                  <Route path="dashboard-legacy" element={<Navigate to="/painel" replace />} />
                  <Route path="painel-legacy" element={<Navigate to="/painel" replace />} />

                  {/* Produção / planeamento */}
                  <Route path="producao" element={<Navigate to="/fabrica" replace />} />
                  <Route path="plano-producao" element={<Navigate to="/planeamento" replace />} />
                  <Route path="atribuicao" element={<Navigate to="/fabrica" replace />} />
                  <Route path="operadores" element={<Navigate to="/equipa" replace />} />
                  <Route path="oee" element={<Navigate to="/qualidade?tab=oee" replace />} />
                  <Route path="aprendizagem" element={<Navigate to="/aprendi" replace />} />
                  <Route path="definicoes" element={<Navigate to="/configuracao" replace />} />
                  <Route path="settings" element={<Navigate to="/configuracao?tab=scheduling" replace />} />

                  {/* CORE Master Data → /configuracao?tab=dados-mestre */}
                  <Route path="core">
                    <Route path="products" element={<Navigate to="/configuracao?tab=dados-mestre&sub=products" replace />} />
                    <Route path="machines" element={<Navigate to="/configuracao?tab=dados-mestre&sub=machines" replace />} />
                    <Route path="employees" element={<Navigate to="/equipa?tab=lista" replace />} />
                    <Route path="operations" element={<Navigate to="/configuracao?tab=dados-mestre&sub=operations" replace />} />
                    <Route path="rates" element={<Navigate to="/configuracao?tab=dados-mestre&sub=rates" replace />} />
                    <Route path="tenants" element={<Navigate to="/configuracao?tab=dados-mestre&sub=tenants" replace />} />
                    <Route path="bom" element={<Navigate to="/configuracao?tab=dados-mestre&sub=bom" replace />} />
                    <Route path="customers" element={<Navigate to="/configuracao?tab=dados-mestre&sub=customers" replace />} />
                    <Route path="suppliers" element={<Navigate to="/materiais?tab=fornecedores" replace />} />
                  </Route>

                  {/* PLAN → /fabrica | /planeamento | /expedicao */}
                  <Route path="plan">
                    <Route path="scheduling" element={<Navigate to="/planeamento" replace />} />
                    <Route path="mrp" element={<Navigate to="/materiais?tab=prospecao" replace />} />
                    <Route path="capacity" element={<Navigate to="/fabrica" replace />} />
                    <Route path="timeline" element={<Navigate to="/planeamento" replace />} />
                    <Route path="dispatch" element={<Navigate to="/expedicao" replace />} />
                  </Route>

                  {/* PROFIT → /direcao | /qualidade | /configuracao */}
                  <Route path="profit">
                    <Route path="oee" element={<Navigate to="/qualidade?tab=oee" replace />} />
                    <Route path="quality" element={<Navigate to="/qualidade" replace />} />
                    <Route path="cogs" element={<Navigate to="/custos" replace />} />
                    <Route path="pricing" element={<Navigate to="/custos" replace />} />
                    <Route path="scenarios" element={<Navigate to="/simulacoes" replace />} />
                    <Route path="kpis" element={<Navigate to="/direcao" replace />} />
                  </Route>

                  {/* HR → /equipa */}
                  <Route path="hr">
                    <Route path="allocations" element={<Navigate to="/equipa" replace />} />
                    <Route path="payroll" element={<Navigate to="/equipa" replace />} />
                    <Route path="productivity" element={<Navigate to="/equipa" replace />} />
                  </Route>

                  {/* SUPPLY → /materiais */}
                  <Route path="supply">
                    <Route path="inventory" element={<Navigate to="/materiais?tab=stock" replace />} />
                    <Route path="forecast" element={<Navigate to="/materiais?tab=prospecao" replace />} />
                    <Route path="rop" element={<Navigate to="/materiais?tab=stock" replace />} />
                    <Route path="abc" element={<Navigate to="/materiais?tab=prospecao" replace />} />
                  </Route>

                  {/* WORKFORCE → /equipa */}
                  <Route path="workforce">
                    <Route index element={<Navigate to="/equipa" replace />} />
                    <Route path="risk" element={<Navigate to="/equipa?tab=risco" replace />} />
                    <Route path="simulator" element={<Navigate to="/equipa?tab=simulador" replace />} />
                    <Route path="training" element={<Navigate to="/equipa?tab=formacao" replace />} />
                  </Route>

                  {/* SHARED + diagnóstico / sandbox / twin */}
                  <Route path="decisions" element={<Navigate to="/inbox" replace />} />
                  <Route path="suggestions" element={<Navigate to="/painel?tab=aprovacoes" replace />} />
                  <Route path="explain" element={<Navigate to="/qualidade?tab=diagnostico" replace />} />
                  <Route path="explain/:metricId" element={<Navigate to="/qualidade?tab=diagnostico" replace />} />
                  <Route path="twin" element={<Navigate to="/simulacoes" replace />} />
                  <Route path="sandbox" element={<Navigate to="/simulacoes" replace />} />

                  {/* Admin antigos → /configuracao | /saude | /rbac | /aprendi */}
                  <Route path="admin">
                    <Route path="rag-ingest" element={<Navigate to="/configuracao?tab=sistema&sub=rag" replace />} />
                    <Route path="dqa" element={<Navigate to="/configuracao?tab=trust" replace />} />
                    <Route path="audit-trail" element={<Navigate to="/aprendi?tab=audit" replace />} />
                    <Route path="rbac" element={<Navigate to="/rbac" replace />} />
                    <Route path="learned-rules" element={<Navigate to="/aprendi?tab=regras" replace />} />
                    <Route path="regras" element={<Navigate to="/regras" replace />} />
                    <Route path="cura-secagem" element={<Navigate to="/configuracao?tab=cura" replace />} />
                    <Route path="data-quality" element={<Navigate to="/configuracao?tab=trust" replace />} />
                    <Route path="tool-registry" element={<Navigate to="/configuracao?tab=sistema&sub=tools" replace />} />
                    <Route path="data-ingestion" element={<Navigate to="/configuracao?tab=sistema&sub=ingestion" replace />} />
                    <Route path="health" element={<Navigate to="/saude" replace />} />
                  </Route>

                  {/* Legacy reachable diversos */}
                  <Route path="products" element={<Navigate to="/configuracao?tab=dados-mestre&sub=products" replace />} />
                  <Route path="machines" element={<Navigate to="/configuracao?tab=dados-mestre&sub=machines" replace />} />
                  <Route path="relatorios-legacy" element={<Navigate to="/relatorios" replace />} />
                  <Route path="inbox-legacy" element={<Navigate to="/inbox" replace />} />
                  <Route path="dados-mestre-legacy" element={<Navigate to="/configuracao?tab=dados-mestre" replace />} />

                  {/* Fallback */}
                  <Route path="*" element={<Navigate to="/painel" replace />} />
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
