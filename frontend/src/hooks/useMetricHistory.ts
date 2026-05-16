/**
 * useMetricHistory — Hook for fetching historical metric data
 * Part of TIER 2: OPERATIONAL EXCELLENCE
 *
 * ZERO MOCKS: hits the real `/v1/explain/metric/:id/history` endpoint.
 * Previously generated synthetic series via Math.sin/Math.random — that
 * masks the absence of real telemetry and silently shows fake trends in
 * a UI users trust. Empty/error states explicit; never silently
 * substituted with fake history.
 */

import { useEffect, useState, useCallback } from 'react';
import type { MetricHistoryPoint } from '@/types';
import { apiFetch } from '../lib/api';

interface UseMetricHistoryOptions {
  days?: number;
  granularity?: 'hour' | 'day' | 'week' | 'month';
}

export function useMetricHistory(metricId: string, options: UseMetricHistoryOptions = {}) {
  const { days = 30, granularity = 'day' } = options;

  const [data, setData] = useState<MetricHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchHistory = useCallback(async () => {
    if (!metricId) {
      setData([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const params = new URLSearchParams({
        days: String(days),
        granularity,
      });
      const payload = await apiFetch<{ points?: MetricHistoryPoint[] } | MetricHistoryPoint[]>(
        `/v1/explain/metric/${encodeURIComponent(metricId)}/history?${params}`
      );
      const points: MetricHistoryPoint[] = Array.isArray(payload)
        ? payload
        : Array.isArray(payload?.points)
        ? payload.points
        : [];
      setData(points);
      setError(null);
    } catch (e) {
      setData([]);
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, [metricId, days, granularity]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return { data, loading, error, refresh: fetchHistory };
}

export default useMetricHistory;
