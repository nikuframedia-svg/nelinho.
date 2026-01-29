import type { InputHTMLAttributes, ReactNode } from 'react';
import { forwardRef } from 'react';

interface DarkInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  containerClassName?: string;
}

export const DarkInput = forwardRef<HTMLInputElement, DarkInputProps>(
  ({ 
    label, 
    error, 
    hint, 
    leftIcon, 
    rightIcon, 
    containerClassName = '',
    className = '',
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
          {leftIcon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary">
              {leftIcon}
            </div>
          )}
          
          <input
            ref={ref}
            className={`
              w-full
              glass-input
              px-4 py-2.5
              text-sm text-text-primary
              placeholder:text-text-tertiary
              ${leftIcon ? 'pl-10' : ''}
              ${rightIcon ? 'pr-10' : ''}
              ${error ? 'border-danger focus:border-danger focus:ring-danger/20' : ''}
              ${className}
            `}
            {...props}
          />
          
          {rightIcon && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary">
              {rightIcon}
            </div>
          )}
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

DarkInput.displayName = 'DarkInput';

// Textarea variant
interface DarkTextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
  containerClassName?: string;
}

export const DarkTextarea = forwardRef<HTMLTextAreaElement, DarkTextareaProps>(
  ({ label, error, hint, containerClassName = '', className = '', ...props }, ref) => {
    return (
      <div className={containerClassName}>
        {label && (
          <label className="block text-sm font-medium text-text-secondary mb-1.5">
            {label}
          </label>
        )}
        
        <textarea
          ref={ref}
          className={`
            w-full
            glass-input
            px-4 py-2.5
            text-sm text-text-primary
            placeholder:text-text-tertiary
            min-h-[100px]
            resize-y
            ${error ? 'border-danger focus:border-danger focus:ring-danger/20' : ''}
            ${className}
          `}
          {...props}
        />
        
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

DarkTextarea.displayName = 'DarkTextarea';

// Search Input variant
interface DarkSearchInputProps extends Omit<DarkInputProps, 'leftIcon'> {
  onClear?: () => void;
}

export function DarkSearchInput({ onClear, value, ...props }: DarkSearchInputProps) {
  return (
    <DarkInput
      leftIcon={
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      }
      rightIcon={
        value && onClear ? (
          <button 
            onClick={onClear}
            className="hover:text-text-white transition-colors"
            type="button"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        ) : undefined
      }
      value={value}
      {...props}
    />
  );
}

