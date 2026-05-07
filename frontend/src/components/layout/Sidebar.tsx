import { NavLink } from 'react-router-dom';
import { cn } from '../../lib/utils';
import {
  LayoutDashboard,
  CalendarDays,
  Package,
  Users,
  DollarSign,
  Settings,
  ChevronDown,
  Sparkles,
  Warehouse,
  FileCheck,
  HelpCircle,
  Info,
  GitBranch,
  FlaskConical,
  Lightbulb,
  Inbox,
  CheckSquare,
  Database,
  Shield,
  Brain,
  BookOpen,
} from 'lucide-react';
import { useState } from 'react';
import { useCapabilities } from '../../providers';

interface NavItem {
  label: string;
  icon: React.ReactNode;
  path?: string;
  children?: { label: string; path: string }[];
  module?: string; // Optional module requirement
}

const navItems: NavItem[] = [
  {
    label: 'Dashboard',
    icon: <LayoutDashboard size={20} />,
    path: '/',
  },
  {
    label: 'Ops Inbox',
    icon: <Inbox size={20} />,
    path: '/inbox',
  },
  {
    label: 'Decisões',
    icon: <CheckSquare size={20} />,
    path: '/decisoes',
  },
  {
    label: 'Aprendizagem',
    icon: <Brain size={20} />,
    path: '/aprendizagem',
  },
  {
    label: 'Operadores',
    icon: <Users size={20} />,
    path: '/operadores',
  },
  {
    label: 'CORE',
    icon: <Package size={20} />,
    module: 'core',
    children: [
      { label: 'Products', path: '/core/products' },
      { label: 'Machines', path: '/core/machines' },
      { label: 'Employees', path: '/core/employees' },
      { label: 'Operations', path: '/core/operations' },
      { label: 'BOM', path: '/core/bom' },
      { label: 'Customers', path: '/core/customers' },
      { label: 'Suppliers', path: '/core/suppliers' },
      { label: 'Rates', path: '/core/rates' },
      { label: 'Tenants', path: '/core/tenants' },
    ],
  },
  {
    label: 'Planning',
    icon: <CalendarDays size={20} />,
    module: 'plan',
    children: [
      { label: 'Scheduling', path: '/plan/scheduling' },
      { label: 'Timeline', path: '/plan/timeline' },
      { label: 'MRP', path: '/plan/mrp' },
      { label: 'Capacity', path: '/plan/capacity' },
    ],
  },
  {
    label: 'Profit',
    icon: <DollarSign size={20} />,
    module: 'profit',
    children: [
      { label: 'KPIs', path: '/profit/kpis' },
      { label: 'OEE', path: '/profit/oee' },
      { label: 'Quality', path: '/profit/quality' },
      { label: 'COGS Analysis', path: '/profit/cogs' },
      { label: 'Pricing', path: '/profit/pricing' },
      { label: 'Scenarios', path: '/profit/scenarios' },
    ],
  },
  {
    label: 'HR',
    icon: <Users size={20} />,
    module: 'hr',
    children: [
      { label: 'Allocations', path: '/hr/allocations' },
      { label: 'Payroll', path: '/hr/payroll' },
      { label: 'Productivity', path: '/hr/productivity' },
    ],
  },
  {
    label: 'Supply',
    icon: <Warehouse size={20} />,
    module: 'supply',
    children: [
      { label: 'Inventory', path: '/supply/inventory' },
      { label: 'Forecast', path: '/supply/forecast' },
      { label: 'ROP', path: '/supply/rop' },
      { label: 'ABC Analysis', path: '/supply/abc' },
    ],
  },
  {
    label: 'Decisions',
    icon: <FileCheck size={20} />,
    module: 'decisions',
    path: '/decisions',
  },
];

// New advanced modules
const advancedNavItems: NavItem[] = [
  {
    label: 'Explainability',
    icon: <Info size={20} />,
    module: 'explain',
    path: '/explain',
  },
  {
    label: 'Digital Twin',
    icon: <GitBranch size={20} />,
    module: 'twin',
    path: '/twin',
  },
  {
    label: 'Sandbox',
    icon: <FlaskConical size={20} />,
    module: 'sandbox',
    path: '/sandbox',
  },
  {
    label: 'Suggestions',
    icon: <Lightbulb size={20} />,
    module: 'improve',
    path: '/suggestions',
  },
];

// Data Management (Admin)
const dataNavItems: NavItem[] = [
  {
    label: 'Data Ingestion',
    icon: <Database size={20} />,
    path: '/admin/data-ingestion',
  },
  {
    label: 'Data Quality',
    icon: <Shield size={20} />,
    path: '/admin/data-quality',
  },
  {
    label: 'Regras Aprendidas',
    icon: <Brain size={20} />,
    path: '/admin/learned-rules',
  },
  {
    label: 'Regras (NL→YAML)',
    icon: <BookOpen size={20} />,
    path: '/admin/regras',
  },
];

const bottomNavItems: NavItem[] = [
  {
    label: 'Settings',
    icon: <Settings size={20} />,
    path: '/settings',
  },
];

