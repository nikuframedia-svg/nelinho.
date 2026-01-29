import { useEffect } from 'react';
import { X } from 'lucide-react';
import { cn } from '../../lib/utils';

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

interface DialogContentProps {
  children: React.ReactNode;
  className?: string;
}

interface DialogHeaderProps {
  children: React.ReactNode;
}

interface DialogTitleProps {
  children: React.ReactNode;
  className?: string;
}

interface DialogDescriptionProps {
  children: React.ReactNode;
  className?: string;
}

export function Dialog({ open, onOpenChange, children }: DialogProps) {
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={() => onOpenChange(false)}
    >
      {children}
    </div>
  );
}

export function DialogContent({ children, className }: DialogContentProps) {
  return (
    <div
      className={cn(
        'bg-white rounded-2xl shadow-xl max-h-[90vh] overflow-hidden flex flex-col',
        className
      )}
      onClick={(e) => e.stopPropagation()}
    >
      {children}
    </div>
  );
}

export function DialogHeader({ children }: DialogHeaderProps) {
  return <div className="px-6 pt-6 pb-4 border-b border-slate-200">{children}</div>;
}

export function DialogTitle({ children, className = '' }: DialogTitleProps) {
  return <h3 className={`text-xl font-bold text-[#1a2744] ${className}`}>{children}</h3>;
}

export function DialogDescription({ children, className = '' }: DialogDescriptionProps) {
  return <p className={`text-sm text-slate-500 mt-1 ${className}`}>{children}</p>;
}

interface DialogCloseButtonProps {
  onClose: () => void;
  className?: string;
}

export function DialogCloseButton({ onClose, className }: DialogCloseButtonProps) {
  return (
    <button
      onClick={onClose}
      className={cn(
        'w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-500 absolute top-4 right-4',
        className
      )}
    >
      <X size={20} />
    </button>
  );
}







