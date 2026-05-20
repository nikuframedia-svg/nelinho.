// CausalPanels · MillPanel (Q.60.X). ZERO MOCKS — endpoints reais.
// Q.61.25 — via causalApi em vez de fetch directo.
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Panel } from '../../dark';
import { isoDays } from '../causalShared';
import { causalPost } from '../../../lib/api/causalApi';

export function MillPanel() {
  const [goodStart, setGoodStart] = useState(isoDays(-30));
  const [goodEnd, setGoodEnd] = useState(isoDays(-15));
  const [badStart, setBadStart] = useState(isoDays(-14));
  const [badEnd, setBadEnd] = useState(isoDays(0));

  const m = useMutation({
    mutationFn: () =>
      causalPost('/v1/explain/diagnostics/what-changed', {
        good_period_start: goodStart,
        good_period_end: goodEnd,
        bad_period_start: badStart,
        bad_period_end: badEnd,
        metric: 'error_rate',
      }),
  });

  const result = m.data as
    | {
        verdict?: string;
        metric_comparison?: { delta?: number; cohens_d?: number };
        changes_found?: any[];
        unchanged?: any[];
      }
    | undefined;

  return (
    <Panel
      title="Mill — what-changed timeline"
      subtitle="Compara 2 períodos → ranking dimensões alteradas">
      <div className="space-y-3">
        <div className="grid grid-cols-4 gap-2">
          <input
            type="date"
            value={goodStart}
            onChange={(e) => setGoodStart(e.target.value)}
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
          <input
            type="date"
            value={goodEnd}
            onChange={(e) => setGoodEnd(e.target.value)}
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
          <input
            type="date"
            value={badStart}
            onChange={(e) => setBadStart(e.target.value)}
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
          <input
            type="date"
            value={badEnd}
            onChange={(e) => setBadEnd(e.target.value)}
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
        </div>
        <div className="flex items-center justify-between text-[10px]" style={{ color: 'var(--fg-3)' }}>
          <span>Período "antes" (good)</span>
          <span>Período "depois" (bad)</span>
        </div>
        <button
          onClick={() => m.mutate()}
          disabled={m.isPending}
          className="rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
        >
          {m.isPending ? 'A comparar…' : 'O que mudou?'}
        </button>
        {result && (
          <div className="rounded-md border p-3 text-xs space-y-2" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <div style={{ color: 'var(--fg-1)' }}>{result.verdict ?? '—'}</div>
            {result.metric_comparison && (
              <div className="flex gap-4 text-[11px]">
                <span style={{ color: 'var(--fg-3)' }}>
                  Δ <span className="tabular-nums" style={{ color: 'var(--fg-1)' }}>{(result.metric_comparison.delta ?? 0).toFixed(3)}</span>
                </span>
                <span style={{ color: 'var(--fg-3)' }}>
                  d <span className="tabular-nums" style={{ color: 'var(--fg-1)' }}>{(result.metric_comparison.cohens_d ?? 0).toFixed(2)}</span>
                </span>
              </div>
            )}
            {(result.changes_found ?? []).length > 0 && (
              <ul className="space-y-1" style={{ color: 'var(--fg-2)' }}>
                {result.changes_found!.slice(0, 6).map((c: any, i: number) => (
                  <li key={i} className="flex justify-between">
                    <span>
                      {c.category} — {c.change}
                    </span>
                    <span className="tabular-nums" style={{ color: 'var(--fg-1)' }}>
                      r={Number(c.correlation ?? 0).toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 4. InvestigatePanel — POST /v1/explain/compute (compute métrica)
// ═══════════════════════════════════════════════════════════════════════════
