/**
 * PageHeader — cabeçalho padrão de cada página-mãe.
 *
 * Pattern repetido em todas as 4 páginas de pages-1.jsx do nelo zip:
 *   ┌─────────────────────────────────────────────────────────┐
 *   │ Painel                                  [Atualizar] [⚙] │
 *   │ VISÃO GERAL · TURNO HOJE · ATUALIZADO HÁ 2 MIN          │
 *   └─────────────────────────────────────────────────────────┘
 *
 * Subtitle em uppercase letter-spaced (Palantir aesthetic).
 * Actions slot à direita aceita qualquer ReactNode (botões, badges).
 *
 * Sprint Q.18.ZIP.A.
 */

import type { ReactNode } from 'react';

export interface PageHeaderProps {
  title: string;
  /** Subtítulo metadata (renderizado uppercase letter-spaced). */
  subtitle?: string;
  /** Ícone opcional à esquerda do título. */
  icon?: ReactNode;
  /** Botões/actions à direita (ex: Atualizar/Filtros/Pedir-ao-Copilot). */
  actions?: ReactNode;
  /** Breadcrumbs opcionais por cima do título. */
  breadcrumbs?: ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  subtitle,
  icon,
  actions,
  breadcrumbs,
  className = '',
}: PageHeaderProps): ReactNode {
  return (
    <header
      className={`
        flex flex-col gap-1.5 px-7 pt-5 pb-4
        bg-dark-900 border-b border-bd-1
        sticky top-13 z-10
        ${className}
      `}
      style={{ top: 52 }}
    >
      {breadcrumbs ? <div className="text-xs">{breadcrumbs}</div> : null}

      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          {icon ? (
            <span className="shrink-0 text-blue">{icon}</span>
          ) : null}
          <div className="min-w-0">
            <h1
              className="text-xl font-semibold text-text-dark-primary leading-tight truncate"
              style={{ letterSpacing: '-0.2px' }}
            >
              {title}
            </h1>
            {subtitle ? (
              <p className="text-[13px] text-text-dark-tertiary mt-0.5">
                {subtitle}
              </p>
            ) : null}
          </div>
        </div>

        {actions ? (
          <div className="flex items-center gap-2 shrink-0">{actions}</div>
        ) : null}
      </div>
    </header>
  );
}
