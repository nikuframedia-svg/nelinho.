/**
 * Sidebar — navegação NELO (Q.52.S).
 *
 * Estrutura do design `shell.jsx`:
 *   PRINCIPAL        → 12 itens: Painel · Planeamento · Fábrica · Expedição ·
 *                      Equipa · Qualidade · Materiais · Simulações · Regras ·
 *                      O que aprendi · Copilot · Configuração
 *   VISTAS ESPECIAIS → Direção (ceo) · Operador (tablet fullscreen)
 *   SISTEMA          → 5 páginas órfãs preservadas: Inbox de decisões ·
 *                      Relatórios · Dados-mestre · Saúde · RBAC
 *
 * Badge dinâmico no Inbox = decisões PROPOSED por aprovar.
 *
 * Sprint Q.52.S (substitui o shell Q.18.ZIP de 10 itens).
 */

import { NavLink, useLocation } from 'react-router-dom';
import {
  Home,
  Calendar,
  Factory,
  Truck,
  Users,
  Shield,
  Boxes,
  FlaskConical,
  BookOpen,
  Brain,
  Sparkles,
  Settings,
  Coins,
  Building2 as Building,
  Tablet,
  Inbox,
  FileText,
  Database,
  HeartPulse,
  Lock,
  Plug,
  Radio,
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

  // Badge dinâmico para o Inbox de decisões (decisões PROPOSED).
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

  const NAV: NavGroup[] = [
    {
      label: 'Principal',
      items: [
        { path: '/painel', label: 'Painel', icon: <Home size={16} /> },
        { path: '/planeamento', label: 'Planeamento', icon: <Calendar size={16} /> },
        { path: '/fabrica', label: 'Fábrica', icon: <Factory size={16} /> },
        { path: '/expedicao', label: 'Expedição', icon: <Truck size={16} /> },
        { path: '/equipa', label: 'Equipa', icon: <Users size={16} /> },
        { path: '/qualidade', label: 'Qualidade', icon: <Shield size={16} /> },
        { path: '/materiais', label: 'Materiais', icon: <Boxes size={16} /> },
        { path: '/simulacoes', label: 'Simulações', icon: <FlaskConical size={16} /> },
        { path: '/custos', label: 'Custos', icon: <Coins size={16} /> },
        { path: '/regras', label: 'Regras', icon: <BookOpen size={16} /> },
        { path: '/aprendi', label: 'O que aprendi', icon: <Brain size={16} /> },
        { path: '/copilot', label: 'Copilot', icon: <Sparkles size={16} /> },
        { path: '/configuracao', label: 'Configuração', icon: <Settings size={16} /> },
      ],
    },
    {
      label: 'Vistas especiais',
      items: [
        { path: '/direcao', label: 'Direção', icon: <Building size={16} /> },
        { path: '/operador', label: 'Operador', icon: <Tablet size={16} /> },
      ],
    },
    {
      label: 'Sistema',
      items: [
        {
          path: '/inbox',
          label: 'Inbox de decisões',
          icon: <Inbox size={16} />,
          badge: inboxBadge && inboxBadge > 0 ? inboxBadge : undefined,
        },
        {
          path: '/decisoes',
          label: 'Decisões',
          icon: <Inbox size={16} />,
          badge: inboxBadge && inboxBadge > 0 ? inboxBadge : undefined,
        },
        { path: '/relatorios', label: 'Relatórios', icon: <FileText size={16} /> },
        { path: '/dados-mestre', label: 'Dados-mestre', icon: <Database size={16} /> },
        { path: '/conexao-erp', label: 'Conexão ERP', icon: <Plug size={16} /> },
        { path: '/ligacoes', label: 'Ligações', icon: <Radio size={16} /> },
        { path: '/saude', label: 'Saúde', icon: <HeartPulse size={16} /> },
        { path: '/rbac', label: 'RBAC', icon: <Lock size={16} /> },
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
    if (path === '/painel') {
      return location.pathname === '/painel' || location.pathname === '/';
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
