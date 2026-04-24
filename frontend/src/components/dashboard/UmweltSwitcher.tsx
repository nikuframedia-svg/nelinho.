/**
 * UmweltSwitcher (Sprint H)
 * ===========================
 *
 * One pill each for the three user "Umwelts" the plan defines
 * (Blueprint v2.0 §7.3):
 *
 *  • **Gestor** (`/`)  — rich operational dashboard, Gantt, explain.
 *  • **Operador** (`/operador`)  — tablet touch-first "my queue".
 *  • **CEO** (`/ceo`)  — read-in-10s €/dia vs target.
 *
 * Dropped into `Layout.tsx` (or any header slot) so any user can jump
 * between them without memorising URLs. No auth yet — role gating
 * will move into the component when JWT lands in Sprint K.
 */

import { NavLink } from 'react-router-dom';
import { Briefcase, Hammer, BarChart3 } from 'lucide-react';

interface Umwelt {
  path: string;
  label: string;
  icon: React.ReactNode;
}

const UMWELTS: Umwelt[] = [
  { path: '/', label: 'Gestor', icon: <Briefcase size={14} /> },
  { path: '/operador', label: 'Operador', icon: <Hammer size={14} /> },
  { path: '/ceo', label: 'CEO', icon: <BarChart3 size={14} /> },
];

interface UmweltSwitcherProps {
  className?: string;
}

export function UmweltSwitcher({ className = '' }: UmweltSwitcherProps) {
  return (
    <div
      className={`inline-flex items-center gap-1 bg-bg-secondary/60 rounded-full p-1 border border-border-subtle ${className}`}
      role="navigation"
      aria-label="Umwelt switcher"
    >
      {UMWELTS.map((u) => (
        <NavLink
          key={u.path}
          to={u.path}
          end={u.path === '/'}
          className={({ isActive }) =>
            `flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              isActive
                ? 'bg-accent text-bg-base shadow-sm'
                : 'text-text-secondary hover:bg-bg-elevated hover:text-text-white'
            }`
          }
        >
          {u.icon}
          {u.label}
        </NavLink>
      ))}
    </div>
  );
}

export default UmweltSwitcher;
