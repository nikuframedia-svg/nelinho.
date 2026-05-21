/**
 * useMoldConflicts — Hook for mold conflict calendar
 * Part of TIER 2: OPERATIONAL EXCELLENCE
 * 
 * Now uses REAL API data from mold-conflicts endpoint!
 */

import { useEffect, useState, useCallback } from 'react';
import { factoryApi } from '@/lib/factoryApi';
import type { MoldConflict } from '@/types';

export function useMoldConflicts() {
  const [conflicts, setConflicts] = useState<MoldConflict[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchConflicts = useCallback(async () => {
    try {
      setLoading(true);
      
      // Try API first
      const response = await factoryApi.getMoldConflicts().catch(() => null);
      
      if (response && response.data && response.data.conflicts) {
        // Transform API response to MoldConflict type
        type RawConflict = {
          id?: string;
          mold_id?: string;
          molde_id?: string;
          date?: string;
          severity?: 'high' | 'medium' | 'low' | string;
          orders?: string[];
          ordens?: string[];
          estimated_delay_hours?: number;
          delay_hours?: number;
        };
        const transformedConflicts: MoldConflict[] = (response.data.conflicts as RawConflict[]).map((conflict, index: number) => ({
          id: conflict.id || `mc-${index}`,
          mold_id: conflict.mold_id || conflict.molde_id || '',
          date: conflict.date || new Date().toISOString().split('T')[0],
          severity: (conflict.severity as 'high' | 'medium' | 'low') || 'medium',
          orders: conflict.orders || conflict.ordens || [],
          estimated_delay_hours: conflict.estimated_delay_hours || conflict.delay_hours || 0,
        }));
        
        setConflicts(transformedConflicts);
        setError(null);
      } else if (response && response.data && response.data.theoretical_conflicts) {
        // Handle theoretical conflicts format
        const theoreticalConflicts = response.data.theoretical_conflicts;
        if (Array.isArray(theoreticalConflicts)) {
          type TheoreticalConflict = {
            molde_id?: string;
            molde?: string | number;
            date?: string;
            conflicting_phases?: number;
            order_ids?: string[];
            estimated_delay?: number;
          };
          const transformedConflicts: MoldConflict[] = (theoreticalConflicts as TheoreticalConflict[]).map((conflict, index: number) => ({
            id: `mc-${index}`,
            mold_id: conflict.molde_id || `M${conflict.molde ?? index}`,
            date: conflict.date || new Date().toISOString().split('T')[0],
            severity: (conflict.conflicting_phases ?? 0) > 3 ? 'high' : (conflict.conflicting_phases ?? 0) > 1 ? 'medium' : 'low',
            orders: conflict.order_ids || [],
            estimated_delay_hours: conflict.estimated_delay || 0,
          }));
          setConflicts(transformedConflicts);
          setError(null);
        }
      } else {
        // No conflicts found - that's actually good news!
        setConflicts([]);
        setError(null);
      }
    } catch (e) {
      setError(e as Error);
      setConflicts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConflicts();
  }, [fetchConflicts]);

  return { conflicts, loading, error, refresh: fetchConflicts };
}

export default useMoldConflicts;
