// Helper de render para testes de componente (Q.60.F).
//
// Envolve o componente nos providers que a app usa em runtime — MENOS o
// CapabilitiesProvider: esse renderiza um <BootLoader/> enquanto a query
// `/capabilities/` não resolve, e em teste (sem servidor) esconderia o
// componente. Componentes que dependam de `useCapabilities()` testam-se mais
// tarde com MSW, onde a query resolve.
import type { ReactElement, ReactNode } from 'react';
import {
  render,
  type RenderOptions,
  type RenderResult,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { UmweltProvider } from '../lib/umwelt';
import { ToastProvider } from '../components/ToastProvider';
import { EntitySheetProvider } from '../components/entitySheets';

// QueryClient novo por teste, sem retries — uma falha de rede resolve já,
// sem timers de retry pendentes a vazar para o teste seguinte.
export function makeTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface ProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  // Entrada inicial do MemoryRouter (ex: '/qualidade?tab=resumo').
  route?: string;
  // Permite partilhar um QueryClient entre render e asserts do teste.
  queryClient?: QueryClient;
  // Q.118.A1 — embrulha ToastProvider para componentes que usam useToast()
  // (ex: páginas que disparam toasts em mutations). Sem isto, esses
  // componentes rebentam com "useToast must be used within ToastProvider".
  withToast?: boolean;
  // Q.118.A1 — embrulha EntitySheetProvider para componentes que usam
  // <Clickable>/useEntitySheet() (entity sheets contextuais). Tem de estar
  // DENTRO do MemoryRouter (usa useSearchParams).
  withEntitySheets?: boolean;
}

export function renderWithProviders(
  ui: ReactElement,
  {
    route = '/',
    queryClient,
    withToast = false,
    withEntitySheets = false,
    ...options
  }: ProvidersOptions = {},
): RenderResult & { queryClient: QueryClient } {
  const client = queryClient ?? makeTestQueryClient();

  function Wrapper({ children }: { children: ReactNode }) {
    // EntitySheetProvider precisa de useSearchParams → dentro do router.
    const inner = withEntitySheets ? (
      <EntitySheetProvider>{children}</EntitySheetProvider>
    ) : (
      children
    );
    const routed = (
      <MemoryRouter initialEntries={[route]}>
        <UmweltProvider>{inner}</UmweltProvider>
      </MemoryRouter>
    );
    const toasted = withToast ? <ToastProvider>{routed}</ToastProvider> : routed;
    return <QueryClientProvider client={client}>{toasted}</QueryClientProvider>;
  }

  return {
    queryClient: client,
    ...render(ui, { wrapper: Wrapper, ...options }),
  };
}
