/**
 * useKeyboardShortcuts Hook
 * 
 * Global keyboard shortcuts for navigation and actions.
 * Press ? to see all available shortcuts.
 */

import { useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

interface ShortcutHandler {
  key: string;
  modifiers?: ('ctrl' | 'meta' | 'shift' | 'alt')[];
  description: string;
  category: 'navigation' | 'action' | 'modal';
  handler: () => void;
}

export interface KeyboardShortcut {
  keys: string;
  description: string;
  category: string;
}

export function useKeyboardShortcuts(onOpenHelp: () => void) {
  const navigate = useNavigate();

  const shortcuts: ShortcutHandler[] = [
    // Navigation (G + key)
    { key: 'd', description: 'Ir para Dashboard', category: 'navigation', handler: () => navigate('/') },
    { key: 'i', description: 'Ir para Inbox', category: 'navigation', handler: () => navigate('/inbox') },
    { key: 'f', description: 'Ir para Factory', category: 'navigation', handler: () => navigate('/core/products') },
    { key: 'p', description: 'Ir para Planning', category: 'navigation', handler: () => navigate('/plan/scheduling') },
    { key: 't', description: 'Ir para Twin Sandbox', category: 'navigation', handler: () => navigate('/twin') },
    { key: 'q', description: 'Ir para Data Quality', category: 'navigation', handler: () => navigate('/admin/data-quality') },
    { key: 't', description: 'Ir para Tool Registry', category: 'navigation', handler: () => navigate('/admin/tool-registry') },
    
    // Actions
    { key: 'n', description: 'Criar novo cenário', category: 'action', handler: () => navigate('/twin?action=new') },
    { key: 'e', description: 'Explicar métrica', category: 'action', handler: () => navigate('/explain') },
    
    // Help
    { key: '?', description: 'Mostrar atalhos', category: 'modal', handler: onOpenHelp },
  ];

  // Track if we're in "G" mode (navigation prefix). Stored in refs so
  // assignments survive re-renders — using `let` here would reset the
  // values on every render and the G-prefix navigation would silently
  // never work (caught by react-hooks/exhaustive-deps).
  const gModeActiveRef = useRef(false);
  const gModeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Don't trigger shortcuts when typing in input/textarea
    const target = e.target as HTMLElement;
    if (
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.isContentEditable
    ) {
      return;
    }

    // Handle ? for help (with or without shift)
    if (e.key === '?' || (e.shiftKey && e.key === '/')) {
      e.preventDefault();
      onOpenHelp();
      return;
    }

    // Handle G prefix for navigation
    if (e.key.toLowerCase() === 'g' && !e.ctrlKey && !e.metaKey && !e.altKey) {
      gModeActiveRef.current = true;
      if (gModeTimeoutRef.current) clearTimeout(gModeTimeoutRef.current);
      gModeTimeoutRef.current = setTimeout(() => {
        gModeActiveRef.current = false;
      }, 1500);
      return;
    }

    // If in G mode, check for navigation shortcuts
    if (gModeActiveRef.current) {
      const navShortcut = shortcuts.find(
        s => s.category === 'navigation' && s.key === e.key.toLowerCase()
      );
      if (navShortcut) {
        e.preventDefault();
        navShortcut.handler();
        gModeActiveRef.current = false;
        if (gModeTimeoutRef.current) clearTimeout(gModeTimeoutRef.current);
        return;
      }
    }

    // Direct shortcuts (N, E)
    const shortcut = shortcuts.find(
      s => s.category === 'action' && s.key === e.key.toLowerCase()
    );
    if (shortcut && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      shortcut.handler();
    }
  }, [navigate, onOpenHelp, shortcuts]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      if (gModeTimeoutRef.current) clearTimeout(gModeTimeoutRef.current);
    };
  }, [handleKeyDown]);

  // Export shortcuts for help modal
  const getShortcutsList = useCallback((): KeyboardShortcut[] => {
    return [
      // Navigation
      { keys: 'G D', description: 'Ir para Dashboard', category: 'Navegação' },
      { keys: 'G I', description: 'Ir para Inbox', category: 'Navegação' },
      { keys: 'G F', description: 'Ir para Factory', category: 'Navegação' },
      { keys: 'G P', description: 'Ir para Planning', category: 'Navegação' },
      { keys: 'G T', description: 'Ir para Twin Sandbox', category: 'Navegação' },
      { keys: 'G Q', description: 'Ir para Data Quality', category: 'Navegação' },
      // Actions
      { keys: '⌘ K', description: 'Abrir Command Palette', category: 'Acções' },
      { keys: 'N', description: 'Criar novo cenário', category: 'Acções' },
      { keys: 'E', description: 'Explicar métrica', category: 'Acções' },
      // Modal
      { keys: '?', description: 'Mostrar atalhos', category: 'Ajuda' },
      { keys: 'Esc', description: 'Fechar modal', category: 'Ajuda' },
    ];
  }, []);

  return { getShortcutsList };
}

export default useKeyboardShortcuts;

