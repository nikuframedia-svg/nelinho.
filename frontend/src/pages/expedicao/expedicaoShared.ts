// ExpedicaoPage — helpers puros partilhados (Q.60.S).
import { type TransportManifestBoat } from '../../lib/api';

export function dayLabel(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  const days = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
  return days[d.getDay()];
}

export function shortDate(iso: string): string {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
}

export function daysUntil(iso: string): number {
  const t = new Date(iso + 'T00:00:00').getTime();
  const today = new Date().setHours(0, 0, 0, 0);
  return Math.round((t - today) / (1000 * 60 * 60 * 24));
}

/** Estado de um barco do manifesto → classificação para a grelha. */
export function classifyBoat(b: TransportManifestBoat): 'ready' | 'at_risk' | 'in_prod' {
  const s = (b.status ?? '').toUpperCase();
  if (s === 'COMPLETED' || s === 'READY' || s === 'DISPATCHED') return 'ready';
  const phase = (b.current_phase ?? '').toLowerCase();
  if (phase.includes('cq') || phase.includes('expedi')) return 'ready';
  if (s === 'AT_RISK' || s === 'LATE' || s === 'DELAYED') return 'at_risk';
  return 'in_prod';
}

export interface BatchCounts {
  ready: number;
  inProd: number;
  atRisk: number;
}

export function countManifest(boats: TransportManifestBoat[]): BatchCounts {
  let ready = 0;
  let atRisk = 0;
  let inProd = 0;
  for (const b of boats) {
    const c = classifyBoat(b);
    if (c === 'ready') ready++;
    else if (c === 'at_risk') {
      atRisk++;
      inProd++;
    } else inProd++;
  }
  return { ready, inProd, atRisk };
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}
