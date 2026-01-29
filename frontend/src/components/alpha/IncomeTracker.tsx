import { TrendingUp, Circle } from 'lucide-react';
import { BarChart, Bar, XAxis, ResponsiveContainer, Cell, Tooltip as RechartsTooltip } from 'recharts';
import { CardBase } from './CardBase';

interface IncomeTrackerProps {
  data?: {
    label: string;
    value: number;
  }[];
  percentageIncrease?: number;
  ratingIncrease?: number;
  highlightedValue?: number;
}

const defaultData = [
  { label: 'Mon', value: 120 },
  { label: 'Tue', value: 180 },
  { label: 'Wed', value: 250 },
  { label: 'Thu', value: 329 },
  { label: 'Fri', value: 200 },
  { label: 'Sat', value: 90 },
  { label: 'Sun', value: 150 },
];

export function IncomeTracker({
  data = defaultData,
  percentageIncrease = 85,
  ratingIncrease = 34,
  highlightedValue = 329,
}: IncomeTrackerProps) {
  const maxValue = Math.max(...data.map(d => d.value));
  const highlightedIndex = data.findIndex(d => d.value === maxValue);

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-bg-elevated border border-border-subtle rounded-lg px-3 py-2 shadow-lg">
          <p className="text-text-white font-semibold">${payload[0].value}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <CardBase
      icon={<Circle size={20} className="text-accent fill-accent" />}
      title="Income Tracker"
      dropdown={{ label: 'Weekly', options: [{ label: 'Weekly', value: 'weekly' }, { label: 'Monthly', value: 'monthly' }] }}
      footer={
        <p className="text-sm text-text-muted">
          Displays data for this month and you can display anything you want.
        </p>
      }
    >
      {/* Stats */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-success text-sm mb-2">
          <TrendingUp size={16} />
          <span>{percentageIncrease}% better than last week</span>
        </div>
        <div>
          <span className="text-4xl font-bold text-text-white">{ratingIncrease}%</span>
          <span className="text-text-gray ml-1">rating</span>
        </div>
        <p className="text-text-muted text-sm mt-1">increases every weeks.</p>
      </div>

      {/* Chart */}
      <div className="h-40 relative">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barCategoryGap="20%">
            <XAxis 
              dataKey="label" 
              axisLine={false} 
              tickLine={false}
              tick={{ fill: '#6b7280', fontSize: 11 }}
            />
            <RechartsTooltip content={<CustomTooltip />} cursor={false} />
            <Bar 
              dataKey="value" 
              radius={[6, 6, 6, 6]}
            >
              {data.map((_entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={index === highlightedIndex ? '#4fd1c5' : 'rgba(79, 209, 197, 0.3)'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {/* Highlighted value label */}
        {highlightedIndex >= 0 && (
          <div 
            className="absolute text-sm font-semibold text-text-white"
            style={{
              top: '10%',
              left: `${(highlightedIndex / data.length) * 100 + (50 / data.length)}%`,
              transform: 'translateX(-50%)',
            }}
          >
            ${highlightedValue}
          </div>
        )}
      </div>

      {/* Dots indicators */}
      <div className="flex items-center justify-center gap-2 mt-4">
        {data.map((_, index) => (
          <div
            key={index}
            className={`w-1.5 h-1.5 rounded-full ${
              index === highlightedIndex ? 'bg-accent' : 'bg-text-muted'
            }`}
          />
        ))}
      </div>

      {/* Toggle slider */}
      <div className="flex justify-center mt-4">
        <div className="w-8 h-8 rounded-full bg-bg-elevated border border-border-subtle flex items-center justify-center text-text-muted text-xs font-medium">
          t
        </div>
      </div>
    </CardBase>
  );
}




