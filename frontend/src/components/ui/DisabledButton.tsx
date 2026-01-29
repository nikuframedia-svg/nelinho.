import { cn } from '../../lib/utils';
import { SimpleTooltip } from './Tooltip';

interface DisabledButtonProps {
  children: React.ReactNode;
  icon?: React.ReactNode;
  tooltip?: string;
  variant?: 'primary' | 'secondary';
  size?: 'sm' | 'md';
  className?: string;
}

export function DisabledButton({ 
  children, 
  icon, 
  tooltip = 'Funcionalidade em desenvolvimento',
  variant = 'primary',
  size = 'md',
  className 
}: DisabledButtonProps) {
  return (
    <SimpleTooltip content={tooltip}>
      <button 
        disabled
        className={cn(
          "flex items-center gap-2 rounded-lg font-medium transition-colors cursor-not-allowed opacity-60",
          size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm',
          variant === 'primary' 
            ? 'bg-slate-400 text-white' 
            : 'bg-slate-100 text-slate-400 border border-slate-200',
          className
        )}
        aria-disabled="true"
      >
        {icon}
        {children}
      </button>
    </SimpleTooltip>
  );
}

// For icon-only buttons
export function DisabledIconButton({ 
  icon, 
  tooltip = 'Funcionalidade em desenvolvimento',
  className 
}: { 
  icon: React.ReactNode; 
  tooltip?: string;
  className?: string;
}) {
  return (
    <SimpleTooltip content={tooltip}>
      <button 
        disabled
        className={cn(
          "p-2 rounded-lg text-slate-300 cursor-not-allowed",
          className
        )}
        aria-disabled="true"
      >
        {icon}
      </button>
    </SimpleTooltip>
  );
}










