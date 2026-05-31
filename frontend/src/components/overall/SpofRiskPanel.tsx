/**
 * SpofRiskPanel — pontos únicos de falha de pessoal, na Overall (Q.118.Q).
 * =========================================================================
 *
 * Liga o planeamento ao risco de workforce: GET /v1/workforce/risks/spof.
 * Cada item = uma fase que depende criticamente de um operador (SPOF). Mostra
 * fase + operador (ambos clicáveis). Degradação honesta: esconde-se sem SPOFs.
 * ZERO MOCKS.
 */

import { useQuery } from '@tanstack/react-query';
import { UserMinus } from 'lucide-react';
import { workforceRisksApi } from '../../lib/api';
import { Clickable } from '../entitySheets';

const PRIO_COLOR: Record<string, string> = {
  critical: 'var(--red)',
  high: 'var(--red)',
  medium: 'var(--amber, #f59e0b)',
};

export function SpofRiskPanel() {
  const query = useQuery({
    queryKey: ['workforce', 'spof', 'overall'],
    queryFn: () => workforceRisksApi.spof(10),
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const items = query.data ?? [];
  if (items.length === 0) return null;

  return (
    <div
      className="rounded-lg border border-purple-500/30 bg-purple-500/5 px-4 py-3"
      data-testid="spof-risk-panel"
    >
      <div className="flex items-center gap-2 mb-2">
        <UserMinus size={15} className="text-purple-300" />
        <p className="text-sm font-medium text-purple-200">
          {items.length} {items.length === 1 ? 'fase' : 'fases'} dependem de uma só pessoa (SPOF)
        </p>
      </div>
      <div className="flex flex-col gap-1.5">
        {items.slice(0, 8).map((s) => (
          <div key={s.id} className="flex items-center gap-1.5 text-xs">
            <span
              className="rounded-full shrink-0"
              style={{ width: 6, height: 6, background: PRIO_COLOR[(s.priority || '').toLowerCase()] ?? 'var(--fg-3)' }}
            />
            <Clickable kind="fase" id={s.target_phase_id}>
              {s.target_phase_name}
            </Clickable>
            <span className="text-fg-3">depende de</span>
            <Clickable kind="operador" id={s.employee_id}>
              {s.employee_name}
            </Clickable>
          </div>
        ))}
      </div>
    </div>
  );
}
