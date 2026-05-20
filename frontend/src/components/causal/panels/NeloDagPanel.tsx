// CausalPanels · NeloDagPanel (Q.60.X). ZERO MOCKS — endpoints reais.
// Q.61.25 — via causalApi em vez de fetch directo.
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Panel, ZipToneBadge } from '../../dark';
import { causalGet } from '../../../lib/api/causalApi';

export function NeloDagPanel() {
  const [tauMax, setTauMax] = useState(2);
  const [alpha, setAlpha] = useState(0.05);
  const [sampleSize, setSampleSize] = useState(300);

  const q = useQuery({
    queryKey: ['nelo-dag', tauMax, alpha, sampleSize],
    queryFn: () =>
      causalGet(
        `/v1/explain/discover?tau_max=${tauMax}&alpha=${alpha}&sample_size=${sampleSize}`,
      ),
    enabled: false,
    retry: 0,
  });

  const result = q.data as
    | {
        status?: string;
        engine?: string;
        sample_size?: number;
        tau_max?: number;
        nodes_examined?: number;
        candidate_edges?: Array<{
          src: string;
          dst: string;
          lag: number;
          strength: number;
          pvalue: number;
          is_new: boolean;
          direction: string;
        }>;
      }
    | undefined
    | null;

  return (
    <Panel
      title="NELO_DAG — graph explorer (PCMCI+)"
      subtitle="Sliders: tau_max (lag) · alpha (sig) · sample_size">
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-2 text-xs">
          <label className="space-y-1">
            <div style={{ color: 'var(--fg-3)' }}>tau_max ({tauMax})</div>
            <input type="range" min={0} max={5} value={tauMax} onChange={(e) => setTauMax(Number(e.target.value))} className="w-full" />
          </label>
          <label className="space-y-1">
            <div style={{ color: 'var(--fg-3)' }}>alpha ({alpha})</div>
            <input
              type="range"
              min={0.01}
              max={0.49}
              step={0.01}
              value={alpha}
              onChange={(e) => setAlpha(Number(e.target.value))}
              className="w-full"
            />
          </label>
          <label className="space-y-1">
            <div style={{ color: 'var(--fg-3)' }}>sample ({sampleSize})</div>
            <input
              type="range"
              min={50}
              max={2000}
              step={50}
              value={sampleSize}
              onChange={(e) => setSampleSize(Number(e.target.value))}
              className="w-full"
            />
          </label>
        </div>
        <button
          onClick={() => q.refetch()}
          disabled={q.isFetching}
          className="rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
        >
          {q.isFetching ? 'A descobrir…' : 'Descobrir edges'}
        </button>
        {result && (
          <div className="rounded-md border text-xs" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <div className="px-3 py-2 border-b flex justify-between" style={{ borderColor: 'var(--bd-1)' }}>
              <ZipToneBadge tone={result.status === 'ok' ? 'green' : result.status === 'degraded' ? 'yellow' : 'gray'} size="sm">
                {result.status ?? '—'}
              </ZipToneBadge>
              <span style={{ color: 'var(--fg-3)' }}>{result.engine}</span>
              <span className="tabular-nums" style={{ color: 'var(--fg-1)' }}>
                {result.candidate_edges?.length ?? 0} edges
              </span>
            </div>
            <div className="overflow-x-auto max-h-72">
              <table className="w-full text-[11px]">
                <thead style={{ color: 'var(--fg-3)' }}>
                  <tr className="text-left">
                    <th className="px-2 py-1">src</th>
                    <th className="px-2 py-1">dst</th>
                    <th className="px-2 py-1 text-right">lag</th>
                    <th className="px-2 py-1 text-right">strength</th>
                    <th className="px-2 py-1 text-right">p</th>
                    <th className="px-2 py-1">novo?</th>
                  </tr>
                </thead>
                <tbody>
                  {(result.candidate_edges ?? []).slice(0, 30).map((e, i) => (
                    <tr key={i} className="border-t" style={{ borderColor: 'var(--bd-1)' }}>
                      <td className="px-2 py-1 font-mono" style={{ color: 'var(--fg-1)' }}>{e.src}</td>
                      <td className="px-2 py-1 font-mono" style={{ color: 'var(--fg-1)' }}>{e.dst}</td>
                      <td className="px-2 py-1 tabular-nums text-right" style={{ color: 'var(--fg-2)' }}>{e.lag}</td>
                      <td className="px-2 py-1 tabular-nums text-right" style={{ color: 'var(--fg-2)' }}>{e.strength.toFixed(2)}</td>
                      <td className="px-2 py-1 tabular-nums text-right" style={{ color: 'var(--fg-2)' }}>{e.pvalue.toFixed(3)}</td>
                      <td className="px-2 py-1">
                        {e.is_new ? (
                          <ZipToneBadge tone="blue" size="sm">novo</ZipToneBadge>
                        ) : (
                          <span style={{ color: 'var(--fg-3)' }}>—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 6. WorldModelPanel — ✗ stub honesto (sem REST endpoint exposto)
// ═══════════════════════════════════════════════════════════════════════════
