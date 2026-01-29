import { cn } from '../../lib/utils';
import type { ReactNode } from 'react';

interface BadgeProps {
  children: ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'neutral' | 'accent' | 'primary' | 'teal';
  dot?: boolean;
  className?: string;
}

export function Badge({ children, variant = 'neutral', dot = false, className }: BadgeProps) {
  const variants = {
    default: 'badge-neutral',
    success: 'badge-success',
    warning: 'badge-warning',
    danger: 'badge-danger',
    neutral: 'badge-neutral',
    accent: 'badge-accent',
    primary: 'badge-primary',
    teal: 'badge-teal',
  };

  const dotColors = {
    default: 'status-dot-neutral',
    success: 'status-dot-success',
    warning: 'status-dot-warning',
    danger: 'status-dot-danger',
    neutral: 'status-dot-neutral',
    accent: 'bg-white',
    primary: 'bg-blue-500',
    teal: 'bg-teal-500',
  };

  return (
    <span className={cn('badge', variants[variant], className)}>
      {dot && <span className={cn('status-dot', dotColors[variant])} />}
      {children}
    </span>
  );
}

// Status indicator without text
export function StatusDot({ status }: { status: 'success' | 'warning' | 'danger' | 'neutral' }) {
  const colors = {
    success: 'status-dot-success',
    warning: 'status-dot-warning',
    danger: 'status-dot-danger',
    neutral: 'status-dot-neutral',
  };
  
  return <span className={cn('status-dot', colors[status])} />;
}

// Tag for categories (pill shaped like Remote, Part-time in reference)
interface TagProps {
  children: ReactNode;
  className?: string;
}

export function Tag({ children, className }: TagProps) {
  return (
    <span className={cn(
      'inline-flex items-center px-3 py-1 rounded-full text-xs font-medium',
      'bg-white/[0.05] text-slate-400 border border-white/[0.08]',
      className
    )}>
      {children}
    </span>
  );
}
