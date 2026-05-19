/**
 * CeoBits — primitivas locais da página Direção (Q.52.E).
 *
 * Card + SectionHeader + EuroBandChart + MarginRow. Port fiel da
 * geometria do design NELO.html (page-ceo.jsx). Dados sempre por props
 * — ZERO MOCKS. As primitivas partilhadas (KPIBig, ObjectiveBar) vêm de
 * components/dark/.
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
}: {
  value: number;
  max?: number;
  color?: string;
  height?: number;
}): ReactNode {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
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
  );
}

// ─── EuroBandChart — €/dia com banda objetivo 30–35K ─────────────────────

export interface EuroBandChartProps {
  /** Série diária em € (não K). */
  series: number[];
  /** Banda alvo inferior/superior em € (default 30000 / 35000). */
  targetMin?: number;
  targetMax?: number;
}

export function EuroBandChart({
  series,
  targetMin = 30000,
  targetMax = 35000,
}: EuroBandChartProps): ReactNode {
  if (series.length < 2) {
    return (
      <div
        style={{
          height: 200,
          display: 'grid',
          placeItems: 'center',
          color: 'var(--fg-3)',
          fontSize: 12,
        }}
      >
        Sem série suficiente para o gráfico.
      </div>
    );
  }
  // Escala em milhares para o viewBox.
  const k = series.map((v) => v / 1000);
  const tMinK = targetMin / 1000;
  const tMaxK = targetMax / 1000;
  const dataMax = Math.max(...k, tMaxK);
  const dataMin = Math.min(...k, tMinK);
  const max = Math.ceil(dataMax * 1.08);
  const min = Math.floor(dataMin * 0.92);
  const W = 600;
  const H = 200;
  const yFor = (vk: number): number =>
    H - ((vk - min) / (max - min || 1)) * (H - 40) - 20;
  const pts = k.map(
    (vk, i) =>
      [(i / (k.length - 1)) * W, yFor(vk)] as [number, number],
  );
  const d = pts
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0]},${p[1]}`)
    .join(' ');
  const dArea = `${d} L${W},${H} L0,${H} Z`;
  const bandTop = yFor(tMaxK);
  const bandBottom = yFor(tMinK);

  return (
    <div style={{ height: H, position: 'relative', marginTop: 14 }}>
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
      >
        <rect
          x={0}
          y={bandTop}
          width={W}
          height={bandBottom - bandTop}
          fill="var(--green)"
          opacity={0.08}
        />
        <line
          x1={0}
          y1={bandTop}
          x2={W}
          y2={bandTop}
          stroke="var(--green)"
          strokeDasharray="3 3"
          strokeWidth={1}
          opacity={0.4}
        />
        <line
          x1={0}
          y1={bandBottom}
          x2={W}
          y2={bandBottom}
          stroke="var(--green)"
          strokeDasharray="3 3"
          strokeWidth={1}
          opacity={0.4}
        />
        <path d={dArea} fill="var(--accent)" fillOpacity={0.1} />
        <path d={d} fill="none" stroke="var(--accent)" strokeWidth={1.8} />
        {pts.map((p, i) => (
          <circle key={i} cx={p[0]} cy={p[1]} r={2.5} fill="var(--accent)" />
        ))}
      </svg>
      <div
        style={{
          position: 'absolute',
          top: bandTop - 6,
          left: 8,
          fontSize: 10,
          color: 'var(--green)',
        }}
      >
        €{Math.round(tMaxK)}K
      </div>
      <div
        style={{
          position: 'absolute',
          top: bandBottom - 6,
          left: 8,
          fontSize: 10,
          color: 'var(--green)',
        }}
      >
        €{Math.round(tMinK)}K
      </div>
    </div>
  );
}

// ─── MarginRow — linha de margem por país/agente ─────────────────────────

export interface MarginRowProps {
  label: string;
  margin: number;
  revenue: number;
  /** Mostrar a etiqueta como pill (país) ou texto simples (agente). */
  asPill?: boolean;
  last?: boolean;
}

export function MarginRow({
  label,
  margin,
  revenue,
  asPill = false,
  last = false,
}: MarginRowProps): ReactNode {
  const tone =
    margin >= 50 ? 'green' : margin >= 47 ? 'yellow' : 'orange';
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: asPill
          ? '44px 1fr 56px 60px'
          : '1fr 80px 56px 60px',
        alignItems: 'center',
        gap: 10,
        padding: '7px 0',
        borderBottom: last ? 'none' : '1px solid var(--bd-1)',
        fontSize: 12,
      }}
    >
      {asPill ? (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1px 7px',
            fontSize: 10.5,
            height: 18,
            borderRadius: 999,
            color: 'var(--fg-1)',
            background: 'var(--bg-3)',
            border: '1px solid var(--bd-1)',
          }}
        >
          {label}
        </span>
      ) : (
        <span
          style={{
            color: 'var(--fg-1)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {label}
        </span>
      )}
      <MiniBar value={margin} max={60} color={`var(--${tone})`} height={3} />
      <span
        className="tabular"
        style={{ color: `var(--${tone})`, fontWeight: 600, textAlign: 'right' }}
      >
        {margin.toFixed(0)}%
      </span>
      <span
        className="tabular"
        style={{ color: 'var(--fg-2)', textAlign: 'right' }}
      >
        €{(revenue / 1000).toFixed(0)}K
      </span>
    </div>
  );
}
