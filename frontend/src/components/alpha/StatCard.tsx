import { MoreHorizontal } from 'lucide-react';
import { cn } from '../../lib/utils';

interface StatCardProps {
  icon: React.ReactNode;
  iconBg?: string;
  label: string;
  value: string | number;
  unit?: string;
  change: {
    value: number;
    label: string;
  };
}

export function StatCard({
  icon,
  iconBg = 'bg-accent-muted',
  label,
  value,
  unit,
  change,
}: StatCardProps) {
  const isPositive = change.value >= 0;

  return (
    <div className="alpha-stat-card">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className={cn(
          'w-10 h-10 rounded-xl flex items-center justify-center',
          iconBg
        )}>
          {icon}
        </div>
        <button className="alpha-menu-btn">
          <MoreHorizontal size={18} />
        </button>
      </div>

      {/* Label */}
      <p className="alpha-stat-label">{label}</p>

      {/* Value */}
      <div className="flex items-baseline gap-1">
        <span className="alpha-stat-value">{value}</span>
        {unit && <span className="alpha-stat-unit">{unit}</span>}
      </div>

      {/* Change */}
      <p className={cn(
        'alpha-stat-change',
        isPositive ? 'positive' : 'negative'
      )}>
        {isPositive ? '+' : ''}{change.value}% {change.label}
      </p>
    </div>
  );
}







