import {
  LineChart as RechartsLine,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
} from 'recharts';
import type { ChartDataPoint } from '../../types';
import { formatCompactNumber } from '../../lib/utils';

interface LineChartProps {
  data: ChartDataPoint[];
  height?: number;
  color?: string;
  showGrid?: boolean;
  showAxis?: boolean;
  showTooltip?: boolean;
  showArea?: boolean;
  glowColor?: string;
  dataKey?: string;
}

export function LineChart({
  data,
  height = 160,
  color = '#14b8a6',
  showGrid = false,
  showAxis = true,
  showTooltip = true,
  showArea = false,
  glowColor,
}: LineChartProps) {
  const gradientId = `gradient-${color.replace('#', '')}`;
  const actualGlowColor = glowColor || color;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsLine data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        {showGrid && (
          <CartesianGrid 
            strokeDasharray="3 3" 
            stroke="rgba(255, 255, 255, 0.06)" 
            vertical={false} 
          />
        )}
        {showAxis && (
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
        )}
        {showTooltip && (
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
            cursor={{ stroke: 'rgba(255, 255, 255, 0.1)', strokeWidth: 1 }}
          />
        )}
        {showArea && (
          <Area
            type="monotone"
            dataKey="value"
            stroke="transparent"
            fill={`url(#${gradientId})`}
          />
        )}
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          dot={false}
          activeDot={{ 
            r: 5, 
            fill: color, 
            stroke: '#111827', 
            strokeWidth: 2,
            style: { filter: `drop-shadow(0 0 6px ${actualGlowColor})` }
          }}
          style={{ filter: `drop-shadow(0 0 4px ${actualGlowColor}40)` }}
        />
      </RechartsLine>
    </ResponsiveContainer>
  );
}
