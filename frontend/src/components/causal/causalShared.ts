// CausalPanels — constantes e helper partilhados (Q.60.X).
import { getApiBase } from '../../lib/api';

export const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
export const BASE = getApiBase();

export function isoDays(offset: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}
