/**
 * Capabilities Hook
 * 
 * React hooks for accessing dynamic capabilities from the backend.
 * Used for feature gating and displaying data quality status.
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { capabilitiesApi } from '../lib/factoryApi';
import type { 
  CapabilitiesResponse, 
  CapabilitiesSummary,
  CapabilityStatus,
  ModuleCapability,
} from '../lib/factoryApi';

// ============================================================================
// QUERY KEYS
// ============================================================================

export const capabilitiesKeys = {
  all: ['capabilities'] as const,
  full: () => [...capabilitiesKeys.all, 'full'] as const,
  summary: () => [...capabilitiesKeys.all, 'summary'] as const,
  modules: () => [...capabilitiesKeys.all, 'modules'] as const,
  features: (moduleId?: string, status?: string) => 
    [...capabilitiesKeys.all, 'features', { moduleId, status }] as const,
  blocked: () => [...capabilitiesKeys.all, 'blocked'] as const,
  degraded: () => [...capabilitiesKeys.all, 'degraded'] as const,
};

// ============================================================================
// MAIN HOOK: useCapabilities
// ============================================================================

/**
 * Hook to fetch full capabilities data.
 * 
 * Returns all modules, features, blocked metrics, etc.
 */
export function useCapabilities() {
  return useQuery({
    queryKey: capabilitiesKeys.full(),
    queryFn: () => capabilitiesApi.getCapabilities(),
    staleTime: 60000, // 1 minute
    gcTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false,
    retry: 2,
  });
}

// ============================================================================
// HELPER HOOKS
// ============================================================================

/**
 * Hook to get capabilities summary (health score, counts).
 */
export function useCapabilitiesSummary() {
  return useQuery({
    queryKey: capabilitiesKeys.summary(),
    queryFn: () => capabilitiesApi.getSummary(),
    staleTime: 60000,
    refetchOnWindowFocus: false,
  });
}

/**
 * Hook to get modules list.
 */
export function useModules() {
  return useQuery({
    queryKey: capabilitiesKeys.modules(),
    queryFn: () => capabilitiesApi.getModules(),
    staleTime: 60000,
  });
}

/**
 * Hook to get features, optionally filtered.
 */
export function useFeatures(moduleId?: string, status?: string) {
  return useQuery({
    queryKey: capabilitiesKeys.features(moduleId, status),
    queryFn: () => capabilitiesApi.getFeatures(moduleId, status),
    staleTime: 60000,
  });
}

/**
 * Hook to get blocked capabilities.
 */
export function useBlockedCapabilities() {
  return useQuery({
    queryKey: capabilitiesKeys.blocked(),
    queryFn: () => capabilitiesApi.getBlocked(),
    staleTime: 60000,
  });
}

/**
 * Hook to get degraded capabilities.
 */
export function useDegradedCapabilities() {
  return useQuery({
    queryKey: capabilitiesKeys.degraded(),
    queryFn: () => capabilitiesApi.getDegraded(),
    staleTime: 60000,
  });
}

// ============================================================================
// FEATURE CHECKING HOOKS
// ============================================================================

/**
 * Check if a specific feature is enabled.
 * 
 * @param featureId - The feature ID to check
 * @returns true if feature is enabled or degraded (usable), false otherwise
 * 
 * @example
 * const canUseWIP = useFeatureEnabled('wip');
 * const canUseOEE = useFeatureEnabled('oee_real'); // will be false (blocked)
 */
export function useFeatureEnabled(featureId: string): boolean {
  const { data } = useCapabilities();
  
  if (!data) return false;
  
  for (const module of data.modules || []) {
    for (const feature of module.features || []) {
      if (feature.id === featureId) {
        return feature.status === 'enabled' || feature.status === 'degraded';
      }
    }
  }
  
  return false;
}

/**
 * Check if a specific feature is blocked.
 * 
 * @param featureId - The feature ID to check
 * @returns true if feature is explicitly blocked
 */
export function useFeatureBlocked(featureId: string): boolean {
  const { data } = useCapabilities();
  
  if (!data) return false;
  
  for (const module of data.modules || []) {
    for (const feature of module.features || []) {
      if (feature.id === featureId) {
        return feature.status === 'blocked';
      }
    }
  }
  
  return false;
}

/**
 * Get detailed feature info.
 * 
 * @param featureId - The feature ID to look up
 * @returns Feature capability info or null if not found
 */
export function useFeatureInfo(featureId: string): CapabilityStatus | null {
  const { data } = useCapabilities();
  
  if (!data) return null;
  
  for (const module of data.modules || []) {
    for (const feature of module.features || []) {
      if (feature.id === featureId) {
        return feature;
      }
    }
  }
  
  return null;
}

/**
 * Get module capability info.
 * 
 * @param moduleId - The module ID to look up
 * @returns Module capability info or null if not found
 */
export function useModuleInfo(moduleId: string): ModuleCapability | null {
  const { data } = useCapabilities();
  
  if (!data) return null;
  
  return data.modules?.find(m => m.id === moduleId) || null;
}

/**
 * Check if there is active data loaded.
 */
export function useHasActiveData(): boolean {
  const { data } = useCapabilities();
  return data?.has_active_data ?? false;
}

/**
 * Get the active ingestion ID if any.
 */
export function useActiveIngestionId(): string | null {
  const { data } = useCapabilities();
  return data?.active_ingestion_id ?? null;
}

/**
 * Get list of blocked metrics.
 */
export function useBlockedMetrics(): string[] {
  const { data } = useCapabilities();
  return data?.blocked_metrics ?? [];
}

/**
 * Get list of allowed metrics.
 */
export function useAllowedMetrics(): string[] {
  const { data } = useCapabilities();
  return data?.allowed_metrics ?? [];
}

// ============================================================================
// UTILITY HOOKS
// ============================================================================

/**
 * Hook to refresh capabilities data.
 */
export function useRefreshCapabilities() {
  const queryClient = useQueryClient();
  
  return () => {
    queryClient.invalidateQueries({ queryKey: capabilitiesKeys.all });
  };
}

/**
 * Get overall system health based on capabilities.
 */
export function useSystemHealth(): {
  score: number;
  status: 'healthy' | 'degraded' | 'critical';
  message: string;
} {
  const { data } = useCapabilitiesSummary();
  
  if (!data) {
    return {
      score: 0,
      status: 'critical',
      message: 'Unable to fetch capabilities',
    };
  }
  
  const score = data.health_score;
  
  if (score >= 80) {
    return {
      score,
      status: 'healthy',
      message: `System healthy (${data.enabled} features enabled)`,
    };
  }
  
  if (score >= 50) {
    return {
      score,
      status: 'degraded',
      message: `System degraded (${data.degraded} features limited, ${data.blocked} blocked)`,
    };
  }
  
  return {
    score,
    status: 'critical',
    message: `System critical (${data.disabled} features disabled, ${data.blocked} blocked)`,
  };
}

// ============================================================================
// TYPES RE-EXPORT
// ============================================================================

export type { 
  CapabilitiesResponse, 
  CapabilitiesSummary, 
  CapabilityStatus, 
  ModuleCapability,
};


