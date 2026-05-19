/**
 * materiaisApi — wrappers tipados para os endpoints de Materiais (Q.52.K).
 *
 * As 5 famílias de supply do `lib/api.ts` não cobrem `/v1/supply/materials/*`
 * nem `/v1/factory-map/shortage-risks`. Como `lib/api.ts` é ficheiro
 * partilhado (proibido editar na Onda 1), estas chamadas passam pelo
 * `apiFetch` exportado — herda circuit-breaker, retry e headers de tenant.
 *
 * Tipos mapeiam 1:1 os schemas Pydantic de `src/supply/api.py`.
 */

import { apiFetch } from '../../lib/api';

// ─── Materiais (stock master) ────────────────────────────────────────────
export interface Material {
  id: string;
  sku_id: string;
  name: string;
  description: string | null;
  unit_of_measure: string;
  category: string | null;
  default_supplier_id: string | null;
  lead_time_days: number;
  min_stock_qty: number;
  reorder_qty: number;
  safety_stock_days: number | null;
  critical_flag: boolean;
  active: boolean;
}

/**
 * Material derivado da BOM — componente-folha de `core.bom_items`.
 *
 * `supply.material_master` está vazio nesta instalação. Os materiais reais
 * da NELO são os componentes-folha das BOMs (`component_product_id` que
 * nunca é `parent_product_id`), cruzados com `core.products`.
 */
/** Stock de um material num armazém. */
export interface WarehouseStockBreakdown {
  warehouse_id: number;
  warehouse_name: string;
  stock: number;
}

export interface BomMaterial {
  id: string;
  product_code: string;
  product_name: string;
  unit_of_measure: string;
  standard_cost: number | null;
  category: string | null;
  product_type: string;
  used_in_n_boms: number;
  total_qty_per: number | null;
  /** Stock total entre armazéns. null se o stock não foi sincronizado. */
  on_hand: number | null;
  /** Repartição do stock por armazém (ERP NELO). */
  warehouses: WarehouseStockBreakdown[];
}

/** Envelope de `/v1/supply/materials/from-bom` — catálogo + estado do stock. */
export interface BomMaterialsEnvelope {
  items: BomMaterial[];
  count: number;
  stock_available: boolean;
  stock_synced_at: string | null;
  stock_source: 'erp_nelo_warehouse_stock' | 'indisponivel';
  unavailable_reason: string | null;
}

/** Prospeção material (MR02) — payload livre do backend. */
export interface MaterialPosition {
  sku_id: string;
  material: {
    name: string | null;
    category: string | null;
    active: boolean | null;
    unit_of_measure: string | null;
  };
  on_hand: number;
  in_transit: {
    qty: number;
    entries: Array<{
      purchase_order_id: string | null;
      qty: number;
      eta: string;
      supplier_id: string | null;
    }>;
  };
  projected_stock_horizon: number;
  min_stock: number;
  below_min: boolean;
  critical: boolean;
  days_to_stockout: number | null;
  rop: number | null;
  lead_time_days: number | null;
}

export interface MaterialMovement {
  transaction_type: 'consume' | 'receive' | 'adjust';
  qty_change: number;
  on_hand_after: number;
  occurred_at: string | null;
  reference_id: string | null;
}

export interface Reconciliation {
  id: string;
  sku_id: string;
  theoretical_qty: number;
  physical_qty: number;
  variance_qty: number;
  variance_pct: number | null;
  counted_at: string | null;
  counted_by: string | null;
  comments: string | null;
  resolved: boolean;
  resolved_at: string | null;
  resolved_by: string | null;
}

/** FM04 — risco de ruptura por ROP. Payload livre. */
export interface ShortageRisk {
  sku_id: string;
  name?: string | null;
  on_hand?: number;
  rop?: number | null;
  days_to_stockout?: number | null;
  severity?: string;
}

export interface Supplier {
  id: string;
  supplier_code: string;
  supplier_name: string;
  material_category: string;
  lead_time_days: number;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  city: string | null;
  country: string | null;
  quality_rating: number | null;
  is_active: boolean;
  is_preferred: boolean;
}

export const materiaisApi = {
  listMaterials: (params?: { active_only?: boolean; category?: string }) => {
    const qs = new URLSearchParams();
    if (params?.active_only !== undefined)
      qs.set('active_only', String(params.active_only));
    if (params?.category) qs.set('category', params.category);
    const q = qs.toString();
    return apiFetch<Material[]>(`/v1/supply/materials${q ? `?${q}` : ''}`);
  },

  listMaterialsFromBom: (params?: {
    search?: string;
    category?: string;
    limit?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.search) qs.set('search', params.search);
    if (params?.category) qs.set('category', params.category);
    if (params?.limit) qs.set('limit', String(params.limit));
    const q = qs.toString();
    return apiFetch<BomMaterialsEnvelope>(
      `/v1/supply/materials/from-bom${q ? `?${q}` : ''}`,
    );
  },

  createMaterial: (data: {
    sku_id: string;
    name: string;
    min_stock_qty?: number;
    reorder_qty?: number;
    lead_time_days?: number;
    unit_of_measure?: string;
    category?: string;
    critical_flag?: boolean;
  }) =>
    apiFetch<Material>('/v1/supply/materials', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getPosition: (skuId: string, horizonDays = 14) =>
    apiFetch<MaterialPosition>(
      `/v1/supply/materials/${encodeURIComponent(skuId)}/position?horizon_days=${horizonDays}`,
    ),

  getMovements: (skuId: string, limit = 50) =>
    apiFetch<MaterialMovement[]>(
      `/v1/supply/materials/${encodeURIComponent(skuId)}/movements?limit=${limit}`,
    ),

  patchMinStock: (skuId: string, minStockQty: number) =>
    apiFetch<Material>(
      `/v1/supply/materials/${encodeURIComponent(skuId)}/min-stock`,
      {
        method: 'PATCH',
        body: JSON.stringify({ min_stock_qty: minStockQty }),
      },
    ),

  adjustStock: (
    skuId: string,
    data: { qty_delta: number; reason: string; actor?: string },
  ) =>
    apiFetch<{
      sku_id: string;
      on_hand_after: number;
      qty_opening: number;
      qty_closing: number;
      qty_delta: number;
      reason: string;
    }>(`/v1/supply/materials/${encodeURIComponent(skuId)}/adjust`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listReconciliations: (params?: {
    unresolved_only?: boolean;
    limit?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.unresolved_only)
      qs.set('unresolved_only', String(params.unresolved_only));
    if (params?.limit) qs.set('limit', String(params.limit));
    const q = qs.toString();
    return apiFetch<Reconciliation[]>(
      `/v1/supply/reconciliation${q ? `?${q}` : ''}`,
    );
  },

  shortageRisks: (horizonDays = 14) =>
    apiFetch<ShortageRisk[] | { items?: ShortageRisk[]; data?: ShortageRisk[] }>(
      `/v1/factory-map/shortage-risks?horizon_days=${horizonDays}`,
    ),

  listSuppliers: () =>
    apiFetch<Supplier[]>('/v1/core/suppliers?limit=200'),
};
