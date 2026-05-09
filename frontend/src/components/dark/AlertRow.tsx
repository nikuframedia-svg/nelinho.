/**
 * AlertRow — variante COMPACTA vertical do AlertCard.
 *
 * AlertCard é card grande para destaque; AlertRow é list-item compacto
 * para listas no Painel ("Alertas activos · 5"). API parecida mas o
 * layout é horizontal denso, sem actions inline (a linha inteira
 * pode ser clickable).
 *
 * Inspiração: pages-1.jsx:43-56 do nelo (1).zip — list de alert-row.
 * Sprint Q.18.ZIP.A.
 */

import type { ReactNode } from 'react';
import { AlertCircle, AlertTriangle, Bell, Info, Activity, Database, Clock, ChevronRight } from 'lucide-react';
import type { AlertSeverity } from './AlertCard';

export type AlertKind = 'danger' | 'warning' | 'info' | 'neutral';

export interface AlertRowProps {
  kind: AlertKind;
  /** Lucide icon component (default by kind). */
  icon?: ReactNode;
  title: string;
  /** Meta texto à direita (ex: "PRODUÇÃO · há 4min"). */
  meta?: string;
  className?: string;
  onClick?: () => void;
}

const KIND_ICON_BG: Record<AlertKind, string> = {
  danger: 'bg-danger/15 text-danger',
  warning: 'bg-warning/15 text-warning',
  info: 'bg-primary-500/15 text-primary-300',
  neutral: 'bg-white/5 text-text-dark-tertiary',
};

const KIND_DEFAULT_ICON: Record<AlertKind, ReactNode> = {
  danger: <AlertCircle className="w-3.5 h-3.5" />,
  warning: <AlertTriangle className="w-3.5 h-3.5" />,
  info: <Info className="w-3.5 h-3.5" />,
  neutral: <Bell className="w-3.5 h-3.5" />,
};

/**
 * Helper — converte AlertSeverity de AlertCard em AlertKind compacto.
 */
export function severityToKind(severity: AlertSeverity): AlertKind {
  switch (severity) {
    case 'critical':
      return 'danger';
    case 'high':
      return 'danger';
    case 'medium':
      return 'warning';
    case 'low':
    default:
      return 'info';
  }
}

export function AlertRow({
  kind,
  icon,
  title,
  meta,
  className = '',
  onClick,
}: AlertRowProps): ReactNode {
  const interactive = onClick !== undefined;
  const iconNode = icon ?? KIND_DEFAULT_ICON[kind];

  return (
    <div
      className={`
        flex items-center gap-3 px-3 py-2.5
        border-b border-white/[0.04] last:border-b-0
        transition-colors duration-150
        ${interactive ? 'cursor-pointer hover:bg-white/[0.03]' : ''}
        ${className}
      `}
      onClick={onClick}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
    >
      <div
        className={`
          shrink-0 w-7 h-7 rounded-md
          flex items-center justify-center
          ${KIND_ICON_BG[kind]}
        `}
      >
        {iconNode}
      </div>

      <div className="flex-1 min-w-0">
        <div className="text-sm text-text-dark-primary leading-snug truncate">
          {title}
        </div>
        {meta ? (
          <div className="text-[10px] uppercase tracking-wider text-text-dark-tertiary mt-0.5">
            {meta}
          </div>
        ) : null}
      </div>

      {interactive ? (
        <ChevronRight className="w-4 h-4 shrink-0 text-text-dark-tertiary" />
      ) : null}
    </div>
  );
}

// Re-export common icons for convenience in callers
export { AlertCircle, AlertTriangle, Bell, Info, Activity, Database, Clock };
