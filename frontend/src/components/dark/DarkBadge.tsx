import type { ReactNode } from 'react';

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'accent' | 'primary' | 'teal';
type BadgeSize = 'sm' | 'md';

interface DarkBadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  icon?: ReactNode;
  /** Pulse subtil para chamar atenção (apaga com prefers-reduced-motion). */
  pulse?: boolean;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  success: 'badge-success',
  warning: 'badge-warning',
  danger: 'badge-danger',
  info: 'badge-primary',
  neutral: 'badge-neutral',
  accent: 'badge-accent',
  primary: 'badge-primary',
  teal: 'badge-teal',
};

const dotClasses: Record<BadgeVariant, string> = {
  success: 'status-dot-success',
  warning: 'status-dot-warning',
  danger: 'status-dot-danger',
  info: 'bg-blue',
  neutral: 'status-dot-neutral',
  accent: 'bg-accent',
  primary: 'bg-blue',
  teal: 'bg-accent',
};

const sizeClasses = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-xs',
};

export function DarkBadge({
  children,
  variant = 'neutral',
  size = 'md',
  dot = false,
  icon,
  pulse = false,
  className = '',
}: DarkBadgeProps) {
  return (
    <span
      className={`badge-dark ${variantClasses[variant]} ${sizeClasses[size]} ${pulse ? 'animate-pulse motion-reduce:animate-none' : ''} ${className}`}
    >
      {dot && (
        <span className={`status-dot ${dotClasses[variant]}`} />
      )}
      {icon && <span className="flex-shrink-0">{icon}</span>}
      {children}
    </span>
  );
}

// Status Badge with built-in status logic
interface StatusBadgeProps {
  status: 'active' | 'inactive' | 'pending' | 'completed' | 'error' | 'warning' | 'processing';
  size?: BadgeSize;
  className?: string;
}

const statusConfig: Record<string, { variant: BadgeVariant; label: string }> = {
  active: { variant: 'success', label: 'Active' },
  inactive: { variant: 'neutral', label: 'Inactive' },
  pending: { variant: 'warning', label: 'Pending' },
  completed: { variant: 'success', label: 'Completed' },
  error: { variant: 'danger', label: 'Error' },
  warning: { variant: 'warning', label: 'Warning' },
  processing: { variant: 'info', label: 'Processing' },
};

export function StatusBadge({ status, size = 'md', className = '' }: StatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.inactive;
  
  return (
    <DarkBadge variant={config.variant} size={size} dot className={className}>
      {config.label}
    </DarkBadge>
  );
}

