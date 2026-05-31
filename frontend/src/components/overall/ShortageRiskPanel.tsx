/**
 * ShortageRiskPanel — faltas de material no plano (Q.118.N).
 * ===========================================================
 *
 * Liga o planeamento ao detector de faltas (FM04): GET
 * /v1/factory-map/shortage-risks. Mostra os SKUs em risco HIGH/MED com dias
 * até rutura. Degradação honesta: esconde-se sem faltas — ZERO MOCKS.
 */

import { useQuery } from '@tanstack/react-query';
import { PackageX } from 'lucide-react';
import { shortageRisksApi } from '../../lib/api';

const SEV_COLOR: Record<string, string> = {
  HIGH: 'var(--red)',
  MED: 'var(--amber, #f59e0b)',
};

export function ShortageRiskPanel() {
  const query = useQuery({
    queryKey: ['factory-map', 'shortage-risks', 'overall'],
    queryFn: () => shortageRisksApi.get(14),
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const atRisk = (query.data?.items ?? []).filter(
    (i) => i.severity === 'HIGH' || i.severity === 'MED',
  );

  if (atRisk.length === 0) return null;

  return (
    <div
      className="rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3"
      data-testid="shortage-risk-panel"
    >
      <div className="flex items-center gap-2 mb-2">
        <PackageX size={15} className="text-red-400" />
        <p className="text-sm font-medium text-red-200">
          {atRisk.length} {atRisk.length === 1 ? 'material' : 'materiais'} em risco de rutura
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {atRisk.slice(0, 12).map((i) => (
          <span
            key={i.sku_id}
            className="inline-flex items-center gap-1.5 rounded-md border border-bd-2 bg-bg-2 px-2 py-1 text-xs"
            title={`Stock ${i.on_hand} · ROP ${i.rop ?? '—'} · procura/dia ${i.avg_daily_demand}`}
          >
            <span
              className="rounded-full"
              style={{ width: 6, height: 6, background: SEV_COLOR[i.severity] ?? 'var(--fg-3)' }}
            />
            <span className="text-fg-1 font-medium">{i.sku_id}</span>
            <span className="text-fg-3">
              {i.days_to_stockout != null ? `${Math.round(i.days_to_stockout)}d` : 'rutura'}
            </span>
          </span>
        ))}
        {atRisk.length > 12 ? (
          <span className="text-xs text-fg-3 self-center">+{atRisk.length - 12}</span>
        ) : null}
      </div>
    </div>
  );
}
