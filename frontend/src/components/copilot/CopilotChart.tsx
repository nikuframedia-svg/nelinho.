/**
 * CopilotChart — renderiza um `ChartSpec` emitido pelo copiloto.
 *
 * Q.53.L. O backend (Q.53.F) acrescentou `charts: ChartSpec[]` à
 * `CopilotResponse`: o LLM emite blocos `<chart>…</chart>` com dados
 * REAIS já recolhidos no contexto. O backend não desenha nada — manda
 * a spec e o frontend renderiza-a aqui, reutilizando `components/charts`
 * (recharts) sem inventar números.
 *
 * Tipos suportados (Literal do schema): line · bar · gauge · scatter ·
 * heatmap. `data` é flexível ({x,y,…} / {value,min,max} / {x,y,value});
 * adaptamos cada forma ao componente certo. Se a `data` vier vazia ou
 * mal formada, mostramos um aviso honesto — nunca um gráfico falso.
 */

import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
} from 'recharts';
import { BarChart3 } from 'lucide-react';
import { LineChart, BarChart, DonutChart } from '../charts';
import type { ChartDataPoint } from '../../types';

// ─── Tipo da spec (espelha src/copilot/schemas.py · ChartSpec) ──────────────

export interface ChartSpec {
  type: 'line' | 'bar' | 'gauge' | 'scatter' | 'heatmap';
  title: string;
  data: Array<Record<string, unknown>>;
  config?: Record<string, unknown>;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function num(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function str(value: unknown): string | null {
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  return null;
}

/** Converte pontos {x,y} do copiloto para o ChartDataPoint {name,value}. */
function toXYPoints(data: Array<Record<string, unknown>>): ChartDataPoint[] {
  return data
    .map((row) => {
      const name = str(row.x ?? row.name ?? row.label ?? row.categoria);
      const value = num(row.y ?? row.value ?? row.valor);
      if (name === null || value === null) return null;
      return { name, value } as ChartDataPoint;
    })
    .filter((p): p is ChartDataPoint => p !== null);
}

const AXIS_TICK = { fontSize: 11, fill: '#64748b' };
const TOOLTIP_STYLE = {
  backgroundColor: 'rgba(17, 24, 39, 0.95)',
  border: '1px solid rgba(255, 255, 255, 0.1)',
  borderRadius: '12px',
  padding: '10px 14px',
} as const;

// ─── Componente ──────────────────────────────────────────────────────────────

export function CopilotChart({ spec }: { spec: ChartSpec }) {
  const config = spec.config ?? {};
  const xLabel = str(config.x_label) ?? undefined;
  const yLabel = str(config.y_label) ?? undefined;
  const unit = str(config.unit) ?? '';

  let body: React.ReactNode;
  let invalid = false;

  if (spec.type === 'line' || spec.type === 'bar') {
    const points = toXYPoints(spec.data);
    if (points.length === 0) {
      invalid = true;
    } else if (spec.type === 'line') {
      body = <LineChart data={points} height={200} showGrid showAxis />;
    } else {
      body = <BarChart data={points} height={200} showGrid showAxis />;
    }
  } else if (spec.type === 'gauge') {
    // gauge: [{value, min, max}] — um único ponto.
    const point = spec.data[0] ?? {};
    const value = num(point.value);
    const min = num(point.min) ?? 0;
    const max = num(point.max) ?? 100;
    if (value === null || max <= min) {
      invalid = true;
    } else {
      const pct = Math.max(0, Math.min(1, (value - min) / (max - min)));
      const donut: ChartDataPoint[] = [
        { name: 'valor', value: pct },
        { name: 'resto', value: 1 - pct },
      ];
      body = (
        <DonutChart
          data={donut}
          height={200}
          colors={['#14b8a6', 'rgba(255,255,255,0.06)']}
          centerValue={`${value}${unit}`}
          centerLabel={`${min}–${max}${unit}`}
        />
      );
    }
  } else if (spec.type === 'scatter') {
    // scatter: [{x, y, ...}] — pares numéricos.
    const points = spec.data
      .map((row) => {
        const x = num(row.x);
        const y = num(row.y);
        if (x === null || y === null) return null;
        const label = str(row.label ?? row.name);
        return label !== null ? { x, y, label } : { x, y };
      })
      .filter((p): p is { x: number; y: number; label?: string } => p !== null);
    if (points.length === 0) {
      invalid = true;
    } else {
      body = (
        <ResponsiveContainer width="100%" height={200}>
          <ScatterChart margin={{ top: 8, right: 8, left: -16, bottom: 4 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" />
            <XAxis
              type="number"
              dataKey="x"
              name={xLabel ?? 'x'}
              axisLine={false}
              tickLine={false}
              tick={AXIS_TICK}
            />
            <YAxis
              type="number"
              dataKey="y"
              name={yLabel ?? 'y'}
              axisLine={false}
              tickLine={false}
              tick={AXIS_TICK}
              width={45}
            />
            <ZAxis range={[60, 60]} />
            <Tooltip
              cursor={{ strokeDasharray: '3 3' }}
              contentStyle={TOOLTIP_STYLE}
              labelStyle={{ color: '#94a3b8', fontSize: 11 }}
              itemStyle={{ color: '#f1f5f9', fontSize: 12 }}
            />
            <Scatter data={points} fill="#14b8a6" />
          </ScatterChart>
        </ResponsiveContainer>
      );
    }
  } else if (spec.type === 'heatmap') {
    // heatmap: [{x, y, value}] — grelha. Construímos linhas/colunas.
    const cells = spec.data
      .map((row) => {
        const x = str(row.x);
        const y = str(row.y);
        const value = num(row.value);
        return x !== null && y !== null && value !== null
          ? { x, y, value }
          : null;
      })
      .filter((c): c is { x: string; y: string; value: number } => c !== null);
    if (cells.length === 0) {
      invalid = true;
    } else {
      body = <HeatmapGrid cells={cells} unit={unit} />;
    }
  } else {
    invalid = true;
  }

  return (
    <div className="rounded-md border border-bd-1 bg-bg-2 px-3 py-2.5">
      <div className="flex items-center gap-1.5 mb-2">
        <BarChart3 size={11} className="text-accent" />
        <span className="text-[11px] font-medium text-fg-1">{spec.title}</span>
      </div>
      {invalid ? (
        <p className="text-[11px] text-fg-3 py-3 text-center">
          Gráfico {spec.type} sem dados utilizáveis — o copiloto não o
          conseguiu preencher com factos reais.
        </p>
      ) : (
        <>
          {body}
          {(xLabel || yLabel) && (
            <div className="flex justify-between mt-1 text-[10px] text-fg-4">
              <span>{xLabel ?? ''}</span>
              <span>{yLabel ?? ''}</span>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── Heatmap simples (grelha x×y com escala de cor) ─────────────────────────

function HeatmapGrid({
  cells,
  unit,
}: {
  cells: Array<{ x: string; y: string; value: number }>;
  unit: string;
}) {
  const xs = Array.from(new Set(cells.map((c) => c.x)));
  const ys = Array.from(new Set(cells.map((c) => c.y)));
  const lookup = new Map(cells.map((c) => [`${c.x}|${c.y}`, c.value]));
  const values = cells.map((c) => c.value);
  const min = Math.min(...values);
  const max = Math.max(...values);

  const color = (value: number): string => {
    const ratio = max > min ? (value - min) / (max - min) : 0.5;
    // teal de baixa→alta opacidade
    return `rgba(20, 184, 166, ${0.15 + ratio * 0.7})`;
  };

  return (
    <div className="overflow-x-auto py-1">
      <table style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th />
            {xs.map((x) => (
              <th
                key={x}
                className="text-[9.5px] text-fg-3 font-medium px-1 pb-1"
                style={{ whiteSpace: 'nowrap' }}
              >
                {x}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ys.map((y) => (
            <tr key={y}>
              <td
                className="text-[9.5px] text-fg-2 pr-2 text-right"
                style={{ whiteSpace: 'nowrap' }}
              >
                {y}
              </td>
              {xs.map((x) => {
                const value = lookup.get(`${x}|${y}`);
                return (
                  <td
                    key={x}
                    title={
                      value !== undefined
                        ? `${x} · ${y}: ${value}${unit}`
                        : `${x} · ${y}: sem dados`
                    }
                    style={{
                      width: 34,
                      height: 28,
                      textAlign: 'center',
                      background:
                        value !== undefined
                          ? color(value)
                          : 'rgba(255,255,255,0.03)',
                      border: '1px solid var(--bd-1)',
                      fontSize: 9.5,
                      color: 'var(--fg-1)',
                      fontFamily: 'monospace',
                    }}
                  >
                    {value !== undefined ? value : '—'}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
