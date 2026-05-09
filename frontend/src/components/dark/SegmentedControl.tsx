/**
 * SegmentedControl — radio-button inline para alternar entre 2-4 vistas.
 *
 * Diferente de Tabs: SegmentedControl é mais compacto (sem underline,
 * sem count badges), usado para alternar VISTAS DA MESMA PÁGINA (e.g.
 * "Por fase / Gantt / Tabela" na Produção). Inspirado no nelo zip
 * pages-1.jsx:283-287.
 *
 * Sprint Q.18.ZIP.A.
 */

import type { ReactNode } from 'react';

export interface SegmentOption {
  id: string;
  label: string;
  icon?: ReactNode;
}

export interface SegmentedControlProps {
  options: SegmentOption[];
  value: string;
  onChange: (id: string) => void;
  size?: 'sm' | 'md';
  className?: string;
  ariaLabel?: string;
}

const SIZE_PADDING = {
  sm: 'px-2.5 py-1 text-xs',
  md: 'px-3 py-1.5 text-sm',
};

export function SegmentedControl({
  options,
  value,
  onChange,
  size = 'md',
  className = '',
  ariaLabel = 'Alternar vista',
}: SegmentedControlProps): ReactNode {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={`
        inline-flex items-center gap-0.5 p-0.5
        bg-dark-800/60 border border-white/[0.06] rounded-md
        ${className}
      `}
    >
      {options.map((opt) => {
        const active = opt.id === value;
        return (
          <button
            key={opt.id}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.id)}
            className={`
              inline-flex items-center gap-1.5 rounded
              font-medium transition-colors duration-150
              ${SIZE_PADDING[size]}
              ${active
                ? 'bg-accent-500/20 text-accent-400'
                : 'text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary'
              }
            `}
          >
            {opt.icon ? <span className="shrink-0">{opt.icon}</span> : null}
            <span>{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
