/**
 * Modal — modal padrão com backdrop + header + body + footer slots.
 *
 * Usado em drag-drop confirmation (Produção, Expedição), "Pedir ao
 * Copilot", forms de adicionar/editar (Equipa, Configuração).
 *
 * Não substitui DarkCard — Modal tem backdrop + close (Esc + click
 * outside) + footer slot fixo. Composição com Panel/DarkCard internamente.
 *
 * Inspiração: pages-1.jsx do nelo zip (modais de confirmação).
 * Sprint Q.18.ZIP.A.
 */

import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { X } from 'lucide-react';

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  /** Conteúdo do body. */
  children: ReactNode;
  /** Slot fixo no fundo (botões Cancelar/Confirmar). */
  footer?: ReactNode;
  /** Largura — default 'md' (~520px). */
  size?: 'sm' | 'md' | 'lg' | 'xl';
  /** Esconder o botão X de fechar (manter Esc). */
  hideCloseButton?: boolean;
  className?: string;
}

const SIZE_CLASS = {
  sm: 'max-w-md',     // ~448px
  md: 'max-w-xl',     // ~576px
  lg: 'max-w-3xl',    // ~768px
  xl: 'max-w-5xl',    // ~1024px
};

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  hideCloseButton = false,
  className = '',
}: ModalProps): ReactNode {
  // ESC para fechar
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Lock body scroll quando aberto
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center px-4 py-8"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? 'modal-title' : undefined}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        aria-hidden="true"
      />

      {/* Container */}
      <div
        className={`
          relative w-full ${SIZE_CLASS[size]}
          bg-dark-800 border border-white/10 rounded-xl
          shadow-elevated
          flex flex-col max-h-[90vh]
          ${className}
        `}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        {(title || !hideCloseButton) && (
          <header className="flex items-center justify-between gap-2 px-5 py-3.5 border-b border-white/[0.08]">
            {title ? (
              <h2
                id="modal-title"
                className="text-base font-semibold text-text-dark-primary truncate"
              >
                {title}
              </h2>
            ) : (
              <span />
            )}
            {!hideCloseButton ? (
              <button
                type="button"
                onClick={onClose}
                className="
                  p-1 rounded-md
                  text-text-dark-tertiary hover:text-text-dark-primary hover:bg-white/5
                  transition-colors duration-150
                  focus:outline-none focus:ring-2 focus:ring-accent-500/40
                "
                aria-label="Fechar"
              >
                <X size={18} />
              </button>
            ) : null}
          </header>
        )}

        {/* Body — scrollable */}
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>

        {/* Footer fixo */}
        {footer ? (
          <footer className="px-5 py-3 border-t border-white/[0.08] flex items-center justify-end gap-2 shrink-0">
            {footer}
          </footer>
        ) : null}
      </div>
    </div>
  );
}
