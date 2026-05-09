/**
 * TopBar — barra fina (52px) por cima do conteúdo, ao lado da Sidebar.
 *
 * Conteúdo (FRONTEND_DESIGN_PROMPT §4.1 + design/nelo-zip/src/shell.jsx:
 * 133-190):
 *   ┌──────────────────────────────────────────────────────────────────┐
 *   │ 🔍 Procurar barco, operador, fase…  ⌘K  | Gestor·Op·CEO | 🔔 | sex 09 mai · 14:23 │
 *   └──────────────────────────────────────────────────────────────────┘
 *
 * Sem nav primária (essa vive na Sidebar). Sem hardcoded user — esse
 * vai no chip da Sidebar via /v1/auth/me.
 *
 * Sprint Q.18.UI.A.1.
 */

import { useState, useEffect } from 'react';
import { Search, Bell, Command } from 'lucide-react';
import { useCommandPalette } from '../../hooks';
import { UmweltSwitcher } from '../dashboard/UmweltSwitcher';

function nowLabel(): string {
  const fmt = new Intl.DateTimeFormat('pt-PT', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
  return fmt.format(new Date());
}

export function TopBar() {
  const { open: openCommandPalette } = useCommandPalette();
  const [now, setNow] = useState(nowLabel());

  useEffect(() => {
    const id = window.setInterval(() => setNow(nowLabel()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <header
      className="
        h-13 px-6 flex items-center gap-4
        bg-dark-800/60 backdrop-blur border-b border-white/[0.06]
        sticky top-0 z-20
      "
      style={{ height: 52 }}
    >
      {/* Search trigger (opens CommandPalette) */}
      <button
        type="button"
        onClick={openCommandPalette}
        className="
          flex items-center gap-2 w-80 max-w-[40vw]
          px-3 py-1.5 rounded-md
          bg-dark-900/60 border border-white/[0.06]
          text-text-dark-tertiary hover:text-text-dark-secondary hover:border-white/10
          transition-colors duration-150
          focus:outline-none focus:ring-2 focus:ring-accent-500/40
        "
        title="Procurar (⌘K)"
        aria-label="Procurar"
      >
        <Search size={14} className="shrink-0" />
        <span className="text-sm flex-1 text-left truncate">
          Procurar barco, operador, fase…
        </span>
        <span className="inline-flex items-center gap-0.5 text-[10px] tabular-nums text-text-dark-tertiary border border-white/10 rounded px-1.5 py-0.5">
          <Command size={10} />K
        </span>
      </button>

      <div className="flex-1" />

      {/* Umwelt switcher (Gestor / Operador / CEO) */}
      <UmweltSwitcher className="hidden md:inline-flex" />

      {/* Notifications — sem mock count. Quando o endpoint existir,
          vem de useQuery. Por agora botão sem badge. */}
      <button
        type="button"
        className="
          relative p-2 rounded-md
          text-text-dark-tertiary hover:text-text-dark-secondary hover:bg-white/5
          transition-colors duration-150
          focus:outline-none focus:ring-2 focus:ring-accent-500/40
        "
        aria-label="Notificações"
        title="Notificações"
      >
        <Bell size={18} />
      </button>

      {/* Date + time */}
      <span
        className="hidden lg:inline text-xs text-text-dark-tertiary tabular-nums"
        aria-label="Data e hora actual"
      >
        {now}
      </span>
    </header>
  );
}
