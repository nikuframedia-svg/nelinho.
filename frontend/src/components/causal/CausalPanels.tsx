/**
 * CausalPanels — 10 painéis para explainability/causal Q.18.ZIP.A.Onda4 (D).
 *
 *  1. ErroTreePanel       — POST /v1/explain/diagnostics/investigate (cascade)
 *  2. ReichenbachPanel    — POST /v1/explain/diagnostics/common-cause
 *  3. MillPanel           — POST /v1/explain/diagnostics/what-changed
 *  4. InvestigatePanel    — POST /v1/explain/compute (compute métrica)
 *  5. NeloDagPanel        — GET  /v1/explain/discover (graph + edges)
 *  6. WorldModelPanel     — ✗ stub (sem REST endpoint exposto)
 *  7. AttributionPanel    — GET  /v1/explain/attribution (waterfall)
 *  8. AblationPanel       — ⚠ stub (módulo existe, REST ausente)
 *  9. WhyKpiPanel         — GET  /kpis/snapshot-explained (drawer KPI)
 * 10. PoetiqPanel         — POST /v1/copilot/poetiq/propose (iterative loop)
 */

import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { AlertTriangle, Sparkles, ChevronRight } from 'lucide-react';
import { Panel, ZipToneBadge, EmptyState } from '../dark';
import { getApiBase } from '../../lib/api';

const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
const BASE = getApiBase();

// ═══════════════════════════════════════════════════════════════════════════
// 1. ErroTreePanel — POST /v1/explain/diagnostics/investigate
// ═══════════════════════════════════════════════════════════════════════════

const ERRO_TREE_TRIGGERS = ['quality_drop', 'throughput_drop', 'delay_spike'] as const;
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

