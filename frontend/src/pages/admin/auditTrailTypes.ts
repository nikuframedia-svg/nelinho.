// Decomposto de AuditTrailPage.tsx (Q.60.AC).
// Q.61.19 — endpoint real /v1/governance/audit-logs (forma paginada).
// Cliente: passa via apiFetch (Q.61.07 — sem fetch directo, sem
// drift de tracing). Mapeia campos backend -> frontend para manter
// AuditTrailPage estavel.
import { request } from '../../lib/api/client';

// ============================================================================
// TYPES
// ============================================================================

// Frontend shape — alguns campos sao mapeados do backend (Q.61.19):
//   timestamp <- created_at
//   user_id   <- actor_id
//   changes   <- new_values
//   before    <- old_values
//   after     <- new_values
export interface AuditLog {
  id: string;
  timestamp: string;
  user_id: string;
  user_name?: string;
  entity_type: string;
  entity_id: string;
  action: string;
  changes: Record<string, any>;
  before_state?: Record<string, any> | null;
  after_state?: Record<string, any> | null;
  metadata?: Record<string, any>;
}

export type ViewMode = 'table' | 'timeline';
export type TabMode = 'audit' | 'decisions';

// ============================================================================
// BACKEND RESPONSE SHAPE (Q.61.19)
// ============================================================================

interface BackendAuditEntry {
  id: string;
  tenant_id: string;
  entity_type: string;
  entity_id: string;
  action: 'INSERT' | 'UPDATE' | 'DELETE';
  old_values: Record<string, any> | null;
  new_values: Record<string, any> | null;
  actor_id: string | null;
  actor_role: string | null;
  reason: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

interface BackendAuditPage {
  entries: BackendAuditEntry[];
  total: number;
  page: number;
  page_size: number;
}

function mapEntry(e: BackendAuditEntry): AuditLog {
  return {
    id: e.id,
    timestamp: e.created_at,
    user_id: e.actor_id ?? 'system',
    user_name: e.actor_role ?? undefined,
    entity_type: e.entity_type,
    entity_id: e.entity_id,
    action: e.action,
    changes: e.new_values ?? {},
    before_state: e.old_values,
    after_state: e.new_values,
    metadata: e.reason ? { reason: e.reason } : undefined,
  };
}

// ============================================================================
// API FUNCTIONS
// ============================================================================

export async function fetchAuditLogs(filters: {
  entity_type?: string;
  user?: string;
  date_from?: string;
  date_to?: string;
}): Promise<AuditLog[]> {
  // Q.61.19 — endpoint real. apiFetch injecta tenant + user + trace_id
  // headers automaticamente (Q.61.12). Substitui o `fetch` directo que
  // Q.61.07 marca como warn.
  const params = new URLSearchParams();
  if (filters.entity_type) params.append('entity_type', filters.entity_type);
  if (filters.user) params.append('actor_id', filters.user);
  if (filters.date_from) params.append('since', filters.date_from);
  if (filters.date_to) params.append('until', filters.date_to);
  params.append('page_size', '100');

  try {
    const page = await request<BackendAuditPage>(
      `/v1/governance/audit-logs?${params}`,
    );
    return page.entries.map(mapEntry);
  } catch (err) {
    // 404 = endpoint nao montado (release antiga) -> empty graceful.
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes('404')) return [];
    throw err;
  }
}

// ============================================================================
// COMPONENT
// ============================================================================
