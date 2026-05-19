/**
 * BarsMini — mini gráfico de barras verticais, sem libs externas.
 *
 * Port fiel do atom `BarsMini` do design NELO.html (atoms.jsx). Cada
 * barra escala em altura e opacidade pelo valor relativo ao máximo.
 * Etiquetas curtas por baixo. Dados sempre por props.
 *
 * Sprint Q.52.B.
 */

import type { ReactNode } from 'react';

export interface BarsMiniDatum {
  /** Etiqueta curta sob a barra (ex: "Seg", "K1"). */
  label: string;
  /** Valor numérico da barra. */
  value: number;
}

export interface BarsMiniProps {
  data: BarsMiniDatum[];
  /** Altura da área de barras em px. */
  height?: number;
  /** Cor base das barras (CSS var ou hex). */
  color?: string;
  /** Forçar o máximo (senão usa o maior valor de `data`). */
  maxOverride?: number;
}

export function BarsMini({
  data,
  height = 72,
  color = 'var(--accent)',
  maxOverride,
}: BarsMiniProps): ReactNode {
  if (data.length === 0) return null;
  const max =
    maxOverride ?? Math.max(...data.map((d) => d.value), 1);
  return (
    <div
      style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height }}
    >
      {data.map((d, i) => {
        const ratio = d.value / max;
        return (
          <div
            key={`${d.label}-${i}`}
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <div
              style={{
                width: '100%',
                height: ratio * height,
                background: color,
                opacity: 0.35 + ratio * 0.65,
                borderRadius: '3px 3px 0 0',
                transition: 'height 0.5s var(--ease-out)',
              }}
            />
            <span style={{ fontSize: 9.5, color: 'var(--fg-3)' }}>
              {d.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
