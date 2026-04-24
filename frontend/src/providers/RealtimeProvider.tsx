/**
 * RealtimeProvider — single shared SSE connection for the whole app
 * ==================================================================
 *
 * Wraps the app in one long-lived `useRealtimeEvents` subscription so
 * every component that calls `useRealtime()` shares the same stream.
 * Opening a new EventSource per component would hit the browser's
 * per-origin connection cap quickly and fire duplicate handlers for
 * every event.
 *
 * Components opt into specific event types via `useRealtimeType(type,
 * handler)`. The provider holds the rolling buffer centrally so late-
 * mounted components can read the most recent events without racing
 * the connection lifecycle.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
} from 'react';

import {
  useRealtimeEvents,
  type RealtimeEvent,
} from '@/hooks/useRealtimeEvents';

interface RealtimeContextValue {
  events: RealtimeEvent[];
  connected: boolean;
  lastHeartbeat: Date | null;
  reconnectAttempts: number;
  subscribe: (
    eventType: string,
    handler: (event: RealtimeEvent) => void,
  ) => () => void;
}

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

interface RealtimeProviderProps {
  children: ReactNode;
  /** Channels to subscribe to — defaults to "all". */
  channels?: string[];
  /** Disable the connection (useful for tests / unauthed routes). */
  enabled?: boolean;
}

const DEFAULT_CHANNELS = ['alerts', 'timeline', 'dashboard', 'governance'];

export function RealtimeProvider({
  children,
  channels = DEFAULT_CHANNELS,
  enabled = true,
}: RealtimeProviderProps) {
  const { events, connected, lastHeartbeat, reconnectAttempts } =
    useRealtimeEvents({ channels, enabled });

  // Per-event-type subscribers. Each component registers a handler via
  // `useRealtimeType(type, cb)` and the provider invokes them as new
  // envelopes arrive. A Map keyed by event_type keeps lookup O(1).
  type Handler = (e: RealtimeEvent) => void;
  const handlersRef = useRef<Map<string, Set<Handler>>>(new Map());

  const subscribe = useCallback(
    (eventType: string, handler: Handler) => {
      const map = handlersRef.current;
      if (!map.has(eventType)) map.set(eventType, new Set());
      map.get(eventType)!.add(handler);
      return () => {
        const pool = map.get(eventType);
        if (!pool) return;
        pool.delete(handler);
        if (pool.size === 0) map.delete(eventType);
      };
    },
    [],
  );

  // Fan out every new envelope to its type-specific subscribers. We
  // track the last processed index so a re-render with the same events
  // slice doesn't re-dispatch old ones.
  const processedLenRef = useRef(0);
  useEffect(() => {
    const map = handlersRef.current;
    for (let i = processedLenRef.current; i < events.length; i += 1) {
      const envelope = events[i];
      const pool = map.get(envelope.event_type);
      if (pool) {
        pool.forEach((h) => {
          try {
            h(envelope);
          } catch {
            // Never let a noisy handler break the stream for others.
          }
        });
      }
    }
    processedLenRef.current = events.length;
  }, [events]);

  const value = useMemo<RealtimeContextValue>(
    () => ({
      events,
      connected,
      lastHeartbeat,
      reconnectAttempts,
      subscribe,
    }),
    [events, connected, lastHeartbeat, reconnectAttempts, subscribe],
  );

  return (
    <RealtimeContext.Provider value={value}>
      {children}
    </RealtimeContext.Provider>
  );
}

/**
 * Read the realtime connection state + the full rolling buffer.
 *
 * Returns `null` when used outside a `RealtimeProvider` so optional
 * integrations (e.g. during SSR) can no-op cleanly.
 */
export function useRealtime(): RealtimeContextValue | null {
  return useContext(RealtimeContext);
}

/**
 * Subscribe to a single `event_type`. The handler is called whenever
 * the RealtimeProvider receives an envelope matching the type.
 *
 * The handler is stored in a ref to avoid re-subscribing on every
 * render — callers can pass an inline arrow without worrying.
 */
export function useRealtimeType(
  eventType: string,
  handler: (event: RealtimeEvent) => void,
): void {
  const ctx = useContext(RealtimeContext);
  const handlerRef = useRef(handler);
  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);

  useEffect(() => {
    if (!ctx) return undefined;
    const unsub = ctx.subscribe(eventType, (event) => {
      handlerRef.current(event);
    });
    return unsub;
  }, [ctx, eventType]);
}
