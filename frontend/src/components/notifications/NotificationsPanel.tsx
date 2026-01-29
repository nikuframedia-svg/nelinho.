/**
 * NotificationsPanel
 * 
 * Displays real-time notifications for critical events.
 * Supports different severity levels and actions.
 */

import { useState, useEffect } from 'react';
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
// MOCK NOTIFICATIONS (would come from backend/websocket in production)
// ═══════════════════════════════════════════════════════════════════════════════

const generateMockNotifications = (): Notification[] => [
  {
    id: '1',
    type: 'critical',
    title: 'Novo bottleneck detectado',
    message: 'Laminação tem agora 450 dias de backlog teórico',
    timestamp: new Date(Date.now() - 2 * 60 * 1000), // 2 min ago
    read: false,
    actionLabel: 'Ver detalhes',
    actionPath: '/inbox',
    simulateAction: {
      type: 'capacity_adjustment',
      params: { phase: 'laminacao' },
    },
  },
  {
    id: '2',
    type: 'warning',
    title: 'Trust Index baixou',
    message: 'Backlog teórico baixou de 63% para 58%',
    timestamp: new Date(Date.now() - 15 * 60 * 1000), // 15 min ago
    read: false,
    actionLabel: 'Ver qualidade',
    actionPath: '/admin/data-quality',
  },
  {
    id: '3',
    type: 'success',
    title: 'Simulação concluída',
    message: 'Cenário "Overtime +20%" completou com sucesso',
    timestamp: new Date(Date.now() - 60 * 60 * 1000), // 1h ago
    read: true,
    actionLabel: 'Ver resultados',
    actionPath: '/twin',
  },
  {
    id: '4',
    type: 'info',
    title: 'Nova ingestão disponível',
    message: 'Folha_IA_extra.xlsx foi actualizada',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000), // 2h ago
    read: true,
    actionLabel: 'Activar',
    actionPath: '/admin/data-quality',
  },
];

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function NotificationsPanel({ isOpen, onClose }: NotificationsPanelProps) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const navigate = useNavigate();

  // Load notifications
  useEffect(() => {
    setNotifications(generateMockNotifications());
  }, []);

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

