import { MoreHorizontal, Phone, MessageSquare } from 'lucide-react';
import { cn } from '../../lib/utils';

interface TimelineEvent {
  id: string;
  title: string;
  location: string;
  time: string;
  date: string;
  status: 'active' | 'completed' | 'pending';
  courier?: {
    name: string;
    avatar?: string;
  };
}

interface TrackingDeliveryProps {
  trackingId?: string;
  deliveryStatus?: 'Delivered' | 'In Transit' | 'Processing';
  events?: TimelineEvent[];
}

const defaultEvents: TimelineEvent[] = [
  {
    id: '1',
    title: 'Your package is being delivered up by courier',
    location: 'London, UK',
    time: '09:12 AM',
    date: 'Today',
    status: 'active',
    courier: {
      name: 'Wataru Endo',
      avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Wataru',
    },
  },
  {
    id: '2',
    title: 'In Transit',
    location: 'London, UK',
    time: '09:12 AM',
    date: 'Today',
    status: 'completed',
  },
];

const statusColors = {
  'Delivered': 'text-success',
  'In Transit': 'text-info',
  'Processing': 'text-warning',
};

export function TrackingDelivery({
  trackingId = '#281731-22-922ppk',
  deliveryStatus = 'Delivered',
  events = defaultEvents,
}: TrackingDeliveryProps) {
  return (
    <div className="alpha-card">
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-base font-semibold text-text-white">Tracking Delivery</h3>
        <button className="alpha-menu-btn">
          <MoreHorizontal size={18} />
        </button>
      </div>
      <p className="text-sm text-text-muted mb-4">Track your delivered order.</p>

      {/* Tracking Info */}
      <div className="flex items-center justify-between py-3 border-y border-border-subtle mb-4">
        <div>
          <p className="text-xs text-text-muted mb-1">Tracking ID</p>
          <p className="text-sm font-semibold text-text-white">{trackingId}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-text-muted mb-1">Status</p>
          <p className={cn('text-sm font-semibold', statusColors[deliveryStatus])}>
            {deliveryStatus}
          </p>
        </div>
      </div>

      {/* Timeline */}
      <div className="alpha-timeline">
        {events.map((event, _index) => (
          <div key={event.id} className="alpha-timeline-item">
            <div className={cn(
              'alpha-timeline-dot',
              event.status === 'active' && 'active',
              event.status === 'completed' && 'completed'
            )} />

            <div>
              <p className="text-sm text-text-white mb-1">{event.title}</p>
              <p className="text-xs text-text-muted">
                {event.date}, {event.location}, {event.time}
              </p>

              {/* Courier Card */}
              {event.courier && (
                <div className="mt-3 flex items-center justify-between p-3 bg-bg-elevated rounded-xl">
                  <div className="flex items-center gap-3">
                    <img
                      src={event.courier.avatar}
                      alt={event.courier.name}
                      className="w-10 h-10 rounded-full"
                    />
                    <div>
                      <p className="text-xs text-text-muted">Courier</p>
                      <p className="text-sm font-medium text-text-white">{event.courier.name}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button className="w-9 h-9 rounded-full bg-bg-card border border-border-subtle flex items-center justify-center text-text-secondary hover:bg-bg-card-hover transition-colors">
                      <Phone size={16} />
                    </button>
                    <button className="w-9 h-9 rounded-full bg-bg-card border border-border-subtle flex items-center justify-center text-text-secondary hover:bg-bg-card-hover transition-colors">
                      <MessageSquare size={16} />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}




