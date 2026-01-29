import { MoreHorizontal, ChevronDown, TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '../../lib/utils';

interface VisitItem {
  value: number;
  percentage: number;
  label: string;
  icon?: React.ReactNode;
  change: number;
}

interface VisitsByCountryProps {
  items?: VisitItem[];
  totalCountries?: number;
  totalPercentage?: number;
  region?: string;
}

const defaultItems: VisitItem[] = [
  { value: 4743, percentage: 50, label: 'Many Source', icon: <span className="text-red-500">▶</span>, change: 4.53 },
  { value: 9759, percentage: 100, label: 'All Socials Channels', icon: <span className="text-accent">◆</span>, change: 8.15 },
  { value: 604, percentage: 20, label: 'Socials Network', icon: <span className="text-orange">●</span>, change: -2.30 },
];

export function VisitsByCountry({
  items = defaultItems,
  totalCountries = 32,
  totalPercentage = 97,
  region = 'Europe',
}: VisitsByCountryProps) {
  const maxValue = Math.max(...items.map(i => i.value));

  return (
    <div className="alpha-card">
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-base font-semibold text-text-white">Visits by Country</h3>
        <div className="flex items-center gap-2">
          <button className="alpha-dropdown">
            <span>{region}</span>
            <ChevronDown size={14} />
          </button>
          <button className="alpha-menu-btn">
            <MoreHorizontal size={18} />
          </button>
        </div>
      </div>

      <p className="text-sm text-text-muted mb-6">
        {totalCountries} countries share {totalPercentage}% visits.
      </p>

      {/* Bars */}
      <div className="space-y-4">
        {items.map((item, index) => (
          <div key={index} className="alpha-h-bar">
            {/* Value */}
            <span className="alpha-h-bar-value">
              {item.value.toLocaleString()}
            </span>

            {/* Bar */}
            <div className="alpha-h-bar-track">
              <div
                className="alpha-h-bar-fill"
                style={{ width: `${(item.value / maxValue) * 100}%` }}
              />
            </div>

            {/* Badge */}
            <div className="alpha-h-bar-badge">
              {item.icon}
              <span>{item.label}</span>
            </div>

            {/* Change */}
            <div className={cn(
              'flex items-center gap-1 text-sm font-medium min-w-[70px] justify-end',
              item.change >= 0 ? 'text-success' : 'text-danger'
            )}>
              {item.change >= 0 ? (
                <TrendingUp size={14} />
              ) : (
                <TrendingDown size={14} />
              )}
              <span>{Math.abs(item.change).toFixed(2)}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}







