// CausalPanels · AttributionPanel (Q.60.X). ZERO MOCKS — endpoints reais.
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Panel, ZipToneBadge } from '../../dark';
import { TENANT, BASE } from '../causalShared';

export function AttributionPanel() {
  const [target, setTarget] = useState('throughput_eur_day');
  const [sampleSize, setSampleSize] = useState(200);

  const q = useQuery({
    queryKey: ['attribution', target, sampleSize],
    queryFn: async () => {
      const r = await fetch(
        `${BASE}/v1/explain/attribution?target=${encodeURIComponent(target)}&sample_size=${sampleSize}`,
        { headers: TENANT },
      );
      if (!r.ok) return null;
      return r.json();
    },
    enabled: false,
    retry: 0,
  });

  const result = q.data as
    | {
        target?: string;
        status?: string;
        engine?: string;
        baseline_mean?: number;
        target_value?: number;
        ranked?: Array<{ node: string; contribution: number; pct: number }>;
      }
    | undefined
    | null;

  return (
    <Panel
      title="Causal attribution — waterfall"
      subtitle="DoWhy-GCM intrinsic_causal_influence sobre NELO_DAG">
      <div className="space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="target node (ex: throughput_eur_day)"
            className="flex-1 rounded-md border px-2 py-1.5 text-xs font-mono"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
          <input
            type="number"
            value={sampleSize}
            min={50}
            max={2000}
            onChange={(e) => setSampleSize(Number(e.target.value) || 200)}
            className="w-24 rounded-md border px-2 py-1.5 text-xs tabular-nums"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
          <button
            onClick={() => q.refetch()}
            disabled={q.isFetching}
            className="rounded-md px-3 py-1.5 text-xs font-medium"
            style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
          >
            {q.isFetching ? '…' : 'Atribuir'}
          </button>
        </div>
        {result && (
          <div className="rounded-md border p-3 text-xs space-y-2" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <div className="flex justify-between">
              <ZipToneBadge tone={result.status === 'ok' ? 'green' : 'yellow'} size="sm">
                {result.status ?? '—'}
              </ZipToneBadge>
              <span style={{ color: 'var(--fg-3)' }}>{result.engine}</span>
            </div>
            <div className="space-y-1">
              {(result.ranked ?? []).slice(0, 10).map((r, i) => {
                const pct = Math.max(0, Math.min(100, Math.abs(r.pct ?? 0) * 100));
                return (
                  <div key={i}>
                    <div className="flex justify-between">
                      <span className="font-mono" style={{ color: 'var(--fg-1)' }}>{r.node}</span>
                      <span className="tabular-nums" style={{ color: 'var(--fg-2)' }}>
                        {(r.contribution ?? 0).toFixed(2)} · {((r.pct ?? 0) * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="h-1.5 rounded mt-1" style={{ background: 'var(--bg-3)' }}>
                      <div
                        className="h-full rounded"
                        style={{ width: `${pct}%`, background: 'var(--blue)' }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 8. AblationPanel — ⚠ stub (módulo existe, REST ausente)
// ═══════════════════════════════════════════════════════════════════════════
