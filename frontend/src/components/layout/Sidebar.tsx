/**
 * Sidebar — port literal de design/nelo-zip/src/shell.jsx Sidebar.
 *
 * 10 itens em 3 grupos:
 *   OPERAÇÃO  → Direção · Inbox de decisões (badge) · Plano de produção · Atribuição diária (badge)
 *   ANÁLISE   → OEE · Qualidade · Operadores · Expedição
 *   SISTEMA   → O que aprendi · Definições
 *
 * Sprint Q.18.ZIP.shell.
 */

import { NavLink, useLocation } from 'react-router-dom';
import {
  Building2 as Building,
  Inbox,
  Calendar,
  Activity,
  TrendingUp,
  Shield,
  Users,
  Truck,
  Brain,
  Settings,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { cn } from '../../lib/utils';
import { authApi, decisionsApi, type CurrentUser } from '../../lib/api';

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
    ceo: 'Direção',
    admin: 'Administrador',
    admin_platform: 'Administrador',
    admin_tenant: 'Administrador',
  };
  return map[role.toLowerCase()] ?? role;
}

interface NavItem {
  path: string;
  label: string;
  icon: ReactNode;
  badge?: number;
}
interface NavGroup {
  label: string;
  items: NavItem[];
}

export function Sidebar() {
  const location = useLocation();

  // Counts dinâmicos para badges Inbox + Atribuição
  const inboxCountQuery = useQuery({
    queryKey: ['sidebar', 'inbox-pending'],
    queryFn: async () => {
      try {
        const r: any = await decisionsApi.list({ status: 'PROPOSED', page_size: 1 });
        return r?.total ?? 0;
      } catch {
        return 0;
      }
    },
    staleTime: 30_000,
    retry: 0,
  });

  const inboxBadge = inboxCountQuery.data ?? undefined;
  // Atribuição badge — sem endpoint dedicado ainda, deixar undefined.

  const NAV: NavGroup[] = [
    {
      label: 'Operação',
      items: [
        { path: '/direcao', label: 'Direção', icon: <Building size={16} /> },
        {
          path: '/inbox',
          label: 'Inbox de decisões',
          icon: <Inbox size={16} />,
          badge: inboxBadge && inboxBadge > 0 ? inboxBadge : undefined,
        },
        { path: '/plano-producao', label: 'Plano de produção', icon: <Calendar size={16} /> },
        { path: '/atribuicao', label: 'Atribuição diária', icon: <Activity size={16} /> },
      ],
    },
    {
      label: 'Análise',
      items: [
        { path: '/oee', label: 'OEE', icon: <TrendingUp size={16} /> },
        { path: '/qualidade', label: 'Qualidade', icon: <Shield size={16} /> },
        { path: '/operadores', label: 'Operadores', icon: <Users size={16} /> },
        { path: '/expedicao', label: 'Expedição', icon: <Truck size={16} /> },
      ],
    },
    {
      label: 'Sistema',
      items: [
        { path: '/aprendizagem', label: 'O que aprendi', icon: <Brain size={16} /> },
        { path: '/definicoes', label: 'Definições', icon: <Settings size={16} /> },
      ],
    },
  ];

  const meQuery = useQuery<CurrentUser>({
    queryKey: ['auth', 'me'],
    queryFn: () => authApi.me(),
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
  const me = meQuery.data;

  const isActive = (path: string): boolean => {
    if (path === '/direcao') {
      return (
        location.pathname === '/direcao' ||
        location.pathname === '/' ||
        location.pathname === '/painel'
      );
    }
    return location.pathname === path || location.pathname.startsWith(path + '/');
  };

  return (
    <aside
      className="h-screen flex flex-col fixed left-0 top-0 bg-dark-800 border-r border-bd-1"
      style={{ width: 240 }}
    >
      {/* Logo */}
      <div
        className="flex items-center gap-2.5 border-b border-bd-1"
        style={{ padding: '18px 20px' }}
      >
        <div
          className="flex items-center justify-center text-white font-bold"
          style={{
            width: 30,
            height: 30,
            background: 'var(--blue)',
            borderRadius: 'var(--r-md)',
            fontSize: 14,
          }}
        >
          N
        </div>
        <div>
          <div
            className="text-text-dark-primary font-semibold leading-tight"
            style={{ fontSize: 14, letterSpacing: '-0.1px' }}
          >
            NELO
          </div>
          <div
            className="text-text-dark-tertiary uppercase font-medium"
            style={{ fontSize: 10, letterSpacing: '0.4px' }}
          >
            ProdPlan ONE
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav
        className="flex-1 overflow-y-auto"
        style={{ padding: '12px 10px' }}
        aria-label="Navegação principal"
      >
        {NAV.map((group) => (
          <div key={group.label} style={{ marginBottom: 18 }}>
            <div
              className="text-text-dark-tertiary uppercase font-semibold"
              style={{
                fontSize: 10,
                letterSpacing: '0.6px',
                padding: '6px 12px 8px 12px',
              }}
            >
              {group.label}
            </div>
            <ul className="flex flex-col">
              {group.items.map((item) => {
                const active = isActive(item.path);
                return (
                  <li key={item.path}>
                    <NavLink
                      to={item.path}
                      className={cn(
                        'group flex items-center w-full relative transition-colors duration-150',
                        active
                          ? 'bg-dark-600 text-text-dark-primary font-medium'
                          : 'bg-transparent text-text-dark-secondary hover:bg-dark-700 hover:text-text-dark-primary',
                      )}
                      style={{
                        padding: '8px 12px',
                        fontSize: 13,
                        gap: 11,
                        borderRadius: 'var(--r-md)',
                      }}
                    >
                      {active ? (
                        <span
                          aria-hidden="true"
                          style={{
                            position: 'absolute',
                            left: -10,
                            top: 8,
                            bottom: 8,
                            width: 2,
                            background: 'var(--blue)',
                            borderRadius: 2,
                          }}
                        />
                      ) : null}
                      <span
                        className={
                          active
                            ? 'text-text-dark-primary'
                            : 'text-text-dark-tertiary group-hover:text-text-dark-secondary'
                        }
                      >
                        {item.icon}
                      </span>
                      <span className="flex-1 truncate">{item.label}</span>
                      {item.badge !== undefined && item.badge > 0 ? (
                        <span
                          className="text-white font-semibold tabular-nums"
                          style={{
                            background: 'var(--orange)',
                            fontSize: 10,
                            padding: '1px 6px',
                            borderRadius: 999,
                            minWidth: 18,
                            textAlign: 'center',
                          }}
                        >
                          {item.badge}
                        </span>
                      ) : null}
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* User footer */}
      <div
        className="flex items-center gap-2.5 border-t border-bd-1"
        style={{ padding: '14px 16px' }}
        title={me?.email ?? '—'}
      >
        <div
          className="rounded-full grid place-items-center font-semibold border"
          style={{
            width: 32,
            height: 32,
            background: 'var(--bg-3)',
            borderColor: 'var(--bd-2)',
            fontSize: 12,
            color: 'var(--fg-1)',
          }}
        >
          {me ? initials(me.name) : '—'}
        </div>
        <div className="flex-1 min-w-0">
          <div
            className="font-medium text-text-dark-primary truncate"
            style={{ fontSize: 12 }}
          >
            {meQuery.isError ? '—' : me?.name ?? 'A carregar…'}
          </div>
          <div className="text-text-dark-tertiary" style={{ fontSize: 10 }}>
            {me ? `${roleLabel(me.role)} · NELO` : meQuery.isError ? 'sem ligação' : '…'}
          </div>
        </div>
      </div>
    </aside>
  );
}
