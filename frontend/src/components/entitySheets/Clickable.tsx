/**
 * Q.116.A — Wrapper clicável que abre a sheet contextual de uma entidade.
 *
 * Usa <button> para a11y (não <a> — não navega para nova rota).
 * stopPropagation para evitar conflito com handlers pai.
 */
import type { ReactNode } from 'react';
import { useEntitySheet } from './EntitySheetProvider';
import type { EntityKind } from '../../lib/api/entityApi';

const KIND_COLOR: Record<EntityKind, string> = {
  modelo:    'var(--accent, #22d3ee)',
  fase:      'var(--teal-400, #2dd4bf)',
  cliente:   'var(--primary, #6366f1)',
  encomenda: 'var(--warning, #f59e0b)',
  operador:  'var(--info, #38bdf8)',
};

interface ClickableProps {
  kind: EntityKind;
  id: string | number;
  children: ReactNode;
  className?: string;
}

export function Clickable({ kind, id, children, className }: ClickableProps) {
  const { openSheet } = useEntitySheet();

  // Defesa: children vazio → render placeholder não-clicável
  if (children === null || children === undefined || children === '') {
    return <span>—</span>;
  }

  function handleClick(e: React.MouseEvent<HTMLButtonElement>) {
    e.stopPropagation();
    openSheet(kind, String(id));
  }

  return (
    <button
      type="button"
      className={className}
      onClick={handleClick}
      style={{
        background: 'transparent',
        border: 'none',
        padding: 0,
        cursor: 'pointer',
        color: KIND_COLOR[kind],
        textDecoration: 'underline dotted',
        textUnderlineOffset: '2px',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLButtonElement).style.opacity = '0.8';
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLButtonElement).style.opacity = '1';
      }}
    >
      {children}
    </button>
  );
}
