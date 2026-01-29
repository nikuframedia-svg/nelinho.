import {
  BarChart as RechartsBar,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { ChartDataPoint } from '../../types';
import { formatCompactNumber } from '../../lib/utils';

interface BarChartProps {
  data: ChartDataPoint[];
  height?: number;
  color?: string;
  secondaryColor?: string;
  showGrid?: boolean;
  showAxis?: boolean;
  horizontal?: boolean;
  stacked?: boolean;
  glowEffect?: boolean;
  dataKey?: string;
}

export function BarChart({
  data,
  height = 160,
  color = '#14b8a6',
  secondaryColor,
  showGrid = false,
  showAxis = true,
  horizontal = false,
  stacked = false,
  glowEffect = true,
}: BarChartProps) {
  const gradientId = `bar-gradient-${color.replace('#', '')}`;
  
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsBar
        data={data}
        layout={horizontal ? 'vertical' : 'horizontal'}
        margin={{ top: 4, right: 4, left: horizontal ? 0 : -20, bottom: 0 }}
        barCategoryGap="20%"
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={1} />
            <stop offset="100%" stopColor={color} stopOpacity={0.6} />
          </linearGradient>
          {secondaryColor && (
            <linearGradient id={`${gradientId}-secondary`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={secondaryColor} stopOpacity={1} />
              <stop offset="100%" stopColor={secondaryColor} stopOpacity={0.6} />
            </linearGradient>
          )}
        </defs>
        {showGrid && (
          <CartesianGrid 
            strokeDasharray="3 3" 
            stroke="rgba(255, 255, 255, 0.06)" 
            vertical={!horizontal} 
            horizontal={horizontal}
          />
        )}
        {showAxis && (
          horizontal ? (
            <>
              <XAxis 
                type="number" 
                axisLine={false} 
                tickLine={false} 
                tick={{ fontSize: 11, fill: '#64748b' }}
                tickFormatter={formatCompactNumber}
              />
              <YAxis 
                type="category" 
                dataKey="name" 
                axisLine={false} 
                tickLine={false} 
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                width={80}
              />
            </>
          ) : (
            <>
              <XAxis 
                dataKey="name" 
                axisLine={false} 
                tickLine={false} 
                tick={{ fontSize: 11, fill: '#64748b' }}
                dy={8}
              />
              <YAxis 
                axisLine={false} 
                tickLine={false} 
                tick={{ fontSize: 11, fill: '#64748b' }}
                tickFormatter={formatCompactNumber}
                width={45}
              />
            </>
          )
        )}
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
          cursor={{ fill: 'rgba(255, 255, 255, 0.03)' }}
        />
        <Bar
          dataKey="value"
          fill={`url(#${gradientId})`}
          radius={[4, 4, 0, 0]}
          stackId={stacked ? 'stack' : undefined}
          style={glowEffect ? { filter: `drop-shadow(0 0 6px ${color}40)` } : undefined}
        >
          {data.map((entry, index) => (
            <Cell 
              key={`cell-${index}`} 
              fill={entry.value2 !== undefined && secondaryColor ? `url(#${gradientId}-secondary)` : `url(#${gradientId})`} 
            />
          ))}
        </Bar>
        {secondaryColor && stacked && (
          <Bar 
            dataKey="value2" 
            fill={`url(#${gradientId}-secondary)`} 
            radius={[4, 4, 0, 0]} 
            stackId="stack" 
          />
        )}
      </RechartsBar>
    </ResponsiveContainer>
  );
}
