import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './index.css';
import { CapabilitiesProvider } from './providers';
import { UmweltProvider } from './lib/umwelt';
import { primeSecureCache } from './lib/secureStorage';

// Q.68.5.C — hidrata o cache in-memory das chaves sensíveis ANTES do
// React montar. A fetch layer (`lib/api/client.ts`) lê tokens síncronos
// via `getSecureCached`; sem este prime, o primeiro request iria sem
// Authorization. Fire-and-forget — o boot do React não espera (latência
// de PBKDF2 é ~5-20ms em hardware moderno).
void primeSecureCache([
  'auth_token',
  'refresh_token',
  'copilot_current_conversation_id',
  'copilot.activeConversation',
  'copilot.pendingAsk',
]);

// Create QueryClient with smart retry logic
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      // Don't retry on 503 (Service Unavailable) or 5xx errors
      retry: (failureCount, rawError: unknown) => {
        const error = rawError as { status?: number; message?: string } | null;
        // Don't retry if it's a server error (5xx)
        if ((error?.status ?? 0) >= 500) return false;
        // Don't retry if database is unavailable
        if (error?.message?.includes('Database') || error?.message?.includes('503')) return false;
        // Otherwise, retry up to 1 time
        return failureCount < 1;
      },
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes
    },
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <CapabilitiesProvider>
        <UmweltProvider>
          <App />
        </UmweltProvider>
      </CapabilitiesProvider>
    </QueryClientProvider>
  </StrictMode>
);
