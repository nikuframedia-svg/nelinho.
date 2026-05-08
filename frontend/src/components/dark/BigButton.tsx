/**
 * BigButton — 100×100px botão para tablet operador (chão de fábrica).
 *
 * Usado na OperadorPage (kiosk fullscreen) onde os operadores carregam
 * com luvas. Touch target ≥ 56×56 (WCAG); o brief especifica 100×100.
 * Cores fortes (verde/vermelho), label maiúsculo, sem decoração extra.
 *
 * Plan v4 §4.9 / FRONTEND_DESIGN_PROMPT §2.2 chão-de-fábrica constraints.
 * Sprint Q.18.UI.A.
 */

import type { ReactNode, ButtonHTMLAttributes } from 'react';

type BigButtonVariant = 'success' | 'danger' | 'primary' | 'neutral';
type BigButtonSize = 'md' | 'lg' | 'xl';

interface BigButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  icon?: ReactNode;
  variant?: BigButtonVariant;
  size?: BigButtonSize;
}

const VARIANT: Record<BigButtonVariant, string> = {
  success:
    'bg-success text-white hover:bg-success-light focus:ring-success/40 active:bg-success-dark',
  danger:
    'bg-danger text-white hover:bg-danger-light focus:ring-danger/40 active:bg-danger-dark',
  primary:
    'bg-accent-500 text-white hover:bg-accent-400 focus:ring-accent-500/40 active:bg-accent-600',
  neutral:
    'bg-dark-600 text-white hover:bg-dark-500 focus:ring-white/20 active:bg-dark-700',
};

const SIZE: Record<BigButtonSize, string> = {
  // 100×100 — brief default, tablet operador
  md: 'min-w-[100px] min-h-[100px] text-base',
  // 140×140 — variante tablet maior
  lg: 'min-w-[140px] min-h-[140px] text-lg',
  // 200×200 — emergência (PROBLEMA)
  xl: 'min-w-[200px] min-h-[200px] text-2xl',
};

export function BigButton({
  label,
  icon,
  variant = 'primary',
  size = 'md',
  className = '',
  disabled,
  ...rest
}: BigButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      className={`
        flex flex-col items-center justify-center gap-2
        px-6 py-4 rounded-2xl
        font-bold uppercase tracking-wide
        shadow-card transition-all duration-150
        focus:outline-none focus:ring-4 focus:ring-offset-2 focus:ring-offset-dark-900
        ${VARIANT[variant]}
        ${SIZE[size]}
        ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer hover:shadow-card-hover active:scale-[0.98]'}
        ${className}
      `}
      {...rest}
    >
      {icon ? <span className="text-3xl leading-none">{icon}</span> : null}
      <span className="text-center leading-tight">{label}</span>
    </button>
  );
}
