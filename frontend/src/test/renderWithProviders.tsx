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
}

export function renderWithProviders(
  ui: ReactElement,
  { route = '/', queryClient, ...options }: ProvidersOptions = {},
): RenderResult & { queryClient: QueryClient } {
  const client = queryClient ?? makeTestQueryClient();

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>
          <UmweltProvider>{children}</UmweltProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  return {
    queryClient: client,
    ...render(ui, { wrapper: Wrapper, ...options }),
  };
}
