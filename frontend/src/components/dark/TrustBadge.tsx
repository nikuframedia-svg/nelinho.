/**
 * TrustBadge — letra A/B/C/D/F colorida indicando qualidade/confiança.
 *
 * Diferente do TrustIndex de DQAPage (esse é numérico 0-1). Esta é
 * a representação visual rápida (1 letra) para mostrar inline no
 * KPICard, ao lado de fontes de dados (SAP/OPC-UA/RFID), etc.
 *
 * Mapeamento para grade letra (alinhado com Trust Index v2 §4.5):
 *   ≥ 0.90 → A   excelente
 *   ≥ 0.80 → B   bom
 *   ≥ 0.70 → C   aceitável
 *   ≥ 0.60 → D   degradado
 *    < 0.60 → F  inaceitável
 *
 * Inspiração: pages-1.jsx do nelo (1).zip — `trust="A"` no KPI grid.
 * Sprint Q.18.ZIP.A.
 */

import type { ReactNode } from 'react';

export type TrustGrade = 'A' | 'B' | 'C' | 'D' | 'F';

export interface TrustBadgeProps {
  grade: TrustGrade;
  /** Tooltip opcional (ex: "Trust 0.87 · 7 components OK"). */
  tooltip?: string;
  size?: 'xs' | 'sm' | 'md';
  className?: string;
}

const GRADE_CLASS: Record<TrustGrade, string> = {
  A: 'bg-success/15 text-success border-success/40',
  B: 'bg-primary-500/15 text-primary-300 border-primary-500/40',
  C: 'bg-warning/15 text-warning border-warning/40',
  D: 'bg-orange-500/15 text-orange-300 border-orange-500/40',
  F: 'bg-danger/15 text-danger border-danger/40',
};

const SIZE_CLASS = {
  xs: 'w-4 h-4 text-[9px]',
  sm: 'w-5 h-5 text-[10px]',
  md: 'w-6 h-6 text-xs',
};

/**
 * Helper — converte score 0..1 em grade letra.
 */
export function scoreToGrade(score: number): TrustGrade {
  if (score >= 0.90) return 'A';
  if (score >= 0.80) return 'B';
  if (score >= 0.70) return 'C';
  if (score >= 0.60) return 'D';
  return 'F';
}

export function TrustBadge({
  grade,
  tooltip,
  size = 'sm',
  className = '',
}: TrustBadgeProps): ReactNode {
  return (
    <span
      className={`
        inline-flex items-center justify-center
        rounded font-bold tabular-nums
        border ${GRADE_CLASS[grade]} ${SIZE_CLASS[size]}
        ${className}
      `}
      title={tooltip ?? `Trust ${grade}`}
      aria-label={tooltip ?? `Trust ${grade}`}
    >
      {grade}
    </span>
  );
}
