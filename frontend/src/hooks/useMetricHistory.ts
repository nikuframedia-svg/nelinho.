/**
 * useMetricHistory — Hook for fetching historical metric data
 * Part of TIER 2: OPERATIONAL EXCELLENCE
 */

import { useEffect, useState, useCallback } from 'react';
import type { MetricHistoryPoint } from '@/types';

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
    try {
      setLoading(true);
      
      // Generate mock historical data for now
      // In production, this would call: /api/v1/explain/metric/${metricId}/history
      const mockData: MetricHistoryPoint[] = [];
      const now = new Date();
      
      for (let i = days - 1; i >= 0; i--) {
        const date = new Date(now);
        date.setDate(date.getDate() - i);
        
        // Add some realistic variation
        const baseValue = 100;
        const variation = Math.sin(i * 0.3) * 20 + Math.random() * 10;
        
        mockData.push({
          date: date.toISOString().split('T')[0],
          value: Math.round(baseValue + variation),
          unit: 'count',
          trust_index: 70 + Math.floor(Math.random() * 20),
        });
      }
      
      setData(mockData);
      setError(null);
    } catch (e) {
      setError(e as Error);
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

