/**
 * OEERing — anel SVG de progresso (OEE / disponibilidade / qualidade).
 *
 * Geometria fiel ao design NELO.html: círculo de raio r=36, perímetro
 * 2·π·r, o arco preenchido usa `strokeDasharray = circ` +
 * `strokeDashoffset = circ·(1 - pct)` e o grupo roda −90° para começar
 * no topo. Tom por thresholds: ≥85 verde · ≥70 amarelo · <70 vermelho.
 *
 * O valor central e a etiqueta vêm por props (ZERO MOCKS).
 *
 * Sprint Q.52.B.
 */

import type { ReactNode } from 'react';

export interface OEERingProps {
  /** Percentagem 0-100 (vinda da API). */
  value: number;
  /** Etiqueta curta sob o valor (ex: "OEE", "Disponib."). */
  label?: string;
  /** Diâmetro total do SVG em px. */
  size?: number;
  /** Espessura do anel em px. */
  thickness?: number;
  /** Forçar cor (senão deriva do valor). */
  color?: string;
}

type RingTone = 'green' | 'yellow' | 'red';

function toneFor(value: number): RingTone {
  if (value >= 85) return 'green';
  if (value >= 70) return 'yellow';
  return 'red';
}

export function OEERing({
  value,
  label,
  size = 96,
  thickness = 8,
  color,
}: OEERingProps): ReactNode {
  const pct = Math.max(0, Math.min(100, value));
  const r = 36;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct / 100);
  const stroke = color ?? `var(--${toneFor(pct)})`;
  // viewBox fixo 0 0 80 80 (centro 40,40, r=36) — size só escala o SVG.
  const vb = 80;

  return (
    <div
      style={{
        position: 'relative',
        width: size,
        height: size,
        display: 'inline-block',
      }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${vb} ${vb}`}>
        <g transform={`rotate(-90 ${vb / 2} ${vb / 2})`}>
          <circle
            cx={vb / 2}
            cy={vb / 2}
            r={r}
            fill="none"
            stroke="var(--bg-3)"
            strokeWidth={thickness}
          />
          <circle
            cx={vb / 2}
            cy={vb / 2}
            r={r}
            fill="none"
            stroke={stroke}
            strokeWidth={thickness}
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 0.8s var(--ease-out)' }}
          />
        </g>
      </svg>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <span
          className="display tabular"
          style={{
            fontSize: size * 0.26,
            fontWeight: 600,
            color: 'var(--fg-0)',
            lineHeight: 1,
            letterSpacing: '-0.02em',
          }}
        >
          {Math.round(pct)}
        </span>
        {label ? (
          <span
            style={{
              fontSize: size * 0.11,
              color: 'var(--fg-3)',
              marginTop: 2,
              textTransform: 'uppercase',
              letterSpacing: 0.4,
              fontWeight: 500,
            }}
          >
            {label}
          </span>
        ) : null}
      </div>
    </div>
  );
}
