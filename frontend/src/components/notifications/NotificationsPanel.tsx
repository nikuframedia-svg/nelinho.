/**
 * NotificationsPanel
 * 
 * Displays real-time notifications for critical events.
 * Supports different severity levels and actions.
 */

import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  X,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  Info,
  Play,
  Eye,
  Trash2,
  Settings,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { pt } from 'date-fns/locale';
import { useRealtime } from '@/providers/RealtimeProvider';
import type { RealtimeEvent } from '@/hooks/useRealtimeEvents';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

export interface Notification {
  id: string;
  type: 'critical' | 'warning' | 'success' | 'info';
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  actionLabel?: string;
  actionPath?: string;
  simulateAction?: {
    type: string;
    params: Record<string, any>;
  };
}

interface NotificationsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  anchorRef?: React.RefObject<HTMLElement>;
}

// ═══════════════════════════════════════════════════════════════════════════════
// SSE → Notification translation (Sprint D.2)
// ═══════════════════════════════════════════════════════════════════════════════

// Map each backend event_type to the shape the panel renders. Keeping
// this as a lookup table makes adding a new notification type a
// one-liner: append to this object and the panel picks it up.
const EVENT_TEMPLATES: Record<
  string,
  {
    type: Notification['type'];
    title: (payload: Record<string, unknown>) => string;
    message: (payload: Record<string, unknown>) => string;
    actionLabel?: string;
    actionPath?: string;
  }
> = {
  MOLD_MAINT_DUE: {
    type: 'warning',
    title: () => 'Molde precisa de manutenção',
    message: (p) =>
      `Molde ${p.mold_code ?? p.mold_id ?? '?'} ultrapassou o threshold de ciclos.`,
    actionLabel: 'Ver moldes',
    actionPath: '/plan/mrp',
  },
  MOLD_HEALTH_DEGRADED: {
    type: 'warning',
    title: () => 'Saúde do molde a degradar',
    message: (p) => `Molde ${p.mold_code ?? '?'} com sinais de degradação.`,
    actionLabel: 'Ver moldes',
    actionPath: '/plan/mrp',
  },
  MATERIAL_SHORTAGE_DETECTED: {
    type: 'critical',
    title: () => 'Rotura de material detectada',
    message: (p) =>
      `Stock ${p.material_code ?? p.sku ?? '?'} abaixo do mínimo (days_to_stockout=${p.days_to_stockout ?? '?'}).`,
    actionLabel: 'Ver stock',
    actionPath: '/supply/inventory',
  },
  CAPACITY_CONSTRAINT_DETECTED: {
    type: 'critical',
    title: () => 'Gargalo de capacidade',
    message: (p) =>
      `Fase ${p.phase ?? '?'} sobrecarregada (${p.utilisation_pct ?? '?'}%).`,
    actionLabel: 'Ver detalhes',
    actionPath: '/inbox',
  },
  QUALITY_RISK_SCORED: {
    type: 'warning',
    title: () => 'Risco de qualidade elevado',
    message: (p) => `Score ${p.score ?? '?'} em ${p.target ?? 'produção'}.`,
    actionLabel: 'Ver qualidade',
    actionPath: '/profit/quality',
  },
  DECISION_EXECUTED: {
    type: 'success',
    title: () => 'Decisão executada',
    message: (p) =>
      `${p.decision_type ?? 'Decisão'} aprovada por ${p.executed_by ?? 'sistema'}.`,
    actionLabel: 'Ver timeline',
    actionPath: '/decisions',
  },
  DECISION_ROLLED_BACK: {
    type: 'warning',
    title: () => 'Decisão revertida',
    message: (p) =>
      `${p.decision_type ?? 'Decisão'} rolled back: ${p.reason ?? 'sem razão'}.`,
    actionLabel: 'Ver timeline',
    actionPath: '/decisions',
  },
  STOCK_ADJUSTED: {
    type: 'info',
    title: () => 'Stock ajustado',
    message: (p) =>
      `${p.sku ?? p.material_code ?? 'Item'} ajustado em ${p.delta_qty ?? '?'}.`,
    actionLabel: 'Ver stock',
    actionPath: '/supply/inventory',
  },
};

