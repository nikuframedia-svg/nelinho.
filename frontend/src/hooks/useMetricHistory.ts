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

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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
      const url = new URL(
        `${API_BASE}/v1/explain/metric/${encodeURIComponent(metricId)}/history`
      );
      url.searchParams.set('days', String(days));
      url.searchParams.set('granularity', granularity);
      const response = await fetch(url.toString());
      if (!response.ok) {
        throw new Error(
          `Metric history API returned ${response.status} ${response.statusText}`
        );
      }
      const payload = await response.json();
      const points: MetricHistoryPoint[] = Array.isArray(payload?.points)
        ? payload.points
        : Array.isArray(payload)
        ? payload
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
