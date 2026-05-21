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
    (typeof b.fase_id === 'string' && b.fase_id) ||
    (typeof b.phase === 'string' && b.phase) ||
    `fase-${index}`;
  const short =
    (typeof b.name === 'string' && b.name) ||
    (typeof b.fase_nome === 'string' && b.fase_nome) ||
    (typeof b.phase === 'string' && b.phase) ||
    id;
  // Carga/capacidade — do serviço semântico (`load`/`capacity`) ou do
  // fallback DB Q.54.E (`backlog_horas`/`capacidade_horas`).
  const load =
    typeof b.load === 'number'
      ? b.load
      : typeof b.backlog_horas === 'number'
        ? b.backlog_horas
        : null;
  const cap =
    typeof b.capacity === 'number'
      ? b.capacity
      : typeof b.capacidade_horas === 'number'
        ? b.capacidade_horas
        : null;
  // Score 0-100 para a ScoreBar. O fallback DB devolve o score em DIAS
  // de backlog (crítico > 5 dias) — escala-se para 0-100 (5d ≈ 100).
  // O serviço semântico já devolve 0-100. Sem score directo, deriva de
  // load/cap.
  let score = 0;
  if (typeof b.score === 'number') {
    score =
      b.score > 0 && b.score <= 20
        ? Math.min(100, Math.round((b.score / 5) * 100))
        : Math.min(100, Math.round(b.score));
  } else if (load !== null && cap !== null && cap > 0) {
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
