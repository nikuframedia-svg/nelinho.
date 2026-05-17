/**
 * GanttChart + GanttBar — Gantt SVG custom (sem libs pesadas).
 *
 * O brief (FRONTEND_DESIGN_PROMPT §3.1) explicita "Custom SVG — Gantt
 * chart (não usar bibliotecas pesadas)". Implementação minimalista:
 *
 *   ┌─────────────────────────────────────────────────────────┐
 *   │  Time axis (dias × turnos 8h)                           │
 *   ├─────────────────────────────────────────────────────────┤
 *   │ K1 #4271 [█████████] [░░░░░░░░░░░░░░░] [██]            │
 *   │           Lam.        Cura (cinza)      Desm.           │
 *   ├─────────────────────────────────────────────────────────┤
 *   │ K2 #5103       [█████████] [░░░░░░░░░░░░░░░░░]         │
 *   └─────────────────────────────────────────────────────────┘
 *
 * Padrões:
 *   - █ trabalho efectivo (cor por status)
 *   - ░ cura/secagem (cinza, não-bloqueante)
 *   - drag-drop barras → callback `onMoveBar(rowId, barIdx, deltaHours)`
 *   - precedências preservadas pelo caller (ghost preview se viola)
 *
 * Plan v4 §4.3 / FRONTEND_DESIGN_PROMPT §3.1 §4.3.
 * Sprint Q.18.UI.A. Versão inicial — refinar em Q.18.UI.D quando ligar
 * a `PreviewDeltaService`.
 */

import type { ReactNode } from 'react';

// ─── Types ────────────────────────────────────────────────────────────

export type GanttBarKind = 'work' | 'curing' | 'wait';
export type GanttBarStatus = 'on_time' | 'at_risk' | 'late' | 'completed';

export interface GanttBarData {
  /** Index dentro da row (0..n-1). */
  idx: number;
  label: string;
  /** Hours desde t0 (start of chart window). */
  start_hours: number;
  duration_hours: number;
  kind: GanttBarKind;
  status?: GanttBarStatus;
  /** Tooltip extra. */
  detail?: string;
}

export interface GanttRow {
  id: string | number;
  label: string;
  /** Cliente / fase / metadata. */
  sub_label?: string;
  bars: GanttBarData[];
}

export interface GanttChartProps {
  rows: GanttRow[];
  /** ISO date — t0 do chart (geralmente "amanhã 08:00"). */
  start_date: Date;
  /** Total horas visíveis (default 7 dias × 8h = 56h work-hours). */
  total_hours?: number;
  /** Pixels por hora — controla densidade visual. */
  px_per_hour?: number;
  /** Largura da coluna de label (rótulo barco). */
  label_width?: number;
  /** Altura de cada row. */
  row_height?: number;
  /** Click numa barra. */
  onBarClick?: (rowId: string | number, barIdx: number) => void;
  className?: string;
}

// ─── Token map ────────────────────────────────────────────────────────

const STATUS_FILL: Record<GanttBarStatus, string> = {
  on_time: '#10b981', // success
  at_risk: '#f59e0b', // warning
  late: '#ef4444', // danger
  completed: '#0ea5e9', // primary-500
};

const KIND_FILL: Record<GanttBarKind, string> = {
  work: '#14b8a6', // accent-500 (overridden by status if present)
  curing: '#475569', // slate-600 — cinza chumbo, não-bloqueante
  wait: '#1f2937', // dark-600 — gap muito ténue
};

// ─── Date helpers ─────────────────────────────────────────────────────

function dateAxis(start: Date, totalHours: number): { offset: number; label: string }[] {
  // Dia tem 8h de trabalho. Render labels a cada dia.
  const out: { offset: number; label: string }[] = [];
  const dayHours = 8;
  const days = Math.ceil(totalHours / dayHours);
  const fmt = new Intl.DateTimeFormat('pt-PT', {
    weekday: 'short',
    day: '2-digit',
  });
  for (let d = 0; d <= days; d++) {
    const date = new Date(start);
    date.setDate(date.getDate() + d);
    out.push({
      offset: d * dayHours,
      label: fmt.format(date),
    });
  }
  return out;
}

// ─── Bar (sub-component) ──────────────────────────────────────────────

