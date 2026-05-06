/**
 * Capabilities Provider
 * =====================
 * 
 * Central provider for backend capabilities and data quality status.
 * Uses REAL API data - NO default fallbacks for capabilities.
 * 
 * Source: /capabilities/ endpoint
 * Contract: src/factory_data_product/config.py
 */

import { createContext, useContext, useMemo } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Ban, RefreshCw } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ═══════════════════════════════════════════════════════════════════════════════
// BLOCKED METRICS (from backend config.py)
// These are NEVER returned with values - they are blocked at the source
// ═══════════════════════════════════════════════════════════════════════════════

export const BLOCKED_METRICS = {
  oee_real: {
    reason: 'Não existem dados de paragens/máquinas',
    required_data: ['machine_downtime', 'planned_production_time'],
  },
  availability_oee: {
    reason: 'Não existem dados de paragens/máquinas',
    required_data: ['machine_downtime', 'planned_production_time'],
  },
  otd_official: {
    reason: 'Não existe promessa comercial (due date)',
    required_data: ['promised_delivery_date'],
  },
  productivity_individual_real: {
    reason: 'Não existem horas reais por funcionário',
    required_data: ['actual_labor_hours_per_employee'],
  },
  cost_real_per_order: {
    reason: 'Não existem horas reais por funcionário',
    required_data: ['actual_labor_hours_per_employee'],
  },
  capacity_real_per_day: {
    reason: 'Não existem dados de turnos/paragens',
    required_data: ['shift_calendar', 'machine_downtime'],
  },
  mold_conflict_confirmed: {
    reason: 'DataPrevista tem apenas 4.8% de cobertura',
    required_data: ['complete_scheduled_dates'],
  },
} as const;

export const BLOCKED_METRIC_IDS = Object.keys(BLOCKED_METRICS) as (keyof typeof BLOCKED_METRICS)[];

// ═══════════════════════════════════════════════════════════════════════════════
// ALLOWED METRICS
// ═══════════════════════════════════════════════════════════════════════════════

export const ALLOWED_METRICS = [
  'wip_theoretical',
  'backlog_theoretical_hours',
  'backlog_theoretical_days',
  'bottleneck_ranking',
  'lead_time_observed',
  'quality_error_count',
  'quality_error_by_type',
  'quality_error_by_phase',
  'mold_conflict_potential',
  'skills_risk_by_phase',
  'cost_theoretical_estimated',
  'capacity_theoretical_per_phase',
] as const;

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

export interface CapabilitiesResponse {
  modules: string[];
  features: string[];
  version: string;
  blocked_metrics?: string[];
  allowed_metrics?: string[];
  trust_index?: Record<string, number>;
  data_product_status?: 'OK' | 'WARNING' | 'DEGRADED' | 'BLOCKED';
  last_ingestion?: string;
}

export interface Capabilities extends CapabilitiesResponse {
  // Enhanced with computed properties
  isMetricBlocked: (metricId: string) => boolean;
  getBlockedReason: (metricId: string) => string | undefined;
}

interface CapabilitiesContextValue {
  capabilities: Capabilities | null;
  isLoading: boolean;
  error: Error | null;
  hasModule: (module: string) => boolean;
  hasFeature: (feature: string) => boolean;
  isMetricBlocked: (metricId: string) => boolean;
  isMetricAllowed: (metricId: string) => boolean;
  getBlockedReason: (metricId: string) => string | undefined;
  blockedMetrics: typeof BLOCKED_METRICS;
  refetch: () => void;
}

// ═══════════════════════════════════════════════════════════════════════════════
// CONTEXT
// ═══════════════════════════════════════════════════════════════════════════════

const CapabilitiesContext = createContext<CapabilitiesContextValue | null>(null);

// ═══════════════════════════════════════════════════════════════════════════════
// API FETCH
// ═══════════════════════════════════════════════════════════════════════════════

async function fetchCapabilities(): Promise<CapabilitiesResponse> {
  // Q.18.AUTH — dev tenant default (não-zero UUID, aceite por require_tenant_header).
  const tenantId = localStorage.getItem('tenant_id') || '00000000-0000-0000-0000-000000000001';
  
  const response = await fetch(`${API_BASE}/v1/capabilities/`, {
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-Id': tenantId,
    },
  });
  
  if (!response.ok) {
    throw new Error(`Failed to load capabilities: ${response.status}`);
  }
  
  return response.json();
}

// ═══════════════════════════════════════════════════════════════════════════════
// BOOT LOADER
// ═══════════════════════════════════════════════════════════════════════════════

function BootLoader() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
      <div className="text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-teal-500 to-teal-600 flex items-center justify-center shadow-lg animate-pulse">
          <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-white mb-2">ProdPlan ONE</h2>
        <p className="text-slate-400 text-sm">Loading capabilities from backend...</p>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ERROR STATE
// ═══════════════════════════════════════════════════════════════════════════════

