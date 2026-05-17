import type { ReactNode, ButtonHTMLAttributes } from 'react';
import { Loader2 } from 'lucide-react';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'accent' | 'outline';
type ButtonSize = 'sm' | 'md' | 'lg';

interface DarkButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: ReactNode;
  iconRight?: ReactNode;
  loading?: boolean;
  fullWidth?: boolean;
  /** Quando true, aplica shadow-glow subtil no hover (cor derivada da variant). */
  glow?: boolean;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-bg-base hover:bg-accent-light focus:ring-accent/30',
  secondary: 'bg-bg-elevated text-text-secondary hover:bg-bg-card-hover hover:text-text-white border border-border-subtle',
  ghost: 'bg-transparent text-text-secondary hover:bg-bg-elevated hover:text-text-white',
  danger: 'bg-danger text-white hover:bg-danger-light focus:ring-danger/30',
  accent: 'bg-orange text-white hover:bg-orange-light focus:ring-orange/30',
  outline: 'bg-transparent text-text-white border border-border-subtle hover:bg-bg-elevated hover:border-border-hover',
};

const glowClasses: Record<ButtonVariant, string> = {
  primary: 'hover:shadow-glow-teal',
  secondary: '',
  ghost: '',
  danger: 'hover:shadow-glow-red',
  accent: 'hover:shadow-glow-amber',
  outline: '',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-xs gap-1.5',
  md: 'px-4 py-2 text-sm gap-2',
  lg: 'px-6 py-3 text-base gap-2.5',
};

export function DarkButton({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  iconRight,
  loading = false,
  fullWidth = false,
  glow = false,
  disabled,
  className = '',
  ...props
}: DarkButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <button
      className={`
        inline-flex items-center justify-center
        font-medium rounded-lg
        transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base
        ${variantClasses[variant]}
        ${sizeClasses[size]}
        ${glow && !isDisabled ? glowClasses[variant] : ''}
        ${fullWidth ? 'w-full' : ''}
        ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}
        ${className}
      `}
      disabled={isDisabled}
      {...props}
    >
      {loading ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : icon ? (
        <span className="flex-shrink-0">{icon}</span>
      ) : null}
      <span>{children}</span>
      {iconRight && !loading && (
        <span className="flex-shrink-0">{iconRight}</span>
      )}
    </button>
  );
}

// Pill Button variant (commonly used for tabs/filters)
interface DarkPillButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  active?: boolean;
  count?: number;
}

export function DarkPillButton({
  children,
  active = false,
  count,
  className = '',
  ...props
}: DarkPillButtonProps) {
  return (
    <button
      className={`
        inline-flex items-center gap-2
        px-4 py-2 rounded-full
        text-sm font-medium
        transition-all duration-200
        ${active 
          ? 'bg-bg-elevated text-text-white border border-border-hover' 
          : 'bg-transparent text-text-secondary hover:bg-bg-elevated hover:text-text-white border border-transparent'
        }
        ${className}
      `}
      {...props}
    >
      {children}
      {count !== undefined && (
        <span className={`
          px-1.5 py-0.5 rounded-full text-xs
          ${active ? 'bg-accent/20 text-accent' : 'bg-bg-card text-text-tertiary'}
        `}>
          {count}
        </span>
      )}
    </button>
  );
}

// Icon Button variant
interface DarkIconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: ReactNode;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'ghost';
}

const iconSizeClasses = {
  sm: 'w-8 h-8',
  md: 'w-10 h-10',
  lg: 'w-12 h-12',
};

export function DarkIconButton({
  icon,
  size = 'md',
  variant = 'default',
  className = '',
  ...props
}: DarkIconButtonProps) {
  return (
    <button
      className={`
        ${iconSizeClasses[size]}
        flex items-center justify-center
        rounded-lg
        transition-all duration-200
        ${variant === 'ghost' 
          ? 'text-text-tertiary hover:text-text-white hover:bg-bg-elevated' 
          : 'bg-bg-secondary text-text-secondary hover:bg-bg-elevated hover:text-text-white'
        }
        ${className}
      `}
      {...props}
    >
      {icon}
    </button>
  );
}

