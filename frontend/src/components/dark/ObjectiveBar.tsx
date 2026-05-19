/**
 * ObjectiveBar — KPI com banda objetivo (low-high range).
 *
 * Port fiel do atom `ObjectiveBar` do design NELO.html (atoms.jsx).
 * Mostra uma barra com a banda alvo destacada a verde e um marcador na
 * posição do valor. Tom: dentro da banda → verde · abaixo → vermelho ·
 * acima → amarelo. Usado na página Direção (5 objetivos do CEO).
 *
 * Sprint Q.52.B.
 */

import type { ReactNode } from 'react';

export interface ObjectiveBarProps {
  /** Valor atual (vindo da API). */
  value: number;
  /** Limite inferior da banda objetivo. */
  low: number;
  /** Limite superior da banda objetivo. */
  high: number;
  /** Máximo da escala — default deriva de high*1.2 / value*1.1. */
  max?: number;
  /** Unidade mostrada nas etiquetas (ex: "%", "€", "/dia"). */
  unit?: string;
  /** Mostrar as etiquetas low/value/high por baixo. */
  showLabels?: boolean;
}

type ObjectiveTone = 'green' | 'red' | 'yellow';

export function ObjectiveBar({
  value,
  low,
  high,
  max,
  unit = '',
  showLabels = true,
}: ObjectiveBarProps): ReactNode {
  const m = max ?? Math.max(high * 1.2, value * 1.1);
  const lowPct = (low / m) * 100;
  const highPct = (high / m) * 100;
  const valPct = (value / m) * 100;
  const inBand = value >= low && value <= high;
  const tone: ObjectiveTone = inBand ? 'green' : value < low ? 'red' : 'yellow';

  return (
    <div>
      <div
        style={{
          position: 'relative',
          height: 8,
          background: 'var(--bg-3)',
          borderRadius: 4,
          overflow: 'hidden',
        }}
      >
        {/* Banda objetivo */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: `${lowPct}%`,
            width: `${highPct - lowPct}%`,
            background: 'var(--green-bg)',
            borderLeft: '1px dashed var(--green-bd)',
            borderRight: '1px dashed var(--green-bd)',
          }}
        />
        {/* Marcador do valor */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: `${Math.min(valPct, 100) - 1}%`,
            width: 2,
            background: `var(--${tone})`,
            borderRadius: 1,
          }}
        />
      </div>
      {showLabels ? (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: 4,
            fontSize: 9.5,
            color: 'var(--fg-3)',
          }}
        >
          <span className="tabular">
            {low}
            {unit}
          </span>
          <span
            className="tabular"
            style={{ color: `var(--${tone})`, fontWeight: 600 }}
          >
            {value}
            {unit}
          </span>
          <span className="tabular">
            {high}
            {unit}
          </span>
        </div>
      ) : null}
    </div>
  );
}
