import { useMemo } from 'react';
import { cn } from '../../lib/utils';
import { format, differenceInHours, parseISO } from 'date-fns';

interface GanttTask {
  id: string;
  name: string;
  start: string;
  end: string;
  color?: string;
  status?: string;
  resource?: string;
}

interface GanttChartProps {
  tasks: GanttTask[];
  startDate: Date;
  endDate: Date;
  hourWidth?: number;
}

const DEFAULT_COLORS = ['#0ea5e9', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'];

export function GanttChart({
  tasks,
  startDate,
  endDate,
  hourWidth = 30,
}: GanttChartProps) {
  const totalHours = differenceInHours(endDate, startDate);
  const hours = Array.from({ length: totalHours + 1 }, (_, i) => {
    const date = new Date(startDate);
    date.setHours(date.getHours() + i);
    return date;
  });

  const processedTasks = useMemo(() => {
    return tasks.map((task, index) => {
      const taskStart = parseISO(task.start);
      const taskEnd = parseISO(task.end);
      const startOffset = differenceInHours(taskStart, startDate);
      const duration = differenceInHours(taskEnd, taskStart);
      
      return {
        ...task,
        left: startOffset * hourWidth,
        width: duration * hourWidth,
        color: task.color || DEFAULT_COLORS[index % DEFAULT_COLORS.length],
      };
    });
  }, [tasks, startDate, hourWidth]);

  return (
    <div className="overflow-x-auto">
      <div className="min-w-max">
        {/* Header */}
        <div className="flex border-b border-surface-200 sticky top-0 bg-white z-10">
          <div className="w-48 flex-shrink-0 px-4 py-3 text-xs font-semibold text-zinc-500 uppercase">
            Task
          </div>
          <div className="flex">
            {hours.map((hour, i) => (
              <div
                key={i}
                className={cn(
                  'text-xs text-zinc-400 text-center border-l border-surface-100',
                  hour.getHours() === 0 && 'bg-surface-50'
                )}
                style={{ width: hourWidth }}
              >
                {hour.getHours() === 0 ? format(hour, 'MMM d') : format(hour, 'HH:mm')}
              </div>
            ))}
          </div>
        </div>

        {/* Tasks */}
        <div className="divide-y divide-surface-100">
          {processedTasks.map((task) => (
            <div key={task.id} className="flex items-center hover:bg-surface-50">
              <div className="w-48 flex-shrink-0 px-4 py-3">
                <p className="text-sm font-medium text-zinc-900 truncate">{task.name}</p>
                {task.resource && (
                  <p className="text-xs text-zinc-500 truncate">{task.resource}</p>
                )}
              </div>
              <div 
                className="relative h-12 flex items-center"
                style={{ width: totalHours * hourWidth }}
              >
                {/* Grid lines */}
                <div className="absolute inset-0 flex">
                  {hours.map((_, i) => (
                    <div
                      key={i}
                      className="h-full border-l border-surface-100"
                      style={{ width: hourWidth }}
                    />
                  ))}
                </div>
                
                {/* Task bar */}
                <div
                  className="absolute h-7 rounded-lg flex items-center px-2 text-xs font-medium text-white shadow-sm"
                  style={{
                    left: task.left,
                    width: Math.max(task.width, 30),
                    backgroundColor: task.color,
                  }}
                >
                  <span className="truncate">{task.status || 'Scheduled'}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}










