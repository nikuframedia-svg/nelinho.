/**
 * useRealtimeEvents — SSE consumer for the RealtimeBridge (Sprint D.2)
 * =====================================================================
 *
 * Opens a single EventSource against `/v1/realtime/events`, filtered
 * by the channels the caller asks for (`alerts`, `timeline`,
 * `dashboard`, `governance`). Reconnects with exponential backoff when
 * the stream drops. The browser's native `EventSource` does not support
 * custom headers, so we pass `tenant_id` via query string per the
 * Sprint D auth decision.
 *
 * Usage:
 *
 *     const { events, connected, lastHeartbeat } = useRealtimeEvents(['alerts']);
 *
 * `events` is a growing queue of received envelopes (capped at 500 to
 * avoid memory issues). Callers typically consume recent ones and
 * dispatch by `event_type`.
 *
 * For apps that want a single shared connection use `RealtimeProvider`
 * from `providers/RealtimeProvider.tsx` — this hook is a lower-level
 * primitive that each component could wire directly, but doing so
 * opens multiple EventSource instances (one per component).
 */

import { useCallback, useEffect, useRef, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Keep at most this many events in the rolling buffer. Old events are
// dropped head-first so long-running pages don't grow unbounded.
const MAX_BUFFERED_EVENTS = 500;

// Reconnect backoff. Matches the SSE-starlette heartbeat cadence
// (30s server-side); we try faster first then back off.
const RECONNECT_DELAYS_MS = [1_000, 2_000, 4_000, 8_000, 15_000, 30_000];

// Payload shape — mirrors the backend `EventBase` dict plus the
// `_topic` field the bridge tacks on during fan-out.
export interface RealtimeEvent {
  event_id?: string;
  event_type: string;
  tenant_id: string;
  source_module?: string;
  timestamp?: string;
  correlation_id?: string | null;
  payload: Record<string, unknown>;
  _topic?: string;
}

export interface UseRealtimeEventsOptions {
  /** Channels to subscribe to (alerts, timeline, dashboard, governance). */
  channels: string[];
  /** Optional tenant override. Defaults to `localStorage.tenant_id`. */
  tenantId?: string;
  /** Disable the stream without unmounting the hook. */
  enabled?: boolean;
  /** Max events kept in the rolling buffer. */
  bufferSize?: number;
}

export interface UseRealtimeEventsResult {
  /** Rolling buffer of received envelopes (most recent last). */
  events: RealtimeEvent[];
  /** True when the stream is open and the `connected` handshake has fired. */
  connected: boolean;
  /** Timestamp of the last heartbeat (or last event) we received. */
  lastHeartbeat: Date | null;
  /** Count of reconnection attempts since the hook mounted. */
  reconnectAttempts: number;
  /** Clear the buffer. */
  clear: () => void;
}

function resolveTenantId(explicit?: string): string {
  if (explicit) return explicit;
  if (typeof window !== 'undefined') {
    return (
      window.localStorage.getItem('tenant_id') ||
      '00000000-0000-0000-0000-000000000000'
    );
  }
  return '00000000-0000-0000-0000-000000000000';
}

export function useRealtimeEvents(
  options: UseRealtimeEventsOptions,
): UseRealtimeEventsResult {
  const {
    channels,
    tenantId: tenantIdOverride,
    enabled = true,
    bufferSize = MAX_BUFFERED_EVENTS,
  } = options;

  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [lastHeartbeat, setLastHeartbeat] = useState<Date | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  const esRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const attemptsRef = useRef(0); // read inside handlers without re-binding

  const clear = useCallback(() => setEvents([]), []);

  // Serialise channels for effect dependency (arrays-by-reference would
  // cause churn on every render).
  const channelsKey = channels.slice().sort().join(',');

  useEffect(() => {
    if (!enabled || channels.length === 0) {
      return undefined;
    }

    const tenantId = resolveTenantId(tenantIdOverride);
    const url = new URL(`${API_BASE}/v1/realtime/events`);
    url.searchParams.set('tenant_id', tenantId);
    url.searchParams.set('channels', channels.join(','));

    let cancelled = false;

    const connect = () => {
      if (cancelled) return;

      const es = new EventSource(url.toString());
      esRef.current = es;

      // "connected" is the server-side handshake event that fires as
      // soon as the stream opens. We DON'T rely on `onopen` because
      // EventSource fires that before the first byte on some proxies.
      es.addEventListener('connected', () => {
        if (cancelled) return;
        setConnected(true);
        setLastHeartbeat(new Date());
        attemptsRef.current = 0;
        setReconnectAttempts(0);
      });

      es.addEventListener('heartbeat', () => {
        if (cancelled) return;
        setLastHeartbeat(new Date());
      });

      // Catch-all `onmessage` — event types without an explicit listener
      // land here. The server names its events by `event_type` so we
      // don't really use this path except for future generic events.
      es.onmessage = (msg) => {
        if (cancelled) return;
        pushEvent(msg);
      };

      // Listen for every known event_type. We can't enumerate them from
      // here (they're defined backend-side in kafka_client.Topics) so we
      // rely on the generic EventSource behaviour: when we
      // `addEventListener(event_type, handler)` later each component can
      // opt in. The Provider version of this hook registers specific
      // types — here we just catch everything via `onmessage` + a
      // wildcard via `message` event.
      es.addEventListener('message', pushEvent);

      es.onerror = () => {
        if (cancelled) return;
        setConnected(false);
        es.close();
        esRef.current = null;
        scheduleReconnect();
      };
    };

    const pushEvent = (msg: MessageEvent) => {
      if (cancelled) return;
      setLastHeartbeat(new Date());
      let parsed: RealtimeEvent | null = null;
      try {
        parsed = JSON.parse(msg.data) as RealtimeEvent;
      } catch {
        // Keep the stream healthy even if one payload is garbage.
        return;
      }
      if (!parsed) return;
      setEvents((prev) => {
        const next = prev.length >= bufferSize
          ? prev.slice(prev.length - bufferSize + 1)
          : prev;
        return [...next, parsed!];
      });
    };

    const scheduleReconnect = () => {
      if (cancelled) return;
      const attempt = attemptsRef.current;
      attemptsRef.current = attempt + 1;
      setReconnectAttempts(attempt + 1);
      const delay =
        RECONNECT_DELAYS_MS[Math.min(attempt, RECONNECT_DELAYS_MS.length - 1)];
      reconnectTimerRef.current = window.setTimeout(connect, delay);
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      setConnected(false);
    };
    // Re-connect when channels change or tenant changes. `bufferSize`
    // is a knob we read during push, not something that should tear
    // the connection down.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channelsKey, tenantIdOverride, enabled]);

  return {
    events,
    connected,
    lastHeartbeat,
    reconnectAttempts,
    clear,
  };
}

export default useRealtimeEvents;
