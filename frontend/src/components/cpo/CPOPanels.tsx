/**
 * CPOPanels — visualizações para CPO Optimization (Onda 3 / C).
 *
 * 1. CPOTimelinePanel    — MAP-Elites alternatives Pareto (5-10 candidates)
 * 2. CPOCommitsPanel     — list commits SHA + decide (approve/reject)
 * 3. CPOReoptimizerCard  — botão re-optimizar com input horizon_days
 * 4. CPOInternalsPanel   — FRRMAB + Surrogate placeholders honestos
 *
 * Sprint Q.18.ZIP.C.Onda3.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Sparkles, GitBranch, Brain, AlertTriangle } from 'lucide-react';
import { Panel, ZipToneBadge, EmptyState } from '../dark';

const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
const BASE = 'http://127.0.0.1:8001';

interface MapElitesCandidate {
  cell_key?: string;
  cell?: [number, number, number];
  fitness?: number;
  utilization?: number;
  tardiness?: number;
  late_orders?: number;
  schedule_id?: string;
  axiom_violations?: string[];
}

interface TimelineResponse {
  commit_sha256: string | null;
  candidates: MapElitesCandidate[];
}

interface CPOCommit {
  sha?: string;
  proposed_at?: string;
  decision_status?: string;
  total_orders?: number;
  fitness?: number;
  axiom_violations?: string[];
}

async function fetchTimeline(): Promise<TimelineResponse> {
  try {
    const r = await fetch(`${BASE}/v1/plan/cpo/timeline`, { headers: TENANT });
    if (!r.ok) return { commit_sha256: null, candidates: [] };
    return await r.json();
  } catch { return { commit_sha256: null, candidates: [] }; }
}

async function fetchCommits(): Promise<CPOCommit[]> {
  try {
    const r = await fetch(`${BASE}/v1/plan/cpo/commits?limit=20`, { headers: TENANT });
    if (!r.ok) return [];
    const d = await r.json();
    return Array.isArray(d) ? d : (d.items ?? d.commits ?? []);
  } catch { return []; }
}

async function runSchedule(horizon_days: number) {
  const r = await fetch(`${BASE}/v1/plan/cpo/schedule`, {
    method: 'POST',
    headers: { ...TENANT, 'Content-Type': 'application/json' },
    body: JSON.stringify({ horizon_days }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

// ═══════════════════════════════════════════════════════════════════════════
// CPOReoptimizerCard — botão re-optimizar
// ═══════════════════════════════════════════════════════════════════════════

export function CPOReoptimizerCard() {
  const [horizon, setHorizon] = useState(14);
  const [lastResult, setLastResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => runSchedule(horizon),
    onSuccess: (data) => {
      setLastResult(data);
      setError(null);
      qc.invalidateQueries({ queryKey: ['cpo'] });
    },
    onError: (err: Error) => {
      setError(err.message);
      setLastResult(null);
    },
  });

  return (
    <div
      style={{
        padding: 16,
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
      }}
    >
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={14} style={{ color: 'var(--blue)' }} />
        <span className="text-sm font-medium" style={{ color: 'var(--fg-0)' }}>
          Re-optimizar plano de produção
        </span>
      </div>
      <div className="text-xs mb-3" style={{ color: 'var(--fg-2)' }}>
        Corre o CPO scheduler v4 (DRCFFS-R + CP-SAT L-RHO fallback) para
        gerar novo schedule respeitando os 7 Spelke axioms. Resultado é uma
        proposta — aprovas em /inbox antes de aplicar.
      </div>
      <div className="flex items-center gap-3">
        <label className="text-xs" style={{ color: 'var(--fg-1)' }}>
          Horizonte:
          <input
            type="number"
            min={1}
            max={90}
            value={horizon}
            onChange={(e) => setHorizon(parseInt(e.target.value) || 14)}
            disabled={mutation.isPending}
            className="ml-2 px-2 py-1 text-xs tabular-nums rounded"
            style={{
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-1)',
              color: 'var(--fg-0)',
              width: 60,
            }}
          />
          <span className="ml-1" style={{ color: 'var(--fg-3)' }}>dias</span>
        </label>
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium text-white transition-colors disabled:opacity-50"
          style={{
            background: 'var(--blue)',
            border: '1px solid var(--blue)',
          }}
        >
          <Sparkles size={12} />
          {mutation.isPending ? 'A correr CPO…' : 'Re-optimizar'}
        </button>
      </div>
      {error && (
        <div
          className="mt-3 px-3 py-2 rounded text-xs"
          style={{
            background: 'var(--red-bg)',
            border: '1px solid var(--red-bd)',
            color: 'var(--red)',
          }}
        >
          Erro: {error}
        </div>
      )}
      {lastResult && (
        <div
          className="mt-3 px-3 py-2 rounded text-xs"
          style={{
            background: 'var(--green-bg)',
            border: '1px solid var(--green-bd)',
            color: 'var(--fg-1)',
          }}
        >
          <strong style={{ color: 'var(--green)' }}>✓ Schedule gerado.</strong>{' '}
          {lastResult.commit_sha
            ? `SHA ${lastResult.commit_sha.slice(0, 8)} · `
            : ''}
          {lastResult.total_orders ?? 0} orders · fitness {Number(lastResult.fitness ?? 0).toFixed(2)}.
          Aprovar em /inbox.
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// CPOTimelinePanel — MAP-Elites alternatives
// ═══════════════════════════════════════════════════════════════════════════

export function CPOTimelinePanel() {
  const q = useQuery({
    queryKey: ['cpo', 'timeline'],
    queryFn: fetchTimeline,
    staleTime: 30_000,
    retry: 0,
  });
  const data = q.data;
  const candidates = data?.candidates ?? [];

  return (
    <Panel
      title="MAP-Elites alternatives — Pareto front"
      badge={candidates.length || '—'}
      flush
    >
      {q.isLoading ? (
        <div className="px-4 py-6 text-center text-xs" style={{ color: 'var(--fg-3)' }}>
          A carregar candidates…
        </div>
      ) : candidates.length === 0 ? (
        <EmptyState
          title="Sem candidates Pareto na timeline"
          hint="Quando o CPO scheduler correr (botão Re-optimizar), o MAP-Elites archive 3D (10×10×5 células: utilização × tardiness × late orders) extrai 5-10 alternativas com trade-offs reais — não só top-K por fitness."
          mascot
          size="sm"
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="border-b" style={{ borderColor: 'var(--bd-1)' }}>
              <tr className="text-left uppercase tracking-wider" style={{ color: 'var(--fg-3)', fontSize: 10 }}>
                <th className="px-3 py-2">Cell</th>
                <th className="px-3 py-2 text-right">Fitness</th>
                <th className="px-3 py-2 text-right">Utilização</th>
                <th className="px-3 py-2 text-right">Tardiness</th>
                <th className="px-3 py-2 text-right">Late orders</th>
                <th className="px-3 py-2">Axiomas</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c, i) => (
                <tr key={i} className="border-b" style={{ borderColor: 'var(--bd-1)' }}>
                  <td className="px-3 py-2 font-mono" style={{ color: 'var(--fg-1)' }}>
                    {c.cell_key ?? (c.cell ? c.cell.join('×') : '—')}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-right" style={{ color: 'var(--green)' }}>
                    {c.fitness !== undefined ? Number(c.fitness).toFixed(3) : '—'}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-right" style={{ color: 'var(--fg-1)' }}>
                    {c.utilization !== undefined ? `${Math.round(c.utilization * 100)}%` : '—'}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-right" style={{ color: 'var(--fg-1)' }}>
                    {c.tardiness !== undefined ? Number(c.tardiness).toFixed(1) : '—'}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-right" style={{ color: c.late_orders ? 'var(--yellow)' : 'var(--fg-1)' }}>
                    {c.late_orders ?? 0}
                  </td>
                  <td className="px-3 py-2">
                    {c.axiom_violations && c.axiom_violations.length > 0 ? (
                      <ZipToneBadge tone="red" size="sm">
                        {c.axiom_violations.length} violado{c.axiom_violations.length > 1 ? 's' : ''}
                      </ZipToneBadge>
                    ) : (
                      <ZipToneBadge tone="green" size="sm">7/7 OK</ZipToneBadge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// CPOCommitsPanel — list commits + axioma quebrado tooltip
// ═══════════════════════════════════════════════════════════════════════════

export function CPOCommitsPanel() {
  const q = useQuery({
    queryKey: ['cpo', 'commits'],
    queryFn: fetchCommits,
    staleTime: 30_000,
    retry: 0,
  });
  const commits = q.data ?? [];

  return (
    <Panel
      title="CPO commits (DRCFFS-R Gantt)"
      badge={commits.length || '—'}
      flush
    >
      {q.isLoading ? (
        <div className="px-4 py-6 text-center text-xs" style={{ color: 'var(--fg-3)' }}>
          A carregar commits…
        </div>
      ) : commits.length === 0 ? (
        <EmptyState
          title="Sem commits CPO ainda"
          hint="Cada Re-optimizar gera um commit SHA com schedule completo. Tooltip de axiomas mostra quais Spelke axioms foram preservados/violados."
          mascot
          size="sm"
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="border-b" style={{ borderColor: 'var(--bd-1)' }}>
              <tr className="text-left uppercase tracking-wider" style={{ color: 'var(--fg-3)', fontSize: 10 }}>
                <th className="px-3 py-2">SHA</th>
                <th className="px-3 py-2">Proposed</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2 text-right">Orders</th>
                <th className="px-3 py-2 text-right">Fitness</th>
                <th className="px-3 py-2">Axiomas</th>
              </tr>
            </thead>
            <tbody>
              {commits.map((c, i) => (
                <tr key={c.sha ?? i} className="border-b" style={{ borderColor: 'var(--bd-1)' }}>
                  <td className="px-3 py-2 font-mono" style={{ color: 'var(--fg-1)' }}>
                    {(c.sha ?? '—').slice(0, 8)}
                  </td>
                  <td className="px-3 py-2" style={{ color: 'var(--fg-2)' }}>
                    {c.proposed_at ? new Date(c.proposed_at).toLocaleString('pt-PT') : '—'}
                  </td>
                  <td className="px-3 py-2">
                    <ZipToneBadge
                      tone={
                        c.decision_status === 'approved' ? 'green'
                          : c.decision_status === 'rejected' ? 'red'
                            : 'yellow'
                      }
                      size="sm"
                    >
                      {c.decision_status ?? 'pending'}
                    </ZipToneBadge>
                  </td>
                  <td className="px-3 py-2 tabular-nums text-right" style={{ color: 'var(--fg-1)' }}>
                    {c.total_orders ?? 0}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-right" style={{ color: 'var(--fg-1)' }}>
                    {c.fitness !== undefined ? Number(c.fitness).toFixed(2) : '—'}
                  </td>
                  <td className="px-3 py-2">
                    {c.axiom_violations && c.axiom_violations.length > 0 ? (
                      <span
                        className="inline-flex items-center gap-1"
                        title={c.axiom_violations.join(', ')}
                      >
                        <AlertTriangle size={11} style={{ color: 'var(--red)' }} />
                        <span style={{ color: 'var(--red)' }} className="text-[11px]">
                          {c.axiom_violations.length} violado{c.axiom_violations.length > 1 ? 's' : ''}
                        </span>
                      </span>
                    ) : (
                      <span className="text-[11px]" style={{ color: 'var(--green)' }}>7/7 ✓</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// CPOInternalsPanel — FRRMAB + Surrogate placeholders honestos
// ═══════════════════════════════════════════════════════════════════════════

export function CPOInternalsPanel() {
  return (
    <Panel title="CPO internals — FRRMAB + Surrogate" flush>
      <div className="px-4 py-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div
          style={{
            padding: 14,
            background: 'var(--bg-2)',
            border: '1px solid var(--bd-1)',
            borderRadius: 'var(--r-md)',
          }}
        >
          <div className="flex items-center gap-2 mb-2">
            <Brain size={13} style={{ color: 'var(--purple)' }} />
            <span className="text-xs font-medium" style={{ color: 'var(--fg-0)' }}>
              FRRMAB Multi-Armed Bandit
            </span>
          </div>
          <div className="text-xs mb-2" style={{ color: 'var(--fg-2)', lineHeight: 1.5 }}>
            Selector adaptativo de 6 operadores de mutação (swap adjacent /
            random / insert move / etc) baseado em UCB1 com decay exponencial
            (c=0.2, window=200). Aprende qual mutação funciona para o estado
            actual em tempo real.
          </div>
          <div className="text-[11px]" style={{ color: 'var(--fg-3)' }}>
            Endpoint REST não exposto — métricas internas backend. Acessível
            apenas via logs do scheduler.
          </div>
        </div>
        <div
          style={{
            padding: 14,
            background: 'var(--bg-2)',
            border: '1px solid var(--bd-1)',
            borderRadius: 'var(--r-md)',
          }}
        >
          <div className="flex items-center gap-2 mb-2">
            <GitBranch size={13} style={{ color: 'var(--blue)' }} />
            <span className="text-xs font-medium" style={{ color: 'var(--fg-0)' }}>
              Surrogate RandomForest
            </span>
          </div>
          <div className="text-xs mb-2" style={{ color: 'var(--fg-2)', lineHeight: 1.5 }}>
            Meta-modelo estima fitness antes de correr decoder custoso (7
            features: n_ops, edd_gap, permutation_entropy, etc). Rejeita
            candidates onde predicted_fitness {'>'}1.2× best_known.
          </div>
          <div className="text-[11px]" style={{ color: 'var(--fg-3)' }}>
            Endpoint REST não exposto — filtro interno scheduler.
            Performance impact: ~30% menos tempo CPO.
          </div>
        </div>
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// CPODashboard — composição
// ═══════════════════════════════════════════════════════════════════════════

export function CPODashboard() {
  return (
    <div className="space-y-4">
      <CPOReoptimizerCard />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CPOTimelinePanel />
        <CPOCommitsPanel />
      </div>
      <CPOInternalsPanel />
    </div>
  );
}
