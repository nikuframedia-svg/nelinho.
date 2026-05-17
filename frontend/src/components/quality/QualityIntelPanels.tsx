/**
 * QualityIntelPanels — 6 painéis para Quality Intelligence Q.18.ZIP.A.Onda6 (F).
 *
 *   1. RootCausePanel       — GET /v1/quality/root-cause?error_code=X
 *   2. ImpactPanel          — GET /v1/quality/impact?error_code=X
 *   3. BySupplierPanel      — GET /v1/quality/by-supplier?since=&until=
 *   4. ByLotPanel           — GET /v1/quality/by-lot?since=&until=
 *   5. WorkerRankingPanel   — GET /v1/quality/workers/ranking?phase_id=X
 *   6. MultiDimPanel        — GET /v1/quality/dashboard?group_by={phase|operator|sku|shift}
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, BarChart3, Users, Factory, Layers, Hash } from 'lucide-react';
import { Panel, ZipToneBadge, EmptyState } from '../dark';
import { getApiBase } from '../../lib/api';

const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
const BASE = getApiBase();

function isoDays(offset: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}

// ═══════════════════════════════════════════════════════════════════════════
// 1. RootCausePanel
// ═══════════════════════════════════════════════════════════════════════════

export function RootCausePanel() {
  const [code, setCode] = useState('');
  const [active, setActive] = useState('');

  const q = useQuery({
    queryKey: ['root-cause', active],
    queryFn: async () => {
      if (!active) return null;
      const r = await fetch(`${BASE}/v1/quality/root-cause?error_code=${encodeURIComponent(active)}`, {
        headers: TENANT,
      });
      if (!r.ok) return null;
      return r.json();
    },
    enabled: !!active,
    retry: 0,
  });

  const data = q.data as
    | {
        error_code?: string;
        total_events?: number;
        dimensions?: Record<string, Array<{ value: string; count: number; freq_pct: number; zscore: number }>>;
        summary?: string;
      }
    | undefined
    | null;

  return (
    <Panel title="Root-cause analyzer" subtitle="Distribuição por dimensão (z-score → outlier)">
      <div className="space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="error_code (ex: laminagem-bolha)"
            className="flex-1 rounded-md border px-2 py-1.5 text-xs font-mono"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
          <button
            onClick={() => setActive(code.trim())}
            disabled={!code.trim()}
            className="rounded-md px-3 py-1.5 text-xs font-medium"
            style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
          >
            <Search size={12} className="inline mr-1" />
            Analisar
          </button>
        </div>
        {q.isFetching && (
          <div className="text-xs px-2 py-3" style={{ color: 'var(--fg-3)' }}>
            A correr análise…
          </div>
        )}
        {data && (
          <div className="rounded-md border p-3 text-xs space-y-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <div className="flex justify-between">
              <span style={{ color: 'var(--fg-3)' }}>Eventos</span>
              <span className="tabular-nums" style={{ color: 'var(--fg-1)' }}>{data.total_events ?? 0}</span>
            </div>
            {data.summary && <div style={{ color: 'var(--fg-1)' }}>{data.summary}</div>}
            {data.dimensions &&
              Object.entries(data.dimensions).map(([dim, rows]) => (
                <div key={dim}>
                  <div className="font-medium mb-1 capitalize" style={{ color: 'var(--fg-2)' }}>
                    {dim.replace(/_/g, ' ')}
                  </div>
                  <div className="space-y-1">
                    {rows.slice(0, 5).map((r, i) => (
                      <div key={i} className="flex justify-between gap-2">
                        <span className="font-mono truncate" style={{ color: 'var(--fg-2)' }}>{r.value}</span>
                        <span className="tabular-nums shrink-0" style={{ color: 'var(--fg-3)' }}>
                          {r.count}× · {r.freq_pct.toFixed(1)}%
                        </span>
                        {r.zscore >= 2 && (
                          <ZipToneBadge tone="red" size="sm">
                            z={r.zscore.toFixed(1)}
                          </ZipToneBadge>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 2. ImpactPanel
// ═══════════════════════════════════════════════════════════════════════════

export function ImpactPanel() {
  const [code, setCode] = useState('');
  const [active, setActive] = useState('');

  const q = useQuery({
    queryKey: ['impact', active],
    queryFn: async () => {
      if (!active) return null;
      const r = await fetch(`${BASE}/v1/quality/impact?error_code=${encodeURIComponent(active)}`, { headers: TENANT });
      if (!r.ok) return null;
      return r.json();
    },
    enabled: !!active,
    retry: 0,
  });

  const data = q.data as
    | {
        error_code?: string;
        total_events?: number;
        cumulative_cost_eur?: number;
        hours_lost?: number;
        affected_orders?: number;
        share_of_tenant_rework?: number;
      }
    | undefined
    | null;

  const tiles = data
    ? [
        { label: 'Eventos', value: data.total_events ?? 0, fmt: (v: number) => v.toString() },
        { label: 'Custo €', value: data.cumulative_cost_eur ?? 0, fmt: (v: number) => `€${v.toFixed(0)}` },
        { label: 'Horas perdidas', value: data.hours_lost ?? 0, fmt: (v: number) => `${v.toFixed(1)}h` },
        { label: 'Encomendas afectadas', value: data.affected_orders ?? 0, fmt: (v: number) => v.toString() },
      ]
    : [];

  return (
    <Panel title="Impact per error" subtitle="€ acumulados + horas perdidas + encomendas afectadas">
      <div className="space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="error_code"
            className="flex-1 rounded-md border px-2 py-1.5 text-xs font-mono"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
          <button
            onClick={() => setActive(code.trim())}
            disabled={!code.trim()}
            className="rounded-md px-3 py-1.5 text-xs font-medium"
            style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
          >
            <BarChart3 size={12} className="inline mr-1" />
            Computar
          </button>
        </div>
        {data && (
          <div className="grid grid-cols-2 gap-2">
            {tiles.map((t) => (
              <div key={t.label} className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
                <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>
                  {t.label}
                </div>
                <div className="text-lg font-semibold tabular-nums mt-1" style={{ color: 'var(--fg-1)' }}>
                  {t.fmt(t.value as number)}
                </div>
              </div>
            ))}
            {typeof data.share_of_tenant_rework === 'number' && (
              <div className="col-span-2 rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
                <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>
                  Share do retrabalho do tenant
                </div>
                <div className="text-base font-semibold tabular-nums mt-1" style={{ color: 'var(--fg-1)' }}>
                  {(data.share_of_tenant_rework * 100).toFixed(1)}%
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 3. BySupplierPanel
// ═══════════════════════════════════════════════════════════════════════════

interface SupplierRow {
  supplier_id?: string;
  supplier_name?: string;
  rework_count?: number;
  cost_eur?: number;
  defect_rate?: number;
}

export function BySupplierPanel() {
  const [since, setSince] = useState(isoDays(-30));
  const [until, setUntil] = useState(isoDays(0));

  const q = useQuery({
    queryKey: ['by-supplier', since, until],
    queryFn: async () => {
      const r = await fetch(`${BASE}/v1/quality/by-supplier?since=${since}&until=${until}`, { headers: TENANT });
      if (!r.ok) return { items: [] as SupplierRow[] };
      return r.json();
    },
    staleTime: 60_000,
    retry: 0,
  });

  const items = ((q.data as { items?: SupplierRow[] } | undefined)?.items ?? []) as SupplierRow[];

  return (
    <Panel title="Quality by supplier" subtitle="Scorecard fornecedores → custo retrabalho" badge={items.length || '—'}>
      <div className="space-y-3">
        <div className="flex gap-2">
          <input type="date" value={since} onChange={(e) => setSince(e.target.value)}
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
          <input type="date" value={until} onChange={(e) => setUntil(e.target.value)}
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
        </div>
        {q.isLoading ? (
          <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
        ) : items.length === 0 ? (
          <EmptyState title="Sem retrabalho registado" hint="Não há erros associados a fornecedores no período." size="sm" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead style={{ color: 'var(--fg-3)' }}>
                <tr className="text-left">
                  <th className="px-2 py-1">Fornecedor</th>
                  <th className="px-2 py-1 text-right">Retrabalhos</th>
                  <th className="px-2 py-1 text-right">Custo €</th>
                  <th className="px-2 py-1 text-right">Defeito %</th>
                </tr>
              </thead>
              <tbody>
                {items.slice(0, 30).map((it, i) => (
                  <tr key={i} className="border-t" style={{ borderColor: 'var(--bd-1)' }}>
                    <td className="px-2 py-1" style={{ color: 'var(--fg-1)' }}>{it.supplier_name ?? it.supplier_id ?? '—'}</td>
                    <td className="px-2 py-1 text-right tabular-nums" style={{ color: 'var(--fg-2)' }}>{it.rework_count ?? 0}</td>
                    <td className="px-2 py-1 text-right tabular-nums" style={{ color: 'var(--fg-1)' }}>€{(it.cost_eur ?? 0).toFixed(0)}</td>
                    <td className="px-2 py-1 text-right tabular-nums" style={{ color: 'var(--fg-2)' }}>
                      {typeof it.defect_rate === 'number' ? (it.defect_rate * 100).toFixed(1) + '%' : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 4. ByLotPanel
// ═══════════════════════════════════════════════════════════════════════════

interface LotRow {
  material_lot_id?: string;
  rework_count?: number;
  cost_eur?: number;
  affected_ofs?: number;
}

export function ByLotPanel() {
  const [since, setSince] = useState(isoDays(-30));
  const [until, setUntil] = useState(isoDays(0));

  const q = useQuery({
    queryKey: ['by-lot', since, until],
    queryFn: async () => {
      const r = await fetch(`${BASE}/v1/quality/by-lot?since=${since}&until=${until}`, { headers: TENANT });
      if (!r.ok) return { items: [] as LotRow[] };
      return r.json();
    },
    staleTime: 60_000,
    retry: 0,
  });

  const items = ((q.data as { items?: LotRow[] } | undefined)?.items ?? []) as LotRow[];

  return (
    <Panel title="Quality by lot" subtitle="Trace por lote material → custo + OFs afectadas" badge={items.length || '—'}>
      <div className="space-y-3">
        <div className="flex gap-2">
          <input type="date" value={since} onChange={(e) => setSince(e.target.value)}
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
          <input type="date" value={until} onChange={(e) => setUntil(e.target.value)}
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
        </div>
        {q.isLoading ? (
          <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
        ) : items.length === 0 ? (
          <EmptyState title="Sem retrabalho por lote" hint="Não há trace de erros a lotes no período." size="sm" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead style={{ color: 'var(--fg-3)' }}>
                <tr className="text-left">
                  <th className="px-2 py-1">Lote</th>
                  <th className="px-2 py-1 text-right">Retrabalhos</th>
                  <th className="px-2 py-1 text-right">Custo €</th>
                  <th className="px-2 py-1 text-right">OFs</th>
                </tr>
              </thead>
              <tbody>
                {items.slice(0, 30).map((it, i) => (
                  <tr key={i} className="border-t" style={{ borderColor: 'var(--bd-1)' }}>
                    <td className="px-2 py-1 font-mono" style={{ color: 'var(--fg-1)' }}>{it.material_lot_id ?? '—'}</td>
                    <td className="px-2 py-1 text-right tabular-nums" style={{ color: 'var(--fg-2)' }}>{it.rework_count ?? 0}</td>
                    <td className="px-2 py-1 text-right tabular-nums" style={{ color: 'var(--fg-1)' }}>€{(it.cost_eur ?? 0).toFixed(0)}</td>
                    <td className="px-2 py-1 text-right tabular-nums" style={{ color: 'var(--fg-2)' }}>{it.affected_ofs ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 5. WorkerRankingPanel
// ═══════════════════════════════════════════════════════════════════════════

interface WorkerRow {
  employee_id?: string;
  employee_name?: string;
  error_count?: number;
  ops_executed?: number;
  error_rate?: number;
  trend_7d_delta?: number;
}

export function WorkerRankingPanel() {
  const [phaseId, setPhaseId] = useState('');

  const q = useQuery({
    queryKey: ['worker-ranking', phaseId],
    queryFn: async () => {
      const url = phaseId
        ? `${BASE}/v1/quality/workers/ranking?phase_id=${encodeURIComponent(phaseId)}`
        : `${BASE}/v1/quality/workers/ranking`;
      const r = await fetch(url, { headers: TENANT });
      if (!r.ok) return { items: [] as WorkerRow[] };
      return r.json();
    },
    staleTime: 60_000,
    retry: 0,
  });

  const items = ((q.data as { items?: WorkerRow[] } | undefined)?.items ?? []) as WorkerRow[];

  return (
    <Panel title="Worker quality ranking" subtitle="Erros / operações executadas + tendência 7d" badge={items.length || '—'}>
      <div className="space-y-3">
        <input
          type="text"
          value={phaseId}
          onChange={(e) => setPhaseId(e.target.value)}
          placeholder="phase_id (opcional — todas as fases)"
          className="w-full rounded-md border px-2 py-1.5 text-xs font-mono"
          style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
        />
        {q.isLoading ? (
          <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
        ) : items.length === 0 ? (
          <EmptyState title="Sem dados de qualidade por operador" hint="Sem operações suficientes no período." size="sm" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead style={{ color: 'var(--fg-3)' }}>
                <tr className="text-left">
                  <th className="px-2 py-1">Operador</th>
                  <th className="px-2 py-1 text-right">Erros</th>
                  <th className="px-2 py-1 text-right">Ops</th>
                  <th className="px-2 py-1 text-right">Taxa erro</th>
                  <th className="px-2 py-1 text-right">Δ 7d</th>
                </tr>
              </thead>
              <tbody>
                {items.slice(0, 30).map((w, i) => (
                  <tr key={i} className="border-t" style={{ borderColor: 'var(--bd-1)' }}>
                    <td className="px-2 py-1" style={{ color: 'var(--fg-1)' }}>{w.employee_name ?? w.employee_id ?? '—'}</td>
                    <td className="px-2 py-1 text-right tabular-nums" style={{ color: 'var(--fg-2)' }}>{w.error_count ?? 0}</td>
                    <td className="px-2 py-1 text-right tabular-nums" style={{ color: 'var(--fg-2)' }}>{w.ops_executed ?? 0}</td>
                    <td className="px-2 py-1 text-right tabular-nums" style={{ color: 'var(--fg-1)' }}>
                      {typeof w.error_rate === 'number' ? (w.error_rate * 100).toFixed(2) + '%' : '—'}
                    </td>
                    <td className="px-2 py-1 text-right tabular-nums">
                      {typeof w.trend_7d_delta === 'number' ? (
                        <ZipToneBadge tone={w.trend_7d_delta > 0 ? 'red' : 'green'} size="sm">
                          {w.trend_7d_delta > 0 ? '+' : ''}{(w.trend_7d_delta * 100).toFixed(1)}%
                        </ZipToneBadge>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 6. MultiDimPanel
// ═══════════════════════════════════════════════════════════════════════════

const DIMENSIONS = [
  { id: 'phase', label: 'Por fase', icon: Layers },
  { id: 'operator', label: 'Por operador', icon: Users },
  { id: 'sku', label: 'Por SKU', icon: Hash },
  { id: 'shift', label: 'Por turno', icon: Factory },
] as const;
type Dim = (typeof DIMENSIONS)[number]['id'];

interface DimRow {
  dim_value?: string;
  total_reworks?: number;
  error_rate?: number;
  top_error_codes?: string[];
}

export function MultiDimPanel() {
  const [dim, setDim] = useState<Dim>('phase');
  const q = useQuery({
    queryKey: ['quality-dashboard', dim],
    queryFn: async () => {
      const r = await fetch(`${BASE}/v1/quality/dashboard?group_by=${dim}`, { headers: TENANT });
      if (!r.ok) return { items: [] as DimRow[] };
      return r.json();
    },
    staleTime: 60_000,
    retry: 0,
  });

  const items = ((q.data as { items?: DimRow[] } | undefined)?.items ?? []) as DimRow[];

  return (
    <Panel title="Multidim dashboard" subtitle="Group by: fase / operador / SKU / turno">
      <div className="space-y-3">
        <div className="flex gap-1 flex-wrap">
          {DIMENSIONS.map((d) => {
            const Icon = d.icon;
            return (
              <button
                key={d.id}
                onClick={() => setDim(d.id)}
                className="rounded-md px-2.5 py-1 text-xs flex items-center gap-1.5"
                style={{
                  background: dim === d.id ? 'var(--bg-3)' : 'var(--bg-2)',
                  color: dim === d.id ? 'var(--fg-1)' : 'var(--fg-3)',
                  border: '1px solid var(--bd-1)',
                }}
              >
                <Icon size={11} />
                {d.label}
              </button>
            );
          })}
        </div>
        {q.isLoading ? (
          <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
        ) : items.length === 0 ? (
          <EmptyState title="Sem dados na dimensão" size="sm" />
        ) : (
          <div className="space-y-1">
            {items.slice(0, 12).map((r, i) => (
              <div key={i} className="rounded-md border p-2 text-xs" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
                <div className="flex justify-between">
                  <span className="font-mono" style={{ color: 'var(--fg-1)' }}>{r.dim_value ?? '—'}</span>
                  <span className="tabular-nums" style={{ color: 'var(--fg-2)' }}>
                    {r.total_reworks ?? 0} retrabalhos · {typeof r.error_rate === 'number' ? (r.error_rate * 100).toFixed(2) + '%' : '—'}
                  </span>
                </div>
                {r.top_error_codes && r.top_error_codes.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {r.top_error_codes.slice(0, 4).map((c, j) => (
                      <ZipToneBadge key={j} tone="gray" size="sm">{c}</ZipToneBadge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// QualityIntelDashboard — composição
// ═══════════════════════════════════════════════════════════════════════════

export function QualityIntelDashboard() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between px-1">
        <span className="text-xs" style={{ color: 'var(--fg-2)' }}>
          Quality Intelligence — root-cause / impact / por fornecedor / por lote / por operador / multi-dim
        </span>
        <span className="text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Q.18.ZIP.A.Onda6 — F. Quality
        </span>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <RootCausePanel />
        <ImpactPanel />
        <BySupplierPanel />
        <ByLotPanel />
        <WorkerRankingPanel />
        <MultiDimPanel />
      </div>
    </div>
  );
}
