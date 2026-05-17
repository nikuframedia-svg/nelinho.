/**
 * ProfitPanels — Onda 10 (J). Profit Intelligence em /direcao.
 *
 *   1. ThroughputGauge      — GET /v1/profit/dashboard (€/dia gauge + trend)
 *   2. PricingPanel         — POST /v1/profit/pricing/recommend + simulate
 *   3. CogsDrawerPanel      — GET /v1/profit/cogs/orders/{id} (breakdown 6 cats)
 *   4. ScenarioPanel        — POST /v1/profit/scenarios/simulate (sliders)
 *   5. MarginPanel          — GET /v1/profit/cogs/orders/{id}/margin
 */

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { TrendingUp, Calculator, FileText, Sliders, Target } from 'lucide-react';
import { Panel, ZipToneBadge, EmptyState } from '../dark';
import { getApiBase } from '../../lib/api';

const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
const BASE = getApiBase();

// ═══════════════════════════════════════════════════════════════════════════
// 1. ThroughputGauge
// ═══════════════════════════════════════════════════════════════════════════

export function ThroughputGauge() {
  const q = useQuery({
    queryKey: ['profit-dashboard'],
    queryFn: async () => {
      const r = await fetch(`${BASE}/v1/profit/dashboard`, { headers: TENANT });
      if (!r.ok) return null;
      return r.json();
    },
    staleTime: 60_000,
    retry: 0,
  });

  const data = q.data as
    | {
        throughput_eur?: { today?: number; target?: number; week_avg?: number };
        trend_14d?: Array<{ date?: string; eur?: number }>;
      }
    | undefined
    | null;

  const today = data?.throughput_eur?.today ?? 0;
  const target = data?.throughput_eur?.target ?? 32500;
  const trend = (data?.trend_14d ?? []).map((p) => p.eur ?? 0);
  const max = Math.max(...trend, target, 1);
  const pct = Math.min(100, (today / target) * 100);

  return (
    <Panel title="Throughput €/dia" subtitle="Gauge actual vs alvo · trend 14 dias">
      {q.isLoading ? (
        <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
      ) : !data ? (
        <EmptyState title="Profit dashboard indisponível" hint="Endpoint /v1/profit/dashboard não respondeu." size="sm" />
      ) : (
        <div className="space-y-3">
          <div className="rounded-md border p-4 text-center" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>
              Hoje
            </div>
            <div className="text-3xl font-semibold tabular-nums mt-1" style={{ color: pct >= 100 ? 'var(--green)' : pct >= 80 ? 'var(--yellow)' : 'var(--red)' }}>
              €{today.toFixed(0)}
            </div>
            <div className="text-[11px] mt-1" style={{ color: 'var(--fg-3)' }}>
              alvo €{target.toFixed(0)} · {pct.toFixed(0)}%
            </div>
            <div className="h-2 mt-3 rounded" style={{ background: 'var(--bg-3)' }}>
              <div
                className="h-full rounded"
                style={{ width: `${pct}%`, background: pct >= 100 ? 'var(--green)' : pct >= 80 ? 'var(--yellow)' : 'var(--red)' }}
              />
            </div>
          </div>
          {trend.length > 0 && (
            <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <div className="text-[10px] uppercase tracking-wider mb-2" style={{ color: 'var(--fg-3)' }}>
                Trend 14d
              </div>
              <div className="flex items-end gap-1 h-16">
                {trend.map((v, i) => (
                  <div
                    key={i}
                    className="flex-1 rounded-t"
                    style={{
                      height: `${(v / max) * 100}%`,
                      background: v >= target ? 'var(--green)' : 'var(--blue)',
                      minHeight: 2,
                    }}
                    title={`Dia ${i + 1}: €${v.toFixed(0)}`}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 2. PricingPanel
// ═══════════════════════════════════════════════════════════════════════════

export function PricingPanel() {
  const [orderId, setOrderId] = useState('');
  const [markup, setMarkup] = useState(25);
  const [targetMargin, setTargetMargin] = useState(20);

  const m = useMutation({
    mutationFn: async () => {
      const r = await fetch(`${BASE}/v1/profit/pricing/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...TENANT },
        body: JSON.stringify({
          order_id: orderId,
          base_markup_percent: markup,
          target_margin_percent: targetMargin,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
  });

  const data = m.data as
    | { recommended_price?: number; expected_margin_percent?: number; rationale?: string }
    | undefined;

  return (
    <Panel title="Pricing engine" subtitle="POST /v1/profit/pricing/recommend (markup × target margin)">
      <div className="space-y-3">
        <input
          type="text"
          value={orderId}
          onChange={(e) => setOrderId(e.target.value)}
          placeholder="order_id"
          className="w-full rounded-md border px-2 py-1.5 text-xs font-mono"
          style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
        />
        <div className="grid grid-cols-2 gap-2 text-xs">
          <label className="space-y-1">
            <div style={{ color: 'var(--fg-3)' }}>Markup base ({markup}%)</div>
            <input type="range" min={5} max={80} value={markup} onChange={(e) => setMarkup(Number(e.target.value))} className="w-full" />
          </label>
          <label className="space-y-1">
            <div style={{ color: 'var(--fg-3)' }}>Target margin ({targetMargin}%)</div>
            <input type="range" min={5} max={50} value={targetMargin} onChange={(e) => setTargetMargin(Number(e.target.value))} className="w-full" />
          </label>
        </div>
        <button
          onClick={() => m.mutate()}
          disabled={!orderId.trim() || m.isPending}
          className="rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
        >
          {m.isPending ? 'A calcular…' : 'Recomendar preço'}
        </button>
        {data && (
          <div className="rounded-md border p-3 text-xs space-y-1" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <div className="flex justify-between">
              <span style={{ color: 'var(--fg-3)' }}>Preço sugerido</span>
              <span className="font-semibold tabular-nums" style={{ color: 'var(--blue)' }}>
                €{(data.recommended_price ?? 0).toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between">
              <span style={{ color: 'var(--fg-3)' }}>Margem esperada</span>
              <span className="tabular-nums" style={{ color: 'var(--fg-1)' }}>
                {(data.expected_margin_percent ?? 0).toFixed(1)}%
              </span>
            </div>
            {data.rationale && (
              <div className="pt-1 border-t" style={{ borderColor: 'var(--bd-1)', color: 'var(--fg-2)' }}>
                {data.rationale}
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 3. CogsDrawerPanel — breakdown per order
// ═══════════════════════════════════════════════════════════════════════════

export function CogsDrawerPanel() {
  const [orderId, setOrderId] = useState('');
  const [active, setActive] = useState('');

  const q = useQuery({
    queryKey: ['cogs-order', active],
    queryFn: async () => {
      if (!active) return null;
      const r = await fetch(`${BASE}/v1/profit/cogs/orders/${encodeURIComponent(active)}`, { headers: TENANT });
      if (!r.ok) return null;
      return r.json();
    },
    enabled: !!active,
    retry: 0,
  });

  const data = q.data as
    | {
        order_id?: string;
        total_cogs?: number;
        cogs_per_unit?: number;
        breakdown?: { material?: number; labor?: number; machine?: number; setup?: number; overhead?: number; scrap?: number };
        status?: string;
      }
    | undefined
    | null;

  const cats = data?.breakdown
    ? [
        { label: 'Material', value: data.breakdown.material ?? 0, color: 'var(--blue)' },
        { label: 'Labor', value: data.breakdown.labor ?? 0, color: 'var(--green)' },
        { label: 'Machine', value: data.breakdown.machine ?? 0, color: 'var(--yellow)' },
        { label: 'Setup', value: data.breakdown.setup ?? 0, color: 'var(--red-bg)' },
        { label: 'Overhead', value: data.breakdown.overhead ?? 0, color: 'var(--fg-3)' },
        { label: 'Scrap', value: data.breakdown.scrap ?? 0, color: 'var(--red)' },
      ]
    : [];
  const total = cats.reduce((acc, c) => acc + c.value, 0) || 1;

  return (
    <Panel title="COGS per barco" subtitle="Breakdown 6 categorias (material/labor/machine/setup/overhead/scrap)">
      <div className="space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            placeholder="order_id"
            className="flex-1 rounded-md border px-2 py-1.5 text-xs font-mono"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
          <button
            onClick={() => setActive(orderId.trim())}
            disabled={!orderId.trim()}
            className="rounded-md px-3 py-1.5 text-xs font-medium"
            style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
          >
            Carregar
          </button>
        </div>
        {data && (
          <>
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
                <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>
                  Total COGS
                </div>
                <div className="text-lg font-semibold tabular-nums mt-1" style={{ color: 'var(--fg-1)' }}>
                  €{(data.total_cogs ?? 0).toFixed(0)}
                </div>
              </div>
              <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
                <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>
                  Por unidade
                </div>
                <div className="text-lg font-semibold tabular-nums mt-1" style={{ color: 'var(--fg-1)' }}>
                  €{(data.cogs_per_unit ?? 0).toFixed(2)}
                </div>
              </div>
            </div>
            <div className="space-y-1">
              {cats.map((c) => (
                <div key={c.label}>
                  <div className="flex justify-between text-xs">
                    <span style={{ color: 'var(--fg-2)' }}>{c.label}</span>
                    <span className="tabular-nums" style={{ color: 'var(--fg-1)' }}>
                      €{c.value.toFixed(0)} · {((c.value / total) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-1.5 rounded mt-0.5" style={{ background: 'var(--bg-3)' }}>
                    <div className="h-full rounded" style={{ width: `${(c.value / total) * 100}%`, background: c.color }} />
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 4. ScenarioPanel — what-if sliders
// ═══════════════════════════════════════════════════════════════════════════

export function ScenarioPanel() {
  const [orderId, setOrderId] = useState('');
  const [material, setMaterial] = useState(1.0);
  const [labor, setLabor] = useState(1.0);
  const [machine, setMachine] = useState(1.0);
  const [overhead, setOverhead] = useState(1.0);
  const [scrap, setScrap] = useState(1.0);

  const m = useMutation({
    mutationFn: async () => {
      const r = await fetch(`${BASE}/v1/profit/scenarios/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...TENANT },
        body: JSON.stringify({
          base_order_id: orderId,
          material_multiplier: material,
          labor_multiplier: labor,
          machine_multiplier: machine,
          overhead_multiplier: overhead,
          scrap_multiplier: scrap,
          scenario_name: 'what_if',
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
  });

  const data = m.data as
    | { total_cogs?: number; delta_vs_base?: number; new_margin_percent?: number }
    | undefined;

  const sliders = [
    { label: 'Material', value: material, set: setMaterial },
    { label: 'Labor', value: labor, set: setLabor },
    { label: 'Machine', value: machine, set: setMachine },
    { label: 'Overhead', value: overhead, set: setOverhead },
    { label: 'Scrap', value: scrap, set: setScrap },
  ];

  return (
    <Panel title="Profit scenarios — what-if" subtitle="Multiplicadores 0.5×–2.0× → impacto COGS + margem">
      <div className="space-y-3">
        <input
          type="text"
          value={orderId}
          onChange={(e) => setOrderId(e.target.value)}
          placeholder="base_order_id"
          className="w-full rounded-md border px-2 py-1.5 text-xs font-mono"
          style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
        />
        <div className="grid grid-cols-1 gap-2 text-xs">
          {sliders.map((s) => (
            <label key={s.label} className="flex items-center gap-3">
              <span className="w-20" style={{ color: 'var(--fg-3)' }}>{s.label}</span>
              <input
                type="range"
                min={0.5}
                max={2.0}
                step={0.05}
                value={s.value}
                onChange={(e) => s.set(Number(e.target.value))}
                className="flex-1"
              />
              <span className="w-12 text-right tabular-nums" style={{ color: 'var(--fg-1)' }}>{s.value.toFixed(2)}×</span>
            </label>
          ))}
        </div>
        <button
          onClick={() => m.mutate()}
          disabled={!orderId.trim() || m.isPending}
          className="rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
        >
          {m.isPending ? 'A simular…' : 'Simular cenário'}
        </button>
        {data && (
          <div className="rounded-md border p-3 text-xs space-y-1" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <div className="flex justify-between">
              <span style={{ color: 'var(--fg-3)' }}>Novo COGS</span>
              <span className="tabular-nums font-semibold" style={{ color: 'var(--fg-1)' }}>
                €{(data.total_cogs ?? 0).toFixed(0)}
              </span>
            </div>
            {typeof data.delta_vs_base === 'number' && (
              <div className="flex justify-between">
                <span style={{ color: 'var(--fg-3)' }}>Δ vs base</span>
                <ZipToneBadge tone={data.delta_vs_base > 0 ? 'red' : 'green'} size="sm">
                  {data.delta_vs_base > 0 ? '+' : ''}{data.delta_vs_base.toFixed(2)}€
                </ZipToneBadge>
              </div>
            )}
            {typeof data.new_margin_percent === 'number' && (
              <div className="flex justify-between">
                <span style={{ color: 'var(--fg-3)' }}>Nova margem</span>
                <span className="tabular-nums" style={{ color: 'var(--fg-1)' }}>{data.new_margin_percent.toFixed(1)}%</span>
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 5. MarginPanel — margem per order
// ═══════════════════════════════════════════════════════════════════════════

export function MarginPanel() {
  const [orderId, setOrderId] = useState('');
  const [price, setPrice] = useState(1000);

  const q = useQuery({
    queryKey: ['margin', orderId, price],
    queryFn: async () => {
      if (!orderId.trim()) return null;
      const r = await fetch(`${BASE}/v1/profit/cogs/orders/${encodeURIComponent(orderId)}/margin?selling_price=${price}`, { headers: TENANT });
      if (!r.ok) return null;
      return r.json();
    },
    enabled: false,
    retry: 0,
  });

  const data = q.data as
    | { margin_eur?: number; margin_percent?: number; cogs?: number }
    | undefined
    | null;

  return (
    <Panel title="Margin per order" subtitle="Compute margem dado preço de venda">
      <div className="space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            placeholder="order_id"
            className="flex-1 rounded-md border px-2 py-1.5 text-xs font-mono"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
          <input
            type="number"
            value={price}
            onChange={(e) => setPrice(Number(e.target.value) || 0)}
            placeholder="preço €"
            className="w-28 rounded-md border px-2 py-1.5 text-xs tabular-nums"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
          <button
            onClick={() => q.refetch()}
            disabled={!orderId.trim() || q.isFetching}
            className="rounded-md px-3 py-1.5 text-xs font-medium"
            style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
          >
            {q.isFetching ? '…' : 'Compute'}
          </button>
        </div>
        {data && (
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>COGS</div>
              <div className="text-base font-semibold tabular-nums mt-1" style={{ color: 'var(--fg-1)' }}>
                €{(data.cogs ?? 0).toFixed(0)}
              </div>
            </div>
            <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>Margem €</div>
              <div className="text-base font-semibold tabular-nums mt-1" style={{ color: (data.margin_eur ?? 0) > 0 ? 'var(--green)' : 'var(--red)' }}>
                €{(data.margin_eur ?? 0).toFixed(0)}
              </div>
            </div>
            <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>Margem %</div>
              <div className="text-base font-semibold tabular-nums mt-1" style={{ color: (data.margin_percent ?? 0) > 15 ? 'var(--green)' : (data.margin_percent ?? 0) > 5 ? 'var(--yellow)' : 'var(--red)' }}>
                {(data.margin_percent ?? 0).toFixed(1)}%
              </div>
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ProfitDashboard — composição
// ═══════════════════════════════════════════════════════════════════════════

const SECTIONS = [
  { id: 'gauge', label: 'Throughput', icon: TrendingUp },
  { id: 'pricing', label: 'Pricing', icon: Calculator },
  { id: 'cogs', label: 'COGS', icon: FileText },
  { id: 'scenarios', label: 'What-if', icon: Sliders },
  { id: 'margin', label: 'Margem', icon: Target },
] as const;
type SecId = (typeof SECTIONS)[number]['id'];

export function ProfitDashboard() {
  const [sec, setSec] = useState<SecId>('gauge');

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 px-1 pb-2 border-b" style={{ borderColor: 'var(--bd-1)' }}>
        {SECTIONS.map((s) => {
          const Icon = s.icon;
          return (
            <button
              key={s.id}
              onClick={() => setSec(s.id)}
              className="rounded-md px-2.5 py-1.5 text-xs flex items-center gap-1.5"
              style={{
                background: sec === s.id ? 'var(--bg-3)' : 'transparent',
                color: sec === s.id ? 'var(--fg-1)' : 'var(--fg-3)',
              }}
            >
              <Icon size={12} />
              {s.label}
            </button>
          );
        })}
        <span className="ml-auto text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Q.18.ZIP.A.Onda10 — J. Profit
        </span>
      </div>
      {sec === 'gauge' && <ThroughputGauge />}
      {sec === 'pricing' && <PricingPanel />}
      {sec === 'cogs' && <CogsDrawerPanel />}
      {sec === 'scenarios' && <ScenarioPanel />}
      {sec === 'margin' && <MarginPanel />}
    </div>
  );
}
