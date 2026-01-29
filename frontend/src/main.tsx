import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './index.css';
import { CapabilitiesProvider } from './providers';

// Create QueryClient with smart retry logic
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      // Don't retry on 503 (Service Unavailable) or 5xx errors
      retry: (failureCount, error: any) => {
        // Don't retry if it's a server error (5xx)
        if (error?.status >= 500) return false;
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
        <App />
      </CapabilitiesProvider>
    </QueryClientProvider>
  </StrictMode>
);
