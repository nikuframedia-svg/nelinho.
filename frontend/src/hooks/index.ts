export { useToast } from './useToast';
export { useSandboxSimulation } from './useSandboxSimulation';
export type { SandboxAction, SandboxResult, SandboxScenario } from './useSandboxSimulation';
export { useCommandPalette, CommandPaletteProvider } from './useCommandPalette';
export { useKeyboardShortcuts } from './useKeyboardShortcuts';
export type { KeyboardShortcut } from './useKeyboardShortcuts';

// Capabilities hooks
export {
  useCapabilities,
  useCapabilitiesSummary,
  useModules,
  useFeatures,
  useBlockedCapabilities,
  useDegradedCapabilities,
  useFeatureEnabled,
  useFeatureBlocked,
  useFeatureInfo,
  useModuleInfo,
  useHasActiveData,
  useActiveIngestionId,
  useBlockedMetrics,
  useAllowedMetrics,
  useRefreshCapabilities,
  useSystemHealth,
  capabilitiesKeys,
} from './useCapabilities';

export type {
  CapabilitiesResponse,
  CapabilitiesSummary,
  CapabilityStatus,
  ModuleCapability,
} from './useCapabilities';

// ============================================================================
// PALANTIR-LEVEL HOOKS — Real-time Data & Trust
// ============================================================================

// TIER 1: Foundation of Truth
export { useLiveKPIs } from './useLiveKPIs';
export type { LiveKPIs } from './useLiveKPIs';
export { useTrustHeatmap } from './useTrustHeatmap';
export { useQuarantine } from './useQuarantine';
export { useSchemaDrift } from './useSchemaDrift';
export { useBlockedMetrics as useBlockedMetricsWall } from './useBlockedMetrics';

// TIER 2: Operational Excellence
export { useMetricHistory } from './useMetricHistory';
export { useIngestions } from './useIngestions';
export { useMoldConflicts } from './useMoldConflicts';

// TIER 3: Enterprise Excellence
export { useRunbooks } from './useRunbooks';
export { useApprovalChain } from './useApprovalChain';
export { useSoDCheck } from './useSoDCheck';
export { useCoverageAnalysis } from './useCoverageAnalysis';

// TIER 4: CI/DevOps & Future
export { useToolRegistry } from './useToolRegistry';

// ============================================================================
// REAL-TIME — Server-Sent Events bridge (Sprint D.2)
// ============================================================================
export { useRealtimeEvents } from './useRealtimeEvents';
export type {
  RealtimeEvent,
  UseRealtimeEventsOptions,
  UseRealtimeEventsResult,
} from './useRealtimeEvents';

// Sprint D.3 — Dashboard auto-refresh on SSE events + connection badge
export {
  useLiveDashboardRefresh,
  DASHBOARD_TRIGGER_EVENTS,
} from './useLiveDashboardRefresh';
export type {
  UseLiveDashboardRefreshOptions,
  UseLiveDashboardRefreshResult,
} from './useLiveDashboardRefresh';

// Q.52.C — empty state honesto para respostas PARTIAL/degradadas
export {
  useHonestEmptyState,
  detectHonestEmptyState,
} from './useHonestEmptyState';
export type { HonestEmptyState } from './useHonestEmptyState';
