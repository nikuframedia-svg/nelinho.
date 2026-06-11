/**
 * Q.61.27 — Query-key factories (TkDodo pattern).
 *
 * Antes do Q.61.27, os hooks TanStack Query usavam keys literais:
 *
 *   useQuery({ queryKey: ['decisions', 'list', filters], ... })
 *   queryClient.invalidateQueries({ queryKey: ['decisions'] })
 *
 * Inconvenientes:
 *   * keys typoadas viviam silenciosas (`['descisions']` nunca bate)
 *   * invalidacao em cascata exigia conhecer os literais de cada nivel
 *   * sem type-safety nas keys
 *
 * Q.61.27 instala factories por feature (TkDodo):
 *
 *   decisionKeys.all          -> ['decisions']
 *   decisionKeys.lists()      -> ['decisions', 'list']
 *   decisionKeys.list(filt)   -> ['decisions', 'list', filt]
 *   decisionKeys.detail(id)   -> ['decisions', 'detail', id]
 *
 * Hierarquia permite invalidacoes precisas:
 *   queryClient.invalidateQueries({ queryKey: decisionKeys.lists() })
 *   // invalida todas as lists, mantem detail no cache
 *
 * Estrategia:
 *   * Esta versao adiciona factories para 3 features que ja tem
 *     endpoint canonico no backend (decisions, causal/explain,
 *     audit-logs).
 *   * Touched-file pays: os 591 hooks existentes ficam ate alguem
 *     mexer no seu ficheiro. Codemod ts-morph e Q.61.27.1 follow-up.
 */

import type { UUID } from 'crypto';

// ─── decisions ──────────────────────────────────────────────────────────

export interface DecisionFilters {
  status?: string;
  page?: number;
  pageSize?: number;
}

export const decisionKeys = {
  all: ['decisions'] as const,
  lists: () => [...decisionKeys.all, 'list'] as const,
  list: (filters?: DecisionFilters) =>
    [...decisionKeys.lists(), filters ?? {}] as const,
  details: () => [...decisionKeys.all, 'detail'] as const,
  detail: (id: string | UUID) => [...decisionKeys.details(), id] as const,
  pending: () => [...decisionKeys.all, 'pending'] as const,
} as const;

// ─── audit-logs (Q.61.19) ───────────────────────────────────────────────

export interface AuditLogFilters {
  entityType?: string;
  entityId?: string;
  actorId?: string;
  action?: 'INSERT' | 'UPDATE' | 'DELETE';
  since?: string;
  until?: string;
  traceId?: string;
  page?: number;
  pageSize?: number;
}

export const auditLogKeys = {
  all: ['audit-logs'] as const,
  lists: () => [...auditLogKeys.all, 'list'] as const,
  list: (filters?: AuditLogFilters) =>
    [...auditLogKeys.lists(), filters ?? {}] as const,
} as const;

// ─── causal/explain (Q.61.25) ──────────────────────────────────────────

export const causalKeys = {
  all: ['causal'] as const,
  attribution: (target: string, sampleSize: number) =>
    [...causalKeys.all, 'attribution', target, sampleSize] as const,
  neloDag: (tauMax: number, alpha: number, sampleSize: number) =>
    [...causalKeys.all, 'nelo-dag', tauMax, alpha, sampleSize] as const,
  kpiSnapshot: () => [...causalKeys.all, 'kpis-snapshot-explained'] as const,
} as const;

// ─── governance rules (Q.17 YAML policy) ───────────────────────────────

export const ruleKeys = {
  all: ['yaml-policy-rules'] as const,
  lists: () => [...ruleKeys.all, 'list'] as const,
  list: (status?: string) => [...ruleKeys.lists(), status ?? 'any'] as const,
  details: () => [...ruleKeys.all, 'detail'] as const,
  detail: (id: string) => [...ruleKeys.details(), id] as const,
  firings: () => [...ruleKeys.all, 'firings'] as const,
} as const;

