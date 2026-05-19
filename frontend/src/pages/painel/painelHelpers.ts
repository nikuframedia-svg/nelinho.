/**
 * painelHelpers — funções puras de formatação/mapeamento do Painel.
 *
 * Q.52.D · Onda 1 · T1. Sem JSX, sem efeitos — só transformações de
 * dados da API para os átomos NELO. ZERO MOCKS: nada inventa dados,
 * tudo deriva do argumento.
 */

import type { KPIBigStatus } from '../../components/dark';
import type { AlertSeverity, FactoryBottleneck } from './painelApi';

/** €xx,xK — formato curto pt-PT para milhares. */
export function fmtEuroK(n: number): string {
  return `${(n / 1000).toFixed(1).replace('.', ',')}K`;
}

/** €xxx — euros inteiros pt-PT. */
export function fmtEuro(n: number): string {
  return `€${Math.round(n).toLocaleString('pt-PT')}`;
}

/** Severidade do backend (INFO/WARN/CRITICAL) → tom do átomo. */
export function severityTone(
  sev: AlertSeverity,
): 'danger' | 'warning' | 'info' {
  const up = sev.toUpperCase();
  if (up === 'CRITICAL') return 'danger';
  if (up === 'WARN') return 'warning';
  return 'info';
}

/** Etiqueta pt-PT da severidade. */
export function severityLabel(sev: AlertSeverity): string {
  const up = sev.toUpperCase();
  if (up === 'CRITICAL') return 'Crítico';
  if (up === 'WARN') return 'Alto';
  return 'Informação';
}

/** Cor de acento do KPI a partir de um estado semáforo. */
export function kpiAccent(status: KPIBigStatus): KPIBigStatus {
  return status;
}

/**
 * Normaliza um gargalo do snapshot para `{ short, load, cap, score }`.
 * O serviço semântico não tem schema fixo — extraímos os campos que
 * existirem, com fallbacks honestos (nunca inventa números).
 */
export interface PhaseLoad {
  id: string;
  short: string;
  load: number | null;
  cap: number | null;
  score: number;
}

export function normalizeBottleneck(
  b: FactoryBottleneck,
  index: number,
): PhaseLoad {
  const id =
    (typeof b.operation_id === 'string' && b.operation_id) ||
    (typeof b.phase === 'string' && b.phase) ||
    `fase-${index}`;
  const short =
    (typeof b.name === 'string' && b.name) ||
    (typeof b.phase === 'string' && b.phase) ||
    id;
  const load = typeof b.load === 'number' ? b.load : null;
  const cap = typeof b.capacity === 'number' ? b.capacity : null;
  // Score directo do serviço, ou derivado de load/cap quando ambos existem.
  let score = typeof b.score === 'number' ? b.score : 0;
  if (score === 0 && load !== null && cap !== null && cap > 0) {
    score = Math.min(100, Math.round((load / cap) * 100));
  }
  return { id, short, load, cap, score };
}

/** Estado relativo a uma meta-banda min/max. */
export function bandStatus(
  value: number,
  min: number,
  max: number,
): KPIBigStatus {
  if (value < min) return 'red';
  if (value > max) return 'green';
  return 'green';
}
