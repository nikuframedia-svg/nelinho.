/**
 * MoldHealthPanel — moldes em risco, na Overall (Q.118.I).
 * =========================================================
 *
 * Liga o planeamento à saúde dos moldes: GET /v1/plan/molds/health-report
 * (moldes ordenados por risco). Mostra só os vermelhos/amarelos, com o
 * modelo clicável (abre a ficha). Degradação honesta: esconde-se quando
 * não há moldes em risco — ZERO MOCKS.
 */

import { useQuery } from '@tanstack/react-query';
import { Wrench } from 'lucide-react';
import { moldsApi } from '../../lib/api';
import { Clickable } from '../entitySheets';

const CAT_COLOR: Record<string, string> = {
  red: 'var(--red)',
  yellow: 'var(--amber, #f59e0b)',
};

export function MoldHealthPanel() {
  const query = useQuery({
    queryKey: ['plan', 'molds', 'health-report', 'overall'],
    queryFn: () => moldsApi.healthReport({ limit: 20 }),
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const atRisk = (query.data ?? []).filter(
    (m) => m.health?.risk_category === 'red' || m.health?.risk_category === 'yellow',
  );

  if (atRisk.length === 0) return null;

  return (
    <div
      className="rounded-lg border border-orange-500/30 bg-orange-500/5 px-4 py-3"
      data-testid="mold-health-panel"
    >
      <div className="flex items-center gap-2 mb-2">
        <Wrench size={15} className="text-orange-400" />
        <p className="text-sm font-medium text-orange-200">
          {atRisk.length} {atRisk.length === 1 ? 'molde' : 'moldes'} a precisar de atenção
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {atRisk.slice(0, 12).map((m) => (
          <span
            key={m.id}
            className="inline-flex items-center gap-1.5 rounded-md border border-bd-2 bg-bg-2 px-2 py-1 text-xs"
            title={`Saúde ${m.health?.score_0_100 ?? '—'}/100 · ${m.name ?? m.mold_code}`}
          >
            <span
              className="rounded-full"
              style={{
                width: 6,
                height: 6,
                background: CAT_COLOR[m.health?.risk_category ?? ''] ?? 'var(--fg-3)',
              }}
            />
            <Clickable kind="modelo" id={m.model_id}>
              {m.mold_code}
            </Clickable>
            <span className="text-fg-3">{m.health?.score_0_100 ?? '—'}</span>
          </span>
        ))}
        {atRisk.length > 12 ? (
          <span className="text-xs text-fg-3 self-center">+{atRisk.length - 12}</span>
        ) : null}
      </div>
    </div>
  );
}
