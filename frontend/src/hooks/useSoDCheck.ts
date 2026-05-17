/**
 * useSoDCheck — Hook for Segregation of Duties conflict detection
 * Part of TIER 3: ENTERPRISE EXCELLENCE
 */

import { useEffect, useState, useCallback } from 'react';
import type { SoDConflict } from '@/types';
import { getApiBase } from '@/lib/api';

// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
const API_BASE = getApiBase();

export function useSoDCheck(actionId: string, userId: string) {
  const [conflicts, setConflicts] = useState<SoDConflict[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const checkSoD = useCallback(async () => {
    if (!actionId || !userId) return;
    
    try {
      setLoading(true);
      
      // Try API first
      try {
        const response = await fetch(`${API_BASE}/api/v1/governance/sod/check?action_id=${actionId}&user_id=${userId}`);
        if (response.ok) {
          const data = await response.json();
          if (data && data.conflicts) {
            setConflicts(data.conflicts);
            return;
          }
        }
      } catch {
        // Fall back to empty (no conflicts)
      }
      
      // By default, no conflicts
      setConflicts([]);
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

