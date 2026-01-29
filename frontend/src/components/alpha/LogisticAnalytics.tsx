import { Package } from 'lucide-react';
import { CardBase } from './CardBase';

interface LogisticAnalyticsProps {
  data?: number[][];
  yLabels?: number[];
}

const defaultData = [
  [250, 280, 300, 150, 100, 80],
  [220, 180, 260, 120, 90, 70],
  [180, 150, 200, 100, 80, 60],
  [150, 120, 150, 80, 60, 50],
  [100, 90, 100, 60, 50, 40],
];

const defaultYLabels = [300, 200, 100, 100, 100];

function getOpacity(value: number, max: number = 300): number {
  const normalized = Math.min(value / max, 1);
  return 0.2 + (normalized * 0.8);
}

export function LogisticAnalytics({
  data = defaultData,
  yLabels = defaultYLabels,
}: LogisticAnalyticsProps) {
  const maxValue = Math.max(...data.flat());

  return (
    <CardBase
      icon={<Package size={20} className="text-accent" />}
      title="Logistic Analytics"
      dropdown={{ label: 'Monthly', options: [{ label: 'Weekly', value: 'weekly' }, { label: 'Monthly', value: 'monthly' }] }}
      footer={
        <div>
          <p className="text-sm text-text-muted mb-3">Based on this week's stats.</p>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-accent/20" />
              <span className="text-xs text-text-muted">0 - 100</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-accent/50" />
              <span className="text-xs text-text-muted">101 - 200</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-accent" />
              <span className="text-xs text-text-muted">201 - 300</span>
            </div>
          </div>
        </div>
      }
    >
      <div className="flex gap-3">
        {/* Y-axis labels */}
        <div className="flex flex-col justify-between text-right pr-2">
          {yLabels.map((label, index) => (
            <span key={index} className="text-xs text-text-muted h-8 flex items-center justify-end">
              {label}
            </span>
          ))}
        </div>

        {/* Grid */}
        <div className="flex-1 grid grid-rows-5 gap-2">
          {data.map((row, rowIndex) => (
            <div key={rowIndex} className="grid grid-cols-6 gap-2">
              {row.map((value, colIndex) => (
                <div
                  key={colIndex}
                  className="h-8 rounded-md transition-all hover:scale-105 cursor-pointer"
                  style={{
                    backgroundColor: `rgba(79, 209, 197, ${getOpacity(value, maxValue)})`,
                  }}
                  title={`Value: ${value}`}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    </CardBase>
  );
}







