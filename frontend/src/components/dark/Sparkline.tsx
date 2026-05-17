/**
 * Sparkline — micro-chart SVG (~80×24px), sem libs externas.
 *
 * Usado em KPICard.spark para mostrar tendência de N pontos. Auto-escala
 * Y entre min e max dos dados; X linear pelo índice. Stroke fino, sem
 * eixos, sem labels — só a linha e (opcional) um dot no último ponto.
 *
 * Inspiração: pages-1.jsx do nelo (1).zip — KPI grid no Painel.
 * Sprint Q.18.ZIP.A.
 */

import type { ReactNode } from 'react';

export interface SparklineProps {
  /** N valores numéricos (qualquer escala). Vazio → renderiza nada. */
  points: number[];
  /** Cor stroke (default: currentColor). */
  color?: string;
  /** Largura SVG em px. */
  width?: number;
  /** Altura SVG em px. */
  height?: number;
  /** Mostrar dot no último ponto. */
  showLastDot?: boolean;
  /** Espessura da linha. */
  strokeWidth?: number;
  className?: string;
  ariaLabel?: string;
}

export function Sparkline({
  points,
  color = 'currentColor',
  width = 80,
  height = 24,
  showLastDot = true,
  strokeWidth = 1.5,
  className = '',
  ariaLabel = 'Tendência',
}: SparklineProps): ReactNode {
  if (!points || points.length === 0) {
    return null;
  }
  if (points.length === 1) {
    // Só um ponto — desenha uma linha horizontal pequena no meio
    const cy = height / 2;
    return (
      <svg
        width={width}
        height={height}
        className={className}
        role="img"
        aria-label={ariaLabel}
      >
        <line
          x1={2}
          x2={width - 2}
          y1={cy}
          y2={cy}
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          opacity={0.5}
        />
      </svg>
    );
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1; // evita divisão por zero quando todos os valores são iguais
  const padX = 2;
  const padY = 2;
  const innerW = width - padX * 2;
  const innerH = height - padY * 2;

  const stepX = innerW / (points.length - 1);
  const coords = points.map((v, i) => {
    const x = padX + i * stepX;
    // Y inverte porque SVG origin é top-left
    const y = padY + innerH - ((v - min) / range) * innerH;
    return { x, y };
  });

  const pathD = coords
    .map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x.toFixed(2)} ${c.y.toFixed(2)}`)
    .join(' ');

  const last = coords[coords.length - 1];

  return (
    <svg
      width={width}
      height={height}
      className={className}
      role="img"
      aria-label={ariaLabel}
    >
      <path
        d={pathD}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {showLastDot ? (
        <circle cx={last.x} cy={last.y} r={2} fill={color} />
      ) : null}
    </svg>
  );
}
