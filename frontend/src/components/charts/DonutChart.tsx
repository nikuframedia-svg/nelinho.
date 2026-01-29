import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { ChartDataPoint } from '../../types';
import { formatCompactNumber } from '../../lib/utils';

interface DonutChartProps {
  data: ChartDataPoint[];
  height?: number;
  colors?: string[];
  innerRadius?: number;
  outerRadius?: number;
  centerLabel?: string;
  centerValue?: string | number;
  glowEffect?: boolean;
}

// Dark theme optimized colors with good contrast
const DEFAULT_COLORS = ['#14b8a6', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#10b981', '#ec4899'];

export function DonutChart({
  data,
  height = 160,
  colors = DEFAULT_COLORS,
  innerRadius = 50,
  outerRadius = 70,
  centerLabel,
  centerValue,
  glowEffect = true,
}: DonutChartProps) {
  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <defs>
            {colors.map((_color, index) => (
              <filter key={`glow-${index}`} id={`donut-glow-${index}`} x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="2" result="coloredBlur" />
                <feMerge>
                  <feMergeNode in="coloredBlur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            ))}
          </defs>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            paddingAngle={3}
            dataKey="value"
            strokeWidth={0}
          >
            {data.map((_, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={colors[index % colors.length]}
                style={glowEffect ? { filter: `drop-shadow(0 0 4px ${colors[index % colors.length]}60)` } : undefined}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(17, 24, 39, 0.95)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '12px',
              padding: '12px 16px',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
              backdropFilter: 'blur(8px)',
            }}
            labelStyle={{ color: '#94a3b8', fontSize: 11, marginBottom: 4 }}
            itemStyle={{ color: '#f1f5f9', fontSize: 13, fontWeight: 600 }}
            formatter={(value) => [formatCompactNumber(value as number), '']}
          />
        </PieChart>
      </ResponsiveContainer>
      {(centerLabel || centerValue) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          {centerValue && <span className="text-xl font-semibold text-slate-100">{centerValue}</span>}
          {centerLabel && <span className="text-[11px] text-slate-500 mt-0.5">{centerLabel}</span>}
        </div>
      )}
    </div>
  );
}

interface DonutLegendProps {
  data: ChartDataPoint[];
  colors?: string[];
  compact?: boolean;
}

export function DonutLegend({ data, colors = DEFAULT_COLORS, compact = false }: DonutLegendProps) {
  if (compact) {
    return (
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {data.map((item, index) => (
          <div key={item.name} className="flex items-center gap-1.5">
            <div
              className="w-2 h-2 rounded-full"
              style={{ 
                backgroundColor: colors[index % colors.length],
                boxShadow: `0 0 4px ${colors[index % colors.length]}60`
              }}
            />
            <span className="text-xs text-slate-500">{item.name}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {data.map((item, index) => (
        <div key={item.name} className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div
              className="w-2.5 h-2.5 rounded-full"
              style={{ 
                backgroundColor: colors[index % colors.length],
                boxShadow: `0 0 4px ${colors[index % colors.length]}60`
              }}
            />
            <span className="text-[13px] text-slate-400">{item.name}</span>
          </div>
          <span className="text-[13px] font-semibold text-slate-200 tabular-nums">
            {formatCompactNumber(item.value)}
          </span>
        </div>
      ))}
    </div>
  );
}
