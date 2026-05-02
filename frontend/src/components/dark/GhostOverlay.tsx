/**
 * GhostOverlay — Plan v4 §6.1 contract.
 *
 * Semi-transparent layer the manager sees ON the target column /
 * swimlane while dragging a card. Replaces the right-hand-only
 * "fantasma" the previous DragDropPlanner had: now the preview is
 * visually anchored to where the boat would land.
 *
 * Two layout modes:
 *   anchored — absolute-positioned over the parent container; the
 *              parent must be `position: relative` and provide a
 *              padded inner area for the overlay's content.
 *   inline   — flows in the document, used inside SuggestionPanel.
 *
 * The component is content-agnostic: callers pass any ReactNode
 * (typically a `<ConsequenceBlock>` + a "Aceitar" button). When
 * `loading=true`, a pulsing skeleton placeholder shows while the
 * preview-delta call is in flight.
 *
 * Sprint Q.9 Onda 3.1.
 */

import type { ReactNode } from 'react';

export interface GhostOverlayProps {
  /** The body — usually a <ConsequenceBlock /> or a panel. */
  children?: ReactNode;
  /**
   * Layout mode. `anchored` paints over a column; `inline` flows in
   * the document.
   */
  mode?: 'anchored' | 'inline';
  /**
   * If true, render a pulsing skeleton — used while the preview-delta
   * round-trip is in flight (often <300ms but visible on slow links).
   */
  loading?: boolean;
  /** Top-left chip — usually "Sugestão" / "Preview". */
  badge?: string;
  /** Action footer — typically primary + ghost buttons. */
  actions?: ReactNode;
  className?: string;
}

export function GhostOverlay({
  children,
  mode = 'anchored',
  loading = false,
  badge = 'Sugestão',
  actions,
  className = '',
}: GhostOverlayProps) {
  const positionClass =
    mode === 'anchored'
      ? 'absolute inset-0 z-20 flex flex-col'
      : 'flex flex-col w-full';

  return (
    <div
      className={`${positionClass} pointer-events-auto rounded-xl border border-cyan-400/40 bg-slate-900/80 backdrop-blur-sm shadow-xl ${className}`}
    >
      <div className="flex items-center justify-between px-4 pt-3 pb-2 border-b border-cyan-400/20">
        <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-300">
          {badge}
        </span>
        <span className="text-[10px] uppercase tracking-wider text-slate-400">
          preview · não escreve no plano
        </span>
      </div>

      <div className="flex-1 overflow-auto px-4 py-3">
        {loading ? (
          <div className="flex flex-col gap-2 animate-pulse">
            <div className="h-3 rounded bg-slate-700/60" />
            <div className="h-3 rounded bg-slate-700/60 w-4/5" />
            <div className="h-3 rounded bg-slate-700/60 w-2/3" />
            <div className="h-3 rounded bg-slate-700/60 w-3/5" />
            <div className="h-3 rounded bg-slate-700/60 w-1/2" />
          </div>
        ) : (
          children
        )}
      </div>

      {actions ? (
        <div className="px-4 py-2 border-t border-cyan-400/20 flex items-center justify-end gap-2">
          {actions}
        </div>
      ) : null}
    </div>
  );
}
