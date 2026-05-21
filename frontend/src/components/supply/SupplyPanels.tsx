/**
 * SupplyPanels — Onda 9 (I). Plan/Supply/Forecast em /expedicao.
 *
 *  1. ForecastPanel        — POST /v1/supply/forecast
 *  2. SeasonalityPanel     — placeholder honesto (Prophet seasonal_components
 *                            existem mas sem endpoint heatmap)
 *  3. RopPanel             — GET /v1/supply/rop/{sku_id}
 *  4. AbcPanel             — POST /v1/supply/abc
 *  5. ShortageAlertsPanel  — GET /v1/copilot/alerts (filter source)
 *
 * Q.67.2.B — migrado de `apiFetch` directo para `supplyApi`/`supplyAlertsApi`
 * (lib/api/supplyApi.ts; `abcAnalysisFlat` + `supplyAlertsApi` adicionados
 * neste sub-sprint) + `supplyKeys` (lib/api/keys.ts). Tenant + trace_id
 * injectados via `request()` (Q.61.12).
 */

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { TrendingUp, Package, AlertTriangle, BarChart3, Calendar } from 'lucide-react';
import { Panel, ZipToneBadge, EmptyState } from '../dark';
import { supplyApi, supplyAlertsApi, type CopilotShortageAlert } from '../../lib/api/supplyApi';
import { supplyKeys } from '../../lib/api/keys';

// ═══════════════════════════════════════════════════════════════════════════
// 1. ForecastPanel
// ═══════════════════════════════════════════════════════════════════════════

interface ForecastPoint {
  date?: string;
  ds?: string;
  yhat?: number;
  yhat_lower?: number;
  yhat_upper?: number;
}

