import { useMemo } from 'react';
import { format } from 'date-fns';

interface HeatmapProps {
  data: {
    product_types: string[];
    weeks: string[];
    heatmap: Record<string, Record<string, number | null>>;
  };
  height?: number;
  colorScale?: string[]; // From low to high
}

// Dark theme color scale - from red (low) to green (high)
const darkColorScale = [
  'rgba(239, 68, 68, 0.8)',   // Red - low
  'rgba(245, 158, 11, 0.8)',  // Amber
  'rgba(234, 179, 8, 0.8)',   // Yellow
  'rgba(34, 197, 94, 0.6)',   // Light green
  'rgba(16, 185, 129, 0.9)',  // Teal/Green - high
];

export function Heatmap({ data, height = 400, colorScale = darkColorScale }: HeatmapProps) {
  const { product_types, weeks, heatmap } = data;

  // Calculate min/max for color scaling
  const allValues = useMemo(() => {
    const values: number[] = [];
    product_types.forEach(type => {
      weeks.forEach(week => {
        const value = heatmap[type]?.[week];
        if (value !== null && value !== undefined) {
          values.push(value);
        }
      });
    });
    return values;
  }, [product_types, weeks, heatmap]);

  const minValue = Math.min(...allValues, 0);
  const maxValue = Math.max(...allValues, 100);

  const getColor = (value: number | null) => {
    if (value === null || value === undefined) {
      return 'rgba(255, 255, 255, 0.05)'; // Dark gray for no data
    }
    const ratio = (value - minValue) / (maxValue - minValue || 1);
    const index = Math.floor(ratio * (colorScale.length - 1));
    return colorScale[index] || colorScale[colorScale.length - 1];
  };

  const getTextColor = (value: number | null) => {
    if (value === null) return 'rgba(255, 255, 255, 0.3)';
    return 'rgba(255, 255, 255, 0.9)';
  };

  const cellSize = Math.floor((height - 100) / Math.max(product_types.length, 1));
  const weekWidth = Math.max(80, Math.floor(800 / Math.max(weeks.length, 1)));

  return (
    <div className="w-full overflow-x-auto" style={{ height: `${height}px` }}>
      <div className="inline-flex flex-col gap-2">
        {/* Header - Weeks */}
        <div className="flex gap-1 pl-20">
          {weeks.map((week) => {
            const date = new Date(week);
            return (
              <div
                key={week}
                className="text-xs text-slate-500 font-medium flex items-center justify-center"
                style={{ width: `${weekWidth}px`, height: '30px' }}
              >
                <div className="transform -rotate-45 origin-center">
                  {format(date, 'MMM dd')}
                </div>
              </div>
            );
          })}
        </div>

        {/* Rows - Product Types */}
        <div className="flex flex-col gap-1">
          {product_types.map((type) => (
            <div key={type} className="flex items-center gap-2">
              {/* Product Type Label */}
              <div
                className="text-sm font-medium text-slate-400 whitespace-nowrap"
                style={{ width: '80px' }}
              >
                {type}
              </div>

              {/* Heatmap Cells */}
              <div className="flex gap-1">
                {weeks.map((week) => {
                  const value = heatmap[type]?.[week] ?? null;
                  const color = getColor(value);
                  const textColor = getTextColor(value);
                  const displayValue = value !== null ? `${value.toFixed(0)}%` : '—';

                  return (
                    <div
                      key={`${type}-${week}`}
                      className="flex items-center justify-center text-xs font-semibold rounded-lg border border-white/10 hover:border-white/20 hover:scale-105 transition-all cursor-pointer"
                      style={{
                        width: `${weekWidth}px`,
                        height: `${cellSize}px`,
                        backgroundColor: color,
                        color: textColor,
                        boxShadow: value !== null && value >= 70 ? '0 0 12px rgba(16, 185, 129, 0.3)' : 
                                   value !== null && value < 30 ? '0 0 12px rgba(239, 68, 68, 0.3)' : 'none',
                      }}
                      title={`${type} - ${format(new Date(week), 'MMM dd, yyyy')}: ${displayValue}`}
                    >
                      {value !== null ? `${value.toFixed(0)}%` : '—'}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 pl-20 pt-4">
          <span className="text-xs text-slate-500">OTD:</span>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-500 mr-1">Low</span>
            {colorScale.map((color, index) => (
              <div
                key={index}
                className="w-6 h-4 rounded border border-white/10"
                style={{ backgroundColor: color }}
              />
            ))}
            <span className="text-xs text-slate-500 ml-1">High</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-6 h-4 rounded border border-white/10" style={{ backgroundColor: 'rgba(255, 255, 255, 0.05)' }} />
            <span className="text-xs text-slate-500">No data</span>
          </div>
        </div>
      </div>
    </div>
  );
}