export function Sidebar() {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    CORE: true,
    Planning: true,
    Profit: true,
    HR: true,
    Supply: true,
  });
  
  // Get capabilities (with fallback for when provider not available)
  let hasModule: (module: string) => boolean;
  try {
    const capabilities = useCapabilities();
    hasModule = capabilities.hasModule;
  } catch {
    // If CapabilitiesProvider not available, show all items
    hasModule = () => true;
  }

  const toggleExpand = (label: string) => {
    setExpanded((prev) => ({ ...prev, [label]: !prev[label] }));
  };

  const renderNavItem = (item: NavItem) => {
    // Check module requirement
    if (item.module && !hasModule(item.module)) {
      return null;
    }
    
    if (item.path) {
      return (
        <NavLink
          to={item.path}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 px-4 py-3 rounded-xl text-[14px] font-medium transition-all duration-200',
              isActive
                ? 'bg-accent-500/15 text-accent-400 border border-accent-500/30 shadow-glow-teal'
                : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
            )
          }
        >
          <span className="text-current opacity-80">{item.icon}</span>
          <span>{item.label}</span>
        </NavLink>
      );
    }

    return (
      <>
        <button
          onClick={() => toggleExpand(item.label)}
          className="w-full flex items-center justify-between px-4 py-3 rounded-xl text-[14px] font-medium text-slate-400 hover:bg-white/5 hover:text-slate-200 transition-all duration-200"
        >
          <div className="flex items-center gap-3">
            <span className="opacity-80">{item.icon}</span>
            <span>{item.label}</span>
          </div>
          <ChevronDown
            size={16}
            className={cn(
              'opacity-50 transition-transform duration-200',
              expanded[item.label] && 'rotate-180'
            )}
          />
        </button>
        <div className={cn(
          "overflow-hidden transition-all duration-200",
          expanded[item.label] ? "max-h-[400px] opacity-100" : "max-h-0 opacity-0"
        )}>
          {item.children && (
            <div className="ml-10 mt-1 space-y-1">
              {item.children.map((child) => (
                <NavLink
                  key={child.path}
                  to={child.path}
                  className={({ isActive }) =>
                    cn(
                      'block px-4 py-2.5 rounded-lg text-[13px] transition-all duration-200',
                      isActive
                        ? 'text-accent-400 font-semibold bg-accent-500/10'
                        : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'
                    )
                  }
                >
                  {child.label}
                </NavLink>
              ))}
            </div>
          )}
        </div>
      </>
    );
  };

  // Filter nav items based on capabilities
  const visibleNavItems = navItems.filter(item => !item.module || hasModule(item.module));
  const visibleAdvancedItems = advancedNavItems.filter(item => !item.module || hasModule(item.module));

  return (
    <aside className="w-64 h-screen bg-gradient-to-b from-dark-800 to-dark-700 border-r border-white/[0.06] flex flex-col fixed left-0 top-0">
      {/* Logo */}
      <div className="h-18 flex items-center px-5 py-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-500 to-accent-600 flex items-center justify-center shadow-glow-teal">
            <Sparkles size={20} className="text-white" />
          </div>
          <div>
            <span className="font-bold text-xl text-white tracking-tight">ProdPlan</span>
            <span className="block text-[10px] text-accent-400 font-medium tracking-widest uppercase">ONE</span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 overflow-y-auto">
        <ul className="space-y-1">
          {visibleNavItems.map((item) => {
            const rendered = renderNavItem(item);
            return rendered ? <li key={item.label}>{rendered}</li> : null;
          })}
        </ul>
        
        {/* Advanced Modules Section */}
        {visibleAdvancedItems.length > 0 && (
          <>
            <div className="mt-6 mb-3 px-4">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">
                Advanced
              </p>
            </div>
            <ul className="space-y-1">
              {visibleAdvancedItems.map((item) => {
                const rendered = renderNavItem(item);
                return rendered ? <li key={item.label}>{rendered}</li> : null;
              })}
            </ul>
          </>
        )}
        
        {/* Data Management Section */}
        {dataNavItems.length > 0 && (
          <>
            <div className="mt-6 mb-3 px-4">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">
                Data
              </p>
            </div>
            <ul className="space-y-1">
              {dataNavItems.map((item) => {
                const rendered = renderNavItem(item);
                return rendered ? <li key={item.label}>{rendered}</li> : null;
              })}
            </ul>
          </>
        )}
      </nav>

      {/* Bottom */}
      <div className="px-3 py-4 border-t border-white/[0.06]">
        <ul className="space-y-1">
          {bottomNavItems.map((item) => (
            <li key={item.label}>{renderNavItem(item)}</li>
          ))}
        </ul>
        
        {/* Help Link */}
        <button className="w-full flex items-center gap-3 px-4 py-3 mt-2 rounded-xl text-[14px] font-medium text-slate-500 hover:bg-white/5 hover:text-slate-300 transition-all duration-200">
          <HelpCircle size={20} className="opacity-80" />
          <span>Help & Support</span>
        </button>
        
        {/* User Profile */}
        <div className="mt-4 pt-4 border-t border-white/[0.06]">
          <div className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-white/5 transition-colors cursor-pointer">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-500/30 to-accent-600/30 border border-accent-500/30 flex items-center justify-center text-sm font-bold text-accent-400">
              MN
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-200 truncate">Martim N.</p>
              <p className="text-xs text-slate-500 truncate">Administrator</p>
            </div>
            <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-glow-green"></div>
          </div>
        </div>
      </div>
    </aside>
  );
}
