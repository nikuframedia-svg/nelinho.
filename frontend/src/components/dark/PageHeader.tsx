/**
 * PageHeader — port literal de design/nelo-zip/src/atoms.jsx PageHeader.
 *
 * Padding: 20px 28px 16px 28px. Border-bottom bd-1. Sticky top 52 z-10.
 * Ícone opcional 38x38 box bg-2 bd-1 à esquerda do título.
 * Title 20px 600 letter-spacing -0.2. Subtitle 13px regular fg-2.
 *
 * Sprint Q.18.ZIP.shell.
 */

import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { PageHelpButton } from '../help/PageHelpButton';
import { helpIdFromPath, type PageHelpId } from '../../data/pageHelp';

export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /** Ícone à esquerda (renderizado em box 38x38 bg-2 + bd-1). */
  icon?: ReactNode;
  /** Botões/actions à direita. */
  actions?: ReactNode;
  /** Quando definido, renderiza botão "?" (PageHelpButton) à esquerda das actions. */
  helpId?: PageHelpId;
  className?: string;
}

export function PageHeader({
  title,
  subtitle,
  icon,
  actions,
  helpId,
  className = '',
}: PageHeaderProps): ReactNode {
  // Sem `helpId` explícito → deriva-o da rota, para o "?" aparecer em
  // todas as páginas sem cada uma o declarar (Q.56).
  const { pathname } = useLocation();
  const effectiveHelpId = helpId ?? helpIdFromPath(pathname);
  return (
    <header
      className={`flex items-start justify-between sticky z-10 border-b border-bd-1 ${className}`}
      style={{
        padding: '20px 28px 16px 28px',
        background: 'var(--bg-0)',
        top: 52,
        gap: 16,
      }}
    >
      <div className="flex items-center" style={{ gap: 12 }}>
        {icon ? (
          <div
            className="grid place-items-center text-text-dark-secondary"
            style={{
              width: 38,
              height: 38,
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-md)',
              flexShrink: 0,
            }}
          >
            {icon}
          </div>
        ) : null}
        <div className="min-w-0">
          <h1
            className="text-text-dark-primary truncate"
            style={{
              margin: 0,
              fontSize: 20,
              fontWeight: 600,
              letterSpacing: '-0.2px',
            }}
          >
            {title}
          </h1>
          {subtitle ? (
            <div
              className="text-text-dark-tertiary"
              style={{ fontSize: 13, marginTop: 3 }}
            >
              {subtitle}
            </div>
          ) : null}
        </div>
      </div>
      {(effectiveHelpId || actions) ? (
        <div className="flex items-center" style={{ gap: 8 }}>
          {effectiveHelpId ? <PageHelpButton helpId={effectiveHelpId} /> : null}
          {actions}
        </div>
      ) : null}
    </header>
  );
}
