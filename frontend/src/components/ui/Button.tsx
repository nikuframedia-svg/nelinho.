import { cn } from '../../lib/utils';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Loader2, ChevronRight } from 'lucide-react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'accent';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: ReactNode;
  iconRight?: boolean;
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  iconRight = false,
  className,
  disabled,
  ...props
}: ButtonProps) {
  const variants = {
    primary: 'btn-primary',
    secondary: 'btn-secondary',
    ghost: 'btn-ghost',
    danger: 'bg-red-500 text-white hover:bg-red-600',
    accent: 'bg-bg-0 text-fg-0 hover:bg-bg-1 border border-bd-1',
  };

  const sizes = {
    sm: 'btn-sm',
    md: '',
    lg: 'px-6 py-3 text-base',
  };

  const iconElement = loading ? (
    <Loader2 size={16} className="animate-spin" />
  ) : icon ? (
    <span className="[&>svg]:w-4 [&>svg]:h-4">{icon}</span>
  ) : null;

  return (
    <button
      className={cn(
        'btn',
        variants[variant],
        sizes[size],
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {!iconRight && iconElement}
      {children}
      {iconRight && iconElement}
    </button>
  );
}

// Link-style button with arrow (like "Upgrade now" in reference)
interface LinkButtonProps {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}

export function LinkButton({ children, onClick, className }: LinkButtonProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-2 px-4 py-2 bg-white rounded-full text-sm font-medium text-slate-900',
        'hover:bg-slate-50 transition-all',
        className
      )}
    >
      {children}
      <ChevronRight size={16} />
    </button>
  );
}

// Icon-only button
export function IconButton({
  icon,
  className,
  ...props
}: Omit<ButtonProps, 'children' | 'icon'> & { icon: ReactNode }) {
  return (
    <button
      className={cn(
        'p-2 rounded-xl hover:bg-slate-100 transition-colors [&>svg]:w-5 [&>svg]:h-5 text-slate-500',
        className
      )}
      {...props}
    >
      {icon}
    </button>
  );
}
