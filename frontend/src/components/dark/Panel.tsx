/**
 * Panel — composição reutilizável de "card com header padrão".
 *
 * Header tem: título + badge opcional (count, status) + acção opcional
 * à direita ("Ver tudo →"). Body pode ser flush (sem padding) para
 * lists de AlertRow, ou padded para conteúdo normal.
 *
 * Diferença vs DarkCard: DarkCard é genérico com muitas props; Panel é
 * específico para o pattern panel-header / panel-body padrão do nelo
 * zip (pages-1.jsx panels), com badge inline no título.
 *
 * Sprint Q.18.ZIP.A.
 */

import type { ReactNode } from 'react';

export interface PanelProps {
  title?: string;
  /** Badge curto à direita do título (ex: "5", "Crítico"). */
  badge?: ReactNode;
  /** Acção à direita (botão, link). Tipicamente `<button>Ver tudo</button>`. */
  action?: ReactNode;
  /** Sub-título opcional (uma linha pequena, abaixo do título). */
  subtitle?: string;
  /** Quando true, body sem padding interno (útil para lists de AlertRow). */
  flush?: boolean;
  /** Quando true, sem header — só o body wrappped no card. */
  bare?: boolean;
  className?: string;
  bodyClassName?: string;
  children?: ReactNode;
}

export function Panel({
  title,
  badge,
  action,
  subtitle,
  flush = false,
  bare = false,
  className = '',
  bodyClassName = '',
  children,
}: PanelProps) {
  return (
    <section
      className={`
        bg-dark-800 border border-bd-1 rounded-lg
        flex flex-col
        ${className}
      `}
    >
      {!bare && (title || badge || action) ? (
        <header className="flex items-center justify-between gap-2 px-4 py-2.5 border-b border-bd-1">
          <div className="flex items-baseline gap-2 min-w-0">
            {title ? (
              <h3 className="text-sm font-semibold text-text-dark-primary truncate">
                {title}
              </h3>
            ) : null}
            {badge !== undefined && badge !== null ? (
              <span className="text-xs text-text-dark-tertiary tabular-nums">
                · {badge}
              </span>
            ) : null}
            {subtitle ? (
              <span className="text-xs text-text-dark-tertiary truncate">
                {subtitle}
              </span>
            ) : null}
          </div>
          {action ? <div className="shrink-0">{action}</div> : null}
        </header>
      ) : null}

      <div className={`${flush ? '' : 'p-4'} flex-1 ${bodyClassName}`}>
        {children}
      </div>
    </section>
  );
}
