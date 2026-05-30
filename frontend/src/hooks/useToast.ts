import { useState, useCallback } from 'react';
import type { Toast, ToastType } from '../components/ui/Toast';

let toastIdCounter = 0;

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((type: ToastType, message: string, duration?: number) => {
    const id = `toast-${++toastIdCounter}`;
    // Q.124 — dedup: não empilhar toasts idênticos (evita o "storm" quando vários
    // pedidos falham ao mesmo tempo). Se já existe um igual, mantém a lista.
    setToasts((prev) =>
      prev.some((t) => t.type === type && t.message === message)
        ? prev
        : [...prev, { id, type, message, duration }],
    );
    return id;
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const success = useCallback((message: string, duration?: number) => {
    return addToast('success', message, duration);
  }, [addToast]);

  const error = useCallback((message: string, duration?: number) => {
    return addToast('error', message, duration);
  }, [addToast]);

  const warning = useCallback((message: string, duration?: number) => {
    return addToast('warning', message, duration);
  }, [addToast]);

  const info = useCallback((message: string, duration?: number) => {
    return addToast('info', message, duration);
  }, [addToast]);

  return {
    toasts,
    success,
    error,
    warning,
    info,
    dismissToast,
  };
}







