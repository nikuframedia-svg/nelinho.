import { useEffect, useState } from 'react';
import { X, CheckCircle2, AlertTriangle, Info } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

interface ToastProps {
  toast: Toast;
  onDismiss: (id: string) => void;
}

function ToastItem({ toast, onDismiss }: ToastProps) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Trigger animation
    setTimeout(() => setIsVisible(true), 10);

    // Auto-dismiss
    const duration = toast.duration || 5000;
    const timer = setTimeout(() => {
      setIsVisible(false);
      setTimeout(() => onDismiss(toast.id), 300); // Wait for animation
    }, duration);

    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, onDismiss]);

  // Q.124 — tokens dark (antes ícones text-*-600 e fundos bg-*-50/text-*-800, ilegíveis no tema escuro).
  const icons = {
    success: <CheckCircle2 size={20} style={{ color: 'var(--green)' }} />,
    error: <X size={20} style={{ color: 'var(--red)' }} />,
    warning: <AlertTriangle size={20} style={{ color: 'var(--orange)' }} />,
    info: <Info size={20} style={{ color: 'var(--accent)' }} />,
  };

  const toneBg: Record<ToastType, string> = {
    success: 'var(--green-bg)',
    error: 'var(--red-bg)',
    warning: 'var(--orange-bg)',
    info: 'var(--accent-bg)',
  };
  const toneBd: Record<ToastType, string> = {
    success: 'var(--green-bd)',
    error: 'var(--red-bd)',
    warning: 'var(--orange-bd)',
    info: 'var(--accent-bd)',
  };

  return (
    <div
      className={`flex items-start gap-3 p-4 rounded-lg border shadow-lg transition-all duration-300 ${
        isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-full'
      }`}
      style={{
        minWidth: '300px',
        maxWidth: '400px',
        background: toneBg[toast.type],
        borderColor: toneBd[toast.type],
        color: 'var(--fg-1)',
      }}
    >
      {icons[toast.type]}
      <p className="flex-1 text-sm font-medium">{toast.message}</p>
      <button
        onClick={() => {
          setIsVisible(false);
          setTimeout(() => onDismiss(toast.id), 300);
        }}
        className="flex-shrink-0 text-current opacity-60 hover:opacity-100 transition-opacity"
        aria-label="Fechar notificação"
      >
        <X size={16} />
      </button>
    </div>
  );
}

interface ToastContainerProps {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none max-h-[calc(100vh-2rem)] overflow-y-auto pr-0.5">
      {toasts.slice(-5).map((toast) => (
        <div key={toast.id} className="pointer-events-auto">
          <ToastItem toast={toast} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  );
}
