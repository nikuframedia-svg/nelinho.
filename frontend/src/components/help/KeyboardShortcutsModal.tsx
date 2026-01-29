/**
 * KeyboardShortcutsModal
 * 
 * Modal that shows all available keyboard shortcuts.
 * Opens with the ? key.
 */

import { X, Keyboard, Navigation, Zap, HelpCircle } from 'lucide-react';
import type { KeyboardShortcut } from '../../hooks/useKeyboardShortcuts';

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
  shortcuts: KeyboardShortcut[];
}

export function KeyboardShortcutsModal({ isOpen, onClose, shortcuts }: KeyboardShortcutsModalProps) {
  if (!isOpen) return null;

  // Group shortcuts by category
  const groupedShortcuts = shortcuts.reduce((acc, shortcut) => {
    if (!acc[shortcut.category]) {
      acc[shortcut.category] = [];
    }
    acc[shortcut.category].push(shortcut);
    return acc;
  }, {} as Record<string, KeyboardShortcut[]>);

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'Navegação':
        return <Navigation size={16} className="text-blue-400" />;
      case 'Acções':
        return <Zap size={16} className="text-amber-400" />;
      case 'Ajuda':
        return <HelpCircle size={16} className="text-emerald-400" />;
      default:
        return <Keyboard size={16} className="text-text-tertiary" />;
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[200]"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed top-[15%] left-1/2 -translate-x-1/2 w-full max-w-lg z-[201] animate-in fade-in zoom-in-95 duration-200">
        <div className="bg-bg-card border border-border-subtle rounded-2xl shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-accent/20 flex items-center justify-center">
                <Keyboard size={20} className="text-accent" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-text-white">Atalhos de Teclado</h2>
                <p className="text-xs text-text-tertiary">Navegação rápida com o teclado</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-bg-secondary rounded-lg transition-colors"
            >
              <X size={18} className="text-text-tertiary" />
            </button>
          </div>

          {/* Content */}
          <div className="p-5 max-h-[60vh] overflow-y-auto">
            {Object.entries(groupedShortcuts).map(([category, categoryShortcuts]) => (
              <div key={category} className="mb-6 last:mb-0">
                <div className="flex items-center gap-2 mb-3">
                  {getCategoryIcon(category)}
                  <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider">
                    {category}
                  </h3>
                </div>
                <div className="space-y-2">
                  {categoryShortcuts.map((shortcut, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between py-2 px-3 bg-bg-secondary/50 rounded-lg"
                    >
                      <span className="text-sm text-text-white">{shortcut.description}</span>
                      <kbd className="flex items-center gap-1 px-2 py-1 bg-bg-card border border-border-subtle rounded text-xs font-mono text-text-tertiary">
                        {shortcut.keys.split(' ').map((key, i) => (
                          <span key={i} className="px-1">
                            {key}
                          </span>
                        ))}
                      </kbd>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Footer */}
          <div className="px-5 py-3 border-t border-border-subtle bg-bg-secondary/50">
            <p className="text-xs text-text-tertiary text-center">
              Prima <kbd className="px-1.5 py-0.5 bg-bg-card rounded border border-border-subtle">Esc</kbd> ou{' '}
              <kbd className="px-1.5 py-0.5 bg-bg-card rounded border border-border-subtle">?</kbd> para fechar
            </p>
          </div>
        </div>
      </div>
    </>
  );
}

export default KeyboardShortcutsModal;

