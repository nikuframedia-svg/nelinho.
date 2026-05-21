// CausalPanels · InvestigatePanel (Q.60.X). ZERO MOCKS — endpoints reais.
// Q.61.25 — via causalApi em vez de fetch directo.
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Panel } from '../../dark';
import { causalPost } from '../../../lib/api/causalApi';

export function InvestigatePanel() {
  const [metricId, setMetricId] = useState('throughput_eur_day');

  const m = useMutation({
    mutationFn: () =>
      causalPost(
        `/v1/explain/compute?metric_id=${encodeURIComponent(metricId)}`,
        undefined,
      ),
  });

  const result = m.data as
    | { metric_id?: string; value?: number; source?: string; unit?: string; computed_at?: string; scope?: Record<string, unknown>; period?: Record<string, unknown> }
    | undefined;

  return (
    <Panel
      title="Investigate — compute métrica"
      subtitle="POST /v1/explain/compute → valor canónico + fonte">
      <div className="space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={metricId}
            onChange={(e) => setMetricId(e.target.value)}
            placeholder="metric_id"
            className="flex-1 rounded-md border px-2 py-1.5 text-xs font-mono"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
          <button
            onClick={() => m.mutate()}
            disabled={m.isPending}
            className="rounded-md px-3 py-1.5 text-xs font-medium"
            style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
          >
            {m.isPending ? '…' : 'Compute'}
          </button>
        </div>
        {result && (
          <div className="rounded-md border p-3 text-xs space-y-1" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <div className="flex justify-between">
              <span style={{ color: 'var(--fg-3)' }}>Valor</span>
              <span className="tabular-nums font-medium" style={{ color: 'var(--fg-1)' }}>
                {typeof result.value === 'number' ? result.value.toFixed(2) : '—'} {result.unit ?? ''}
              </span>
            </div>
            <div className="flex justify-between">
              <span style={{ color: 'var(--fg-3)' }}>Fonte</span>
              <span className="font-mono" style={{ color: 'var(--fg-1)' }}>
                {result.source ?? '—'}
              </span>
            </div>
            {result.computed_at && (
              <div className="flex justify-between">
                <span style={{ color: 'var(--fg-3)' }}>Computado</span>
                <span style={{ color: 'var(--fg-1)' }}>
                  {new Date(result.computed_at).toLocaleString('pt-PT')}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 5. NeloDagPanel — GET /v1/explain/discover (graph + edges)
// ═══════════════════════════════════════════════════════════════════════════
