import { Plus, Calendar, Search } from 'lucide-react';

interface GreetingSectionProps {
  userName?: string;
  notificationCount?: number;
}

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good Morning';
  if (hour < 18) return 'Good Afternoon';
  return 'Good Evening';
}

function formatDate(): string {
  const now = new Date();
  const options: Intl.DateTimeFormatOptions = { 
    weekday: 'short', 
    day: 'numeric', 
    month: 'short' 
  };
  return now.toLocaleDateString('en-US', options);
}

export function GreetingSection({ 
  userName = 'Martim', 
  notificationCount = 12 
}: GreetingSectionProps) {
  const greeting = getGreeting();
  const date = formatDate();

  return (
    <div className="alpha-greeting">
      <h1 className="alpha-greeting-text">
        <span className="name">Hi {userName}, </span>
        <span className="period">{greeting}!</span>
      </h1>

      <div className="alpha-greeting-actions">
        {/* Create New Request Button */}
        <button className="alpha-btn-create">
          <Plus size={18} />
          Create New Request
        </button>

        {/* Date Badge */}
        <div className="alpha-date-badge">
          <Calendar size={16} />
          <span>{date}</span>
          {notificationCount > 0 && (
            <span className="notification">{notificationCount}</span>
          )}
        </div>

        {/* Search Button */}
        <button className="alpha-icon-btn">
          <Search size={18} />
        </button>
      </div>
    </div>
  );
}







