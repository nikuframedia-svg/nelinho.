/**
 * useRunbooks — Hook for runbook gallery
 * Part of TIER 3: ENTERPRISE EXCELLENCE
 *
 * ZERO MOCKS: hits the real `/v1/runbooks` endpoint. Empty/error
 * states explicit; never silently substituted with fake runbooks.
 */

import { useEffect, useState, useCallback } from 'react';
import type { Runbook } from '@/types';
import { apiFetch } from '../lib/api';

export function useRunbooks() {
  const [runbooks, setRunbooks] = useState<Runbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchRunbooks = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<{ runbooks?: Runbook[] } | Runbook[]>('/v1/runbooks');
      const list: Runbook[] = Array.isArray(data)
        ? data
        : Array.isArray(data?.runbooks)
        ? data.runbooks
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
    await apiFetch<unknown>(`/v1/runbooks/${runbookId}/execute`, { method: 'POST' });
    return true;
  }, []);

  useEffect(() => {
    fetchRunbooks();
  }, [fetchRunbooks]);

  return { runbooks, loading, error, refresh: fetchRunbooks, executeRunbook };
}

export default useRunbooks;
