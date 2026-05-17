/**
 * KPICard — card grande do Painel (homepage) com valor + unidade + alvo + tendência.
 *
 * Distinto do DarkStatCard: o KPICard suporta ALVO (target) e mostra
 * ESTADO (verde/amarelo/vermelho) baseado em regra do utilizador, não
 * só trend. Cada KPI tem um `description` (contexto curto) e é
 * clicável para navegar para a página relevante.
 *
 * NUNCA mostrar percentagem sem contexto: "72%" não diz nada,
 * "72% — faltam 3 operadores, 5 barcos em risco" diz tudo
 * (FRONTEND_DESIGN_PROMPT §2.4).
 *
 * Plan v4 §4.1 / FRONTEND_DESIGN_PROMPT §4.1.
 * Sprint Q.18.UI.A.
 */

import type { ReactNode } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { formatNumber } from '../../lib/utils';
import { Sparkline } from './Sparkline';
import { TrustBadge, type TrustGrade } from './TrustBadge';

export type KPIStatus = 'green' | 'yellow' | 'red' | 'neutral';

export interface KPICardProps {
  /** Curto, ≤ 24 chars. Ex: "Throughput hoje". */
  label: string;
  /** Valor numérico ou já formatado em string. */
  value: number | string;
  /** Unidade fixa (€, h, barcos, operadores, %). NUNCA omitir. */
  unit: string;
  /** Alvo (mostrado como "/ €30.000" ou "/ 14.7"). Opcional. */
  target?: number | string;
  /** Variação vs período anterior (% — vai ter + ou - prefix). */
  trend?: number;
  /** Verde/amarelo/vermelho/neutro. Calculado upstream — KPICard só pinta. */
  status?: KPIStatus;
  /** Sub-texto curto: "expedição sexta", "vs ontem", "média 7 dias". */
  description?: string;
  /** Ícone opcional à esquerda (lucide-react). */
  icon?: ReactNode;
  /** Click navega — ex: para /producao?filter=at_risk. */
  onClick?: () => void;
  className?: string;
  /** Q.18.ZIP.A — Sparkline opcional (N pontos de tendência). Vem de query histórica. */
  spark?: number[];
  /** Q.18.ZIP.A — TrustBadge opcional (qualidade da fonte de dados). */
  trust?: TrustGrade;
}

const STATUS_BORDER: Record<KPIStatus, string> = {
  green: 'border-success/50',
  yellow: 'border-warning/50',
  red: 'border-danger/50',
  neutral: 'border-white/[0.06]',
};

const STATUS_VALUE: Record<KPIStatus, string> = {
  green: 'text-success',
  yellow: 'text-warning',
  red: 'text-danger',
  neutral: 'text-text-dark-primary',
};

const STATUS_GLOW: Record<KPIStatus, string> = {
  green: 'shadow-glow-green/30',
  yellow: 'shadow-glow-amber/30',
  red: 'shadow-glow-red/30',
  neutral: 'shadow-card',
};

export function KPICard({
  label,
  value,
  unit,
  target,
  trend,
  status = 'neutral',
  description,
  icon,
  onClick,
  className = '',
  spark,
  trust,
}: KPICardProps): ReactNode {
  const interactive = onClick !== undefined;
  const valueStr = typeof value === 'number' ? formatNumber(value) : value;
  const targetStr = target === undefined
    ? null
    : typeof target === 'number'
    ? formatNumber(target)
    : String(target);

  const TrendIcon = trend === undefined
    ? null
    : trend > 0
    ? TrendingUp
    : trend < 0
    ? TrendingDown
    : Minus;

  const trendColor =
    trend === undefined
      ? ''
      : trend > 0
      ? 'text-success'
      : trend < 0
      ? 'text-danger'
      : 'text-text-dark-tertiary';

  return (
    <div
      className={`
        relative p-5 rounded-2xl
        bg-gradient-to-br from-dark-800 to-dark-700
        border-2 ${STATUS_BORDER[status]}
        ${STATUS_GLOW[status]}
        transition-all duration-200
        ${interactive ? 'cursor-pointer hover:border-accent-500/60 hover:shadow-card-hover active:scale-[0.99]' : ''}
        ${className}
      `}
      onClick={onClick}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      {/* Header — ícone + label + (trust badge) */}
      <div className="flex items-start justify-between gap-2 mb-4">
        <div className="flex items-center gap-2 min-w-0">
          {icon ? (
            <span className={`${STATUS_VALUE[status]} opacity-80`}>{icon}</span>
          ) : null}
          <span className="text-[11px] font-semibold uppercase tracking-wider text-text-dark-tertiary truncate">
            {label}
          </span>
          {/* Q.18.ZIP.A — Trust badge inline com label */}
          {trust ? <TrustBadge grade={trust} size="xs" /> : null}
        </div>

        {trend !== undefined && TrendIcon ? (
          <div className={`inline-flex items-center gap-1 ${trendColor}`}>
            <TrendIcon className="w-3.5 h-3.5" />
            <span className="text-xs font-semibold tabular-nums">
              {trend > 0 ? '+' : ''}
              {trend.toFixed(1)}%
            </span>
          </div>
        ) : null}
      </div>

      {/* Valor + unidade */}
      <div className="flex items-baseline gap-2">
        <span
          className={`text-4xl font-bold tabular-nums leading-none ${STATUS_VALUE[status]}`}
        >
          {valueStr}
        </span>
        <span className="text-base font-medium text-text-dark-secondary">
          {unit}
        </span>
        {targetStr ? (
          <span className="text-sm text-text-dark-tertiary tabular-nums">
            / {targetStr}
          </span>
        ) : null}
      </div>

      {/* Descrição contextual — NUNCA omitir para % */}
      {description ? (
        <p className="text-xs text-text-dark-secondary mt-2 leading-snug">
          {description}
        </p>
      ) : null}

      {/* Q.18.ZIP.A — Sparkline tendência (renderiza só se passado) */}
      {spark && spark.length > 0 ? (
        <div className={`mt-3 ${STATUS_VALUE[status]} opacity-70`}>
          <Sparkline points={spark} width={120} height={26} />
        </div>
      ) : null}
    </div>
  );
}
