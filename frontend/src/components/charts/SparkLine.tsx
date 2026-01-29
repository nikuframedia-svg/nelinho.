/**
 * Sparkline
 * 
 * Minimal inline chart for showing trends.
 * Supports different colors and animations.
 */

import { useMemo } from 'react';

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: 'accent' | 'success' | 'warning' | 'danger' | 'neutral';
  fill?: boolean;
  animated?: boolean;
  className?: string;
}

export function Sparkline({
  data,
  width = 100,
  height = 32,
  color = 'accent',
  fill = true,
  animated = true,
  className = '',
}: SparklineProps) {
  const colorMap = {
    accent: { stroke: '#00D9FF', fill: 'rgba(0, 217, 255, 0.1)' },
    success: { stroke: '#10B981', fill: 'rgba(16, 185, 129, 0.1)' },
    warning: { stroke: '#F59E0B', fill: 'rgba(245, 158, 11, 0.1)' },
    danger: { stroke: '#EF4444', fill: 'rgba(239, 68, 68, 0.1)' },
    neutral: { stroke: '#64748B', fill: 'rgba(100, 116, 139, 0.1)' },
  };

  const { stroke, fill: fillColor } = colorMap[color];

  const pathData = useMemo(() => {
    if (data.length < 2) return '';

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const padding = 2;

    const points = data.map((value, index) => {
      const x = (index / (data.length - 1)) * (width - padding * 2) + padding;
      const y = height - ((value - min) / range) * (height - padding * 2) - padding;
      return { x, y };
    });

    let d = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const curr = points[i];
      const cpx = (prev.x + curr.x) / 2;
      d += ` Q ${prev.x} ${prev.y} ${cpx} ${(prev.y + curr.y) / 2}`;
    }
    d += ` L ${points[points.length - 1].x} ${points[points.length - 1].y}`;

    return d;
  }, [data, width, height]);

  const fillPathData = useMemo(() => {
    if (!fill || data.length < 2) return '';
    return `${pathData} L ${width - 2} ${height - 2} L 2 ${height - 2} Z`;
  }, [pathData, fill, width, height, data.length]);

  if (data.length < 2) {
    return (
      <div 
        className={`flex items-center justify-center text-text-tertiary text-xs ${className}`}
        style={{ width, height }}
      >
        —
      </div>
    );
  }

  return (
    <svg
      width={width}
      height={height}
      className={`overflow-visible ${className}`}
      viewBox={`0 0 ${width} ${height}`}
    >
      {fill && (
        <>
          <defs>
            <linearGradient id={`sparkline-gradient-${color}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={fillColor.replace('0.1', '0.3')} />
              <stop offset="100%" stopColor={fillColor.replace('0.1', '0')} />
            </linearGradient>
          </defs>
          <path
            d={fillPathData}
            fill={`url(#sparkline-gradient-${color})`}
            className={animated ? 'animate-fadeIn' : ''}
          />
        </>
      )}
      <path
        d={pathData}
        fill="none"
        stroke={stroke}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={animated ? 'sparkline-path' : ''}
        style={{
          strokeDasharray: animated ? 1000 : 'none',
          strokeDashoffset: animated ? 1000 : 0,
          animation: animated ? 'sparkline-draw 1s ease forwards' : 'none',
        }}
      />
      <circle
        cx={width - 2}
        cy={(() => {
          const min = Math.min(...data);
          const max = Math.max(...data);
          const range = max - min || 1;
          const lastValue = data[data.length - 1];
          return height - ((lastValue - min) / range) * (height - 4) - 2;
        })()}
        r={3}
        fill={stroke}
        className={animated ? 'animate-pulse' : ''}
      />
    </svg>
  );
}

export default Sparkline;
