/**
 * DQA Dashboard — Trust Index v2 (Blueprint v2.0 §4.5)
 * =====================================================
 *
 * Sprint Q.1 migration: this page now reads the live 7-component Trust Index
 * from `/v1/dqa/trust-index?scope=factory` instead of the legacy
 * `/v1/factory/quality-report` 4-status segment list.
 *
 * Components shown (Blueprint v2.0 weights):
 *   Completeness 0.15 · Validity 0.20 · Freshness 0.15 · Consistency 0.20
 *   Provenance 0.15 · Anomaly 0.10 · Evidence 0.05  (CC reserved)
 *
 * Effective gates shown (configurable via tenant_configuration.trust):
 *   solver_suggestion_only 0.50 · use_p90_durations 0.60 · auto_reorder 0.70
 *   auto_commit 0.75 · quality_disposition 0.80
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  AlertTriangle,
  Ban,
  CheckCircle2,
  Info,
  Loader2,
  RefreshCw,
  Shield,
  ShieldCheck,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkBadge, DarkButton, DarkCard } from '../../components/dark';
import { dqaApi, type TrustIndexV2Response } from '../../lib/api';

// ───────────────────────────────────────────────────────────────────────────────
// Component / gate metadata — single source of truth for labels + thresholds
// ───────────────────────────────────────────────────────────────────────────────

const COMPONENT_LABELS: Record<keyof TrustIndexV2Response['components'], string> = {
  completeness: 'Completeness',
  validity: 'Validity',
  freshness: 'Freshness',
  consistency: 'Consistency',
  provenance: 'Provenance',
  anomaly: 'Anomaly',
  evidence: 'Evidence',
  causal_coherence: 'Causal Coherence (reserved)',
  timeliness: 'Timeliness (legacy)',
};

const GATE_LABELS: Record<keyof TrustIndexV2Response['effective_gates'], string> = {
  solver_suggestion_only: 'Solver suggestion-only',
  use_p90_durations: 'Use P90 durations',
  auto_reorder: 'Auto-reorder',
  auto_commit: 'Auto-commit',
  quality_disposition: 'Quality disposition',
};

// Default thresholds — used when the API doesn't return per-tenant overrides
// (the response only carries booleans). Mirrors `src/dqa/trust_gates.py`.
const GATE_THRESHOLDS: Record<keyof TrustIndexV2Response['effective_gates'], number> = {
  solver_suggestion_only: 0.5,
  use_p90_durations: 0.6,
  auto_reorder: 0.7,
  auto_commit: 0.75,
  quality_disposition: 0.8,
};

const PCT = (value: number) => `${(value * 100).toFixed(0)}%`;

const trustColor = (value: number): string => {
  if (value >= 0.75) return 'text-emerald-400';
  if (value >= 0.5) return 'text-amber-400';
  return 'text-red-400';
};

const trustBadge = (value: number): 'success' | 'warning' | 'danger' => {
  if (value >= 0.75) return 'success';
  if (value >= 0.5) return 'warning';
  return 'danger';
};

// ───────────────────────────────────────────────────────────────────────────────
// Component
// ───────────────────────────────────────────────────────────────────────────────

export function DQAPage() {
  const queryClient = useQueryClient();

  const {
    data: trust,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['dqa', 'trust-index', 'factory'],
    queryFn: () => dqaApi.trustIndex({ scope: 'factory' }),
    staleTime: 60_000,
    retry: 1,
  });

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['dqa', 'trust-index'] });
    refetch();
  };

  const componentEntries = trust
    ? (Object.keys(COMPONENT_LABELS) as Array<keyof typeof COMPONENT_LABELS>)
        .map((key) => ({ key, value: trust.components[key], weight: trust.weights[key as keyof typeof trust.weights] }))
        .filter((row) => row.value !== null && row.value !== undefined)
    : [];

  const gateEntries = trust
    ? (Object.keys(GATE_LABELS) as Array<keyof typeof GATE_LABELS>).map((key) => ({
        key,
        allowed: trust.effective_gates[key],
        threshold: GATE_THRESHOLDS[key],
      }))
    : [];

  return (
    <DarkPageLayout
      title="Data Quality Center"
      subtitle="Trust Index v2 — Blueprint v2.0 §4.5 (factory scope)"
      icon={<Shield size={20} />}
      actions={
        <DarkButton variant="secondary" icon={<RefreshCw size={16} />} onClick={handleRefresh}>
          Refresh
        </DarkButton>
      }
    >
      {isLoading && (
        <DarkCard className="text-center py-10">
          <Loader2 size={32} className="mx-auto mb-2 text-teal-400 animate-spin" />
          <p className="text-slate-400">A calcular Trust Index…</p>
        </DarkCard>
      )}

      {error && (
        <DarkCard className="border-red-500/30 bg-red-500/10">
          <div className="flex items-center gap-3 text-red-400">
            <AlertCircle size={20} />
            <div className="flex-1">
              <p className="font-medium">Falha ao carregar Trust Index</p>
              <p className="text-sm text-red-400/80">{(error as Error).message}</p>
            </div>
            <DarkButton variant="secondary" size="sm" onClick={() => refetch()}>
              Retry
            </DarkButton>
          </div>
        </DarkCard>
      )}

      {trust && (
        <>
          {/* Composite + scope summary */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <DarkCard>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-500/20 rounded-lg">
                  <Shield size={20} className="text-blue-400" />
                </div>
                <div>
                  <p className="text-xs text-slate-400">Composite</p>
                  <p className={`text-2xl font-bold ${trustColor(trust.composite)}`}>
                    {PCT(trust.composite)}
                  </p>
                </div>
              </div>
            </DarkCard>
            <DarkCard>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-slate-700/40 rounded-lg">
                  <Info size={20} className="text-slate-300" />
                </div>
                <div>
                  <p className="text-xs text-slate-400">Scope</p>
                  <p className="text-2xl font-bold text-white capitalize">{trust.scope}</p>
                </div>
              </div>
            </DarkCard>
            <DarkCard>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-emerald-500/20 rounded-lg">
                  <ShieldCheck size={20} className="text-emerald-400" />
                </div>
                <div>
                  <p className="text-xs text-slate-400">Gates abertos</p>
                  <p className="text-2xl font-bold text-emerald-400">
                    {gateEntries.filter((g) => g.allowed).length} / {gateEntries.length}
                  </p>
                </div>
              </div>
            </DarkCard>
            <DarkCard>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-amber-500/20 rounded-lg">
                  <AlertTriangle size={20} className="text-amber-400" />
                </div>
                <div>
                  <p className="text-xs text-slate-400">Componentes monitorizados</p>
                  <p className="text-2xl font-bold text-amber-400">
                    {componentEntries.length}
                  </p>
                </div>
              </div>
            </DarkCard>
          </div>

          {/* Components breakdown */}
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-white mb-4">Componentes (peso × score)</h2>
            <DarkCard>
              <div className="space-y-3">
                {componentEntries.map(({ key, value, weight }) => {
                  const v = value as number;
                  return (
                    <div
                      key={key}
                      className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg border border-slate-700/50"
                    >
                      <div className="flex items-center gap-3 flex-1">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-white">{COMPONENT_LABELS[key]}</span>
                            {weight !== undefined && (
                              <span className="text-xs text-slate-500">
                                (peso {(weight * 100).toFixed(0)}%)
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="w-32 h-2 bg-slate-700 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              v >= 0.75
                                ? 'bg-emerald-500'
                                : v >= 0.5
                                ? 'bg-amber-500'
                                : 'bg-red-500'
                            }`}
                            style={{ width: `${Math.min(100, Math.max(0, v * 100))}%` }}
                          />
                        </div>
                        <span className={`text-lg font-bold w-14 text-right ${trustColor(v)}`}>
                          {PCT(v)}
                        </span>
                        <DarkBadge variant={trustBadge(v)}>
                          {v >= 0.75 ? 'OK' : v >= 0.5 ? 'WARN' : 'LOW'}
                        </DarkBadge>
                      </div>
                    </div>
                  );
                })}
              </div>
            </DarkCard>
          </div>

          {/* Gates */}
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <ShieldCheck size={20} className="text-teal-400" />
              Effective Gates (Blueprint v2.0 §4.5)
            </h2>
            <DarkCard>
              <div className="space-y-3">
                {gateEntries.map(({ key, allowed, threshold }) => (
                  <div
                    key={key}
                    className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      {allowed ? (
                        <CheckCircle2 size={18} className="text-emerald-400" />
                      ) : (
                        <Ban size={18} className="text-red-400" />
                      )}
                      <span className="text-white">{GATE_LABELS[key]}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500">
                        threshold {(threshold * 100).toFixed(0)}%
                      </span>
                      <DarkBadge variant={allowed ? 'success' : 'danger'}>
                        {allowed ? 'Open' : 'Blocked'}
                      </DarkBadge>
                    </div>
                  </div>
                ))}
              </div>
            </DarkCard>
          </div>
        </>
      )}
    </DarkPageLayout>
  );
}

export default DQAPage;
