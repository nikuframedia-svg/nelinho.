/**
 * Sheet — modal centrado com superfície glass (NELO.html atoms.jsx).
 *
 * Port fiel do atom `Sheet`: backdrop escuro com blur, painel `.glass`
 * com raio `--r-xl`, cabeçalho display + botão fechar circular, corpo
 * scrollável e rodapé opcional. Fecha com Esc, com clique no backdrop e
 * tranca o scroll do body enquanto aberto.
 *
 * Distinto do `Modal` legacy (Tailwind) — este bate certo com a
 * geometria do protótipo NELO e é usado pelos BoatDetailSheet etc.
 *
 * Sprint Q.52.B.
 */

import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';
import { X } from 'lucide-react';

export interface SheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** Slot fixo no fundo (botões de ação). */
  footer?: ReactNode;
  /** Largura do painel em px (default 560). */
  width?: number;
}

export function Sheet({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  width = 560,
}: SheetProps): ReactNode {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  // Q.57 — renderizado num portal para `document.body`. Um overlay
  // `position: fixed` não pode ser filho do contentor da página: o
  // `DarkPageLayout` marca-o com `.page-enter`, cujo `.page-enter > *`
  // dava ao backdrop um `opacity: 0` base — a janela fazia fade-in e
  // depois revertia para invisível ("abre e desaparece logo"). O portal
  // tira o Sheet dessa árvore e de qualquer containing-block de um
  // ancestral com transform/filter.
  return createPortal(
    <div
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        background: 'rgba(0,0,0,0.6)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        animation: 'fade-in 0.18s ease',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="anim-up glass"
        style={{
          width,
          maxWidth: '90vw',
          maxHeight: '86vh',
          borderRadius: 'var(--r-xl)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          boxShadow: 'var(--shadow-3)',
        }}
      >
        <div
          style={{
            padding: '18px 22px',
            borderBottom: '1px solid var(--bd-1)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 12,
          }}
        >
          <div>
            <div
              className="display"
              style={{ fontSize: 18, fontWeight: 600, letterSpacing: '-0.3px' }}
            >
              {title}
            </div>
            {subtitle ? (
              <div
                style={{ fontSize: 12.5, color: 'var(--fg-2)', marginTop: 3 }}
              >
                {subtitle}
              </div>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            style={{
              width: 28,
              height: 28,
              borderRadius: '50%',
              background: 'var(--bg-3)',
              border: 'none',
              color: 'var(--fg-1)',
              display: 'grid',
              placeItems: 'center',
              cursor: 'pointer',
            }}
          >
            <X size={14} />
          </button>
        </div>

        <div style={{ overflowY: 'auto', padding: 22, flex: 1 }}>
          {children}
        </div>

        {footer ? (
          <div
            style={{
              padding: '14px 22px',
              borderTop: '1px solid var(--bd-1)',
              background: 'var(--bg-1)',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: 8,
            }}
          >
            {footer}
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}
