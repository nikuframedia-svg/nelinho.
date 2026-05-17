/**
 * EmptyState — placeholder consistente para listas vazias / sem dados.
 *
 * Substitui mensagens ad-hoc tipo "Sem barcos em produção" espalhadas
 * pelas páginas. Pode mostrar o Nelinho mascot (com `mascot` prop)
 * para suavizar a sensação de vazio e reforçar identidade.
 *
 * Sprint Q.18.ZIP.L.
 */

import type { ReactNode } from 'react';
import { CopilotMascot } from '../copilot/CopilotMascot';

export interface EmptyStateProps {
  /** Título principal — frase curta ("Sem barcos em produção"). */
  title: string;
  /** Texto secundário explicando contexto / próximo passo. */
  hint?: string;
  /** Mostrar o Nelinho astronauta. Default true. */
  mascot?: boolean;
  /** Ícone alternativo (lucide-react) quando mascot=false. */
  icon?: ReactNode;
  /** Acção opcional (botão, link). */
  action?: ReactNode;
  /** Tamanho do estado vazio. */
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const SIZE_PADDING = {
  sm: 'py-6',
  md: 'py-10',
  lg: 'py-16',
};

const MASCOT_SIZE = {
  sm: 'sm' as const,
  md: 'md' as const,
  lg: 'lg' as const,
};

export function EmptyState({
  title,
  hint,
  mascot = true,
  icon,
  action,
  size = 'md',
  className = '',
}: EmptyStateProps) {
  return (
    <div
      className={`
        flex flex-col items-center justify-center gap-3 text-center
        ${SIZE_PADDING[size]} px-4
        ${className}
      `}
    >
      {mascot ? (
        <CopilotMascot size={MASCOT_SIZE[size]} className="opacity-80" />
      ) : icon ? (
        <div className="text-text-dark-tertiary opacity-60">{icon}</div>
      ) : null}

      <div className="text-sm font-medium text-text-dark-primary">{title}</div>

      {hint ? (
        <p className="text-xs text-text-dark-tertiary max-w-md">{hint}</p>
      ) : null}

      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
