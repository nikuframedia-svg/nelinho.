// CausalPanels · ErroTreePanel (Q.60.X). ZERO MOCKS — endpoints reais.
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Panel, ZipToneBadge } from '../../dark';
import { TENANT, BASE } from '../causalShared';

export const ERRO_TREE_TRIGGERS = ['quality_drop', 'throughput_drop', 'delay_spike'] as const;
type ErroTreeTrigger = (typeof ERRO_TREE_TRIGGERS)[number];

export function ErroTreePanel() {
  const [trigger, setTrigger] = useState<ErroTreeTrigger>('quality_drop');
  const [periodDays, setPeriodDays] = useState(7);
  const [phaseId, setPhaseId] = useState('');

  const m = useMutation({
    mutationFn: async () => {
      const r = await fetch(`${BASE}/v1/explain/diagnostics/investigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...TENANT },
        body: JSON.stringify({
          trigger,
          period_days: periodDays,
          phase_id: phaseId.trim() || null,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
  });

  const result = m.data as
    | {
        root_cause?: {
          type: string;
          entity: string;
          confidence: number;
          credible_interval_95: { low: number; high: number };
          evidence: string[];
        } | null;
        chain?: any[];
        steps_checked?: number;
        recommendation?: string;
      }
    | undefined;

  return (
    <Panel
      title="ERRO-TREE — cascade detector"
      subtitle="Mold → Worker → Overload (3-detector cascade)">
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-2">
          <select
            value={trigger}
            onChange={(e) => setTrigger(e.target.value as ErroTreeTrigger)}
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          >
            {ERRO_TREE_TRIGGERS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <input
            type="number"
            value={periodDays}
            min={1}
            max={90}
            onChange={(e) => setPeriodDays(Number(e.target.value) || 7)}
            placeholder="period_days"
            className="rounded-md border px-2 py-1.5 text-xs tabular-nums"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
          <input
            type="text"
            value={phaseId}
            onChange={(e) => setPhaseId(e.target.value)}
            placeholder="phase_id (opcional)"
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
        </div>
        <button
          onClick={() => m.mutate()}
          disabled={m.isPending}
          className="rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
        >
          {m.isPending ? 'A investigar…' : 'Investigar'}
        </button>
        {m.isError && (
          <div className="text-xs" style={{ color: 'var(--red)' }}>
            Erro: {(m.error as Error).message}
          </div>
        )}
        {result && (
          <div className="rounded-md border p-3 text-xs space-y-2" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <div className="flex items-center justify-between">
              <span style={{ color: 'var(--fg-3)' }}>Steps checked</span>
              <span className="tabular-nums" style={{ color: 'var(--fg-1)' }}>
                {result.steps_checked ?? 0}
              </span>
            </div>
            {result.root_cause ? (
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <ZipToneBadge tone="red" size="sm">
                    Root cause
                  </ZipToneBadge>
                  <span className="font-mono" style={{ color: 'var(--fg-1)' }}>
                    {result.root_cause.type} / {result.root_cause.entity}
                  </span>
                </div>
                <div style={{ color: 'var(--fg-2)' }}>
                  Confidence {(result.root_cause.confidence * 100).toFixed(1)}% — CI 95%{' '}
                  <span className="tabular-nums">
                    [{(result.root_cause.credible_interval_95.low * 100).toFixed(1)}–
                    {(result.root_cause.credible_interval_95.high * 100).toFixed(1)}%]
                  </span>
                </div>
                <ul className="list-disc list-inside" style={{ color: 'var(--fg-3)' }}>
                  {(result.root_cause.evidence ?? []).map((e: string, i: number) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <div style={{ color: 'var(--fg-3)' }}>Sem causa raiz isolada — verifica chain detalhada.</div>
            )}
            {result.recommendation && (
              <div className="pt-1 border-t" style={{ borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}>
                <strong>Recomendação:</strong> {result.recommendation}
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 2. ReichenbachPanel — POST /v1/explain/diagnostics/common-cause
// ═══════════════════════════════════════════════════════════════════════════
