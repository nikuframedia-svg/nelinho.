/**
 * OtdRiskPanel — ordens em risco de atraso, na Overall (Q.118.H).
 * ================================================================
 *
 * Liga o planeamento ao modelo de risco de entrega (OTD): GET
 * /v1/plan/orders/otd-risk. Mostra só as ordens em risco alto/médio, com a
 * encomenda clicável (abre a ficha). Degradação honesta: esconde-se quando
 * não há modelo (model_available=false) ou nenhuma ordem em risco — ZERO MOCKS.
 */

import { useQuery } from '@tanstack/react-query';
import { AlertTriangle } from 'lucide-react';
import { otdRiskApi } from '../../lib/api';
import { Clickable } from '../entitySheets';

const BAND_COLOR: Record<string, string> = {
  alto: 'var(--red)',
  medio: 'var(--amber, #f59e0b)',
};

export function OtdRiskPanel() {
  const query = useQuery({
    queryKey: ['plan', 'otd-risk', 'overall'],
    queryFn: () => otdRiskApi.list(50),
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const data = query.data;
  // Só mostramos ordens em risco real (alto/médio).
  const atRisk = (data?.orders ?? []).filter(
    (o) => o.risk_band === 'alto' || o.risk_band === 'medio',
  );

  // Sem modelo, erro, ou nenhuma ordem em risco → não polui o ecrã.
  if (!data?.model_available || atRisk.length === 0) return null;

  return (
    <div
      className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3"
      data-testid="otd-risk-panel"
    >
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle size={15} className="text-amber-400" />
        <p className="text-sm font-medium text-amber-200">
          {atRisk.length} {atRisk.length === 1 ? 'ordem' : 'ordens'} em risco de atraso
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {atRisk.slice(0, 12).map((o) => (
          <span
            key={o.of_id}
            className="inline-flex items-center gap-1.5 rounded-md border border-bd-2 bg-bg-2 px-2 py-1 text-xs"
            title={`${o.product_name ?? ''} · ${o.current_phase_name ?? ''} · entrega ${o.transport_date ?? '—'}`}
          >
            <span
              className="rounded-full"
              style={{ width: 6, height: 6, background: BAND_COLOR[o.risk_band] ?? 'var(--fg-3)' }}
            />
            <Clickable kind="encomenda" id={o.of_id}>
              #{o.of_id}
            </Clickable>
            <span className="text-fg-3">{Math.round(o.late_probability * 100)}%</span>
          </span>
        ))}
        {atRisk.length > 12 ? (
          <span className="text-xs text-fg-3 self-center">+{atRisk.length - 12}</span>
        ) : null}
      </div>
    </div>
  );
}
