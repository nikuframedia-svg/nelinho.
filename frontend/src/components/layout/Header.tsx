import { Search, Bell } from 'lucide-react';

interface HeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export function Header({ title, subtitle, actions }: HeaderProps) {
  return (
    <header className="h-18 bg-white/60 backdrop-blur-xl border-b border-slate-100/50 px-6 flex items-center justify-between sticky top-0 z-20">
      <div className="flex items-center gap-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900">{title}</h1>
          {subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Search */}
        <div className="relative">
          <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Enter your search request..."
            className="w-72 pl-11 pr-4 py-3 rounded-full border border-slate-200 bg-white text-slate-900 text-sm focus:outline-none focus:border-slate-300 focus:ring-4 focus:ring-slate-100/50 transition-all placeholder:text-slate-400"
          />
        </div>

        {/* Notifications */}
        <button className="relative p-3 rounded-2xl hover:bg-slate-100 transition-colors group">
          <Bell size={20} className="text-slate-500 group-hover:text-slate-700 transition-colors" />
          <span className="absolute top-2.5 right-2.5 w-2.5 h-2.5 bg-red-500 rounded-full border-2 border-white" />
        </button>

        {/* Actions */}
        {actions}

        {/* User avatar */}
        <div className="w-11 h-11 rounded-full bg-gradient-to-br from-pink-400 to-pink-600 overflow-hidden ring-2 ring-white shadow-lg cursor-pointer hover:ring-4 transition-all">
          <img 
            src="https://api.dicebear.com/7.x/avataaars/svg?seed=user&backgroundColor=ffdfbf" 
            alt="User"
            className="w-full h-full object-cover"
          />
        </div>
      </div>
    </header>
  );
}
