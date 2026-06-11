/**
 * Q.173.AF — lógica pura de filtragem das operações do Gantt.
 *
 * `filterOps` é uma função pura (sem efeitos, sem imports React): aceita
 * as operações, o contexto (FiltersContextOut) e os 12 filtros activos e
 * devolve o subconjunto visível. Exportada assim para poder ser testada em
 * Vitest sem montar nenhum componente.
 *
 * Invariante: ZERO mocks — os dados vêm sempre do context real do backend.
 */

import type { ScheduledOp } from './types';
import type { FiltersContextOut } from '../../lib/api/planApi';

// ─── Tipos ───────────────────────────────────────────────────────────────────

/** Fonte de uma operação: realizada, planeada, ou desconhecida. */
export type OpSource = 'actual' | 'plan' | undefined;

/**
 * Estado dos 12 filtros.
 *
 * Valores vazios/null/false = filtro inactivo (passa tudo).
 * Codificados como types primitivos para ser serializados em URL params.
 */
export interface PlanFilterState {
  /** 1. Texto-livre: order_id / operator_name / phase_name / cliente. */
  text: string;
  /** 2. Modelos (códigos de produto, multi-select). */
  modelos: string[];
  /** 3. Fases (IDs, multi-select). */
  fases: string[];
  /** 4. Operadores (IDs, multi-select). */
  operadores: string[];
  /** 5. Setores (nomes, multi-select). */
  setores: string[];
  /** 6. Expedição: promessa entre estas datas (YYYY-MM-DD | ''). */
  expedicaoFrom: string;
  expedicaoTo: string;
  /** 6b. Mostrar ordens SEM promessa de expedição. */
  expedicaoSemPromessa: boolean;
  /** 7. Gama (disciplina, multi-select). */
  gamas: string[];
  /** 8. Materiais em risco: só ordens afectadas pelo forecast de ruturas. */
  materialRisco: boolean;
  /** 9. Reparações: 'so' = só reparações | 'excluir' = esconder | '' = todos. */
  reparacoes: 'so' | 'excluir' | '';
  /** 10. Prioridade boost: só ordens com boost > 0. */
  prioridade: boolean;
  /** 11. Datas (PeriodSelector) — não duplicado aqui; passa por windowStart/End. */
  // (gerido pelo OverallPage, não neste state)
  /** 12. Estado da operação. */
  estado: 'todos' | 'realizado' | 'planeado' | 'atrasado' | 'risco_material';
}

/** Estado inicial "sem filtros activos". */
export const FILTER_DEFAULTS: PlanFilterState = {
  text: '',
  modelos: [],
  fases: [],
  operadores: [],
  setores: [],
  expedicaoFrom: '',
  expedicaoTo: '',
  expedicaoSemPromessa: false,
  gamas: [],
  materialRisco: false,
  reparacoes: '',
  prioridade: false,
  estado: 'todos',
};

// ─── Predicados auxiliares ────────────────────────────────────────────────────

function matchesText(op: ScheduledOp, q: string): boolean {
  if (!q) return true;
  const ql = q.toLowerCase();
  return [op.order_id, op.operator_name, op.phase_name, op.cliente].some(
    (v) => (v ?? '').toLowerCase().includes(ql),
  );
}

function matchesModelo(
  op: ScheduledOp,
  modelos: string[],
  orderProducts: Record<string, string>,
): boolean {
  if (modelos.length === 0) return true;
  const productCode = op.product_id ?? (op.order_id ? orderProducts[op.order_id] : undefined);
  return !!productCode && modelos.includes(productCode);
}

function matchesFase(op: ScheduledOp, fases: string[]): boolean {
  if (fases.length === 0) return true;
  return fases.includes(op.phase_id);
}

function matchesOperador(op: ScheduledOp, operadores: string[]): boolean {
  if (operadores.length === 0) return true;
  const id = op.operator_id ?? op.operator_name ?? '';
  return operadores.includes(id);
}

