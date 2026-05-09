/**
 * Breadcrumbs — navegação hierárquica curta.
 *
 * Mostra `Nelo · Operação · Painel` na TopBar (slot adicionado em
 * Q.18.ZIP.A) ou no PageHeader. Cada crumb pode ser uma string
 * simples ou um link clickable.
 *
 * Sprint Q.18.ZIP.A.
 */

import type { ReactNode } from 'react';
import { ChevronRight } from 'lucide-react';

export interface BreadcrumbItem {
  label: string;
  /** Se passado, item vira <a>; caso contrário, span simples. */
  href?: string;
  /** Callback alternativo (Link wrapper). */
  onClick?: () => void;
}

export interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  className?: string;
  /** Separador (default: ChevronRight). */
  separator?: ReactNode;
}

export function Breadcrumbs({
  items,
  className = '',
  separator,
}: BreadcrumbsProps): ReactNode {
  if (items.length === 0) return null;
  const sep = separator ?? <ChevronRight className="w-3 h-3 text-text-dark-tertiary" />;

  return (
    <nav
      aria-label="Localização"
      className={`flex items-center gap-1 text-xs text-text-dark-tertiary ${className}`}
    >
      {items.map((item, idx) => {
        const isLast = idx === items.length - 1;
        const inner = (
          <span
            className={
              isLast
                ? 'text-text-dark-secondary font-medium'
                : 'hover:text-text-dark-secondary transition-colors'
            }
          >
            {item.label}
          </span>
        );
        return (
          <span key={`${item.label}-${idx}`} className="inline-flex items-center gap-1">
            {item.href || item.onClick ? (
              <a
                href={item.href}
                onClick={(e) => {
                  if (item.onClick) {
                    e.preventDefault();
                    item.onClick();
                  }
                }}
                className="cursor-pointer"
              >
                {inner}
              </a>
            ) : (
              inner
            )}
            {!isLast ? <span className="opacity-60">{sep}</span> : null}
          </span>
        );
      })}
    </nav>
  );
}
