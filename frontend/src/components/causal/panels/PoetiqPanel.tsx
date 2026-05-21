// CausalPanels · PoetiqPanel (Q.60.X). ZERO MOCKS — endpoints reais.
// Q.61.25 — via causalApi em vez de fetch directo.
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Panel } from '../../dark';
import { causalPost } from '../../../lib/api/causalApi';

export function PoetiqPanel() {
  const [goal, setGoal] = useState('Maximizar throughput sem violar safety_net');
  const [rounds, setRounds] = useState(3);

  const m = useMutation({
    mutationFn: () => causalPost('/v1/copilot/poetiq/propose', { goal, rounds }),
  });

  const result = m.data as
    | {
        proposal?: any;
        delta?: any;
        cpo_kpis?: any;
        commit_sha?: string;
        diff_vs_parent?: any;
      }
    | undefined;

  return (
    <Panel
      title="POETIQ — iterative loop"
      subtitle="LLM propõe → CPO valida → Copilot itera N rondas">
      <div className="space-y-3">
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          rows={2}
          placeholder="Objetivo (ex: maximizar throughput sem violar safety_net)"
          className="w-full rounded-md border px-2 py-1.5 text-xs"
          style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
        />
        <div className="flex items-center gap-3">
          <label className="text-xs flex items-center gap-2" style={{ color: 'var(--fg-3)' }}>
            Rondas
            <input
              type="number"
              value={rounds}
              min={1}
              max={5}
              onChange={(e) => setRounds(Number(e.target.value) || 3)}
              className="w-16 rounded-md border px-2 py-1 text-xs tabular-nums"
              style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
            />
          </label>
          <button
            onClick={() => m.mutate()}
            disabled={m.isPending}
            className="rounded-md px-3 py-1.5 text-xs font-medium ml-auto"
            style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
          >
            {m.isPending ? 'A iterar…' : 'Correr POETIQ'}
          </button>
        </div>
        {m.isError && (
          <div className="text-xs" style={{ color: 'var(--red)' }}>
            Erro: {(m.error as Error).message}
          </div>
        )}
        {result && (
          <div className="rounded-md border p-3 text-xs space-y-2" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            {result.commit_sha && (
              <div className="flex justify-between">
                <span style={{ color: 'var(--fg-3)' }}>Commit</span>
                <span className="font-mono" style={{ color: 'var(--fg-1)' }}>
                  {result.commit_sha.slice(0, 12)}
                </span>
              </div>
            )}
            {result.cpo_kpis && (
              <pre className="text-[10px] font-mono overflow-x-auto" style={{ color: 'var(--fg-2)' }}>
                {JSON.stringify(result.cpo_kpis, null, 2).slice(0, 600)}
              </pre>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// CausalDashboard — composição com tabs internas
// ═══════════════════════════════════════════════════════════════════════════