// ─── data product / semantic views (Q.67.2.C) ──────────────────────────

export const dataProductKeys = {
  all: ['dataProduct'] as const,
  semanticViews: () => [...dataProductKeys.all, 'semantic-views'] as const,
  semanticQuery: (viewId: string | null) =>
    [...dataProductKeys.all, 'semantic-query', viewId] as const,
} as const;

// ─── workforce / skill matrix (Q.67.2.C) ───────────────────────────────

export const workforceKeys = {
  all: ['workforce'] as const,
  employees: (limit?: number) =>
    [...workforceKeys.all, 'employees', limit ?? null] as const,
  skillMatrix: (employeeId: string | null) =>
    [...workforceKeys.all, 'skill-matrix', employeeId] as const,
} as const;

// ─── profit (Q.67.2.A) ──────────────────────────────────────────────────
//
// Cobre os panels de ProfitPanels.tsx (Onda 10/J): dashboard € hoje,
// COGS breakdown por order, margem dado preço de venda.

export const profitKeys = {
  all: ['profit'] as const,
  dashboard: () => [...profitKeys.all, 'dashboard'] as const,
  cogsOrder: (orderId: string) => [...profitKeys.all, 'cogs-order', orderId] as const,
  margin: (orderId: string, sellingPrice: number) =>
    [...profitKeys.all, 'margin', orderId, sellingPrice] as const,
  // Q.115.M — preview defensivo por commit SHA (esconde se 404)
  preview: (commitSha: string) =>
    [...profitKeys.all, 'preview', commitSha] as const,
  // Q.117.D — série histórica de um KPI (gráfico de tendência da tab KPIs)
  kpiHistory: (name: string, days: number) =>
    [...profitKeys.all, 'kpi-history', name, days] as const,
} as const;

// ─── cube semantic layer — dashboard + picker de measures ───────────────
//
// Tab KPIs do LLM: dashboard curado (7 cards) + picker das 127 measures do
// contrato (catálogo estático + valores ad-hoc por selecção).

export const cubeKeys = {
  all: ['cube'] as const,
  dashboard: () => [...cubeKeys.all, 'dashboard-dev'] as const,
  measures: () => [...cubeKeys.all, 'measures'] as const,
  measureCards: (selection: readonly string[]) =>
    [...cubeKeys.all, 'measure-cards', selection] as const,
} as const;

// ─── twin (Q.67.2.A) ────────────────────────────────────────────────────
//
// Digital Twin sandbox (Onda 17/Q): scenarios CRUD + compare.

export const twinKeys = {
  all: ['twin'] as const,
  scenarios: () => [...twinKeys.all, 'scenarios'] as const,
  compare: (scenarioId: string | null) =>
    [...twinKeys.all, 'compare', scenarioId ?? 'none'] as const,
} as const;

// ─── ops (Q.67.2.A) ─────────────────────────────────────────────────────
//
// Painéis admin/ops: health, rate-limit (copilot/diagnose), auth/me.

export const opsKeys = {
  all: ['ops'] as const,
  healthReady: () => [...opsKeys.all, 'health-ready'] as const,
  healthLive: () => [...opsKeys.all, 'health-live'] as const,
  copilotDiagnose: () => [...opsKeys.all, 'copilot-diagnose'] as const,
  authMe: () => [...opsKeys.all, 'auth-me'] as const,
} as const;

// ─── ML registry (Q.67.2.B) ────────────────────────────────────────────
//
// Suporta MlRegistryPanel (Onda 16/P): lista de modelos, versões e
// versão activa por modelo.

export const mlKeys = {
  all: ['ml'] as const,
  models: () => [...mlKeys.all, 'models'] as const,
  versions: (modelName: string | null | undefined) =>
    [...mlKeys.all, 'versions', modelName ?? ''] as const,
  active: (modelName: string | null | undefined) =>
    [...mlKeys.all, 'active', modelName ?? ''] as const,
} as const;

