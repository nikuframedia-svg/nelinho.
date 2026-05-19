/**
 * RiskBadge — risco preditivo de defeito (0..1), pílula monoespaçada.
 *
 * Port fiel do atom `RiskBadge` do design NELO.html (atoms.jsx). Tom
 * calculado por thresholds: ≥25% vermelho · ≥15% laranja · ≥8% amarelo ·
 * <8% verde. Dados sempre por props — o caller passa o `value` vindo da
 * API (nunca hardcoded).
 *
 * Sprint Q.52.B.
 */

import type { ReactNode } from 'react';

export type RiskTone = 'red' | 'orange' | 'yellow' | 'green';

export interface RiskBadgeProps {
  /** Risco 0..1 (ex: 0.18 → "18%"). */
  value: number;
  size?: 'sm' | 'md';
  /** Mostrar a palavra "risco" antes da percentagem. */
  label?: boolean;
}

function toneFor(pct: number): RiskTone {
  if (pct >= 25) return 'red';
  if (pct >= 15) return 'orange';
  if (pct >= 8) return 'yellow';
  return 'green';
}

export function RiskBadge({
  value,
  size = 'sm',
  label = true,
}: RiskBadgeProps): ReactNode {
  const pct = Math.round(value * 100);
  const tone = toneFor(pct);
  return (
    <span
      title={`Risco preditivo de defeito: ${pct}%`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: size === 'sm' ? '1px 6px' : '2px 8px',
        fontSize: size === 'sm' ? 10 : 11,
        borderRadius: 999,
        background: `var(--${tone}-bg)`,
        border: `1px solid var(--${tone}-bd)`,
        color: `var(--${tone})`,
        fontFamily: "'Geist Mono', ui-monospace, monospace",
        fontWeight: 600,
        lineHeight: 1.4,
        whiteSpace: 'nowrap',
      }}
    >
      <span
        style={{
          width: 5,
          height: 5,
          borderRadius: '50%',
          background: `var(--${tone})`,
        }}
      />
      {label ? (
        <span
          style={{
            fontWeight: 500,
            fontSize: size === 'sm' ? 9 : 10,
            opacity: 0.8,
          }}
        >
          risco
        </span>
      ) : null}
      <span>{pct}%</span>
    </span>
  );
}
