import type { ReactNode } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface DarkStatCardProps {
  icon?: ReactNode;
  iconBg?: string;
  label: string;
  value: string | number;
  unit?: string;
  change?: { value: number; label?: string };
  trend?: 'up' | 'down' | 'neutral';
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  subtitle?: ReactNode;
}

const sizeClasses = {
  sm: {
    card: 'p-3',
    value: 'text-xl',
    unit: 'text-sm',
    label: 'text-xs',
    icon: 'w-8 h-8',
    iconInner: 'w-4 h-4',
  },
  md: {
    card: 'p-4',
    value: 'text-2xl',
    unit: 'text-base',
    label: 'text-sm',
    icon: 'w-10 h-10',
    iconInner: 'w-5 h-5',
  },
  lg: {
    card: 'p-5',
    value: 'text-3xl',
    unit: 'text-lg',
    label: 'text-base',
    icon: 'w-12 h-12',
    iconInner: 'w-6 h-6',
  },
};

export function DarkStatCard({
  icon,
  iconBg = 'bg-accent-muted',
  label,
  value,
  unit,
  change,
  trend = 'neutral',
  className = '',
  size = 'md',
}: DarkStatCardProps) {
  const sizes = sizeClasses[size];

  const getTrendIcon = () => {
    switch (trend) {
      case 'up':
        return <TrendingUp className="w-3.5 h-3.5" />;
      case 'down':
        return <TrendingDown className="w-3.5 h-3.5" />;
      default:
        return <Minus className="w-3.5 h-3.5" />;
    }
  };

  const getTrendColor = () => {
    switch (trend) {
      case 'up':
        return 'text-success';
      case 'down':
        return 'text-danger';
      default:
        return 'text-text-tertiary';
    }
  };

  return (
    <div className={`alpha-stat-card ${sizes.card} ${className}`}>
      {/* Header with icon */}
      <div className="flex items-start justify-between">
        {icon && (
          <div className={`${sizes.icon} flex items-center justify-center rounded-xl ${iconBg} text-accent`}>
            {icon}
          </div>
        )}
        
        {/* Change indicator */}
        {change && (
          <div className={`flex items-center gap-1 ${getTrendColor()}`}>
            {getTrendIcon()}
            <span className="text-xs font-medium">
              {change.value > 0 ? '+' : ''}{change.value}%
            </span>
          </div>
        )}
      </div>

      {/* Value */}
      <div className="flex items-baseline gap-1 mt-3">
        <span className={`${sizes.value} font-bold text-text-white tabular-nums`}>
          {typeof value === 'number' ? value.toLocaleString() : value}
        </span>
        {unit && (
          <span className={`${sizes.unit} font-medium text-text-gray`}>
            {unit}
          </span>
        )}
      </div>

      {/* Label */}
      <p className={`${sizes.label} text-text-gray mt-1`}>
        {label}
      </p>

      {/* Change label */}
      {change?.label && (
        <p className="text-xs text-text-tertiary mt-1">
          {change.label}
        </p>
      )}
    </div>
  );
}

