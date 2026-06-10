import { cn } from '../../lib/utils';

interface PillBarChartProps {
  data: { label: string; value: number }[];
  height?: number;
  maxValue?: number;
  activeIndex?: number;
  onSelect?: (index: number) => void;
  showTooltip?: boolean;
}

export function PillBarChart({
  data,
  height = 180,
  maxValue,
  activeIndex,
  onSelect,
  showTooltip = true,
}: PillBarChartProps) {
  if (data.length === 0) return null;
  const max = maxValue || Math.max(...data.map(d => d.value), 0);
  
  const formatValue = (value: number) => {
    if (value >= 1000) {
      return `$${(value / 1000).toFixed(1)}k`;
    }
    return `$${value}`;
  };
  
  return (
    <div className="flex items-end justify-center gap-3" style={{ height }}>
      {data.map((item, index) => {
        const barHeight = Math.max(40, (item.value / max) * (height - 60));
        const isActive = activeIndex === index;
        
        return (
          <div
            key={index}
            className="flex flex-col items-center gap-3 cursor-pointer group"
            onClick={() => onSelect?.(index)}
          >
            {/* Tooltip */}
            <div className={cn(
              "transition-all duration-300 transform",
              showTooltip && isActive 
                ? "opacity-100 translate-y-0" 
                : "opacity-0 translate-y-2 pointer-events-none"
            )}>
              <div className="chart-tooltip">
                {formatValue(item.value)}
              </div>
            </div>
            
            {/* Bar with dot */}
            <div className="relative">
              {/* Dot at top */}
              <div className={cn(
                "pill-bar-dot",
                isActive && "active"
              )} 
              style={{
                background: isActive ? '#3b82f6' : '#cbd5e1',
                boxShadow: isActive ? '0 2px 8px rgba(59, 130, 246, 0.4)' : '0 2px 4px rgba(0, 0, 0, 0.1)'
              }}
              />
              
              {/* Pill bar */}
              <div
                className={cn(
                  "w-10 rounded-full transition-all duration-300",
                  isActive ? "bg-gradient-to-b from-slate-200 to-slate-250" : "bg-gradient-to-b from-slate-100 to-slate-150",
                  "group-hover:from-slate-150 group-hover:to-slate-200"
                )}
                style={{ 
                  height: barHeight,
                  background: isActive 
                    ? 'linear-gradient(180deg, #e2e8f0 0%, #cbd5e1 100%)' 
                    : 'linear-gradient(180deg, #f1f5f9 0%, #e2e8f0 100%)',
                  boxShadow: 'inset 0 2px 4px rgba(0, 0, 0, 0.03)'
                }}
              />
            </div>
            
            {/* Label */}
            <div
              className={cn(
                "w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-300",
                isActive 
                  ? "bg-slate-900 text-white shadow-lg" 
                  : "text-slate-400 group-hover:text-slate-600 group-hover:bg-slate-100"
              )}
              style={{
                boxShadow: isActive ? '0 4px 12px rgba(15, 23, 42, 0.3)' : 'none'
              }}
            >
              {item.label}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Horizontal segment progress bar
interface SegmentProgressProps {
  total: number;
  filled: number;
  height?: number;
}

export function SegmentProgress({ total, filled, height = 28 }: SegmentProgressProps) {
  const segments = Array.from({ length: total }, (_, i) => i < filled);
  
  return (
    <div className="progress-segments" style={{ height }}>
      {segments.map((isFilled, index) => (
        <div
          key={index}
          className={cn(
            "progress-segment",
            isFilled ? "filled" : "empty"
          )}
          style={{
            transitionDelay: `${index * 20}ms`
          }}
        />
      ))}
    </div>
  );
}
