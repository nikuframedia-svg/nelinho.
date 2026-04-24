/**
 * LiveBadge — SSE connection status indicator
 * =============================================
 *
 * Tiny pill-shaped component that tells the user at a glance whether
 * the dashboard is in live mode. Three states:
 *
 *  • `connected + recent event` → green dot, "Ao vivo" or "há Xs"
 *  • `connected + stale`        → amber dot, "há Xm" (no event for a while)
 *  • `disconnected`             → red dot, "Desligado"
 *
 * The "stale" threshold defaults to 90 seconds — slightly longer than
 * the server's 30s heartbeat so a couple of missed beats don't scare
 * the operator into calling IT.
 *
 * The component self-ticks every 10 seconds so the elapsed-time label
 * stays fresh without needing the parent to re-render.
 */

import { useEffect, useState } from 'react';
import { useRealtime } from '@/providers/RealtimeProvider';

interface LiveBadgeProps {
  /** Timestamp of the last event the dashboard actually reacted to.
   *  Passed in from `useLiveDashboardRefresh().lastEventAt`. */
  lastEventAt?: Date | null;
  /** Number of seconds before a connected-but-silent stream is shown
   *  as "stale". Defaults to 90s (3× the server heartbeat interval). */
  staleAfterSeconds?: number;
  /** Optional class overrides — useful when embedding next to buttons
   *  that already have sizing. */
  className?: string;
}

function formatSince(from: Date, now: Date): string {
  const secs = Math.max(0, Math.floor((now.getTime() - from.getTime()) / 1000));
  if (secs < 5) return 'agora';
  if (secs < 60) return `há ${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `há ${mins}m`;
  const hours = Math.floor(mins / 60);
  return `há ${hours}h`;
}

export function LiveBadge({
  lastEventAt,
  staleAfterSeconds = 90,
  className = '',
}: LiveBadgeProps) {
  const realtime = useRealtime();
  const [now, setNow] = useState(() => new Date());

  // Re-tick once every 10 seconds. Cheap (one setState) and enough to
  // keep "há 42s" readable without introducing a flicker.
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 10_000);
    return () => clearInterval(id);
  }, []);

  if (!realtime) {
    return (
      <span
        className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-bg-secondary/50 text-xs text-text-tertiary ${className}`}
        title="Real-time não está configurado nesta vista"
      >
        <span className="w-2 h-2 rounded-full bg-text-tertiary" />
        Sem realtime
      </span>
    );
  }

  const { connected, lastHeartbeat, reconnectAttempts } = realtime;
  const lastActivityCandidates = [lastEventAt ?? null, lastHeartbeat ?? null].filter(
    (d): d is Date => d instanceof Date,
  );
  const lastActivity =
    lastActivityCandidates.length > 0
      ? new Date(Math.max(...lastActivityCandidates.map((d) => d.getTime())))
      : null;
  const secsSince = lastActivity
    ? Math.floor((now.getTime() - lastActivity.getTime()) / 1000)
    : null;
  const stale = secsSince !== null && secsSince > staleAfterSeconds;

  if (!connected) {
    return (
      <span
        className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-red-500/15 border border-red-500/30 text-xs text-red-300 ${className}`}
        title={`Desligado do stream SSE (tentativas: ${reconnectAttempts})`}
      >
        <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
        Desligado{reconnectAttempts > 0 ? ` · a reconectar (${reconnectAttempts})` : ''}
      </span>
    );
  }

  if (stale) {
    return (
      <span
        className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-xs text-amber-200 ${className}`}
        title="Ligado mas sem eventos recentes"
      >
        <span className="w-2 h-2 rounded-full bg-amber-400" />
        Em espera {lastActivity ? `· ${formatSince(lastActivity, now)}` : ''}
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-xs text-emerald-200 ${className}`}
      title={
        lastEventAt
          ? `Último evento ${formatSince(lastEventAt, now)}`
          : 'Stream ligado — à escuta de eventos'
      }
    >
      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
      Ao vivo{lastEventAt ? ` · ${formatSince(lastEventAt, now)}` : ''}
    </span>
  );
}

export default LiveBadge;
