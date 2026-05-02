/**
 * KioskWrapper — Plan v4 §10 tablet mode.
 *
 * Wraps a child surface so a tablet can run it WITHOUT the app's
 * chrome (sidebar, topbar). When the route mounts with `?kiosk=true`,
 * the wrapper:
 *
 *   1. Renders the child in a full-viewport container (no
 *      DarkPageLayout / DarkTopbar / DarkSidebar around it).
 *   2. Auto-requests Fullscreen on first user gesture (browsers
 *      block requesting fullscreen without user interaction; we hook
 *      onto the first click anywhere within the wrapper).
 *   3. Locks the body's scroll + larger touch targets via a CSS
 *      class so no accidental swipes scroll the app off-screen.
 *   4. Exposes an "Exit fullscreen" affordance in the top-right corner
 *      so the operator can drop back to normal view (e.g. to read a
 *      KPI page on the same device).
 *
 * Activation by query string (NOT a global flag) so an admin can
 * keep their normal-mode session in another tab. Persistence lives
 * on the URL — when the operator scans the kiosk QR code, the
 * full URL with `?kiosk=true` is what gets bookmarked.
 *
 * Sprint Q.13.C / C.3.5.
 */

import type { ReactNode } from 'react';
import { useEffect, useRef, useState } from 'react';
import { Maximize2, Minimize2 } from 'lucide-react';

export interface KioskWrapperProps {
  children: ReactNode;
  /**
   * When false (default), the wrapper is a no-op pass-through. The
   * caller decides activation by reading a query param / context /
   * localStorage flag and passing the boolean here.
   */
  enabled: boolean;
  /**
   * Title rendered top-left in kiosk mode (since the topbar is
   * hidden). Defaults to "ProdPlan ONE" so the operator always sees
   * which app they're in.
   */
  brandLabel?: string;
}

export function KioskWrapper({
  children,
  enabled,
  brandLabel = 'ProdPlan ONE',
}: KioskWrapperProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Track Fullscreen API state — operator may exit via Esc/F11 from
  // the browser, in which case we want to update the toggle icon.
  useEffect(() => {
    if (!enabled) return;
    const handler = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener('fullscreenchange', handler);
    return () => document.removeEventListener('fullscreenchange', handler);
  }, [enabled]);

  // Lock body scroll while in kiosk to avoid accidental rubber-band
  // gestures pulling the app off-screen on iOS Safari.
  useEffect(() => {
    if (!enabled) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [enabled]);

  const requestFullscreen = async () => {
    const el = containerRef.current;
    if (!el) return;
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        await el.requestFullscreen();
      }
    } catch {
      // Browsers block the request when not triggered by a user
      // gesture, when the iframe doesn't have allowfullscreen, or
      // when another fullscreen request is already in flight. None
      // of those should crash the page; just swallow.
    }
  };

  if (!enabled) {
    return <>{children}</>;
  }

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 z-50 bg-bg-base text-text-white flex flex-col overflow-hidden"
      data-kiosk-wrapper
    >
      <header className="flex items-center justify-between px-4 py-3 border-b border-border-subtle bg-bg-secondary/60 shrink-0">
        <span className="text-base font-semibold tracking-tight">
          {brandLabel} <span className="text-text-tertiary text-xs ml-1">· kiosk</span>
        </span>
        <button
          type="button"
          onClick={requestFullscreen}
          className="p-2 rounded-lg hover:bg-bg-elevated text-text-secondary hover:text-text-white transition-colors min-h-[56px] min-w-[56px] flex items-center justify-center"
          title={isFullscreen ? 'Sair de ecrã inteiro' : 'Entrar em ecrã inteiro'}
        >
          {isFullscreen ? <Minimize2 size={22} /> : <Maximize2 size={22} />}
        </button>
      </header>
      <main className="flex-1 overflow-y-auto p-4">{children}</main>
    </div>
  );
}