function eventToNotification(event: RealtimeEvent): Notification | null {
  const tpl = EVENT_TEMPLATES[event.event_type];
  if (!tpl) return null;
  const ts = event.timestamp ? new Date(event.timestamp) : new Date();
  return {
    id: event.event_id ?? `${event.event_type}-${ts.getTime()}`,
    type: tpl.type,
    title: tpl.title(event.payload ?? {}),
    message: tpl.message(event.payload ?? {}),
    timestamp: ts,
    read: false,
    actionLabel: tpl.actionLabel,
    actionPath: tpl.actionPath,
  };
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

// Keep at most this many notifications in the panel. Older ones fall off
// the bottom — consistent with the rolling buffer in the SSE hook.
const MAX_NOTIFICATIONS_IN_PANEL = 50;

export function NotificationsPanel({ isOpen, onClose }: NotificationsPanelProps) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const navigate = useNavigate();
  const realtime = useRealtime();
  // Track which buffer index we've already turned into notifications so
  // a re-render (or an unrelated state update) doesn't re-process the
  // same events. The provider's `events` array grows append-only, so
  // "new" = anything past `processedLenRef.current`.
  const processedLenRef = useRef(0);

  useEffect(() => {
    if (!realtime) return;
    const total = realtime.events.length;
    if (total === processedLenRef.current) return;

    const fresh = realtime.events.slice(processedLenRef.current, total);
    processedLenRef.current = total;

    setNotifications((prev) => {
      const seen = new Set(prev.map((n) => n.id));
      const toAdd: Notification[] = [];
      for (const ev of fresh) {
        const note = eventToNotification(ev);
        if (!note) continue;
        if (seen.has(note.id)) continue;
        seen.add(note.id);
        toAdd.push(note);
      }
      if (toAdd.length === 0) return prev;
      const merged = [...toAdd.reverse(), ...prev];
      return merged.length > MAX_NOTIFICATIONS_IN_PANEL
        ? merged.slice(0, MAX_NOTIFICATIONS_IN_PANEL)
        : merged;
    });
  }, [realtime?.events.length, realtime]);

  const unreadCount = notifications.filter(n => !n.read).length;

  const markAsRead = (id: string) => {
    setNotifications(prev =>
      prev.map(n => (n.id === id ? { ...n, read: true } : n))
    );
  };

  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
  };

  const deleteNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const handleAction = (notification: Notification) => {
    markAsRead(notification.id);
    if (notification.actionPath) {
      navigate(notification.actionPath);
      onClose();
    }
  };

  const handleSimulate = (notification: Notification) => {
    markAsRead(notification.id);
    if (notification.simulateAction) {
      const params = new URLSearchParams({
        action: notification.simulateAction.type,
        ...notification.simulateAction.params,
      });
      navigate(`/twin?${params.toString()}`);
      onClose();
    }
  };

  const getIcon = (type: Notification['type']) => {
    switch (type) {
      case 'critical':
        return <AlertTriangle size={18} className="text-red-400" />;
      case 'warning':
        return <AlertCircle size={18} className="text-amber-400" />;
      case 'success':
        return <CheckCircle size={18} className="text-emerald-400" />;
      case 'info':
        return <Info size={18} className="text-blue-400" />;
    }
  };

  const getBorderColor = (type: Notification['type']) => {
    switch (type) {
      case 'critical':
        return 'border-l-red-500';
      case 'warning':
        return 'border-l-amber-500';
      case 'success':
        return 'border-l-emerald-500';
      case 'info':
        return 'border-l-blue-500';
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[180]"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed top-16 right-4 w-96 max-h-[70vh] bg-bg-card border border-border-subtle rounded-xl shadow-2xl z-[181] animate-in fade-in slide-in-from-top-2 duration-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle bg-bg-secondary/50">
          <div className="flex items-center gap-2">
            <Bell size={18} className="text-accent" />
            <span className="font-semibold text-text-white">Notificações</span>
            {unreadCount > 0 && (
              <span className="px-1.5 py-0.5 bg-accent/20 text-accent text-xs font-bold rounded-full">
                {unreadCount} novas
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {unreadCount > 0 && (
              <button
                onClick={markAllAsRead}
                className="p-1.5 hover:bg-bg-secondary rounded-lg transition-colors text-text-tertiary hover:text-text-white"
                title="Marcar todas como lidas"
              >
                <CheckCircle size={16} />
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-bg-secondary rounded-lg transition-colors text-text-tertiary hover:text-text-white"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Notifications List */}
        <div className="max-h-[calc(70vh-120px)] overflow-y-auto">
          {notifications.length === 0 ? (
            <div className="px-4 py-12 text-center">
              <Bell size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" />
              <p className="text-text-tertiary">Sem notificações</p>
            </div>
          ) : (
            notifications.map(notification => (
              <div
                key={notification.id}
                className={`
                  px-4 py-3 border-b border-border-subtle last:border-b-0
                  border-l-4 ${getBorderColor(notification.type)}
                  ${!notification.read ? 'bg-accent/5' : ''}
                  transition-colors hover:bg-bg-secondary/50
                `}
              >
                <div className="flex items-start gap-3">
                  <div className="mt-0.5">{getIcon(notification.type)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <p className={`font-medium truncate ${!notification.read ? 'text-text-white' : 'text-text-secondary'}`}>
                        {notification.title}
                      </p>
                      <button
                        onClick={() => deleteNotification(notification.id)}
                        className="p-1 hover:bg-bg-secondary rounded opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Trash2 size={12} className="text-text-tertiary" />
                      </button>
                    </div>
                    <p className="text-xs text-text-tertiary mt-0.5 line-clamp-2">
                      {notification.message}
                    </p>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs text-text-tertiary">
                        {formatDistanceToNow(notification.timestamp, { addSuffix: true, locale: pt })}
                      </span>
                      <div className="flex items-center gap-1">
                        {notification.actionLabel && (
                          <button
                            onClick={() => handleAction(notification)}
                            className="flex items-center gap-1 px-2 py-1 text-xs text-accent hover:bg-accent/10 rounded transition-colors"
                          >
                            <Eye size={12} />
                            {notification.actionLabel}
                          </button>
                        )}
                        {notification.simulateAction && (
                          <button
                            onClick={() => handleSimulate(notification)}
                            className="flex items-center gap-1 px-2 py-1 text-xs text-blue-400 hover:bg-blue-400/10 rounded transition-colors"
                          >
                            <Play size={12} />
                            Simular
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-border-subtle bg-bg-secondary/50">
          <button
            onClick={() => {
              navigate('/settings');
              onClose();
            }}
            className="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-white transition-colors"
          >
            <Settings size={12} />
            Configurar alertas
          </button>
          <span className="text-xs text-text-tertiary">
            {notifications.length} notificações
          </span>
        </div>
      </div>
    </>
  );
}

export default NotificationsPanel;

