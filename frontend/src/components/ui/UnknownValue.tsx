/**
 * UnknownValue
 * ============
 * 
 * Displays a placeholder for unknown/null values.
 * 
 * RULE: Unknown ≠ 0
 * When data is not available, we show "—" instead of 0.
 */

import { HelpCircle } from 'lucide-react';

interface UnknownValueProps {
  reason?: string;
  showIcon?: boolean;
  className?: string;
}

export function UnknownValue({ 
  reason = 'Dados não disponíveis', 
  showIcon = false,
  className = '',
}: UnknownValueProps) {
  return (
    <span 
      className={`inline-flex items-center gap-1 text-text-tertiary italic ${className}`}
      title={reason}
    >
      <span>—</span>
      {showIcon && <HelpCircle size={12} className="opacity-50" />}
    </span>
  );
}

/**
 * Helper function to display value or unknown
 */
export function displayValueOrUnknown(
  value: number | null | undefined,
  formatter?: (v: number) => string,
): string {
  if (value === null || value === undefined) {
    return '—';
  }
  return formatter ? formatter(value) : String(value);
}

export default UnknownValue;

