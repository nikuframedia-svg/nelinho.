/**
 * useRunbooks — Hook for runbook gallery
 * Part of TIER 3: ENTERPRISE EXCELLENCE
 *
 * ZERO MOCKS: hits the real `/v1/runbooks` endpoint. Empty/error
 * states explicit; never silently substituted with fake runbooks.
 */

import { useEffect, useState, useCallback } from 'react';
import type { Runbook } from '@/types';
import { getApiBase } from '@/lib/api';

// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
const API_BASE = getApiBase();

export function useRunbooks() {
  const [runbooks, setRunbooks] = useState<Runbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchRunbooks = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/v1/runbooks`);
      if (!response.ok) {
        throw new Error(
          `Runbooks API returned ${response.status} ${response.statusText}`
        );
      }
      const data = await response.json();
      const list: Runbook[] = Array.isArray(data?.runbooks)
        ? data.runbooks
        : Array.isArray(data)
        ? data
        : [];
      setRunbooks(list);
      setError(null);
    } catch (e) {
      setRunbooks([]);
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  const executeRunbook = useCallback(async (runbookId: string): Promise<boolean> => {
    const response = await fetch(`${API_BASE}/v1/runbooks/${runbookId}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) {
      throw new Error(
        `Runbook execute failed: ${response.status} ${response.statusText}`
      );
    }
    return true;
  }, []);

  useEffect(() => {
    fetchRunbooks();
  }, [fetchRunbooks]);

  return { runbooks, loading, error, refresh: fetchRunbooks, executeRunbook };
}

export default useRunbooks;
