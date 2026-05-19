// Decomposto de AuditTrailPage.tsx (Q.60.AC).
import { getApiBase } from '../../lib/api';

// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
export const API_BASE = getApiBase();

// ============================================================================
// TYPES
// ============================================================================

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
// API FUNCTIONS
// ============================================================================

export async function fetchAuditLogs(filters: {
  entity_type?: string;
  user?: string;
  date_from?: string;
  date_to?: string;
}): Promise<AuditLog[]> {
  const tenantId = localStorage.getItem('tenant_id') || '00000000-0000-0000-0000-000000000000';
  
  const params = new URLSearchParams();
  if (filters.entity_type) params.append('entity_type', filters.entity_type);
  if (filters.user) params.append('user', filters.user);
  if (filters.date_from) params.append('date_from', filters.date_from);
  if (filters.date_to) params.append('date_to', filters.date_to);
  
  const response = await fetch(`${API_BASE}/v1/governance/audit-logs?${params}`, {
    headers: {
      'X-Tenant-Id': tenantId,
    },
  });
  
  if (!response.ok) {
    // If 404, endpoint not yet implemented - return empty array with notice
    if (response.status === 404) {
      return [];
    }
    throw new Error(`Failed to fetch audit logs: ${response.status}`);
  }
  
  return response.json();
}

// ============================================================================
// COMPONENT
// ============================================================================
