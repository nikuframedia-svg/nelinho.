// CausalPanels · ReichenbachPanel (Q.60.X). ZERO MOCKS — endpoints reais.
// Q.61.25 — via causalApi em vez de fetch directo.
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Panel, ZipToneBadge } from '../../dark';
import { causalPost } from '../../../lib/api/causalApi';

export function ReichenbachPanel() {
  const [phasesStr, setPhasesStr] = useState('laminagem,acabamento');
  const [periodDays, setPeriodDays] = useState(7);

  const m = useMutation({
    mutationFn: () => {
      const phases = phasesStr.split(',').map((s) => s.trim()).filter(Boolean);
      if (phases.length < 2) throw new Error('Mínimo 2 fases (separadas por vírgula).');
      return causalPost('/v1/explain/diagnostics/common-cause', {
        deviating_phases: phases,
        period_days: periodDays,
      });
    },
  });

  const result = m.data as
    | { verdict?: string; common_causes?: any[]; independent_causes?: any[]; checks_run?: number }
    | undefined;

  return (
    <Panel
      title="Reichenbach — common-cause detector"
      subtitle="2+ fases derivam → procura recurso partilhado">
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <input
            type="text"
            value={phasesStr}
            onChange={(e) => setPhasesStr(e.target.value)}
            placeholder="fases (csv): laminagem,acabamento"
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
          <input
            type="number"
            value={periodDays}
            min={1}
            max={90}
            onChange={(e) => setPeriodDays(Number(e.target.value) || 7)}
            className="rounded-md border px-2 py-1.5 text-xs tabular-nums"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
        </div>
        <button
          onClick={() => m.mutate()}
          disabled={m.isPending}
          className="rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
        >
          {m.isPending ? 'A correr…' : 'Procurar causa comum'}
        </button>
        {m.isError && (
          <div className="text-xs" style={{ color: 'var(--red)' }}>
            {(m.error as Error).message}
          </div>
        )}
        {result && (
          <div className="rounded-md border p-3 text-xs space-y-2" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <div className="flex items-center justify-between">
              <span style={{ color: 'var(--fg-3)' }}>Veredicto</span>
              <ZipToneBadge tone={result.verdict === 'common_cause' ? 'red' : 'green'} size="sm">
                {result.verdict ?? '—'}
              </ZipToneBadge>
            </div>
            <div className="flex items-center justify-between">
              <span style={{ color: 'var(--fg-3)' }}>Checks run</span>
              <span className="tabular-nums" style={{ color: 'var(--fg-1)' }}>
                {result.checks_run ?? 0}
              </span>
            </div>
            {(result.common_causes ?? []).length > 0 && (
              <div>
                <div className="font-medium mb-1" style={{ color: 'var(--fg-1)' }}>
                  Causas comuns ({result.common_causes!.length})
                </div>
                <ul className="space-y-1" style={{ color: 'var(--fg-2)' }}>
                  {result.common_causes!.map((c: any, i: number) => (
                    <li key={i} className="font-mono">
                      {JSON.stringify(c).slice(0, 120)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 3. MillPanel — POST /v1/explain/diagnostics/what-changed
// ═══════════════════════════════════════════════════════════════════════════
