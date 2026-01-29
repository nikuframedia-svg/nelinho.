/**
 * LiveActivityFeed
 * 
 * Real-time feed of system activity and events.
 * Shows recent actions, updates, and alerts.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  Database,
  AlertTriangle,
  CheckCircle,
  FileSpreadsheet,
  Users,
  GitBranch,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { pt } from 'date-fns/locale';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface ActivityItem {
  id: string;
  type: 'ingest' | 'alert' | 'scenario' | 'quality' | 'user' | 'system';
  title: string;
  description?: string;
  timestamp: Date;
  status?: 'success' | 'warning' | 'error' | 'pending';
  link?: string;
  metadata?: Record<string, any>;
}

interface LiveActivityFeedProps {
  maxItems?: number;
  showHeader?: boolean;
  compact?: boolean;
  className?: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// MOCK DATA (would come from WebSocket in production)
// ═══════════════════════════════════════════════════════════════════════════════

const generateMockActivity = (): ActivityItem[] => [
  {
    id: '1',
    type: 'ingest',
    title: 'Ingestão concluída',
    description: 'Folha_IA_extra.xlsx processado com sucesso',
    timestamp: new Date(Date.now() - 5 * 60 * 1000),
    status: 'success',
    link: '/admin/data-quality',
  },
  {
    id: '2',
    type: 'alert',
    title: 'Novo bottleneck detectado',
    description: 'Laminação com backlog crítico',
    timestamp: new Date(Date.now() - 12 * 60 * 1000),
    status: 'warning',
    link: '/inbox',
  },
  {
    id: '3',
    type: 'scenario',
    title: 'Simulação completada',
    description: '"Overtime +20%" pronto para revisão',
    timestamp: new Date(Date.now() - 25 * 60 * 1000),
    status: 'success',
    link: '/twin',
  },
  {
    id: '4',
    type: 'quality',
    title: 'Trust Index actualizado',
    description: 'Backlog teórico: 58% → 60%',
    timestamp: new Date(Date.now() - 45 * 60 * 1000),
    status: 'success',
  },
  {
    id: '5',
    type: 'user',
    title: 'Maria Silva aprovou cenário',
    description: 'Cenário "Redistribuição Moldes" publicado',
    timestamp: new Date(Date.now() - 90 * 60 * 1000),
    status: 'success',
    link: '/twin',
  },
  {
    id: '6',
    type: 'system',
    title: 'Backup automático',
    description: 'Snapshot criado com sucesso',
    timestamp: new Date(Date.now() - 120 * 60 * 1000),
    status: 'success',
  },
];

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function LiveActivityFeed({
  maxItems = 6,
  showHeader = true,
  compact = false,
  className = '',
}: LiveActivityFeedProps) {
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    setActivities(generateMockActivity().slice(0, maxItems));
  }, [maxItems]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => {
      setActivities(generateMockActivity().slice(0, maxItems));
      setIsRefreshing(false);
    }, 1000);
  };

  const getIcon = (type: ActivityItem['type'], status?: ActivityItem['status']) => {
    const iconClass = status === 'error' 
      ? 'text-red-400' 
      : status === 'warning' 
      ? 'text-amber-400' 
      : 'text-accent';
    
    switch (type) {
      case 'ingest':
        return <FileSpreadsheet size={16} className={iconClass} />;
      case 'alert':
        return <AlertTriangle size={16} className={iconClass} />;
      case 'scenario':
        return <GitBranch size={16} className={iconClass} />;
      case 'quality':
        return <Database size={16} className={iconClass} />;
      case 'user':
        return <Users size={16} className={iconClass} />;
      case 'system':
        return <Activity size={16} className={iconClass} />;
      default:
        return <CheckCircle size={16} className={iconClass} />;
    }
  };

  const getStatusDot = (status?: ActivityItem['status']) => {
    const colors = {
      success: 'bg-emerald-400',
      warning: 'bg-amber-400',
      error: 'bg-red-400',
      pending: 'bg-blue-400 animate-pulse',
    };
    return colors[status || 'success'];
  };

  return (
    <div className={`bg-bg-card border border-border-subtle rounded-xl ${className}`}>
      {showHeader && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
          <div className="flex items-center gap-2">
            <Activity size={18} className="text-accent" />
            <span className="font-semibold text-text-white">Actividade</span>
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          </div>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="p-1.5 hover:bg-bg-secondary rounded-lg transition-colors"
            title="Actualizar"
          >
            <RefreshCw 
              size={14} 
              className={`text-text-tertiary ${isRefreshing ? 'animate-spin' : ''}`} 
            />
          </button>
        </div>
      )}

      <div className={compact ? 'py-2' : 'py-3'}>
        {activities.map((activity, index) => (
          <div
            key={activity.id}
            className={`
              flex items-start gap-3 px-4 
              ${compact ? 'py-2' : 'py-3'}
              ${activity.link ? 'cursor-pointer hover:bg-bg-secondary/50' : ''}
              transition-colors
              ${index > 0 ? 'border-t border-border-subtle/50' : ''}
            `}
            onClick={() => activity.link && navigate(activity.link)}
            style={{ animationDelay: `${index * 50}ms` }}
          >
            {/* Icon */}
            <div className="mt-0.5 relative">
              {getIcon(activity.type, activity.status)}
              <span 
                className={`absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full ${getStatusDot(activity.status)} border border-bg-card`}
              />
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-text-white truncate">
                {activity.title}
              </p>
              {activity.description && !compact && (
                <p className="text-xs text-text-tertiary mt-0.5 truncate">
                  {activity.description}
                </p>
              )}
              <p className="text-xs text-text-muted mt-1">
                {formatDistanceToNow(activity.timestamp, { addSuffix: true, locale: pt })}
              </p>
            </div>

            {/* Action */}
            {activity.link && (
              <ArrowRight size={14} className="text-text-tertiary opacity-0 group-hover:opacity-100 transition-opacity mt-1" />
            )}
          </div>
        ))}
      </div>

      {!compact && (
        <div className="px-4 py-2 border-t border-border-subtle">
          <button
            onClick={() => navigate('/activity')}
            className="w-full text-center text-xs text-accent hover:text-accent-light transition-colors"
          >
            Ver toda a actividade →
          </button>
        </div>
      )}
    </div>
  );
}

export default LiveActivityFeed;

