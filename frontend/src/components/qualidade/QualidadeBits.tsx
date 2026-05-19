/**
 * QualidadeBits — primitivas locais da página Qualidade (Q.52.I).
 *
 * Card + SectionHeader + MiniBar + HullHeatmap. Port fiel da geometria
 * do design NELO.html (page-qualidade.jsx). Dados sempre por props —
 * ZERO MOCKS. O HullHeatmap só renderiza com zonas reais; sem fonte de
 * defeitos por zona a página mostra um empty state honesto.
 */

import type { CSSProperties, ReactNode } from 'react';

// ─── Card ────────────────────────────────────────────────────────────────

export function Card({
  children,
  style,
  padding = 18,
}: {
  children: ReactNode;
  style?: CSSProperties;
  padding?: number;
}): ReactNode {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        padding,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ─── SectionHeader ───────────────────────────────────────────────────────

export function SectionHeader({
  icon,
  title,
  subtitle,
  action,
}: {
  icon?: ReactNode;
  title: string;
  subtitle?: string;
  action?: ReactNode;
}): ReactNode {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 12,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
        {icon ? <span style={{ color: 'var(--fg-2)' }}>{icon}</span> : null}
        <div>
          <h2
            style={{
              margin: 0,
              fontSize: 14,
              fontWeight: 600,
              color: 'var(--fg-0)',
              letterSpacing: '-0.1px',
            }}
          >
            {title}
          </h2>
          {subtitle ? (
            <div style={{ fontSize: 11.5, color: 'var(--fg-2)', marginTop: 2 }}>
              {subtitle}
            </div>
          ) : null}
        </div>
      </div>
      {action}
    </div>
  );
}

// ─── MiniBar ─────────────────────────────────────────────────────────────

export function MiniBar({
  value,
  max = 100,
  color = 'var(--accent)',
  height = 4,
  label,
}: {
  value: number;
  max?: number;
  color?: string;
  height?: number;
  label?: string;
}): ReactNode {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div>
      <div
        style={{
          height,
          background: 'var(--bg-3)',
          borderRadius: 999,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            background: color,
            borderRadius: 999,
            transition: 'width 0.6s var(--ease-out)',
          }}
        />
      </div>
      {label ? (
        <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 4 }}>
          {label}
        </div>
      ) : null}
    </div>
  );
}

// ─── HullHeatmap — silhueta SVG do casco com zonas de defeito ───────────

export interface HullZone {
  id: string;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
  count: number;
}

export interface HullHeatmapProps {
  /** Zonas com contagem de defeitos (da API real). */
  zones: HullZone[];
}

function zoneTone(intensity: number): string {
  if (intensity > 0.7) return 'red';
  if (intensity > 0.4) return 'orange';
  if (intensity > 0.2) return 'yellow';
  return 'green';
}

export function HullHeatmap({ zones }: HullHeatmapProps): ReactNode {
  const maxCount = Math.max(1, ...zones.map((z) => z.count));
  return (
    <div>
      <svg viewBox="0 0 400 86" style={{ width: '100%', height: 220 }}>
        <defs>
          <linearGradient id="hull-grad" x1="0%" x2="100%">
            <stop offset="0%" stopColor="var(--bg-2)" />
            <stop offset="100%" stopColor="var(--bg-3)" />
          </linearGradient>
        </defs>
        {/* Silhueta do casco */}
        <path
          d="M 12 44 Q 30 28 80 24 L 320 24 Q 370 28 388 44 Q 370 60 320 64 L 80 64 Q 30 60 12 44 Z"
          fill="url(#hull-grad)"
          stroke="var(--bd-2)"
          strokeWidth="0.5"
        />
        {zones.map((z) => {
          const intensity = z.count / maxCount;
          const tone = zoneTone(intensity);
          return (
            <g key={z.id}>
              <rect
                x={z.x}
                y={z.y}
                width={z.w}
                height={z.h}
                fill={`var(--${tone})`}
                fillOpacity={0.1 + intensity * 0.35}
                stroke={`var(--${tone})`}
                strokeOpacity={0.5}
                strokeWidth="0.6"
                rx="3"
              />
              <text
                x={z.x + z.w / 2}
                y={z.y + z.h / 2 + 1}
                textAnchor="middle"
                fontSize="6"
                fill="var(--fg-0)"
                fontWeight="500"
              >
                {z.label}
              </text>
              <text
                x={z.x + z.w / 2}
                y={z.y + z.h / 2 + 9}
                textAnchor="middle"
                fontSize="5"
                fill={`var(--${tone})`}
                fontWeight="600"
              >
                {z.count}
              </text>
            </g>
          );
        })}
        <text x="12" y="80" fontSize="5" fill="var(--fg-3)">
          ← proa
        </text>
        <text
          x="388"
          y="80"
          textAnchor="end"
          fontSize="5"
          fill="var(--fg-3)"
        >
          popa →
        </text>
      </svg>
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          gap: 14,
          marginTop: 8,
          fontSize: 10.5,
          color: 'var(--fg-3)',
        }}
      >
        {[
          { tone: 'green', label: 'Baixa', op: 0.3 },
          { tone: 'yellow', label: 'Média', op: 0.4 },
          { tone: 'orange', label: 'Alta', op: 0.5 },
          { tone: 'red', label: 'Crítica', op: 0.6 },
        ].map((l) => (
          <span key={l.tone}>
            <span
              style={{
                display: 'inline-block',
                width: 10,
                height: 10,
                background: `var(--${l.tone})`,
                opacity: l.op,
                borderRadius: 2,
                marginRight: 5,
                verticalAlign: 'middle',
              }}
            />
            {l.label}
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── Banner — faixa de aviso/info colorida ──────────────────────────────

export function Banner({
  tone,
  children,
}: {
  tone: 'orange' | 'yellow' | 'accent' | 'green';
  children: ReactNode;
}): ReactNode {
  return (
    <div
      style={{
        padding: 14,
        background: `var(--${tone}-bg)`,
        border: `1px solid var(--${tone}-bd)`,
        borderRadius: 'var(--r-md)',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}
    >
      {children}
    </div>
  );
}