function matchesSetor(
  op: ScheduledOp,
  setores: string[],
  phaseSectors: Record<string, string>,
): boolean {
  if (setores.length === 0) return true;
  const setor = phaseSectors[op.phase_id];
  return !!setor && setores.includes(setor);
}

function matchesExpedicao(
  op: ScheduledOp,
  from: string,
  to: string,
  semPromessa: boolean,
  ordersDue: Record<string, string>,
): boolean {
  if (!from && !to && !semPromessa) return true;
  const due = op.order_id ? ordersDue[op.order_id] : undefined;
  if (semPromessa) return due === undefined;
  if (!due) return false;
  if (from && due < from) return false;
  if (to && due > to) return false;
  return true;
}

function matchesGama(
  op: ScheduledOp,
  gamas: string[],
  orderProducts: Record<string, string>,
  productGamas: Record<string, string>,
): boolean {
  if (gamas.length === 0) return true;
  const productCode = op.product_id ?? (op.order_id ? orderProducts[op.order_id] : undefined);
  if (!productCode) return false;
  const gama = productGamas[productCode];
  return !!gama && gamas.includes(gama);
}

function matchesMaterialRisco(
  op: ScheduledOp,
  materialRisco: boolean,
  ordersMaterialRisk: string[],
): boolean {
  if (!materialRisco) return true;
  return !!op.order_id && ordersMaterialRisk.includes(op.order_id);
}

function matchesReparacoes(
  op: ScheduledOp,
  reparacoes: 'so' | 'excluir' | '',
  repairPhaseIds: string[],
): boolean {
  if (!reparacoes) return true;
  const isRepair = repairPhaseIds.includes(op.phase_id);
  if (reparacoes === 'so') return isRepair;
  return !isRepair; // 'excluir'
}

function matchesPrioridade(
  op: ScheduledOp,
  prioridade: boolean,
  ordersBoost: Record<string, number>,
): boolean {
  if (!prioridade) return true;
  return !!op.order_id && (ordersBoost[op.order_id] ?? 0) > 0;
}

function matchesEstado(
  op: ScheduledOp,
  estado: PlanFilterState['estado'],
  ordersDue: Record<string, string>,
  ordersMaterialRisk: string[],
): boolean {
  if (estado === 'todos') return true;
  if (estado === 'realizado') return op.source === 'actual';
  if (estado === 'planeado') return op.source !== 'actual';
  if (estado === 'atrasado') {
    if (!op.order_id || !op.end) return false;
    const due = ordersDue[op.order_id];
    return !!due && op.end > due;
  }
  if (estado === 'risco_material') {
    return !!op.order_id && ordersMaterialRisk.includes(op.order_id);
  }
  return true;
}

// ─── Função pura principal ────────────────────────────────────────────────────

/**
 * Filtra as operações do Gantt de acordo com os 12 filtros activos.
 *
 * Função pura: sem efeitos, sem estado, testável directamente.
 * O filtro de datas (janela temporal) é feito upstream no OverallPage.
 */
