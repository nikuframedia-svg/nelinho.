/**
 * ProdPlan ONE — API: Cube (camada semântica / KPIs reais).
 * ==========================================================
 *
 * A página de KPIs (/llm) consome as MEASURES REAIS do Cube via
 * GET /api/copilot/cube/dashboard-dev (dev-only, sem LLM, determinístico).
 * Substitui o caminho legacy /v1/profit/kpis/* (quase vazio).
 *
 * Em dev usamos directamente o endpoint -dev (sem auth, X-Tenant-Id dev),
 * espelhando o padrão de copilotApi.ask().
 */
import { API_BASE } from './client';

const DEV_TENANT = '00000000-0000-0000-0000-000000000001';

export type CubeItemStatus = 'ok' | 'no_data' | 'error';

export interface CubeDashboardCard {
  key: string;
  label: string;
  unit: string; // '', '%', '€'
  value: number | null;
  status: CubeItemStatus;
}

export interface CubeDashboardSeriesPoint {
  x: string;
  y: number | null;
}

export interface CubeDashboardChart {
  key: string;
  label: string;
  kind: 'line' | 'bar';
  series: CubeDashboardSeriesPoint[];
  status: CubeItemStatus;
}

export interface CubeDashboard {
  cards: CubeDashboardCard[];
  charts: CubeDashboardChart[];
}

/** Uma measure do catálogo do Cube (para o menu "Adicionar indicador"). */
export interface CubeMeasureCatalogEntry {
  name: string; // id canónico, ex: "consumo_material.consumo"
  label: string; // descrição PT-PT (fallback para name)
  unit: string; // '', '%', '€'
  domain: string; // prefixo do cube, ex: "consumo_material" — agrupa o menu
  dimensions: string[];
  supports_period: boolean; // tem dimensão `tempo` → permite filtro "este mês"
}

export interface CubeMeasureCatalog {
  measures: CubeMeasureCatalogEntry[];
}

export interface CubeMeasureCardItem {
  measure: string;
  period: 'none' | 'month';
}

export interface CubeMeasureCards {
  cards: CubeDashboardCard[];
}

/** Fetch dev (sem auth, X-Tenant-Id dev) com error envelope normalizado. */
async function cubeDevFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'X-Tenant-Id': DEV_TENANT, ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message =
      (errorData as { detail?: string; message?: string }).detail ||
      (errorData as { message?: string }).message ||
      `HTTP ${response.status}`;
    const err = new Error(message);
    (err as Error & { status?: number }).status = response.status;
    throw err;
  }
  return (await response.json()) as T;
}

export const cubeApi = {
  /** KPIs + gráficos reais do Cube (operações NELO via marts). */
  dashboard: async (): Promise<CubeDashboard> => {
    const url = `${API_BASE}/api/copilot/cube/dashboard-dev`;
    const response = await fetch(url, {
      method: 'GET',
      headers: { 'X-Tenant-Id': DEV_TENANT },
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const message =
        (errorData as { detail?: string; message?: string }).detail ||
        (errorData as { message?: string }).message ||
        `HTTP ${response.status}`;
      const err = new Error(message);
      (err as Error & { status?: number }).status = response.status;
      throw err;
    }
    return (await response.json()) as CubeDashboard;
  },

  /** Catálogo completo das measures registadas (alimenta o picker de KPIs). */
  measures: (): Promise<CubeMeasureCatalog> =>
    cubeDevFetch<CubeMeasureCatalog>('/api/copilot/cube/measures-dev'),

  /** Valores actuais das measures escolhidas no picker. */
  measureCards: (items: CubeMeasureCardItem[]): Promise<CubeMeasureCards> =>
    cubeDevFetch<CubeMeasureCards>('/api/copilot/cube/measure-cards-dev', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items }),
    }),
};
