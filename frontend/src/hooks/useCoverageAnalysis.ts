/**
 * useCoverageAnalysis — Hook for table coverage analysis
 * Part of TIER 3: ENTERPRISE EXCELLENCE
 *
 * ZERO MOCKS: hits the real `/v1/factory/semantic/coverage` endpoint.
 * The previous implementation hardcoded a fixed snapshot of one tenant's
 * tables, which silently rotted whenever ingestion changed and is the
 * exact pattern the ZERO MOCKS rule forbids. Empty/error states are
 * explicit; never silently substituted with fake rows.
 */

import { useEffect, useState, useCallback } from 'react';
import type { TableCoverage } from '@/types';
import { apiFetch } from '../lib/api';

export function useCoverageAnalysis() {
  const [coverage, setCoverage] = useState<TableCoverage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchCoverage = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<{ tables?: TableCoverage[] } | TableCoverage[]>(
        '/v1/factory/semantic/coverage'
      );
      const list: TableCoverage[] = Array.isArray(data)
        ? data
        : Array.isArray(data?.tables)
        ? data.tables
        : [];
      setCoverage(list);
      setError(null);
    } catch (e) {
      setCoverage([]);
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCoverage();
  }, [fetchCoverage]);

  return { coverage, loading, error, refresh: fetchCoverage };
}

export default useCoverageAnalysis;
