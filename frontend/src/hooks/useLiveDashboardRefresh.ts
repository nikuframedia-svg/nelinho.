/**
 * useLiveDashboardRefresh — auto-refresh the dashboard when SSE fires
 * =====================================================================
 *
 * Plumbs the shared SSE stream into the dashboard's TanStack queries.
 * Whenever an event type the dashboard cares about arrives (schedule
 * changes, MRP recomputes, decisions executed, stock movements, rework
 * entries) we trigger the caller's `refresh()` function.
 *
 * Two guardrails:
 *
 * 1. **Debounce** — a single commit may fan out several events (e.g.
 *    `SCHEDULE_CREATED` immediately followed by `MATERIAL_REQUIREMENT_
 *    PLANNED`). Debouncing by a short window (1.5s by default) collapses
 *    the burst into a single API round-trip instead of hammering four
 *    queries twelve times.
 *
 * 2. **Tracked counters** — the hook returns the number of events seen
 *    and the timestamp of the last relevant one so the UI can render a
 *    "live há Xs" badge. A stream that hasn't fired for a while is the
 *    user's cue to question the connection, not a silent lie.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRealtime } from '@/providers/RealtimeProvider';

/** Event types that should cause the dashboard to re-fetch. */
export const DASHBOARD_TRIGGER_EVENTS = [
  'SCHEDULE_CREATED',
  'SCHEDULE_UPDATED',
  'MRP_CALCULATED',
  'MATERIAL_REQUIREMENT_PLANNED',
  'MATERIAL_SHORTAGE_DETECTED',
  'STOCK_ADJUSTED',
  'STOCK_RECONCILED',
  'REWORK_ENTRY_CREATED',
  'DECISION_EXECUTED',
  'DECISION_ROLLED_BACK',
  'MOLD_HEALTH_DEGRADED',
  'COGS_CALCULATED',
] as const;

type DashboardTriggerEvent = (typeof DASHBOARD_TRIGGER_EVENTS)[number];
const DASHBOARD_TRIGGER_SET = new Set<string>(DASHBOARD_TRIGGER_EVENTS);

export interface UseLiveDashboardRefreshResult {
  /** ISO timestamp of the last event that triggered a refresh, or null. */
  lastEventAt: Date | null;
  /** Total number of trigger events processed during this mount. */
  eventCount: number;
  /** Type of the last trigger event — useful to label "refreshed because X". */
  lastEventType: DashboardTriggerEvent | null;
}

export interface UseLiveDashboardRefreshOptions {
  /** Milliseconds to wait before calling `refresh` after a burst. */
  debounceMs?: number;
  /** Optional allow-list override; defaults to DASHBOARD_TRIGGER_EVENTS. */
  eventTypes?: readonly string[];
}

export function useLiveDashboardRefresh(
  refresh: () => void,
  options: UseLiveDashboardRefreshOptions = {},
): UseLiveDashboardRefreshResult {
  const { debounceMs = 1500, eventTypes } = options;
  const triggerSet =
    eventTypes && eventTypes.length > 0 ? new Set(eventTypes) : DASHBOARD_TRIGGER_SET;

  const realtime = useRealtime();
  const [state, setState] = useState<UseLiveDashboardRefreshResult>({
    lastEventAt: null,
    eventCount: 0,
    lastEventType: null,
  });

  // Keep `refresh` in a ref so the effect doesn't re-subscribe on every
  // parent render — TanStack's `refetch` is a fresh reference each tick.
  const refreshRef = useRef(refresh);
  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);

  // Debounced trigger. A new event inside the window cancels the pending
  // call and schedules a fresh one — only the final event of a burst
  // actually pulls the API.
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scheduleRefresh = useCallback(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      refreshRef.current();
      debounceTimer.current = null;
    }, debounceMs);
  }, [debounceMs]);

  useEffect(
    () => () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    },
    [],
  );

  // Fan out: walk the rolling buffer from where we left off, trigger the
  // debounced refetch on matching events, and advance our cursor.
  const processedLenRef = useRef(0);
  useEffect(() => {
    if (!realtime) return;
    const total = realtime.events.length;
    if (total === processedLenRef.current) return;

    const fresh = realtime.events.slice(processedLenRef.current, total);
    processedLenRef.current = total;

    let newEvents = 0;
    let lastType: DashboardTriggerEvent | null = null;
    let lastAt: Date | null = null;
    for (const ev of fresh) {
      if (!triggerSet.has(ev.event_type)) continue;
      newEvents += 1;
      lastType = ev.event_type as DashboardTriggerEvent;
      lastAt = ev.timestamp ? new Date(ev.timestamp) : new Date();
    }
    if (newEvents === 0) return;

    scheduleRefresh();
    setState((prev) => ({
      lastEventAt: lastAt ?? prev.lastEventAt,
      eventCount: prev.eventCount + newEvents,
      lastEventType: lastType ?? prev.lastEventType,
    }));
    // We intentionally depend on `realtime?.events.length` (a stable
    // primitive) instead of the array itself so we don't re-run on
    // unrelated renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [realtime?.events.length, realtime, scheduleRefresh]);

  return state;
}
