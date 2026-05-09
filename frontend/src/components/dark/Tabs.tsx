/**
 * Tabs — navegação por tabs com count badge opcional.
 *
 * Usado em todas as páginas-mãe que têm múltiplas vistas:
 * - Equipa: Lista (80) / Alocações / Produtividade / Risco (3) / Simulador / Formação
 * - Qualidade: Resumo / Erros / Moldes / Retrabalho / Diagnóstico / OEE
 * - Configuração: 10 tabs
 * - Relatórios: 5 tabs
 * - Planeamento: 4 tabs
 *
 * Layout horizontal scrollable em mobile; underline activo + count badge
 * laranja na tab activa, neutro nas outras.
 *
 * Sprint Q.18.ZIP.A.
 */

import type { ReactNode } from 'react';

export interface TabItem {
  id: string;
  label: string;
  /** Badge count opcional (ex: 3 SPOFs, 80 colaboradores). */
  count?: number;
  /** Ícone à esquerda (lucide-react). */
  icon?: ReactNode;
  /** Disabled — non-clickable, opacidade reduzida. */
  disabled?: boolean;
}

export interface TabsProps {
  tabs: TabItem[];
  /** ID da tab activa. */
  value: string;
  onChange: (id: string) => void;
  className?: string;
  /** Variante visual. 'underline' = underline padrão (default); 'pills' = pílulas. */
  variant?: 'underline' | 'pills';
}

export function Tabs({
  tabs,
  value,
  onChange,
  className = '',
  variant = 'underline',
}: TabsProps): ReactNode {
  if (variant === 'pills') {
    return (
      <div
        className={`
          inline-flex items-center gap-1 p-1 rounded-lg
          bg-dark-800/60 border border-white/[0.06]
          ${className}
        `}
        role="tablist"
      >
        {tabs.map((tab) => {
          const active = tab.id === value;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={active}
              disabled={tab.disabled}
              onClick={() => !tab.disabled && onChange(tab.id)}
              className={`
                inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md
                text-xs font-medium transition-colors duration-150
                ${active
                  ? 'bg-accent-500/20 text-accent-400'
                  : 'text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary'
                }
                ${tab.disabled ? 'opacity-40 cursor-not-allowed' : ''}
              `}
            >
              {tab.icon ? <span className="shrink-0">{tab.icon}</span> : null}
              <span>{tab.label}</span>
              {tab.count !== undefined ? (
                <span
                  className={`
                    inline-flex items-center justify-center min-w-[18px] h-4 px-1
                    rounded-full text-[10px] font-bold tabular-nums
                    ${active ? 'bg-accent-400/30 text-accent-300' : 'bg-white/[0.08] text-text-dark-tertiary'}
                  `}
                >
                  {tab.count}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    );
  }

  // variant = 'underline'
  return (
    <div
      className={`
        flex items-center gap-1 border-b border-white/[0.06]
        overflow-x-auto
        ${className}
      `}
      role="tablist"
    >
      {tabs.map((tab) => {
        const active = tab.id === value;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={tab.disabled}
            onClick={() => !tab.disabled && onChange(tab.id)}
            className={`
              relative inline-flex items-center gap-2 px-4 py-2.5
              text-sm font-medium transition-colors duration-150
              border-b-2 -mb-px
              ${active
                ? 'border-accent-400 text-accent-400'
                : 'border-transparent text-text-dark-secondary hover:text-text-dark-primary hover:border-white/10'
              }
              ${tab.disabled ? 'opacity-40 cursor-not-allowed' : ''}
            `}
          >
            {tab.icon ? <span className="shrink-0">{tab.icon}</span> : null}
            <span>{tab.label}</span>
            {tab.count !== undefined ? (
              <span
                className={`
                  inline-flex items-center justify-center min-w-[20px] h-5 px-1.5
                  rounded-full text-[10px] font-bold tabular-nums
                  ${active ? 'bg-accent-500/20 text-accent-400' : 'bg-white/[0.06] text-text-dark-tertiary'}
                `}
              >
                {tab.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
