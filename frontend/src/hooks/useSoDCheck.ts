/**
 * useSoDCheck — Hook for Segregation of Duties conflict detection
 * Part of TIER 3: ENTERPRISE EXCELLENCE
 */

import { useEffect, useState, useCallback } from 'react';
import type { SoDConflict } from '@/types';
import { apiFetch } from '../lib/api';

export function useSoDCheck(actionId: string, userId: string) {
  const [conflicts, setConflicts] = useState<SoDConflict[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const checkSoD = useCallback(async () => {
    if (!actionId || !userId) return;
    
    try {
      setLoading(true);

      try {
        const params = new URLSearchParams({ action_id: actionId, user_id: userId });
        const data = await apiFetch<{ conflicts?: SoDConflict[] }>(
          `/api/v1/governance/sod/check?${params}`
        );
        setConflicts(Array.isArray(data?.conflicts) ? data.conflicts : []);
      } catch {
        // No SoD telemetry available — no conflicts is the safe default.
        setConflicts([]);
      }
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, [actionId, userId]);

  useEffect(() => {
    checkSoD();
  }, [checkSoD]);

  return { conflicts, loading, error, refresh: checkSoD };
}

export default useSoDCheck;

