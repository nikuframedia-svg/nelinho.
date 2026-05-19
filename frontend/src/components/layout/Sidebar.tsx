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
  FileCode,
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
        { path: '/regras', label: 'Regras Q.17 (YAML)', icon: <FileCode size={16} /> },
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
      className="h-screen flex flex-col fixed left-0 top-0"
      style={{
        width: 220,
        background: 'var(--bg-0)',
        borderRight: '1px solid var(--bd-1)',
      }}
    >
      {/* Logo */}
      <div
        className="flex items-center gap-2.5"
        style={{ padding: '18px 18px', borderBottom: '1px solid var(--bd-1)' }}
      >
        <div
          className="flex items-center justify-center font-bold"
          style={{
            width: 28,
            height: 28,
            background: 'var(--fg-0)',
            color: 'var(--bg-0)',
            borderRadius: 'var(--r-xs)',
            fontSize: 14,
          }}
        >
          N
        </div>
        <div>
          <div
            className="display text-text-dark-primary font-semibold leading-tight"
            style={{ fontSize: 14, letterSpacing: '-0.2px' }}
          >
            NELO
          </div>
          <div
            className="text-text-dark-tertiary uppercase font-medium"
            style={{ fontSize: 9.5, letterSpacing: '0.8px' }}
          >
            ProdPlan
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav
        className="flex-1 overflow-y-auto overflow-x-hidden"
        style={{ padding: '14px 10px' }}
        aria-label="Navegação principal"
      >
        {NAV.map((group) => (
          <div key={group.label} style={{ marginBottom: 14 }}>
            <div
              className="text-text-dark-muted uppercase font-semibold"
              style={{
                fontSize: 9.5,
                letterSpacing: '0.8px',
                padding: '8px 11px 6px 11px',
              }}
            >
              {group.label}
            </div>
            <ul className="flex flex-col" style={{ gap: 2 }}>
              {group.items.map((item) => {
                const active = isActive(item.path);
                return (
                  <li key={item.path}>
                    <NavLink
                      to={item.path}
                      className={cn(
                        'group flex items-center w-full relative',
                        active
                          ? 'text-text-dark-primary font-medium'
                          : 'text-text-dark-tertiary',
                      )}
                      style={{
                        padding: '8px 11px',
                        fontSize: 13,
                        gap: 11,
                        borderRadius: 'var(--r-sm)',
                        background: active ? 'var(--bg-3)' : 'transparent',
                        transition: 'background 0.16s, color 0.16s',
                      }}
                      onMouseEnter={(e) => {
                        if (!active)
                          e.currentTarget.style.background = 'var(--bg-2)';
                      }}
                      onMouseLeave={(e) => {
                        if (!active)
                          e.currentTarget.style.background = 'transparent';
                      }}
                    >
                      <span
                        className={
                          active
                            ? 'text-text-dark-primary flex'
                            : 'text-text-dark-tertiary group-hover:text-text-dark-secondary flex'
                        }
                      >
                        {item.icon}
                      </span>
                      <span className="flex-1 truncate">{item.label}</span>
                      {item.badge !== undefined && item.badge > 0 ? (
                        <span
                          className="text-white font-semibold tabular-nums"
                          style={{
                            background: 'var(--accent)',
                            fontSize: 9.5,
                            padding: '0 5px',
                            borderRadius: 999,
                            minWidth: 16,
                            height: 14,
                            lineHeight: '14px',
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
        className="flex items-center gap-2.5"
        style={{ padding: '12px 14px', borderTop: '1px solid var(--bd-1)' }}
        title={me?.email ?? '—'}
      >
        <div
          className="rounded-full grid place-items-center font-semibold border"
          style={{
            width: 28,
            height: 28,
            background: 'linear-gradient(135deg, var(--bg-3), var(--bg-4))',
            borderColor: 'var(--bd-2)',
            fontSize: 11,
            color: 'var(--fg-0)',
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
