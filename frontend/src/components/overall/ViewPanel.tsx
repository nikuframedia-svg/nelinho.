/**
 * ViewPanel — painel com header sticky e corpo overflow-auto (C3).
 *
 * Usado no quad-layout para embrulhar cada uma das 4 vistas.
 * Header mostra: título + contagem em mono + chip de seleção activa.
 */

import { memo, type ReactNode } from 'react';
import { X } from 'lucide-react';
import type { PlanSelection } from './selection';

interface ViewPanelProps {
  title: string;
  count?: number;
  selection?: PlanSelection | null;
  onClearSelection?: () => void;
  children: ReactNode;
}

export const ViewPanel = memo(function ViewPanel({
  title,
  count,
  selection,
  onClearSelection,
  children,
}: ViewPanelProps) {
  return (
    <div
      className="flex flex-col rounded-xl border overflow-hidden"
      style={{
        background: 'var(--bg-2)',
        borderColor: 'var(--bd-2)',
        minHeight: 0,
      }}
    >
      {/* Header sticky */}
      <div
        className="flex items-center gap-2 px-3 py-2 flex-shrink-0 border-b"
        style={{
          background: 'var(--bg-3)',
          borderColor: 'var(--bd-1)',
        }}
      >
        <span
          className="text-xs font-semibold flex-1"
          style={{ color: 'var(--fg-1)' }}
        >
          {title}
        </span>

        {count !== undefined && (
          <span
            className="text-[10px] font-mono tabular-nums px-1.5 py-0.5 rounded"
            style={{
              background: 'var(--bg-4)',
              color: 'var(--fg-3)',
            }}
          >
            {count}
          </span>
        )}

        {selection && onClearSelection && (
          <button
            onClick={onClearSelection}
            className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full transition-colors"
            style={{
              background: 'var(--accent-bg)',
              border: '1px solid var(--accent-bd)',
              color: 'var(--accent)',
            }}
            title="Limpar seleção"
          >
            <span className="font-mono truncate max-w-[80px]">
              {selection.kind}: {selection.id.slice(0, 8)}
            </span>
            <X size={10} />
          </button>
        )}
      </div>

      {/* Corpo scrollável */}
      <div className="flex-1 overflow-auto p-2" style={{ minHeight: 0 }}>
        {children}
      </div>
    </div>
  );
});