export function filterOps(
  ops: ScheduledOp[],
  ctx: FiltersContextOut | null | undefined,
  filters: PlanFilterState,
): ScheduledOp[] {
  // Sem contexto do backend, só aplica o filtro de texto (resiliente).
  const orderProducts = ctx?.order_products ?? {};
  const productGamas = ctx?.product_gamas ?? {};
  const phaseSectors = ctx?.phase_sectors ?? {};
  const ordersBoost = ctx?.orders_boost ?? {};
  const ordersDue = ctx?.orders_due ?? {};
  const ordersMaterialRisk = ctx?.orders_material_risk ?? [];
  const repairPhaseIds = ctx?.repair_phase_ids ?? [];

  return ops.filter((op) => {
    if (!matchesText(op, filters.text)) return false;
    if (!matchesModelo(op, filters.modelos, orderProducts)) return false;
    if (!matchesFase(op, filters.fases)) return false;
    if (!matchesOperador(op, filters.operadores)) return false;
    if (!matchesSetor(op, filters.setores, phaseSectors)) return false;
    if (!matchesExpedicao(op, filters.expedicaoFrom, filters.expedicaoTo, filters.expedicaoSemPromessa, ordersDue)) return false;
    if (!matchesGama(op, filters.gamas, orderProducts, productGamas)) return false;
    if (!matchesMaterialRisco(op, filters.materialRisco, ordersMaterialRisk)) return false;
    if (!matchesReparacoes(op, filters.reparacoes, repairPhaseIds)) return false;
    if (!matchesPrioridade(op, filters.prioridade, ordersBoost)) return false;
    if (!matchesEstado(op, filters.estado, ordersDue, ordersMaterialRisk)) return false;
    return true;
  });
}

/**
 * Conta quantos filtros estão activos (excluindo o texto — já tem campo próprio
 * e o PeriodSelector). Usado no badge do botão "Filtros".
 */
export function countActiveFilters(f: PlanFilterState): number {
  let n = 0;
  if (f.modelos.length) n++;
  if (f.fases.length) n++;
  if (f.operadores.length) n++;
  if (f.setores.length) n++;
  if (f.expedicaoFrom || f.expedicaoTo || f.expedicaoSemPromessa) n++;
  if (f.gamas.length) n++;
  if (f.materialRisco) n++;
  if (f.reparacoes) n++;
  if (f.prioridade) n++;
  if (f.estado !== 'todos') n++;
  return n;
}

/**
 * Serializa os filtros para URLSearchParams (prefix `f_`).
 * Arrays são codificados como múltiplos valores do mesmo param.
 */
export function filtersToSearchParams(f: PlanFilterState): URLSearchParams {
  const p = new URLSearchParams();
  if (f.text) p.set('f_text', f.text);
  for (const v of f.modelos) p.append('f_modelo', v);
  for (const v of f.fases) p.append('f_fase', v);
  for (const v of f.operadores) p.append('f_operador', v);
  for (const v of f.setores) p.append('f_setor', v);
  if (f.expedicaoFrom) p.set('f_exp_from', f.expedicaoFrom);
  if (f.expedicaoTo) p.set('f_exp_to', f.expedicaoTo);
  if (f.expedicaoSemPromessa) p.set('f_exp_sem', '1');
  for (const v of f.gamas) p.append('f_gama', v);
  if (f.materialRisco) p.set('f_mat_risco', '1');
  if (f.reparacoes) p.set('f_rep', f.reparacoes);
  if (f.prioridade) p.set('f_prio', '1');
  if (f.estado !== 'todos') p.set('f_estado', f.estado);
  return p;
}

/**
 * Desserializa os filtros de URLSearchParams (prefix `f_`).
 * Valores desconhecidos são ignorados silenciosamente.
 */
export function filtersFromSearchParams(p: URLSearchParams): PlanFilterState {
  const rep = p.get('f_rep');
  const estado = p.get('f_estado');
  return {
    text: p.get('f_text') ?? '',
    modelos: p.getAll('f_modelo'),
    fases: p.getAll('f_fase'),
    operadores: p.getAll('f_operador'),
    setores: p.getAll('f_setor'),
    expedicaoFrom: p.get('f_exp_from') ?? '',
    expedicaoTo: p.get('f_exp_to') ?? '',
    expedicaoSemPromessa: p.get('f_exp_sem') === '1',
    gamas: p.getAll('f_gama'),
    materialRisco: p.get('f_mat_risco') === '1',
    reparacoes: rep === 'so' || rep === 'excluir' ? rep : '',
    prioridade: p.get('f_prio') === '1',
    estado: (estado === 'realizado' || estado === 'planeado' || estado === 'atrasado' || estado === 'risco_material')
      ? estado
      : 'todos',
  };
}
