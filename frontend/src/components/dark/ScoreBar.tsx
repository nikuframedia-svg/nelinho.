/**
 * ScoreBar — barra de pontuação 0-100, usada no ranking de gargalo.
 *
 * Port fiel do atom `ScoreBar` do design NELO.html (atoms.jsx). Tom por
 * thresholds: ≥80 vermelho · ≥60 laranja · ≥40 amarelo · <40 verde
 * (score alto = gargalo grave). Valor numérico monoespaçado à direita.
 *
 * Sprint Q.52.B.
 */

import type { ReactNode } from 'react';

export interface ScoreBarProps {
  /** Pontuação 0-100 (vinda da API). */
  score: number;
}

type ScoreTone = 'red' | 'orange' | 'yellow' | 'green';

function toneFor(score: number): ScoreTone {
  if (score >= 80) return 'red';
  if (score >= 60) return 'orange';
  if (score >= 40) return 'yellow';
  return 'green';
}

export function ScoreBar({ score }: ScoreBarProps): ReactNode {
  const tone = toneFor(score);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div
        style={{
          flex: 1,
          height: 5,
          background: 'var(--bg-3)',
          borderRadius: 3,
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <div
          style={{
            width: `${Math.max(0, Math.min(100, score))}%`,
            height: '100%',
            background: `var(--${tone})`,
            borderRadius: 3,
            transition: 'width 0.6s var(--ease-out)',
          }}
        />
      </div>
      <span
        className="mono tabular"
        style={{
          fontSize: 10.5,
          color: `var(--${tone})`,
          width: 28,
          textAlign: 'right',
          fontWeight: 600,
        }}
      >
        {Math.round(score)}
      </span>
    </div>
  );
}
