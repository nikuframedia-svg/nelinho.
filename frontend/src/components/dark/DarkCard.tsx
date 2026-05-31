import type { ReactNode } from 'react';
import { ChevronDown, MoreHorizontal } from 'lucide-react';

interface DropdownOption {
  label: string;
  value: string;
  onClick?: () => void;
}

interface DarkCardProps {
  children?: ReactNode;
  title?: string;
  subtitle?: string;
  icon?: ReactNode;
  action?: ReactNode;
  dropdown?: { label: string; options: DropdownOption[] };
  footer?: ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  interactive?: boolean;
  onClick?: () => void;
}

const paddingClasses = {
  none: '',
  sm: 'p-4',
  md: 'p-5',
  lg: 'p-6',
};

export function DarkCard({
  children,
  title,
  subtitle,
  icon,
  action,
  dropdown,
  footer,
  className = '',
  padding = 'md',
  interactive = false,
  onClick,
}: DarkCardProps) {
  const baseClasses = interactive 
    ? 'alpha-card card-interactive cursor-pointer' 
    : 'alpha-card';
  
  return (
    <div 
      className={`${baseClasses} ${paddingClasses[padding]} ${className}`}
      onClick={onClick}
    >
      {/* Card Header */}
      {(title || icon || action || dropdown) && (
        <div className="alpha-card-header">
          <div className="alpha-card-title">
            {icon && <div className="alpha-card-icon">{icon}</div>}
            <div>
              {title && (
                <h3 className="text-base font-semibold text-text-white">
                  {title}
                </h3>
              )}
              {subtitle && (
                <p className="text-sm text-text-gray mt-0.5">{subtitle}</p>
              )}
            </div>
          </div>

          <div className="alpha-card-actions">
            {dropdown && (
              <button className="alpha-dropdown">
                {dropdown.label}
                <ChevronDown className="w-4 h-4" />
              </button>
            )}
            {action}
            {!action && !dropdown && (
              <button className="alpha-menu-btn">
                <MoreHorizontal className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Card Content */}
      <div className={title || icon ? '' : ''}>{children}</div>

      {/* Card Footer */}
      {footer && (
        <div className="mt-4 pt-4 border-t border-border-subtle">
          {footer}
        </div>
      )}
    </div>
  );
}

