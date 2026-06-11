/**
 * Sidebar — navegação NELO consolidada (Q.115.P).
 *
 * 4 itens apenas:
 *   Decisões      → /decisoes
 *   Planeamento   → /overall
 *   Copiloto      → /llm
 *   Configurações → /configuracoes
 *
 * Sem agrupamentos. Altura de item 56px+. Badge dinâmico nas Decisões.
 */

import { NavLink, useLocation } from 'react-router-dom';
import {
  CheckSquare,
  LayoutGrid,
  Truck,
  Package,
  Bot,
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

const NAV_ITEMS: Omit<NavItem, 'badge'>[] = [
  { path: '/decisoes',      label: 'Decisões',      icon: <CheckSquare size={20} /> },
  { path: '/overall',       label: 'Planeamento',   icon: <LayoutGrid size={20} /> },
  { path: '/expedicao',     label: 'Expedição',     icon: <Truck size={20} /> },
  { path: '/materiais',     label: 'Materiais',     icon: <Package size={20} /> },
  { path: '/llm',           label: 'Copiloto',      icon: <Bot size={20} /> },
  { path: '/configuracoes', label: 'Configurações', icon: <Settings size={20} /> },
];

export function Sidebar() {
  const location = useLocation();

  // Badge dinâmico para Decisões (decisões PROPOSED por aprovar).
  const inboxCountQuery = useQuery({
    queryKey: ['sidebar', 'inbox-pending'],
    queryFn: async () => {
      try {
        const r = await decisionsApi.list({ status: 'PROPOSED', page_size: 1 });
        return r.total ?? 0;
      } catch {
        return 0;
      }
    },
    staleTime: 30_000,
    retry: 0,
  });

  const inboxBadge = inboxCountQuery.data ?? undefined;

  const meQuery = useQuery<CurrentUser>({
    queryKey: ['auth', 'me'],
    queryFn: () => authApi.me(),
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
  const me = meQuery.data;

  const isActive = (path: string): boolean => {
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

      {/* Nav — 4 itens */}
      <nav
        className="flex-1 overflow-y-auto overflow-x-hidden"
        style={{ padding: '14px 10px' }}
        aria-label="Navegação principal"
      >
        <ul className="flex flex-col" style={{ gap: 4 }}>
          {NAV_ITEMS.map((item) => {
            const active = isActive(item.path);
            const badge = item.path === '/decisoes' && inboxBadge && inboxBadge > 0
              ? inboxBadge
              : undefined;

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
                    padding: '16px 14px',
                    fontSize: 13,
                    gap: 12,
                    borderRadius: 'var(--r-sm)',
                    background: active ? 'var(--bg-3)' : 'transparent',
                    borderLeft: active ? '3px solid var(--accent)' : '3px solid transparent',
                    transition: 'background 0.16s, color 0.16s, border-color 0.16s',
                    minHeight: 56,
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
                  {badge !== undefined ? (
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
                      {badge}
                    </span>
                  ) : null}
                </NavLink>
              </li>
            );
          })}
        </ul>
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
