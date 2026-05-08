/**
 * AlertCard — alerta (CopilotAlert) com severidade + título + detalhe + acções.
 *
 * Usado no Painel topo (lista de alertas activos). Cada alerta tem:
 * - severidade (critical / high / medium / low) → borda esquerda colorida
 * - título: 1 linha curta com problema
 * - detalhe: 1 linha de contexto numérico ("23% esta semana vs 12% normal")
 * - cause opcional: vem do ERRO-TREE quando há diagnóstico
 * - acções: botões accionáveis ("Ver", "Propor manutenção")
 * - source: auto (sistema detectou) | manual (humano criou)
 *
 * Plan v4 §4.1 / FRONTEND_DESIGN_PROMPT §4.1.
 * Sprint Q.18.UI.A.
 */

import type { ReactNode } from 'react';
import { AlertCircle, AlertTriangle, Bell, Info, Bot, User } from 'lucide-react';

export type AlertSeverity = 'critical' | 'high' | 'medium' | 'low';
export type AlertSource = 'auto' | 'manual';

export interface AlertCardAction {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
}

export interface AlertCardProps {
  severity: AlertSeverity;
  title: string;
  detail?: string;
  cause?: string;
  actions?: AlertCardAction[];
  timestamp?: Date | string;
  source?: AlertSource;
  className?: string;
  onClick?: () => void;
}

const SEVERITY_BORDER: Record<AlertSeverity, string> = {
  critical: 'border-l-danger',
  high: 'border-l-orange-500',
  medium: 'border-l-warning',
  low: 'border-l-primary-500',
};

const SEVERITY_ICON_COLOR: Record<AlertSeverity, string> = {
  critical: 'text-danger',
  high: 'text-orange-400',
  medium: 'text-warning',
  low: 'text-primary-400',
};

const SEVERITY_LABEL: Record<AlertSeverity, string> = {
  critical: 'Crítico',
  high: 'Alto',
  medium: 'Médio',
  low: 'Informação',
};

const ACTION_VARIANT = {
  primary: 'bg-accent-500 text-white hover:bg-accent-400',
  secondary:
    'bg-transparent text-text-dark-secondary border border-white/10 hover:bg-white/5 hover:text-text-dark-primary',
  danger: 'bg-danger text-white hover:bg-danger-light',
};

function severityIcon(severity: AlertSeverity) {
  const cls = `w-5 h-5 ${SEVERITY_ICON_COLOR[severity]}`;
  switch (severity) {
    case 'critical':
      return <AlertCircle className={cls} />;
    case 'high':
      return <AlertTriangle className={cls} />;
    case 'medium':
      return <Bell className={cls} />;
    case 'low':
    default:
      return <Info className={cls} />;
  }
}

function relativeTime(value: Date | string): string {
  const date = value instanceof Date ? value : new Date(value);
  const diffMs = Date.now() - date.getTime();
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return 'agora';
  if (minutes < 60) return `há ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `há ${hours}h`;
  const days = Math.floor(hours / 24);
  return `há ${days}d`;
}

export function AlertCard({
  severity,
  title,
  detail,
  cause,
  actions,
  timestamp,
  source,
  className = '',
  onClick,
}: AlertCardProps): ReactNode {
  const interactive = onClick !== undefined;
  return (
    <div
      className={`
        flex items-start gap-3 p-4
        bg-dark-800/80 rounded-lg border border-white/[0.06] border-l-4 ${SEVERITY_BORDER[severity]}
        transition-colors duration-150
        ${interactive ? 'cursor-pointer hover:bg-dark-700/80' : ''}
        ${className}
      `}
      onClick={onClick}
      role={interactive ? 'button' : 'alert'}
      aria-label={`${SEVERITY_LABEL[severity]}: ${title}`}
    >
      <div className="shrink-0 pt-0.5">{severityIcon(severity)}</div>

      <div className="flex flex-col gap-1 flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={`text-[10px] font-semibold uppercase tracking-wider ${SEVERITY_ICON_COLOR[severity]}`}
          >
            {SEVERITY_LABEL[severity]}
          </span>
          {source ? (
            <span
              className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-text-dark-tertiary"
              title={source === 'auto' ? 'Detectado pelo sistema' : 'Criado manualmente'}
            >
              {source === 'auto' ? (
                <Bot className="w-3 h-3" />
              ) : (
                <User className="w-3 h-3" />
              )}
              {source === 'auto' ? 'auto' : 'manual'}
            </span>
          ) : null}
          {timestamp ? (
            <span className="text-[10px] text-text-dark-tertiary tabular-nums ml-auto">
              {relativeTime(timestamp)}
            </span>
          ) : null}
        </div>

        <h4 className="text-sm font-semibold text-text-dark-primary leading-snug">
          {title}
        </h4>

        {detail ? (
          <p className="text-xs text-text-dark-secondary leading-snug">{detail}</p>
        ) : null}

        {cause ? (
          <p className="text-xs text-text-dark-tertiary italic leading-snug">
            <span className="font-medium">Causa:</span> {cause}
          </p>
        ) : null}

        {actions && actions.length > 0 ? (
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            {actions.map((action, idx) => (
              <button
                key={`${action.label}-${idx}`}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  action.onClick();
                }}
                className={`
                  inline-flex items-center px-3 py-1.5 rounded-md text-xs font-medium
                  transition-colors duration-150
                  ${ACTION_VARIANT[action.variant ?? 'secondary']}
                `}
              >
                {action.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
