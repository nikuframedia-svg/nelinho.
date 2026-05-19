/**
 * Segmented — controlo segmentado Apple-like (pílula).
 *
 * Port fiel do atom `Segmented` do design NELO.html (atoms.jsx):
 * contentor pílula em `--bg-2`, segmento ativo em `--bg-4`. Distinto do
 * `SegmentedControl` legacy (Tailwind, raio quadrado) — este bate certo
 * com a geometria do protótipo NELO.
 *
 * Genérico no tipo do valor para alternar vistas type-safe.
 *
 * Sprint Q.52.B.
 */

import type { ReactNode } from 'react';

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  icon?: ReactNode;
}

export interface SegmentedProps<T extends string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  size?: 'sm' | 'md';
  ariaLabel?: string;
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  size = 'md',
  ariaLabel = 'Alternar vista',
}: SegmentedProps<T>): ReactNode {
  const h = size === 'sm' ? 26 : 32;
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      style={{
        display: 'inline-flex',
        background: 'var(--bg-2)',
        border: '1px solid var(--bd-1)',
        borderRadius: h / 2,
        padding: 2,
        gap: 2,
      }}
    >
      {options.map((o) => {
        const active = value === o.value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            style={{
              padding: '0 12px',
              height: h - 4,
              background: active ? 'var(--bg-4)' : 'transparent',
              color: active ? 'var(--fg-0)' : 'var(--fg-2)',
              border: 'none',
              borderRadius: (h - 4) / 2,
              fontSize: 11.5,
              fontWeight: active ? 600 : 500,
              cursor: 'pointer',
              transition: 'background 0.18s, color 0.18s',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
            }}
          >
            {o.icon}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
