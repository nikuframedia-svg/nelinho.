import { lazy, Suspense, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ToastProvider } from './components/ToastProvider';
import { ContractDegradedBanner } from './components/ContractDegradedBanner';
import { SkeletonLoader } from './components/ui/Skeleton';
import { CommandPaletteProvider } from './hooks';
import { RealtimeProvider } from './providers/RealtimeProvider';
import { EntitySheetProvider, ActiveEntitySheet } from './components/entitySheets';

/**
 * App router — Q.115.P (consolidação 4 páginas).
 *
 * Páginas activas:
 *   /decisoes      — DecisoesPage (Q.115.J)
 *   /overall       — OverallPage  (Q.115.K)
 *   /llm           — LLMPage      (Q.115.N)
 *   /configuracoes — ConfiguracoesPage (Q.115.O)
 *
 * Standalone (fora do Layout):
 *   /login         — LoginPage
 *   /operador      — OperadorTabletPage
 *
 * Todas as outras rotas → 404 PT-PT (NotFoundPage).
 */

// ── Páginas standalone (fora do Layout, sem sidebar) ─────────────────
const LoginPage = lazy(() => import('./pages/login/LoginPage'));
// Q.52.Q — vista tablet do operador, fullscreen sem sidebar.
const OperadorTabletPage = lazy(() => import('./pages/operadores/OperadorTabletPage'));

// ── 4 páginas activas Q.115 ───────────────────────────────────────────
// Q.115.J — Decisões estilo Tinder
const DecisoesPage = lazy(() => import('./pages/decisoes/DecisoesPage'));
// Q.115.K — Planeamento Overall (timeline + drag-drop por fase)
const OverallPage = lazy(() => import('./pages/overall/OverallPage'));
// Q.135.F1 — Expedição (camiões + drag-drop + CTP). Estava construída mas órfã.
const ExpedicaoPage = lazy(() => import('./pages/expedicao/ExpedicaoPage'));
// Q.115.N — Página LLM consolidada (Chat + KPIs + Regras LLM)
const LLMPage = lazy(() => import('./pages/llm/LLMPage'));
// Q.115.O — Página Configurações consolidada (6 tabs)
const ConfiguracoesPage = lazy(() => import('./pages/configuracoes/ConfiguracoesPage'));
// Q.173.AC — Materiais (ruturas + stock + encomendas)
const MateriaisPage = lazy(() => import('./pages/materiais/MateriaisPage'));

// ── Pesquisa global (Q.52.S) — overlay/modal, mantém rota ─────────────
const SearchResultsPage = lazy(() => import('./pages/search/SearchResultsPage'));

// ── 404 PT-PT ─────────────────────────────────────────────────────────
function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[60vh] gap-4 text-text-dark-tertiary">
      <div style={{ fontSize: 48 }}>404</div>
      <div style={{ fontSize: 16 }} className="text-text-dark-primary font-medium">
        Página não encontrada
      </div>
      <div style={{ fontSize: 13 }} className="text-center max-w-sm">
        Esta página foi removida na consolidação Q.115.
        Navega para{' '}
        <a href="/decisoes" className="underline">Decisões</a>,{' '}
        <a href="/overall" className="underline">Planeamento</a>,{' '}
        <a href="/llm" className="underline">Copiloto</a>{' '}
        ou{' '}
        <a href="/configuracoes" className="underline">Configurações</a>.
      </div>
    </div>
  );
}

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
              <EntitySheetProvider>
                <ContractDegradedBanner />

                <Routes>
                  {/* ── Standalone (fora do Layout, sem sidebar) ── */}
                  <Route path="/login" element={<Lazy count={3}><LoginPage /></Lazy>} />
                  {/* Q.52.Q — tablet do operador em ecrã inteiro. */}
                  <Route path="/operador" element={<Lazy count={3}><OperadorTabletPage /></Lazy>} />

                  <Route path="/" element={<Layout />}>
                    {/* Raiz → Decisões (página principal Q.115). */}
                    <Route index element={<Navigate to="/decisoes" replace />} />

                    {/* ── 4 páginas activas Q.115 ── */}
                    <Route path="decisoes" element={<Lazy><DecisoesPage /></Lazy>} />
                    <Route path="overall"  element={<Lazy count={4}><OverallPage /></Lazy>} />
                    <Route path="expedicao" element={<Lazy count={4}><ExpedicaoPage /></Lazy>} />
                    <Route path="materiais" element={<Lazy count={3}><MateriaisPage /></Lazy>} />
                    <Route path="llm"      element={<Lazy count={3}><LLMPage /></Lazy>} />
                    <Route path="configuracoes" element={<Lazy><ConfiguracoesPage /></Lazy>} />

                    {/* ── Pesquisa global (overlay) ── */}
                    <Route path="pesquisa" element={<Lazy count={4}><SearchResultsPage /></Lazy>} />

                    {/* ── Catch-all → 404 PT-PT ── */}
                    <Route path="*" element={<NotFoundPage />} />
                  </Route>
                </Routes>
                <ActiveEntitySheet />
              </EntitySheetProvider>
            </BrowserRouter>
          </RealtimeProvider>
        </ToastProvider>
      </CommandPaletteProvider>
    </ErrorBoundary>
  );
}

export default App;
