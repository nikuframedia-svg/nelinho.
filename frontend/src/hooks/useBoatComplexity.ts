/**
 * useBoatComplexity — Q.155.E. Mapa de complexidade (ICB 0–100) por produto.
 *
 * UMA query partilhada (deduplicada) — NUNCA por-cartão (lição Q.144: 1 fetch/
 * OpCard rebentava o browser). Devolve dois índices: por product_id (op.product_id)
 * e por product_name (boat_id da aba "Barcos exigentes").
 */
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { boatComplexityApi } from '../lib/api';
import { boatComplexityKeys } from '../lib/api/keys';

export interface ComplexityInfo {
  score: number; // 0–100
  rank: number;
}

export interface BoatComplexityMaps {
  byId: Map<string, ComplexityInfo>;
  byName: Map<string, ComplexityInfo>;
}

export function useBoatComplexity(): BoatComplexityMaps {
  const { data } = useQuery({
    queryKey: boatComplexityKeys.list(),
    queryFn: () => boatComplexityApi.list(),
    staleTime: 10 * 60_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  return useMemo(() => {
    const byId = new Map<string, ComplexityInfo>();
    const byName = new Map<string, ComplexityInfo>();
    for (const b of data ?? []) {
      const info: ComplexityInfo = { score: Math.round(b.complexity_score * 100), rank: b.rank };
      byId.set(String(b.product_id), info);
      if (b.product_name) byName.set(String(b.product_name), info);
    }
    return { byId, byName };
  }, [data]);
}

export default useBoatComplexity;