// ─── Supply panels (Q.67.2.B) ──────────────────────────────────────────
//
// SupplyPanels (Onda 9/I): ROP calc + shortage alerts (copilot/alerts
// filtered por source=shortage_detector). Forecast e ABC são mutations.

export interface SupplyRopFilters {
  skuId: string;
  avgDailyDemand: number;
  leadTimeDays: number;
  leadTimeStdDev: number;
  serviceLevel: number;
}

export const supplyKeys = {
  all: ['supply'] as const,
  rop: (filters: SupplyRopFilters) =>
    [
      ...supplyKeys.all,
      'rop',
      filters.skuId,
      filters.avgDailyDemand,
      filters.leadTimeDays,
      filters.leadTimeStdDev,
      filters.serviceLevel,
    ] as const,
  shortageAlerts: () =>
    [...supplyKeys.all, 'copilot-alerts', 'shortage'] as const,
} as const;

// ─── plan / CPO commits (Q.115.K) ──────────────────────────────────────

export const planKeys = {
  all: ['plan'] as const,
  schedule: () => [...planKeys.all, 'schedule'] as const,
  scheduleCurrent: () => [...planKeys.schedule(), 'current'] as const,
  // Q.141 — linha temporal: actuals (o que aconteceu) por intervalo.
  timeline: () => [...planKeys.all, 'timeline'] as const,
  actuals: (from: string, to: string) =>
    [...planKeys.timeline(), 'actuals', from, to] as const,
  // Q.163 — catálogo canónico de fases (ordem FP_SEQUENCIA) para o /overall.
  phaseCatalog: () => [...planKeys.all, 'phase-catalog'] as const,
  // Q.149.C.3 — alertas de override manual que o reapply do robô já não
  // conseguiu re-aplicar (a pessoa escolhida deixou de ser viável com o WIP).
  manualOverrideAlerts: () => [...planKeys.all, 'manual-override-alerts'] as const,
  // Q.153.C2 — barcos excluídos/adiados do plano (drag p/ zona de remoção).
  excludedBoats: () => [...planKeys.all, 'excluded-boats'] as const,
} as const;

// ─── Reports admin (Q.67.2.B) ──────────────────────────────────────────
//
// ReportsAdminPanel (Onda 18/R): 3 mutations (schedule, email, retention).
// As lists ainda não existem como GET — keys preparam o terreno.

export const reportsKeys = {
  all: ['reports'] as const,
  schedules: () => [...reportsKeys.all, 'schedules'] as const,
  emails: () => [...reportsKeys.all, 'emails'] as const,
  retentions: () => [...reportsKeys.all, 'retentions'] as const,
} as const;

// ─── revenue-target (Q.115.B) ───────────────────────────────────────────

export const revenueTargetKeys = {
  all: ['revenue-target'] as const,
  lists: () => [...revenueTargetKeys.all, 'list'] as const,
} as const;

// ─── client-priority (Q.115.B) ──────────────────────────────────────────

export const clientPriorityKeys = {
  all: ['client-priority'] as const,
  lists: () => [...clientPriorityKeys.all, 'list'] as const,
} as const;

// ─── user-input (Q.115.B) ───────────────────────────────────────────────

export const userInputKeys = {
  all: ['user-input'] as const,
  lists: () => [...userInputKeys.all, 'list'] as const,
  list: (status?: string) => [...userInputKeys.lists(), status ?? 'all'] as const,
} as const;

// ─── learning / affinities (Q.115.G) + plan-vs-actual (Q.115.V) ─────────

export const learningKeys = {
  all: ['learning'] as const,
  affinities: (params?: { operator_id?: string; phase_id?: string; top?: number }) =>
    [...learningKeys.all, 'affinities', params ?? {}] as const,
  planVsActual: (params?: { days?: number }) =>
    [...learningKeys.all, 'plan-vs-actual', params ?? {}] as const,
} as const;

