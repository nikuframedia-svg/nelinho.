/**
 * TrendIndicator
 * 
 * Shows trend direction (↑ ↓ →) with percentage change.
 * Color-coded based on whether increase is good or bad.
 */

import { TrendingUp, TrendingDown, Minus, ArrowUp, ArrowDown } from 'lucide-react';

interface TrendIndicatorProps {
  value: number; // Percentage change
  inverted?: boolean; // If true, decrease is good (e.g., for errors, costs)
  showIcon?: boolean;
  showValue?: boolean;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'compact' | 'badge';
  className?: string;
}

export function TrendIndicator({
  value,
  inverted = false,
  showIcon = true,
  showValue = true,
  size = 'md',
  variant = 'default',
  className = '',
}: TrendIndicatorProps) {
  const isPositive = value > 0;
  const isNeutral = value === 0;
  const isGood = inverted ? !isPositive : isPositive;

  const getColor = () => {
    if (isNeutral) return 'text-text-tertiary';
    return isGood ? 'text-emerald-400' : 'text-red-400';
  };

  const getBgColor = () => {
    if (isNeutral) return 'bg-text-tertiary/10';
    return isGood ? 'bg-emerald-400/10' : 'bg-red-400/10';
  };

  const sizeClasses = {
    sm: { icon: 12, text: 'text-xs', padding: 'px-1.5 py-0.5' },
    md: { icon: 14, text: 'text-sm', padding: 'px-2 py-1' },
    lg: { icon: 16, text: 'text-base', padding: 'px-2.5 py-1.5' },
  };

  const { icon: iconSize, text: textClass, padding } = sizeClasses[size];

  const Icon = isNeutral
    ? Minus
    : isPositive
    ? variant === 'compact' ? ArrowUp : TrendingUp
    : variant === 'compact' ? ArrowDown : TrendingDown;

  const formattedValue = `${isPositive ? '+' : ''}${value.toFixed(1)}%`;

  if (variant === 'compact') {
    return (
      <span className={`inline-flex items-center gap-0.5 ${getColor()} ${className}`}>
        {showIcon && <Icon size={iconSize} />}
        {showValue && <span className={textClass}>{formattedValue}</span>}
      </span>
    );
  }

  if (variant === 'badge') {
    return (
      <span
        className={`inline-flex items-center gap-1 ${padding} ${getBgColor()} ${getColor()} rounded-full ${className}`}
      >
        {showIcon && <Icon size={iconSize} />}
        {showValue && <span className={`${textClass} font-medium`}>{formattedValue}</span>}
      </span>
    );
  }

  // Default variant
  return (
    <span className={`inline-flex items-center gap-1 ${getColor()} ${className}`}>
      {showIcon && <Icon size={iconSize} />}
      {showValue && <span className={`${textClass} font-medium`}>{formattedValue}</span>}
    </span>
  );
}

export default TrendIndicator;