function CapabilitiesError({ error, onRetry }: { error: Error; onRetry: () => void }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-slate-800/50 border border-red-500/30 rounded-2xl p-8 text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-500/20 flex items-center justify-center">
          <AlertTriangle size={32} className="text-red-400" />
        </div>
        <h2 className="text-xl font-bold text-white mb-2">Failed to Load Capabilities</h2>
        <p className="text-red-400 text-sm mb-4">{error.message}</p>
        <p className="text-slate-400 text-xs mb-6">
          The application cannot start without capabilities from the backend.
          This ensures all data governance rules are enforced.
        </p>
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-2 px-6 py-3 bg-teal-600 hover:bg-teal-500 text-white rounded-lg font-medium transition-colors"
        >
          <RefreshCw size={18} />
          Retry Connection
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// DEGRADED MODE WARNING
// ═══════════════════════════════════════════════════════════════════════════════

function DegradedModeWarning({ status }: { status: string }) {
  if (status === 'OK') return null;
  
  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-amber-500/10 border-b border-amber-500/30 px-4 py-2">
      <div className="max-w-7xl mx-auto flex items-center gap-3">
        <Ban size={18} className="text-amber-400" />
        <p className="text-sm text-amber-300">
          <strong>Data Product Status: {status}</strong> — Some features may be limited due to data quality issues.
        </p>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PROVIDER
// ═══════════════════════════════════════════════════════════════════════════════

export function CapabilitiesProvider({ children }: { children: ReactNode }) {
  const { data: capabilitiesResponse, isLoading, error, refetch } = useQuery({
    queryKey: ['capabilities'],
    queryFn: fetchCapabilities,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
  });

  // Enhanced capabilities with computed methods
  const capabilities = useMemo<Capabilities | null>(() => {
    if (!capabilitiesResponse) return null;
    
    return {
      ...capabilitiesResponse,
      isMetricBlocked: (metricId: string) => {
        // Check local blocked list first
        if (BLOCKED_METRIC_IDS.includes(metricId as keyof typeof BLOCKED_METRICS)) {
          return true;
        }
        // Check backend list
        return capabilitiesResponse.blocked_metrics?.includes(metricId) ?? false;
      },
      getBlockedReason: (metricId: string) => {
        const blockedInfo = BLOCKED_METRICS[metricId as keyof typeof BLOCKED_METRICS];
        return blockedInfo?.reason;
      },
    };
  }, [capabilitiesResponse]);

  const hasModule = (module: string): boolean => {
    return capabilities?.modules?.includes(module) ?? false;
  };

  const hasFeature = (feature: string): boolean => {
    return capabilities?.features?.includes(feature) ?? false;
  };

  const isMetricBlocked = (metricId: string): boolean => {
    // Always check local blocked list
    if (BLOCKED_METRIC_IDS.includes(metricId as keyof typeof BLOCKED_METRICS)) {
      return true;
    }
    return capabilities?.blocked_metrics?.includes(metricId) ?? false;
  };

  const isMetricAllowed = (metricId: string): boolean => {
    return ALLOWED_METRICS.includes(metricId as typeof ALLOWED_METRICS[number]);
  };

  const getBlockedReason = (metricId: string): string | undefined => {
    const blockedInfo = BLOCKED_METRICS[metricId as keyof typeof BLOCKED_METRICS];
    return blockedInfo?.reason;
  };

  // Show boot loader while loading capabilities
  if (isLoading) {
    return <BootLoader />;
  }

  // Show error state - DO NOT continue without capabilities
  if (error) {
    return <CapabilitiesError error={error as Error} onRetry={() => refetch()} />;
  }

  const contextValue: CapabilitiesContextValue = {
    capabilities,
    isLoading,
    error: error as Error | null,
    hasModule,
    hasFeature,
    isMetricBlocked,
    isMetricAllowed,
    getBlockedReason,
    blockedMetrics: BLOCKED_METRICS,
    refetch: () => refetch(),
  };

  return (
    <CapabilitiesContext.Provider value={contextValue}>
      {capabilities?.data_product_status && (
        <DegradedModeWarning status={capabilities.data_product_status} />
      )}
      {children}
    </CapabilitiesContext.Provider>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// HOOK
// ═══════════════════════════════════════════════════════════════════════════════

export function useCapabilities(): CapabilitiesContextValue {
  const context = useContext(CapabilitiesContext);
  if (!context) {
    throw new Error('useCapabilities must be used within a CapabilitiesProvider');
  }
  return context;
}

// ═══════════════════════════════════════════════════════════════════════════════
// UTILITY HOOK - Check specific metric status
// ═══════════════════════════════════════════════════════════════════════════════

export function useMetricStatus(metricId: string) {
  const { isMetricBlocked, isMetricAllowed, getBlockedReason } = useCapabilities();
  
  return {
    isBlocked: isMetricBlocked(metricId),
    isAllowed: isMetricAllowed(metricId),
    blockedReason: getBlockedReason(metricId),
    canDisplay: !isMetricBlocked(metricId),
    canSimulate: isMetricAllowed(metricId) && !isMetricBlocked(metricId),
  };
}