// ─── runbooks (Q.115.H) ─────────────────────────────────────────────────

export const runbookKeys = {
  all: ['runbooks'] as const,
  lists: () => [...runbookKeys.all, 'list'] as const,
  list: (params?: { error_code?: string }) =>
    [...runbookKeys.lists(), params ?? {}] as const,
} as const;

// ─── governance (preference-rules) ──────────────────────────────────────

export const governanceKeys = {
  all: ['governance'] as const,
  preferenceRules: (params?: { status?: string; type?: string }) =>
    [...governanceKeys.all, 'preference-rules', params ?? {}] as const,
} as const;

// ─── quality risk preview (Q.115.E) ─────────────────────────────────────

export const qualityRiskKeys = {
  all: ['quality-risk'] as const,
  preview: (operatorId: string, boatId: string, phaseId: string) =>
    [...qualityRiskKeys.all, 'preview', operatorId, boatId, phaseId] as const,
} as const;

// ─── entity summaries (Q.116.A) ─────────────────────────────────────────

export const entityKeys = {
  all: ['entity'] as const,
  modelo: (id: string) => [...entityKeys.all, 'modelo', id] as const,
  fase: (id: string) => [...entityKeys.all, 'fase', id] as const,
  faseConfig: (id: string) => [...entityKeys.all, 'fase', id, 'config'] as const,
  cliente: (id: string) => [...entityKeys.all, 'cliente', id] as const,
  encomenda: (id: string | number) => [...entityKeys.all, 'encomenda', String(id)] as const,
  operador: (id: string) => [...entityKeys.all, 'operador', id] as const,
} as const;

// ─── diagnostics / ERP connection (Q.117.A) ─────────────────────────────
//
// Estado da integração ERP NELO (GET /v1/diagnostics/erp-connection):
// frescor por mirror lido de core.etl_run. Alimenta o SyncStatusBadge no
// TopBar global — "ERP há Xm" + dot de estado.

export const diagnosticsKeys = {
  all: ['diagnostics'] as const,
  erpConnection: () => [...diagnosticsKeys.all, 'erp-connection'] as const,
} as const;

// ─── master data cancel/retire/deactivate (Q.115.X5) ─────────────────────

export const masterDataKeys = {
  all: ['master-data'] as const,
  workOrders: () => [...masterDataKeys.all, 'work-orders'] as const,
  encomendas: () => [...masterDataKeys.all, 'encomendas'] as const,
  boats: (showRetired: boolean) => [...masterDataKeys.all, 'boats', { showRetired }] as const,
  employees: (showInactive: boolean) => [...masterDataKeys.all, 'employees', { showInactive }] as const,
} as const;

// ─── core master-data (Q.154.A) ──────────────────────────────────────────
//
// Colaboradores p/ resolver `employee_code → employee_name` em vários sítios
// (FaseSheet, editor de plano). `employeesForPlanEditor()` tem o MESMO valor do
// literal histórico do OverallPage (Q.147.C) DE PROPÓSITO: o TanStack Query
// desduplica o fetch e reaproveita o cache de 10 min. Se mudares um, muda o
// outro (OverallPage.tsx ~L175 + hooks/useEmployeeNamesByCode.ts).

export const coreKeys = {
  all: ['core'] as const,
  employees: () => [...coreKeys.all, 'employees'] as const,
  employeesForPlanEditor: () =>
    [...coreKeys.employees(), 'for-plan-editor'] as const, // → ['core','employees','for-plan-editor']
  // Q.159 — só operadores ATIVOS (active_only=true, ~107) para os DROPDOWNS de
  // atribuição. Key SEPARADA da de cima de propósito: a resolução de nomes
  // (useEmployeeNamesByCode, mapa de nomes do OverallPage) precisa da lista
  // COMPLETA incl. terminados (ops históricas), por isso não pode partilhar
  // cache com o subconjunto ativo.
  employeesActiveForPlanEditor: () =>
    [...coreKeys.employees(), 'active-for-plan-editor'] as const,
} as const;

