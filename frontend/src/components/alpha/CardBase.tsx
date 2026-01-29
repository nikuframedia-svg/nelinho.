import { MoreHorizontal, ChevronDown } from 'lucide-react';
import { cn } from '../../lib/utils';

interface DropdownOption {
  label: string;
  value: string;
}

interface CardBaseProps {
  icon?: React.ReactNode;
  iconBg?: string;
  title: string;
  dropdown?: {
    label: string;
    options: DropdownOption[];
    value?: string;
    onChange?: (value: string) => void;
  };
  showMenu?: boolean;
  footer?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  noPadding?: boolean;
}

export function CardBase({
  icon,
  iconBg = 'bg-accent-muted',
  title,
  dropdown,
  showMenu = true,
  footer,
  children,
  className,
  noPadding = false,
}: CardBaseProps) {
  return (
    <div className={cn('alpha-card', className)}>
      {/* Header */}
      <div className="alpha-card-header">
        <div className="alpha-card-title">
          {icon && (
            <div className={cn('alpha-card-icon', iconBg)}>
              {icon}
            </div>
          )}
          <span className="text-base font-semibold text-text-white">{title}</span>
        </div>

        <div className="alpha-card-actions">
          {dropdown && (
            <button className="alpha-dropdown">
              <span>{dropdown.label}</span>
              <ChevronDown size={14} />
            </button>
          )}
          {showMenu && (
            <button className="alpha-menu-btn">
              <MoreHorizontal size={18} />
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className={cn(!noPadding && 'mt-4')}>
        {children}
      </div>

      {/* Footer */}
      {footer && (
        <div className="mt-4 pt-4 border-t border-border-subtle">
          {footer}
        </div>
      )}
    </div>
  );
}







