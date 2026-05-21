// CausalPanels — helper partilhado (Q.60.X).
// Q.61.25 — TENANT/BASE removidos: panels migrados para causalApi.ts
// (que usa request() com tenant + trace_id automaticos via apiFetch).
// Resta o `isoDays` (utility de datas).

export function isoDays(offset: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}
