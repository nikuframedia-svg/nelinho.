/**
 * Sidebar — navegação principal alinhada com FRONTEND_DESIGN_PROMPT.md.
 *
 * 8 páginas em 3 grupos (jornada do utilizador, não topologia backend):
 *   Operação  → Painel · Produção · Planeamento · Expedição
 *   Análise   → Equipa · Qualidade · Relatórios
 *   Sistema   → Configuração
 *
 * Inspiração visual: design/nelo-zip/src/shell.jsx (3 grupos).
 *
 * Durante o refactor incremental Q.18.UI.B-J, alguns paths ainda fazem
 * redirect para a rota antiga (ver App.tsx). À medida que cada página
 * é construída, o path passa a apontar para a versão nativa.
 *
 * Sprint Q.18.UI.A.
 */

import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Factory,
  CalendarDays,
  Truck,
  Users,
  Shield,
  FileText,
  Settings,
  Sparkles,
  HelpCircle,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { cn } from '../../lib/utils';
import { useCapabilities } from '../../providers';
import { authApi, type CurrentUser } from '../../lib/api';

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0 || parts[0] === '') return '—';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function roleLabel(role: string): string {
  const map: Record<string, string> = {
    manager: 'Gestor',
    operator: 'Operador',
    ceo: 'CEO',
    admin: 'Administrador',
    admin_platform: 'Administrador',
    admin_tenant: 'Administrador',
  };
  return map[role.toLowerCase()] ?? role;
}

interface NavItem {
  /** Path canónico (PT-PT). */
  path: string;
  /** Label em PT-PT — texto curto. */
  label: string;
  icon: ReactNode;
  /** Capability gate (omitir = sempre visível). */
  module?: string;
  /** Badge dinâmico (count). Implementado mais tarde com queries reais. */
  badge?: number;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV: NavGroup[] = [
  {
    label: 'Operação',
    items: [
      {
        path: '/painel',
        label: 'Painel',
        icon: <LayoutDashboard size={18} />,
      },
      {
        path: '/producao',
        label: 'Produção',
        icon: <Factory size={18} />,
      },
      {
        path: '/planeamento',
        label: 'Planeamento',
        icon: <CalendarDays size={18} />,
      },
      {
        path: '/expedicao',
        label: 'Expedição',
        icon: <Truck size={18} />,
      },
    ],
  },
  {
    label: 'Análise',
    items: [
      {
        path: '/equipa',
        label: 'Equipa',
        icon: <Users size={18} />,
      },
      {
        path: '/qualidade',
        label: 'Qualidade',
        icon: <Shield size={18} />,
      },
      {
        path: '/relatorios',
        label: 'Relatórios',
        icon: <FileText size={18} />,
      },
    ],
  },
  {
    label: 'Sistema',
    items: [
      {
        path: '/configuracao',
        label: 'Configuração',
        icon: <Settings size={18} />,
      },
    ],
  },
];

export function Sidebar() {
  const location = useLocation();

  let hasModule: (module: string) => boolean;
  try {
    const capabilities = useCapabilities();
    hasModule = capabilities.hasModule;
  } catch {
    hasModule = () => true;
  }

  // Sprint Q.18.UI.A.1 — utilizador real vem de /v1/auth/me. ZERO MOCKS:
  // se erro / loading, mostra placeholder explícito ("—"), nunca dados
  // hardcoded.
  const meQuery = useQuery<CurrentUser>({
    queryKey: ['auth', 'me'],
    queryFn: () => authApi.me(),
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
  const me = meQuery.data;

  const isActive = (path: string): boolean => {
    if (path === '/painel') {
      return location.pathname === '/painel' || location.pathname === '/';
    }
    return location.pathname === path || location.pathname.startsWith(path + '/');
  };

  return (
    <aside className="w-64 h-screen bg-gradient-to-b from-dark-800 to-dark-700 border-r border-white/[0.06] flex flex-col fixed left-0 top-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent-500 to-accent-600 flex items-center justify-center shadow-glow-teal">
            <Sparkles size={18} className="text-white" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-text-dark-primary tracking-tight leading-tight">
              NELO
            </div>
            <div className="text-[10px] text-accent-400 font-medium tracking-widest uppercase">
              ProdPlan ONE
            </div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 overflow-y-auto" aria-label="Navegação principal">
        {NAV.map((group) => {
          const visibleItems = group.items.filter(
            (item) => !item.module || hasModule(item.module)
          );
          if (visibleItems.length === 0) return null;
          return (
            <div key={group.label} className="mb-6 last:mb-0">
              <div className="px-3 mb-2">
                <span className="text-[10px] font-semibold uppercase tracking-widest text-text-dark-tertiary">
                  {group.label}
                </span>
              </div>
              <ul className="flex flex-col gap-0.5">
                {visibleItems.map((item) => {
                  const active = isActive(item.path);
                  return (
                    <li key={item.path}>
                      <NavLink
                        to={item.path}
                        className={cn(
                          'group flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150 relative',
                          active
                            ? 'bg-accent-500/15 text-accent-400 border border-accent-500/30'
                            : 'text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-transparent'
                        )}
                      >
                        {active ? (
                          <span
                            className="absolute left-0 top-2 bottom-2 w-0.5 bg-accent-400 rounded-r"
                            aria-hidden="true"
                          />
                        ) : null}
                        <span
                          className={cn(
                            'shrink-0',
                            active ? 'text-accent-400' : 'text-text-dark-tertiary group-hover:text-text-dark-secondary'
                          )}
                        >
                          {item.icon}
                        </span>
                        <span className="flex-1 truncate">{item.label}</span>
                        {item.badge !== undefined && item.badge > 0 ? (
                          <span className="inline-flex items-center justify-center min-w-[18px] h-4 px-1 rounded-full text-[10px] font-bold bg-orange-500 text-white tabular-nums">
                            {item.badge}
                          </span>
                        ) : null}
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>

      {/* Bottom — help + user */}
      <div className="px-3 py-4 border-t border-white/[0.06]">
        <button
          type="button"
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-text-dark-tertiary hover:bg-white/5 hover:text-text-dark-secondary transition-colors duration-150"
          aria-label="Ajuda"
        >
          <HelpCircle size={18} className="opacity-80" />
          <span>Ajuda</span>
        </button>

        <div className="mt-3 pt-3 border-t border-white/[0.06]">
          <div
            className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
            title={me?.email ?? '—'}
          >
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-accent-500/30 to-accent-700/30 border border-accent-500/40 flex items-center justify-center text-xs font-bold text-accent-300">
              {me ? initials(me.name) : '—'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-text-dark-primary truncate">
                {meQuery.isError ? '—' : me?.name ?? 'A carregar…'}
              </p>
              <p className="text-[10px] text-text-dark-tertiary truncate">
                NELO · {me ? roleLabel(me.role) : (meQuery.isError ? 'sem ligação' : '…')}
              </p>
            </div>
            <div
              className={cn(
                'w-2 h-2 rounded-full',
                meQuery.isError
                  ? 'bg-danger'
                  : meQuery.isLoading
                  ? 'bg-warning'
                  : 'bg-success shadow-glow-green'
              )}
              aria-label={
                meQuery.isError
                  ? 'Sem ligação'
                  : meQuery.isLoading
                  ? 'A ligar'
                  : 'Online'
              }
            />
          </div>
        </div>
      </div>
    </aside>
  );
}
