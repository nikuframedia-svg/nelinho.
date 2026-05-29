/**
 * OtdHeatmap — mapa de calor OTD por produto × semana (Q.118.K).
 * ===============================================================
 *
 * Liga a tab KPIs ao detalhe de entrega: GET /v1/profit/kpis/otd-heatmap
 * (kpisApi.getOtdHeatmap). Matriz produto × semana, célula = % entregas a
 * tempo (verde alto, vermelho baixo). Degradação honesta: esconde-se sem
 * dados — ZERO MOCKS.
 */

import { useQuery } from '@tanstack/react-query';
import { Grid3x3 } from 'lucide-react';
import { DarkCard } from '../../components/dark';
import { kpisApi } from '../../lib/api';

interface OtdHeatmapResponse {
  product_types: string[];
  weeks: string[];
  heatmap: Record<string, Record<string, number | null>>;
  start_date?: string;
  end_date?: string;
}

function cellColor(v: number | null | undefined): string {
  if (v == null) return 'var(--bg-2)';
  if (v >= 90) return 'rgba(34,197,94,0.30)'; // verde
  if (v >= 75) return 'rgba(245,158,11,0.30)'; // âmbar
  return 'rgba(239,68,68,0.30)'; // vermelho
}

export function OtdHeatmap() {
  const query = useQuery({
    queryKey: ['profit', 'otd-heatmap', 12],
    queryFn: () => kpisApi.getOtdHeatmap(12) as Promise<OtdHeatmapResponse>,
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const data = query.data;
  const productTypes = data?.product_types ?? [];
  const weeks = data?.weeks ?? [];

  if (query.isLoading || productTypes.length === 0 || weeks.length === 0) return null;

  return (
    <DarkCard className="mt-5">
      <div className="flex items-center gap-2 mb-3">
        <Grid3x3 size={15} className="text-fg-2" />
        <p className="text-sm font-medium text-fg-1">Entregas a tempo (OTD) · produto × semana</p>
      </div>
      <div className="overflow-x-auto">
        <table className="text-xs border-separate" style={{ borderSpacing: 2 }}>
          <thead>
            <tr>
              <th className="text-left text-fg-3 font-medium px-2 py-1">Produto</th>
              {weeks.map((w) => (
                <th key={w} className="text-fg-3 font-normal px-1 py-1 whitespace-nowrap">
                  {w.slice(5)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {productTypes.map((pt) => (
              <tr key={pt}>
                <td className="text-fg-1 font-medium px-2 py-1 whitespace-nowrap">{pt}</td>
                {weeks.map((w) => {
                  const v = data?.heatmap?.[pt]?.[w];
                  return (
                    <td
                      key={w}
                      className="text-center text-fg-1 rounded"
                      style={{ background: cellColor(v), minWidth: 34, padding: '4px 2px' }}
                      title={`${pt} · ${w}: ${v == null ? 'sem dados' : `${v.toFixed(0)}%`}`}
                    >
                      {v == null ? '—' : `${v.toFixed(0)}`}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </DarkCard>
  );
}
