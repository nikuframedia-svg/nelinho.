import type { SelectHTMLAttributes, ReactNode } from 'react';
import { forwardRef } from 'react';
import { ChevronDown } from 'lucide-react';

interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface DarkSelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label?: string;
  error?: string;
  hint?: string;
  options: SelectOption[];
  placeholder?: string;
  containerClassName?: string;
  icon?: ReactNode;
}

export const DarkSelect = forwardRef<HTMLSelectElement, DarkSelectProps>(
  ({ 
    label, 
    error, 
    hint, 
    options, 
    placeholder,
    containerClassName = '',
    className = '',
    icon,
    ...props 
  }, ref) => {
    return (
      <div className={containerClassName}>
        {label && (
          <label className="block text-sm font-medium text-text-secondary mb-1.5">
            {label}
          </label>
        )}
        
        <div className="relative">
          {icon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary pointer-events-none">
              {icon}
            </div>
          )}
          
          <select
            ref={ref}
            className={`
              w-full
              appearance-none
              bg-bg-elevated
              border border-border-subtle
              rounded-lg
              px-4 py-2.5
              pr-10
              text-sm text-text-primary
              cursor-pointer
              transition-colors duration-200
              hover:border-border-hover
              focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20
              ${icon ? 'pl-10' : ''}
              ${error ? 'border-danger focus:border-danger focus:ring-danger/20' : ''}
              ${className}
            `}
            {...props}
          >
            {placeholder && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}
            {options.map((option) => (
              <option 
                key={option.value} 
                value={option.value}
                disabled={option.disabled}
              >
                {option.label}
              </option>
            ))}
          </select>
          
          <div className="absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary pointer-events-none">
            <ChevronDown className="w-4 h-4" />
          </div>
        </div>
        
        {error && (
          <p className="mt-1.5 text-xs text-danger">{error}</p>
        )}
        
        {hint && !error && (
          <p className="mt-1.5 text-xs text-text-tertiary">{hint}</p>
        )}
      </div>
    );
  }
);

DarkSelect.displayName = 'DarkSelect';

// Button-style dropdown (for filters/actions)
interface DarkDropdownButtonProps {
  label: string;
  value?: string;
  onClick?: () => void;
  className?: string;
}

export function DarkDropdownButton({ 
  label, 
  value, 
  onClick, 
  className = '' 
}: DarkDropdownButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`
        alpha-dropdown
        ${className}
      `}
    >
      <span className="text-text-tertiary">{label}:</span>
      <span className="text-text-white">{value || 'All'}</span>
      <ChevronDown className="w-4 h-4 text-text-tertiary" />
    </button>
  );
}