// ─── Q.155 — melhores operadores por fase (curado manual) ─────────────────

export const phasePreferredKeys = {
  all: ['phase-preferred'] as const,
  phases: () => [...phasePreferredKeys.all, 'phases'] as const,
  forPhase: (phaseId: string) => [...phasePreferredKeys.all, 'phase', phaseId] as const,
} as const;

export const boatComplexityKeys = {
  all: ['boat-complexity'] as const,
  list: () => [...boatComplexityKeys.all, 'list'] as const,
} as const;

// ─── factory-map snapshot (Q.158) ────────────────────────────────────────
//
// Snapshot global da fábrica (GET /v1/factory-map/snapshot): "barcos em
// produção" pela regra EXATA da NELO (boats_em_producao) + gargalos. Lido no
// header do /overall (KPI ≈830).

export const fabricaKeys = {
  all: ['factory-map'] as const,
  snapshot: () => [...fabricaKeys.all, 'snapshot'] as const,
} as const;

// ─── workforce sectors / níveis por sector (Q.140) ───────────────────────
//
// Níveis por (pessoa × sector) + ranking por sector. ranking(area) e
// employeeLevels(id) invalidam-se após o PATCH /sector-level.

export const sectorKeys = {
  all: ['workforce-sectors'] as const,
  list: () => [...sectorKeys.all, 'list'] as const,
  ranking: (areaGroup: string) => [...sectorKeys.all, 'ranking', areaGroup] as const,
  employeeLevels: (employeeId: string) =>
    [...sectorKeys.all, 'employee', employeeId] as const,
} as const;

// ─── Q.159 — operadores ativos (contagem + quebra por área) ──────────────
//
// GET /v1/workforce/operators/summary → {count, window_days, by_area}.
// "operador ativo" = E_ACTIVO + trabalho nos últimos 2 meses (~107). Lido no
// cabeçalho da aba Equipa·Níveis.

export const operatorsKeys = {
  all: ['workforce-operators'] as const,
  summary: () => [...operatorsKeys.all, 'summary'] as const,
} as const;

// ─── copilot alerts (AlertasTab) ─────────────────────────────────────────────
//
// GET /v1/copilot/alerts — lista de alertas do copiloto (Q.61.27 factory).

export const copilotAlertsKeys = {
  all: ['copilot', 'alerts'] as const,
  list: (filter?: string) =>
    filter
      ? ([...copilotAlertsKeys.all, filter] as const)
      : (copilotAlertsKeys.all as readonly string[]),
} as const;

// ─── config (Q.173.O) ─────────────────────────────────────────────────────────
//
// GET /v1/config/{category} → {key: value}
// POST /v1/config/{category}/{key} → grava (201)
// Categorias: planning, transporte, alertas

export const configKeys = {
  all: ['config'] as const,
  category: (cat: string) => [...configKeys.all, cat] as const,
} as const;

// ─── phase-gaps / cura (Q.173.O) ─────────────────────────────────────────────
//
// GET /v1/plan/phase-gaps → {items: PhaseGap[]}
// PATCH /v1/plan/phase-gaps/{from}/{to} → upsert com auditoria

export const phaseGapsKeys = {
  all: ['phase-gaps'] as const,
  list: () => [...phaseGapsKeys.all, 'list'] as const,
} as const;

// ─── transporte / expedição (ExpedicaoPage, listaComponents) ─────────────────
//
// GET /v1/transport/batches + /manifest/{id} + /otd.

export const transportKeys = {
  all: ['expedicao'] as const,
  batches: (fromDate?: string) =>
    [...transportKeys.all, 'batches', fromDate ?? ''] as const,
  manifest: (batchId: string) =>
    [...transportKeys.all, 'manifest', batchId] as const,
  otd: () => [...transportKeys.all, 'otd'] as const,
} as const;
