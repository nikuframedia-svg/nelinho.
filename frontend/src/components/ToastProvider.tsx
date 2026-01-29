import { createContext, useContext, useEffect } from 'react';
import type { ReactNode } from 'react';
import { useToast } from '../hooks/useToast';
import { ToastContainer } from './ui/Toast';
import { setToastContext } from '../lib/api';
import { setBackendHealthToastContext } from '../lib/backend-health';

interface ToastContextType {
  success: (message: string, duration?: number) => string;
  error: (message: string, duration?: number) => string;
  warning: (message: string, duration?: number) => string;
  info: (message: string, duration?: number) => string;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const toast = useToast();

  // Register toast context for retry logic and backend health
  useEffect(() => {
    setToastContext({
      info: toast.info,
    });
    setBackendHealthToastContext({
      error: toast.error,
    });
    
    return () => {
      setToastContext(null);
      setBackendHealthToastContext(null);
    };
  }, [toast.info, toast.error]);

  return (
    <ToastContext.Provider
      value={{
        success: toast.success,
        error: toast.error,
        warning: toast.warning,
        info: toast.info,
      }}
    >
      {children}
      <ToastContainer toasts={toast.toasts} onDismiss={toast.dismissToast} />
    </ToastContext.Provider>
  );
}

export function useToastContext() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
}