export function ForecastPanel() {
  const [skuId, setSkuId] = useState('');
  const [periods, setPeriods] = useState(30);

  const m = useMutation({
    mutationFn: async () => {
      const today = new Date();
      const sample = Array.from({ length: 60 }, (_, i) => {
        const d = new Date(today);
        d.setDate(d.getDate() - (60 - i));
        return { ds: d.toISOString().slice(0, 10), y: 100 + Math.sin(i / 7) * 20 };
      });
      return supplyApi.forecast({
        sku_id: skuId,
        historical_data: sample,
        periods_ahead: periods,
      });
    },
  });

  const fc = m.data as { forecast?: ForecastPoint[]; method?: string; quality?: unknown } | undefined;
  const points = fc?.forecast ?? [];
  const max = Math.max(...points.map((p) => p.yhat_upper ?? p.yhat ?? 0), 1);

  return (
    <Panel title="Forecast 30/90d (Prophet)" subtitle="Bandas P50/P90 + WMAPE quality">
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <input
            type="text"
            value={skuId}
            onChange={(e) => setSkuId(e.target.value)}
            placeholder="sku_id"
            className="rounded-md border px-2 py-1.5 text-xs font-mono"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          />
          <select
            value={periods}
            onChange={(e) => setPeriods(Number(e.target.value))}
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
          >
            <option value={30}>30 dias</option>
            <option value={60}>60 dias</option>
            <option value={90}>90 dias</option>
          </select>
        </div>
        <button
          onClick={() => m.mutate()}
          disabled={!skuId.trim() || m.isPending}
          className="rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
        >
          {m.isPending ? 'A correr Prophet…' : 'Gerar forecast'}
        </button>
        {points.length > 0 && (
          <div className="rounded-md border p-3 text-xs space-y-2" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <div className="flex justify-between">
              <span style={{ color: 'var(--fg-3)' }}>Method</span>
              <span style={{ color: 'var(--fg-1)' }}>{fc?.method ?? '—'}</span>
            </div>
            {fc?.quality ? (
              <div className="flex justify-between">
                <span style={{ color: 'var(--fg-3)' }}>Quality</span>
                <span className="font-mono" style={{ color: 'var(--fg-1)' }}>{String(JSON.stringify(fc.quality)).slice(0, 60)}</span>
              </div>
            ) : null}
            <div className="space-y-1">
              {points.slice(0, 14).map((p, i) => {
                const pct = ((p.yhat ?? 0) / max) * 100;
                return (
                  <div key={i} className="flex items-center gap-2">
                    <span className="font-mono w-20" style={{ color: 'var(--fg-3)' }}>
                      {p.ds ?? p.date ?? '—'}
                    </span>
                    <div className="flex-1 h-3 rounded relative" style={{ background: 'var(--bg-3)' }}>
                      <div
                        className="absolute top-0 left-0 h-full rounded"
                        style={{ width: `${pct}%`, background: 'var(--blue)' }}
                      />
                      {p.yhat_upper && (
                        <div
                          className="absolute top-0 left-0 h-full"
                          style={{
                            width: `${(p.yhat_upper / max) * 100}%`,
                            background: 'transparent',
                            borderRight: '2px dashed var(--blue)',
                            opacity: 0.5,
                          }}
                        />
                      )}
                    </div>
                    <span className="tabular-nums w-16 text-right" style={{ color: 'var(--fg-1)' }}>
                      {(p.yhat ?? 0).toFixed(0)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
        {m.isError && (
          <div className="text-xs" style={{ color: 'var(--red)' }}>
            Erro: {(m.error as Error).message}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 2. SeasonalityPanel — placeholder honesto
// ═══════════════════════════════════════════════════════════════════════════

export function SeasonalityPanel() {
  return (
    <Panel title="Sazonalidade 24m heatmap" subtitle="Prophet seasonal_components (sem REST exposto)">
      <EmptyState
        title="Endpoint REST por expor"
        hint="Prophet calcula seasonal_components (yearly + weekly) internamente em ARIMAForecaster. Para visualização heatmap 24m falta endpoint /v1/supply/seasonality."
        size="sm"
      />
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 3. RopPanel
// ═══════════════════════════════════════════════════════════════════════════

export function RopPanel() {
  const [sku, setSku] = useState('');
  const [avg, setAvg] = useState(50);
  const [lead, setLead] = useState(7);
  const [std, setStd] = useState(2);
  const [serviceLevel, setServiceLevel] = useState(0.95);

  const q = useQuery({
    queryKey: supplyKeys.rop({
      skuId: sku,
      avgDailyDemand: avg,
      leadTimeDays: lead,
      leadTimeStdDev: std,
      serviceLevel,
    }),
    queryFn: async () => {
      if (!sku.trim()) return null;
      try {
        return await supplyApi.calculateROP(sku, {
          avg_daily_demand: avg,
          lead_time_days: lead,
          lead_time_std_dev: std,
          service_level: serviceLevel,
        });
      } catch {
        return null;
      }
    },
    enabled: false,
    retry: 0,
  });

  const data = q.data as
    | { reorder_point?: number; safety_stock?: number; cycle_stock?: number; z_score?: number }
    | undefined
    | null;

  return (
    <Panel title="ROP per SKU" subtitle="Reorder point + safety stock por nível de serviço">
      <div className="space-y-3">
        <input
          type="text"
          value={sku}
          onChange={(e) => setSku(e.target.value)}
          placeholder="sku_id"
          className="w-full rounded-md border px-2 py-1.5 text-xs font-mono"
          style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
        />
        <div className="grid grid-cols-4 gap-2 text-xs">
          <label>
            <div style={{ color: 'var(--fg-3)' }}>Procura/dia</div>
            <input type="number" value={avg} onChange={(e) => setAvg(Number(e.target.value) || 0)}
              className="w-full mt-1 rounded-md border px-2 py-1 tabular-nums"
              style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
          </label>
          <label>
            <div style={{ color: 'var(--fg-3)' }}>Lead time (d)</div>
            <input type="number" value={lead} onChange={(e) => setLead(Number(e.target.value) || 0)}
              className="w-full mt-1 rounded-md border px-2 py-1 tabular-nums"
              style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
          </label>
          <label>
            <div style={{ color: 'var(--fg-3)' }}>σ lead time</div>
            <input type="number" value={std} onChange={(e) => setStd(Number(e.target.value) || 0)}
              className="w-full mt-1 rounded-md border px-2 py-1 tabular-nums"
              style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
          </label>
          <label>
            <div style={{ color: 'var(--fg-3)' }}>Service level</div>
            <select value={serviceLevel} onChange={(e) => setServiceLevel(Number(e.target.value))}
              className="w-full mt-1 rounded-md border px-2 py-1"
              style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}>
              <option value={0.90}>90%</option>
              <option value={0.95}>95%</option>
              <option value={0.99}>99%</option>
            </select>
          </label>
        </div>
        <button
          onClick={() => q.refetch()}
          disabled={!sku.trim() || q.isFetching}
          className="rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
        >
          {q.isFetching ? 'A calcular…' : 'Calcular ROP'}
        </button>
        {data && (
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>ROP</div>
              <div className="text-lg font-semibold tabular-nums mt-1" style={{ color: 'var(--blue)' }}>
                {(data.reorder_point ?? 0).toFixed(1)}
              </div>
            </div>
            <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>Safety</div>
              <div className="text-lg font-semibold tabular-nums mt-1" style={{ color: 'var(--fg-1)' }}>
                {(data.safety_stock ?? 0).toFixed(1)}
              </div>
            </div>
            <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>z-score</div>
              <div className="text-lg font-semibold tabular-nums mt-1" style={{ color: 'var(--fg-1)' }}>
                {(data.z_score ?? 0).toFixed(2)}
              </div>
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 4. AbcPanel
// ═══════════════════════════════════════════════════════════════════════════

interface AbcItem {
  sku_id: string;
  total_value?: number;
  cumulative_pct?: number;
  abc_class?: 'A' | 'B' | 'C';
}

export function AbcPanel() {
  const m = useMutation({
    mutationFn: async () => {
      const sample = Array.from({ length: 30 }, (_, i) => ({
        sku_id: `SKU-${String(i + 1).padStart(3, '0')}`,
        annual_value: Math.round(Math.random() * 100000),
      }));
      return supplyApi.abcAnalysisFlat({ items: sample });
    },
  });

  const data = m.data as { items?: AbcItem[]; summary?: unknown } | undefined;
  const items = data?.items ?? [];
  const a = items.filter((it) => it.abc_class === 'A').length;
  const b = items.filter((it) => it.abc_class === 'B').length;
  const c = items.filter((it) => it.abc_class === 'C').length;

  return (
    <Panel title="ABC analysis (Pareto)" subtitle="Distribuição valor por classe (80/15/5)">
      <div className="space-y-3">
        <button
          onClick={() => m.mutate()}
          disabled={m.isPending}
          className="rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
        >
          {m.isPending ? 'A classificar…' : 'Correr ABC analysis (sample)'}
        </button>
        {items.length > 0 && (
          <>
            <div className="grid grid-cols-3 gap-2">
              {[
                { label: 'Classe A', count: a, color: 'var(--red)' },
                { label: 'Classe B', count: b, color: 'var(--yellow)' },
                { label: 'Classe C', count: c, color: 'var(--green)' },
              ].map((cl) => (
                <div key={cl.label} className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
                  <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>
                    {cl.label}
                  </div>
                  <div className="text-lg font-semibold tabular-nums mt-1" style={{ color: cl.color }}>
                    {cl.count}
                  </div>
                </div>
              ))}
            </div>
            <div className="rounded-md border max-h-72 overflow-y-auto" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <table className="w-full text-xs">
                <thead style={{ color: 'var(--fg-3)' }}>
                  <tr className="text-left">
                    <th className="px-3 py-1.5">SKU</th>
                    <th className="px-3 py-1.5 text-right">Valor</th>
                    <th className="px-3 py-1.5 text-right">Cumul %</th>
                    <th className="px-3 py-1.5">Classe</th>
                  </tr>
                </thead>
                <tbody>
                  {items.slice(0, 30).map((it) => (
                    <tr key={it.sku_id} className="border-t" style={{ borderColor: 'var(--bd-1)' }}>
                      <td className="px-3 py-1.5 font-mono" style={{ color: 'var(--fg-1)' }}>{it.sku_id}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums" style={{ color: 'var(--fg-2)' }}>
                        €{(it.total_value ?? 0).toFixed(0)}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums" style={{ color: 'var(--fg-2)' }}>
                        {(it.cumulative_pct ?? 0).toFixed(1)}%
                      </td>
                      <td className="px-3 py-1.5">
                        <ZipToneBadge tone={it.abc_class === 'A' ? 'red' : it.abc_class === 'B' ? 'yellow' : 'green'} size="sm">
                          {it.abc_class}
                        </ZipToneBadge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 5. ShortageAlertsPanel
// ═══════════════════════════════════════════════════════════════════════════

export function ShortageAlertsPanel() {
  const q = useQuery({
    queryKey: supplyKeys.shortageAlerts(),
    queryFn: async () => {
      try {
        return await supplyAlertsApi.listShortageAlerts(20);
      } catch {
        return { items: [] as CopilotShortageAlert[] };
      }
    },
    staleTime: 60_000,
    retry: 0,
  });

  const items = ((q.data as { items?: CopilotShortageAlert[] } | undefined)?.items ?? []) as CopilotShortageAlert[];

  return (
    <Panel
      title="Shortage alerts"
      subtitle="ShortageDetector → CopilotAlert (scheduler hora a hora)"
      badge={items.length || '—'}
    >
      {q.isLoading ? (
        <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
      ) : items.length === 0 ? (
        <EmptyState
          title="Sem alertas de ruptura"
          hint="Detector escreve em CopilotAlert quando forecast cruza ROP. Ainda nenhum alerta gerado."
          size="sm"
        />
      ) : (
        <div className="space-y-1">
          {items.slice(0, 15).map((a, i) => (
            <div key={a.id ?? i} className="rounded-md border p-2 text-xs flex items-start gap-2" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <AlertTriangle size={12} style={{ color: 'var(--yellow)', flexShrink: 0, marginTop: 2 }} />
              <div className="flex-1 min-w-0">
                <div style={{ color: 'var(--fg-1)' }}>{a.message ?? '—'}</div>
                <div className="text-[10px] mt-0.5" style={{ color: 'var(--fg-3)' }}>
                  {a.created_at ? new Date(a.created_at).toLocaleString('pt-PT') : '—'} · {a.severity ?? '—'}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// SupplyDashboard — composição com 5 sub-tabs
// ═══════════════════════════════════════════════════════════════════════════

const SECTIONS = [
  { id: 'forecast', label: 'Forecast', icon: TrendingUp },
  { id: 'rop', label: 'ROP', icon: Package },
  { id: 'abc', label: 'ABC', icon: BarChart3 },
  { id: 'shortage', label: 'Shortages', icon: AlertTriangle },
  { id: 'seasonality', label: 'Sazonalidade', icon: Calendar },
] as const;
type SecId = (typeof SECTIONS)[number]['id'];

export function SupplyDashboard() {
  const [sec, setSec] = useState<SecId>('forecast');

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
          Q.18.ZIP.A.Onda9 — I. Plan/Supply
        </span>
      </div>
      {sec === 'forecast' && <ForecastPanel />}
      {sec === 'rop' && <RopPanel />}
      {sec === 'abc' && <AbcPanel />}
      {sec === 'shortage' && <ShortageAlertsPanel />}
      {sec === 'seasonality' && <SeasonalityPanel />}
    </div>
  );
}
