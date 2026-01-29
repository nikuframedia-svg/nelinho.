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
import { formatCompactNumber } from '../../lib/utils';

interface WaterfallDataPoint {
  name: string;
  value: number;
  cumulative?: number; // Cumulative value up to this point
  isSubtotal?: boolean; // Whether this is a subtotal row
}

interface WaterfallChartProps {
  data: WaterfallDataPoint[];
  height?: number;
  positiveColor?: string;
  negativeColor?: string;
  subtotalColor?: string;
  showGrid?: boolean;
  showAxis?: boolean;
}

export function WaterfallChart({
  data,
  height = 300,
  positiveColor = '#22c55e',
  negativeColor = '#ef4444',
  subtotalColor = '#3b82f6',
  showGrid = true,
  showAxis = true,
}: WaterfallChartProps) {
  // Transform data for waterfall display
  const transformedData = data.map((item, index) => {
    const prevCumulative = index > 0 ? data[index - 1].cumulative || 0 : 0;
    const currentValue = item.value;
    const newCumulative = prevCumulative + currentValue;

    return {
      ...item,
      start: prevCumulative,
      end: newCumulative,
      cumulative: newCumulative,
      isPositive: currentValue >= 0,
    };
  });

  // For waterfall, we need to render each bar starting from the previous cumulative value
  // Recharts doesn't support waterfall natively, so we'll use stacked bars with a transparent base
  const chartData = transformedData.map((item) => ({
    name: item.name,
    base: item.start,
    value: item.value,
    cumulative: item.cumulative,
    isSubtotal: item.isSubtotal || false,
    isPositive: item.isPositive,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsBar
        data={chartData}
        margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
      >
        {showGrid && (
          <CartesianGrid 
            strokeDasharray="3 3" 
            stroke="#e2e8f0" 
            vertical={false}
            strokeOpacity={0.8}
          />
        )}
        {showAxis && (
          <>
            <XAxis 
              dataKey="name" 
              axisLine={false} 
              tickLine={false} 
              tick={{ fontSize: 11, fill: '#94a3b8' }}
              dy={8}
            />
            <YAxis 
              axisLine={false} 
              tickLine={false} 
              tick={{ fontSize: 11, fill: '#94a3b8' }}
              tickFormatter={formatCompactNumber}
              width={60}
            />
          </>
        )}
        <Tooltip
          contentStyle={{
            backgroundColor: '#0f172a',
            border: 'none',
            borderRadius: '6px',
            padding: '8px 12px',
            boxShadow: '0 4px 12px rgb(0 0 0 / 0.15)',
          }}
          labelStyle={{ color: '#94a3b8', fontSize: 11, marginBottom: 4 }}
          itemStyle={{ color: 'white', fontSize: 13, fontWeight: 500 }}
          formatter={(value: number | undefined) => [
            value !== undefined ? `${value >= 0 ? '+' : ''}${formatCompactNumber(value)}` : '',
            '',
          ]}
        />
        {/* Base (transparent) bar to position the visible bar */}
        <Bar dataKey="base" stackId="waterfall" fill="transparent" />
        {/* Visible bar showing the value */}
        <Bar
          dataKey="value"
          stackId="waterfall"
          radius={[2, 2, 0, 0]}
        >
          {chartData.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={
                entry.isSubtotal
                  ? subtotalColor
                  : entry.isPositive
                  ? positiveColor
                  : negativeColor
              }
            />
          ))}
        </Bar>
      </RechartsBar>
    </ResponsiveContainer>
  );
}