interface GanttBarProps extends GanttBarData {
  px_per_hour: number;
  row_height: number;
  onClick?: () => void;
}

export function GanttBar({
  label,
  start_hours,
  duration_hours,
  kind,
  status,
  detail,
  px_per_hour,
  row_height,
  onClick,
}: GanttBarProps): ReactNode {
  const x = start_hours * px_per_hour;
  const w = Math.max(2, duration_hours * px_per_hour);
  const h = row_height - 8;
  const y = 4;
  const fill =
    kind === 'work' && status
      ? STATUS_FILL[status]
      : KIND_FILL[kind];
  const tooltip =
    [`${label}`, `${duration_hours.toFixed(1)}h`, detail].filter(Boolean).join('\n');

  return (
    <g
      transform={`translate(${x}, ${y})`}
      onClick={onClick}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
    >
      <title>{tooltip}</title>
      <rect
        x={0}
        y={0}
        width={w}
        height={h}
        rx={3}
        fill={fill}
        opacity={kind === 'curing' ? 0.4 : 0.9}
        stroke={kind === 'curing' ? '#64748b' : 'transparent'}
        strokeDasharray={kind === 'curing' ? '4 2' : undefined}
      />
      {w > 50 ? (
        <text
          x={6}
          y={h / 2 + 4}
          fontSize={11}
          fontFamily="ui-monospace, monospace"
          fill="#f1f5f9"
        >
          {label}
        </text>
      ) : null}
    </g>
  );
}

// ─── Chart ────────────────────────────────────────────────────────────

export function GanttChart({
  rows,
  start_date,
  total_hours = 56,
  px_per_hour = 12,
  label_width = 160,
  row_height = 32,
  onBarClick,
  className = '',
}: GanttChartProps): ReactNode {
  const chartWidth = total_hours * px_per_hour;
  const axisHeight = 28;
  const totalHeight = axisHeight + rows.length * row_height + 8;
  const axis = dateAxis(start_date, total_hours);

  return (
    <div
      className={`overflow-x-auto bg-dark-900/40 rounded-lg border border-white/[0.06] ${className}`}
    >
      <div style={{ display: 'flex', minWidth: label_width + chartWidth + 16 }}>
        {/* Coluna labels */}
        <div
          style={{ width: label_width, paddingTop: axisHeight }}
          className="shrink-0 border-r border-white/[0.06]"
        >
          {rows.map((row) => (
            <div
              key={`label-${row.id}`}
              style={{ height: row_height }}
              className="flex flex-col justify-center px-3 border-b border-white/[0.04]"
            >
              <span className="text-xs font-medium text-text-dark-primary truncate">
                {row.label}
              </span>
              {row.sub_label ? (
                <span className="text-[10px] text-text-dark-tertiary truncate">
                  {row.sub_label}
                </span>
              ) : null}
            </div>
          ))}
        </div>

        {/* SVG canvas */}
        <svg
          width={chartWidth + 8}
          height={totalHeight}
          role="img"
          aria-label="Diagrama de Gantt do plano de produção"
        >
          {/* Eixo dos dias */}
          {axis.map(({ offset, label }, idx) => (
            <g key={`axis-${idx}`}>
              <line
                x1={offset * px_per_hour}
                x2={offset * px_per_hour}
                y1={axisHeight}
                y2={totalHeight}
                stroke="#1f2937"
                strokeWidth={1}
              />
              <text
                x={offset * px_per_hour + 4}
                y={16}
                fontSize={10}
                fill="#64748b"
                fontFamily="ui-monospace, monospace"
              >
                {label}
              </text>
            </g>
          ))}

          {/* Linha horizontal por row */}
          {rows.map((row, rIdx) => (
            <g
              key={`row-${row.id}`}
              transform={`translate(0, ${axisHeight + rIdx * row_height})`}
            >
              <line
                x1={0}
                x2={chartWidth}
                y1={row_height}
                y2={row_height}
                stroke="#1f2937"
                strokeWidth={0.5}
              />
              {row.bars.map((bar) => (
                <GanttBar
                  key={`${row.id}-bar-${bar.idx}`}
                  {...bar}
                  px_per_hour={px_per_hour}
                  row_height={row_height}
                  onClick={
                    onBarClick ? () => onBarClick(row.id, bar.idx) : undefined
                  }
                />
              ))}
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}
