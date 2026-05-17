/**
 * UmweltPills — switcher 3 papéis para TopBar (Onda 12 L).
 * Gestor (default, write) / Operador (touch-first) / CEO (read-only).
 */

import { Briefcase, Hammer, BarChart3, Lock } from 'lucide-react';
import { useUmwelt, type Umwelt } from '../../lib/umwelt';

const PILLS: Array<{ id: Umwelt; label: string; icon: React.ComponentType<{ size?: number }> }> = [
  { id: 'gestor', label: 'Gestor', icon: Briefcase },
  { id: 'operador', label: 'Operador', icon: Hammer },
  { id: 'ceo', label: 'CEO', icon: BarChart3 },
];

export function UmweltPills() {
  const { umwelt, setUmwelt, isReadOnly } = useUmwelt();
  return (
    <div
      className="inline-flex items-center gap-0.5 rounded-md p-0.5 text-xs"
      style={{ background: 'var(--bg-2)', border: '1px solid var(--bd-1)' }}
    >
      {PILLS.map((p) => {
        const Icon = p.icon;
        const active = umwelt === p.id;
        return (
          <button
            key={p.id}
            type="button"
            onClick={() => setUmwelt(p.id)}
            className="flex items-center gap-1 px-2 py-1 rounded transition-colors"
            style={{
              background: active ? 'var(--bg-3)' : 'transparent',
              color: active ? 'var(--fg-1)' : 'var(--fg-3)',
            }}
            title={p.id === 'ceo' ? 'Vista read-only — sem write actions' : undefined}
          >
            <Icon size={11} />
            <span>{p.label}</span>
            {p.id === 'ceo' && active && <Lock size={10} style={{ color: 'var(--yellow)' }} />}
          </button>
        );
      })}
      {isReadOnly && (
        <span className="ml-1 px-2 py-0.5 rounded text-[10px] font-medium" style={{ background: 'var(--yellow-bg)', color: 'var(--yellow)' }}>
          Read-only
        </span>
      )}
    </div>
  );
}
