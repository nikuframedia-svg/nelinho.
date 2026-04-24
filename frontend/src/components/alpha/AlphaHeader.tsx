import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Bell, Settings, ChevronDown, Command } from 'lucide-react';
import { NavTab } from './NavTab';
import { NotificationsPanel } from '../notifications/NotificationsPanel';
import { UmweltSwitcher } from '../dashboard/UmweltSwitcher';
import { useCommandPalette } from '../../hooks';

const navItems = [
  { label: 'Dashboard', path: '/' },
  { label: 'Inbox', path: '/inbox' },
  { label: 'Factory', path: '/core/products' },
  { label: 'Workforce', path: '/workforce' },
  { label: 'Planning', path: '/plan/scheduling' },
  { label: 'Twin', path: '/twin' },
  { label: 'Data Quality', path: '/admin/data-quality' },
  { label: 'Tools', path: '/admin/tool-registry' },
];

export function AlphaHeader() {
  const location = useLocation();
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const { open: openCommandPalette } = useCommandPalette();
  
  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  // Mock notification count (would come from context/API in production)
  const notificationCount = 3;

  return (
    <header className="alpha-header">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            className="w-5 h-5 text-bg-base"
            stroke="currentColor"
            strokeWidth={2.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 3L3 9l9 6 9-6-9-6z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 15l9 6 9-6"
            />
          </svg>
        </div>
        <span className="text-lg font-semibold text-text-white">ProdPlan.</span>
      </div>

      {/* Center Navigation */}
      <nav className="alpha-nav">
        {navItems.map((item) => (
          <NavLink key={item.path} to={item.path}>
            <NavTab active={isActive(item.path)}>
              {item.label}
            </NavTab>
          </NavLink>
        ))}
      </nav>

      {/* Right Section */}
      <div className="flex items-center gap-3">
        {/* Sprint H — Umwelt switcher */}
        <UmweltSwitcher className="hidden md:inline-flex" />

        {/* Command Palette Trigger */}
        <button
          onClick={openCommandPalette}
          className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-bg-secondary/50 hover:bg-bg-secondary rounded-lg text-text-tertiary hover:text-text-white transition-colors"
          title="Command Palette (⌘+K)"
        >
          <Command size={14} />
          <span className="text-xs">⌘K</span>
        </button>

        {/* Notifications */}
        <button 
          onClick={() => setIsNotificationsOpen(!isNotificationsOpen)}
          className={`alpha-icon-btn relative ${isNotificationsOpen ? 'bg-bg-secondary' : ''}`}
        >
          <Bell size={18} />
          {notificationCount > 0 && (
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-orange rounded-full text-[10px] font-bold flex items-center justify-center text-white animate-pulse">
              {notificationCount}
            </span>
          )}
        </button>
        
        <NavLink to="/settings" className="alpha-icon-btn">
          <Settings size={18} />
        </NavLink>

        {/* User Dropdown */}
        <button className="alpha-user-dropdown">
          <img
            src="https://api.dicebear.com/7.x/avataaars/svg?seed=Nuno"
            alt="Avatar"
            className="alpha-avatar"
          />
          <div className="text-left">
            <p className="text-sm font-medium text-text-white">Nuno Andre Santos</p>
            <p className="text-xs text-text-muted">user@prodplan.com</p>
          </div>
          <ChevronDown size={16} className="text-text-tertiary ml-2" />
        </button>
      </div>

      {/* Notifications Panel */}
      <NotificationsPanel
        isOpen={isNotificationsOpen}
        onClose={() => setIsNotificationsOpen(false)}
      />
    </header>
  );
}