export function ReichenbachPanel() {
  const [phasesStr, setPhasesStr] = useState('laminagem,acabamento');
  const [periodDays, setPeriodDays] = useState(7);

  const m = useMutation({
    mutationFn: async () => {
      const phases = phasesStr.split(',').map((s) => s.trim()).filter(Boolean);
      if (phases.length < 2) throw new Error('Mínimo 2 fases (separadas por vírgula).');
      const r = await fetch(`${BASE}/v1/explain/diagnostics/common-cause`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...TENANT },
        body: JSON.stringify({ deviating_phases: phases, period_days: periodDays }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
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

function isoDays(offset: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}

export function MillPanel() {
  const [goodStart, setGoodStart] = useState(isoDays(-30));
  const [goodEnd, setGoodEnd] = useState(isoDays(-15));
  const [badStart, setBadStart] = useState(isoDays(-14));
  const [badEnd, setBadEnd] = useState(isoDays(0));

  const m = useMutation({
    mutationFn: async () => {
      const r = await fetch(`${BASE}/v1/explain/diagnostics/what-changed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...TENANT },
        body: JSON.stringify({
          good_period_start: goodStart,
          good_period_end: goodEnd,
          bad_period_start: badStart,
          bad_period_end: badEnd,
          metric: 'error_rate',
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
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

export function InvestigatePanel() {
  const [metricId, setMetricId] = useState('throughput_eur_day');

  const m = useMutation({
    mutationFn: async () => {
      const r = await fetch(`${BASE}/v1/explain/compute?metric_id=${encodeURIComponent(metricId)}`, {
        method: 'POST',
        headers: TENANT,
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
  });

  const result = m.data as
    | { metric_id?: string; value?: number; source?: string; unit?: string; computed_at?: string; scope?: any; period?: any }
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

export function NeloDagPanel() {
  const [tauMax, setTauMax] = useState(2);
  const [alpha, setAlpha] = useState(0.05);
  const [sampleSize, setSampleSize] = useState(300);

  const q = useQuery({
    queryKey: ['nelo-dag', tauMax, alpha, sampleSize],
    queryFn: async () => {
      const r = await fetch(
        `${BASE}/v1/explain/discover?tau_max=${tauMax}&alpha=${alpha}&sample_size=${sampleSize}`,
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

export function WorldModelPanel() {
  return (
    <Panel
      title="World-model — forecast bands"
      subtitle="src.copilot.causal.world_model (sem REST exposto)">
      <EmptyState
        title="Endpoint REST por expor"
        hint="Módulo Python com Monte Carlo rollout existe (causal_query) mas /v1/explain/forecast ainda não está implementado. Para já, world-model corre apenas via tool-call interno do Copilot."
        size="sm"
      />
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 7. AttributionPanel — GET /v1/explain/attribution (waterfall)
// ═══════════════════════════════════════════════════════════════════════════

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

export function AblationPanel() {
  return (
    <Panel
      title="Ablation kit — feature importance"
      subtitle="src.copilot.causal.ablkit (sem REST exposto)">
      <EmptyState
        title="Endpoint REST por expor"
        hint="Detector ABL kit já existe como módulo Python para o Copilot. /v1/explain/ablation está planeado mas ainda não exposto. Por agora, importância de features só visível via Copilot drawer."
        size="sm"
      />
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 9. WhyKpiPanel — GET /kpis/snapshot-explained (drawer KPI)
// ═══════════════════════════════════════════════════════════════════════════

export function WhyKpiPanel() {
  const q = useQuery({
    queryKey: ['kpis-snapshot-explained'],
    queryFn: async () => {
      const r = await fetch(`${BASE}/kpis/snapshot-explained`, { headers: TENANT });
      if (!r.ok) return null;
      return r.json();
    },
    staleTime: 60_000,
    retry: 0,
  });

  const data = q.data as
    | { oee?: any; availability?: any; otd?: any; quality?: any }
    | undefined
    | null;

  const items = data
    ? [
        { id: 'oee', label: 'OEE', payload: data.oee },
        { id: 'availability', label: 'Disponibilidade', payload: data.availability },
        { id: 'otd', label: 'OTD', payload: data.otd },
        { id: 'quality', label: 'Qualidade', payload: data.quality },
      ]
    : [];

  return (
    <Panel
      title='"Por que?" — KPIs explicados'
      subtitle="GET /kpis/snapshot-explained (Direção/OEE/Qualidade)">
      {q.isLoading ? (
        <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>
          A carregar KPIs…
        </div>
      ) : !data ? (
        <EmptyState title="Sem snapshot disponível" hint="Backend retornou vazio. Snapshot é regenerado de hora em hora." size="sm" />
      ) : (
        <div className="space-y-2">
          {items.map((it) => (
            <details key={it.id} className="rounded-md border" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <summary className="cursor-pointer px-3 py-2 text-xs flex items-center justify-between">
                <span style={{ color: 'var(--fg-1)' }}>{it.label}</span>
                <span className="tabular-nums" style={{ color: 'var(--fg-3)' }}>
                  {typeof it.payload?.value === 'number' ? `${(it.payload.value * 100).toFixed(1)}%` : '—'}
                </span>
              </summary>
              <pre
                className="px-3 py-2 text-[10px] overflow-x-auto border-t font-mono"
                style={{ borderColor: 'var(--bd-1)', color: 'var(--fg-2)' }}
              >
                {JSON.stringify(it.payload ?? {}, null, 2).slice(0, 800)}
              </pre>
            </details>
          ))}
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 10. PoetiqPanel — POST /v1/copilot/poetiq/propose (iterative loop)
// ═══════════════════════════════════════════════════════════════════════════

export function PoetiqPanel() {
  const [goal, setGoal] = useState('Maximizar throughput sem violar safety_net');
  const [rounds, setRounds] = useState(3);

  const m = useMutation({
    mutationFn: async () => {
      const r = await fetch(`${BASE}/v1/copilot/poetiq/propose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...TENANT },
        body: JSON.stringify({ goal, rounds }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
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

const SECTIONS = [
  { id: 'diag', label: 'Diagnostics' },
  { id: 'graph', label: 'NELO_DAG + Attribution' },
  { id: 'why', label: 'Por que?' },
  { id: 'iter', label: 'POETIQ + World-model' },
] as const;
type SectionId = (typeof SECTIONS)[number]['id'];

export function CausalDashboard() {
  const [section, setSection] = useState<SectionId>('diag');

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 px-1">
        <Sparkles size={14} style={{ color: 'var(--fg-3)' }} />
        <div className="flex gap-1 text-xs">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              onClick={() => setSection(s.id)}
              className="rounded-md px-2.5 py-1 transition-colors flex items-center gap-1"
              style={{
                background: section === s.id ? 'var(--bg-3)' : 'transparent',
                color: section === s.id ? 'var(--fg-1)' : 'var(--fg-3)',
              }}
            >
              {s.label}
              {section === s.id && <ChevronRight size={11} />}
            </button>
          ))}
        </div>
        <span className="ml-auto text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Q.18.ZIP.A.Onda4 — D. Causal/Explain
        </span>
      </div>

      {section === 'diag' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <ErroTreePanel />
          <ReichenbachPanel />
          <MillPanel />
          <InvestigatePanel />
        </div>
      )}

      {section === 'graph' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <NeloDagPanel />
          <AttributionPanel />
          <AblationPanel />
        </div>
      )}

      {section === 'why' && (
        <div className="grid grid-cols-1 gap-4">
          <WhyKpiPanel />
          <Panel title="Drawer ExplainDrawer existente" subtitle="Para invocar drawer per-KPI usa o ExplainDrawer já wired em /direcao e /qualidade.">
            <div className="px-3 py-3 text-xs flex items-start gap-2" style={{ color: 'var(--fg-2)' }}>
              <AlertTriangle size={14} style={{ color: 'var(--yellow)' }} />
              <span>
                Componente <code className="font-mono">ExplainDrawer</code> abre em qualquer KPI das pages Direção/OEE/Qualidade.
                Aqui mostra-se apenas o snapshot agregado de 4 KPIs raiz.
              </span>
            </div>
          </Panel>
        </div>
      )}

      {section === 'iter' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <PoetiqPanel />
          <WorldModelPanel />
        </div>
      )}
    </div>
  );
}
