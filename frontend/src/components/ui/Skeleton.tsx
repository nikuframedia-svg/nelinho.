interface SkeletonProps {
  className?: string;
  width?: string | number;
  height?: string | number;
}

export function Skeleton({ className = '', width, height }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse bg-slate-200 rounded ${className}`}
      style={{
        width: width || '100%',
        height: height || '1rem',
      }}
    />
  );
}

export function SkeletonLoader({ count = 3, className = '' }: { count?: number; className?: string }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} height="1rem" />
      ))}
    </div>
  );
}

export function CardSkeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`bg-white rounded-2xl p-6 border border-slate-200 ${className}`}>
      <Skeleton height="1.5rem" width="60%" className="mb-4" />
      <Skeleton height="2rem" width="40%" className="mb-2" />
      <Skeleton height="1rem" width="80%" />
    </div>
  );
}

export function TableSkeleton({ rows = 5, cols = 4, className = '' }: { rows?: number; cols?: number; className?: string }) {
  return (
    <div className={`overflow-hidden ${className}`}>
      {/* Header */}
      <div className="grid gap-4 mb-4" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} height="1.5rem" />
        ))}
      </div>
      {/* Rows */}
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <div key={rowIndex} className="grid gap-4" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
            {Array.from({ length: cols }).map((_, colIndex) => (
              <Skeleton key={colIndex} height="1.25rem" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChartSkeleton({ height = 300, className = '' }: { height?: number; className?: string }) {
  return (
    <div className={`bg-white rounded-2xl p-6 border border-slate-200 ${className}`}>
      <Skeleton height="1.5rem" width="40%" className="mb-4" />
      <div className="relative" style={{ height: `${height}px` }}>
        <div className="absolute inset-0 flex items-end justify-around gap-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <Skeleton
              key={i}
              width="8%"
              height={`${Math.random() * 60 + 30}%`}
              className="rounded-t"
            />
          ))}
        </div>
      </div>
      <div className="mt-4 flex justify-around gap-4">
        {Array.from({ length: 10 }).map((_, i) => (
          <Skeleton key={i} height="0.75rem" width="8%" />
        ))}
      </div>
    </div>
  );
}







