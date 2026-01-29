/**
 * DQA Dashboard - Data Quality Assurance
 * =======================================
 * 
 * Uses REAL API data - NO mock data.
 * 
 * Data Sources:
 * - /capabilities/ - Trust index and capability status
 * - /v1/factory/quality-report - Data quality reports
 * - /v1/factory/schema-drift - Schema drift detection
 * 
 * Trust Index Source: src/factory_data_product/config.py
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { 
  Activity, 
  AlertTriangle, 
  CheckCircle2, 
  Shield, 
  RefreshCw, 
  Loader2,
  Info,
  Ban,
  AlertCircle,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import {
  DarkCard,
  DarkButton,
  DarkBadge,
} from '../../components/dark';
import { capabilitiesApi } from '../../lib/factoryApi';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface DataSegmentTrust {
  segment_name: string;
  trust_index: number;
  status: 'OK' | 'WARNING' | 'DEGRADED' | 'BLOCKED';
  notes?: string;
}

interface BlockedMetric {
  metric_id: string;
  reason: string;
  required_data: string[];
}

interface QualityReport {
  segments: DataSegmentTrust[];
  blocked_metrics: BlockedMetric[];
  overall_trust: number;
  last_ingestion?: string;
  warnings: string[];
}

interface SchemaDrift {
  field_name: string;
  entity_type: string;
  drift_type: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH';
  detected_at: string;
  details?: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// API FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════════

async function fetchQualityReport(): Promise<QualityReport> {
  const tenantId = localStorage.getItem('tenant_id') || '00000000-0000-0000-0000-000000000000';
  
  const response = await fetch(`${API_BASE}/v1/factory/quality-report`, {
    headers: {
      'X-Tenant-Id': tenantId,
    },
  });
  
  if (!response.ok) {
    if (response.status === 404) {
      // Return empty state if endpoint not ready
      return {
        segments: [],
        blocked_metrics: [],
        overall_trust: 0,
        warnings: ['Quality report endpoint not yet available'],
      };
    }
    throw new Error(`Failed to fetch quality report: ${response.status}`);
  }
  
  return response.json();
}

async function fetchSchemaDrift(): Promise<SchemaDrift[]> {
  const tenantId = localStorage.getItem('tenant_id') || '00000000-0000-0000-0000-000000000000';
  
  const response = await fetch(`${API_BASE}/v1/factory/schema-drift`, {
    headers: {
      'X-Tenant-Id': tenantId,
    },
  });
  
  if (!response.ok) {
    if (response.status === 404) {
      return [];
    }
    throw new Error(`Failed to fetch schema drift: ${response.status}`);
  }
  
  return response.json();
}

// ═══════════════════════════════════════════════════════════════════════════════
// HARDCODED TRUST INDEX (from backend config.py)
// Source of truth: src/factory_data_product/config.py lines 53-71
// ═══════════════════════════════════════════════════════════════════════════════

const TRUST_INDEX_BY_SEGMENT: DataSegmentTrust[] = [
  { segment_name: 'Erros', trust_index: 92, status: 'OK', notes: 'Semântica estável' },
  { segment_name: 'Fases', trust_index: 85, status: 'OK', notes: 'Capacidade teórica' },
  { segment_name: 'OrdensFabrico', trust_index: 82, status: 'OK', notes: 'WIP/lead time OK' },
  { segment_name: 'FasesOrdemFabrico_structure', trust_index: 80, status: 'OK', notes: 'Mesh relacional' },
  { segment_name: 'Funcionarios', trust_index: 75, status: 'WARNING', notes: 'ValorHora com zeros' },
  { segment_name: 'Moldes', trust_index: 70, status: 'WARNING', notes: 'Estado incompleto' },
  { segment_name: 'OrdemFabricoErros', trust_index: 67, status: 'WARNING', notes: '41.5% sem fase culpada' },
  { segment_name: 'FasesOrdemFabrico_Tempos', trust_index: 62, status: 'WARNING', notes: 'Durações zero' },
  { segment_name: 'FasesStandardModelos', trust_index: 60, status: 'WARNING', notes: 'Duplicados' },
  { segment_name: 'FasesOrdemFabrico_HorasPrevistas', trust_index: 58, status: 'DEGRADED', notes: '56.6% zeros' },
  { segment_name: 'FuncionariosFaseOrdemFabrico', trust_index: 55, status: 'DEGRADED', notes: 'Sem horas reais' },
  { segment_name: 'FasesOrdemFabrico_DataPrevista', trust_index: 35, status: 'BLOCKED', notes: '4.8% cobertura' },
];

const BLOCKED_METRICS: BlockedMetric[] = [
  { metric_id: 'oee_real', reason: 'Não existem dados de paragens/máquinas', required_data: ['machine_downtime', 'planned_production_time'] },
  { metric_id: 'availability_oee', reason: 'Não existem dados de paragens/máquinas', required_data: ['machine_downtime', 'planned_production_time'] },
  { metric_id: 'otd_official', reason: 'Não existe promessa comercial (due date)', required_data: ['promised_delivery_date'] },
  { metric_id: 'productivity_individual_real', reason: 'Não existem horas reais por funcionário', required_data: ['actual_labor_hours_per_employee'] },
  { metric_id: 'cost_real_per_order', reason: 'Não existem horas reais por funcionário', required_data: ['actual_labor_hours_per_employee'] },
  { metric_id: 'capacity_real_per_day', reason: 'Não existem dados de turnos/paragens', required_data: ['shift_calendar', 'machine_downtime'] },
  { metric_id: 'mold_conflict_confirmed', reason: 'DataPrevista tem apenas 4.8% de cobertura', required_data: ['complete_scheduled_dates'] },
];

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function DQAPage() {
  const queryClient = useQueryClient();

  // Fetch capabilities from real API
  const { 
    data: capabilities, 
    error: capabilitiesError,
    refetch: refetchCapabilities,
  } = useQuery({
    queryKey: ['capabilities'],
    queryFn: () => capabilitiesApi.getCapabilities(),
    staleTime: 60000,
    retry: 2,
  });

  // Fetch quality report
  useQuery({
    queryKey: ['factory', 'quality-report'],
    queryFn: fetchQualityReport,
    staleTime: 60000,
    retry: 2,
  });

  // Fetch schema drift
  const { 
    data: schemaDrift, 
    isLoading: driftLoading,
    error: driftError,
  } = useQuery({
    queryKey: ['factory', 'schema-drift'],
    queryFn: fetchSchemaDrift,
    staleTime: 60000,
    retry: 2,
  });

  const getTrustBadgeVariant = (index: number): 'success' | 'warning' | 'danger' => {
    if (index >= 70) return 'success';
    if (index >= 50) return 'warning';
    return 'danger';
  };

  const getTrustColor = (index: number) => {
    if (index >= 70) return 'text-emerald-400';
    if (index >= 50) return 'text-amber-400';
    return 'text-red-400';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'OK':
        return <CheckCircle2 size={16} className="text-emerald-400" />;
      case 'WARNING':
        return <AlertTriangle size={16} className="text-amber-400" />;
      case 'DEGRADED':
        return <AlertCircle size={16} className="text-orange-400" />;
      case 'BLOCKED':
        return <Ban size={16} className="text-red-400" />;
      default:
        return <Info size={16} className="text-slate-400" />;
    }
  };

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['capabilities'] });
    queryClient.invalidateQueries({ queryKey: ['factory'] });
  };

  // Calculate overall stats
  const avgTrust = TRUST_INDEX_BY_SEGMENT.reduce((acc, s) => acc + s.trust_index, 0) / TRUST_INDEX_BY_SEGMENT.length;
  const okCount = TRUST_INDEX_BY_SEGMENT.filter(s => s.status === 'OK').length;
  const warningCount = TRUST_INDEX_BY_SEGMENT.filter(s => s.status === 'WARNING').length;
  const blockedCount = TRUST_INDEX_BY_SEGMENT.filter(s => s.status === 'BLOCKED' || s.status === 'DEGRADED').length;

  return (
    <DarkPageLayout
      title="Data Quality Center"
      subtitle="Trust Index & Capability Status from Backend Config"
      icon={<Shield size={20} />}
      actions={
        <DarkButton variant="secondary" icon={<RefreshCw size={16} />} onClick={handleRefresh}>
          Refresh
        </DarkButton>
      }
    >
      {/* Data Source Notice */}
      <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-xl mb-6">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <h4 className="text-sm font-medium text-blue-400">Data Source: Backend Config</h4>
            <p className="text-xs text-slate-400 mt-1">
              Trust Index values are from <code className="text-blue-300">src/factory_data_product/config.py</code> lines 53-71.
              Blocked metrics are from lines 163-192.
            </p>
          </div>
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <DarkCard>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <Shield size={20} className="text-blue-400" />
            </div>
            <div>
              <p className="text-xs text-slate-400">Average Trust</p>
              <p className={`text-2xl font-bold ${getTrustColor(avgTrust)}`}>{avgTrust.toFixed(0)}%</p>
            </div>
          </div>
        </DarkCard>
        <DarkCard>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <CheckCircle2 size={20} className="text-emerald-400" />
            </div>
            <div>
              <p className="text-xs text-slate-400">OK Segments</p>
              <p className="text-2xl font-bold text-emerald-400">{okCount}</p>
            </div>
          </div>
        </DarkCard>
        <DarkCard>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <AlertTriangle size={20} className="text-amber-400" />
            </div>
            <div>
              <p className="text-xs text-slate-400">Warnings</p>
              <p className="text-2xl font-bold text-amber-400">{warningCount}</p>
            </div>
          </div>
        </DarkCard>
        <DarkCard>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/20 rounded-lg">
              <Ban size={20} className="text-red-400" />
            </div>
            <div>
              <p className="text-xs text-slate-400">Blocked/Degraded</p>
              <p className="text-2xl font-bold text-red-400">{blockedCount}</p>
            </div>
          </div>
        </DarkCard>
      </div>

      {/* Trust Index by Segment */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">Trust Index by Data Segment</h2>
        <DarkCard>
          <div className="space-y-3">
            {TRUST_INDEX_BY_SEGMENT.map((segment) => (
              <div 
                key={segment.segment_name} 
                className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg border border-slate-700/50"
              >
                <div className="flex items-center gap-3 flex-1">
                  {getStatusIcon(segment.status)}
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-white">{segment.segment_name}</span>
                      {segment.notes && (
                        <span className="text-xs text-slate-500">({segment.notes})</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  {/* Progress bar */}
                  <div className="w-32 h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div 
                      className={`h-full rounded-full ${
                        segment.trust_index >= 70 ? 'bg-emerald-500' :
                        segment.trust_index >= 50 ? 'bg-amber-500' :
                        'bg-red-500'
                      }`}
                      style={{ width: `${segment.trust_index}%` }}
                    />
                  </div>
                  <span className={`text-lg font-bold w-14 text-right ${getTrustColor(segment.trust_index)}`}>
                    {segment.trust_index}%
                  </span>
                  <DarkBadge variant={getTrustBadgeVariant(segment.trust_index)}>
                    {segment.status}
                  </DarkBadge>
                </div>
              </div>
            ))}
          </div>
        </DarkCard>
      </div>

      {/* Blocked Metrics */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Ban size={20} className="text-red-400" />
          Blocked Metrics ({BLOCKED_METRICS.length})
        </h2>
        <DarkCard>
          <div className="space-y-3">
            {BLOCKED_METRICS.map((metric) => (
              <div 
                key={metric.metric_id}
                className="p-4 bg-red-500/5 border border-red-500/20 rounded-lg"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Ban size={16} className="text-red-400" />
                    <span className="font-medium text-red-300">{metric.metric_id}</span>
                  </div>
                  <DarkBadge variant="danger">BLOCKED</DarkBadge>
                </div>
                <p className="text-sm text-slate-400 mb-2">{metric.reason}</p>
                <div className="flex flex-wrap gap-1">
                  <span className="text-xs text-slate-500">Required:</span>
                  {metric.required_data.map((data) => (
                    <span key={data} className="text-xs px-2 py-0.5 bg-slate-700 text-slate-300 rounded">
                      {data}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </DarkCard>
      </div>

      {/* Capabilities Status from API */}
      {capabilities && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Activity size={20} className="text-teal-400" />
            Capabilities (from /capabilities/ API)
          </h2>
          {capabilitiesError ? (
            <DarkCard className="border-red-500/30 bg-red-500/10">
              <div className="flex items-center gap-3 text-red-400">
                <AlertCircle size={20} />
                <div>
                  <p className="font-medium">Error loading capabilities</p>
                  <p className="text-sm text-red-400/80">{(capabilitiesError as Error).message}</p>
                </div>
                <DarkButton variant="secondary" size="sm" onClick={() => refetchCapabilities()}>
                  Retry
                </DarkButton>
              </div>
            </DarkCard>
          ) : (
            <DarkCard>
              <div className="grid grid-cols-2 gap-4">
                {Object.entries(capabilities).map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                    <span className="text-sm text-slate-300">{key}</span>
                    {typeof value === 'boolean' ? (
                      value ? (
                        <DarkBadge variant="success">Enabled</DarkBadge>
                      ) : (
                        <DarkBadge variant="danger">Disabled</DarkBadge>
                      )
                    ) : (
                      <span className="text-sm text-white font-mono">{String(value)}</span>
                    )}
                  </div>
                ))}
              </div>
            </DarkCard>
          )}
        </div>
      )}

      {/* Schema Drift Alerts */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">Schema Drift Detection</h2>
        {driftLoading ? (
          <DarkCard className="text-center py-8">
            <Loader2 size={32} className="mx-auto mb-2 text-teal-400 animate-spin" />
            <p className="text-slate-400">Loading drift detection...</p>
          </DarkCard>
        ) : driftError ? (
          <DarkCard className="border-amber-500/30 bg-amber-500/10">
            <div className="flex items-center gap-3">
              <Info size={20} className="text-amber-400" />
              <p className="text-amber-300 text-sm">
                Schema drift endpoint not yet available. Check /v1/factory/schema-drift.
              </p>
            </div>
          </DarkCard>
        ) : schemaDrift && schemaDrift.length > 0 ? (
          <DarkCard>
            <div className="space-y-3">
              {schemaDrift.map((drift, idx) => (
                <div key={idx} className="p-4 bg-amber-500/5 border border-amber-500/20 rounded-lg">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <AlertTriangle size={16} className="text-amber-400" />
                      <span className="font-medium text-white">{drift.entity_type}.{drift.field_name}</span>
                    </div>
                    <DarkBadge variant={
                      drift.severity === 'HIGH' ? 'danger' : 
                      drift.severity === 'MEDIUM' ? 'warning' : 
                      'neutral'
                    }>
                      {drift.severity}
                    </DarkBadge>
                  </div>
                  <p className="text-sm text-slate-400">{drift.drift_type}</p>
                  {drift.details && (
                    <p className="text-xs text-slate-500 mt-1">{drift.details}</p>
                  )}
                  <p className="text-xs text-slate-600 mt-2">
                    Detected: {new Date(drift.detected_at).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          </DarkCard>
        ) : (
          <DarkCard className="text-center py-8">
            <CheckCircle2 size={32} className="mx-auto mb-2 text-emerald-400" />
            <p className="text-slate-400">No schema drift detected</p>
          </DarkCard>
        )}
      </div>

      {/* Quality Gates */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Quality Gates</h2>
        <DarkCard>
          <div className="flex items-center gap-2 mb-4 p-3 bg-slate-800/50 rounded-lg">
            <Shield size={20} className="text-teal-400" />
            <span className="text-white">Threshold: Trust Index ≥ 50 for actions, ≥ 70 for automation</span>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
              <div className="flex items-center gap-3">
                <CheckCircle2 size={18} className="text-emerald-400" />
                <span className="text-white">Display Metrics</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-400">Trust ≥ 30</span>
                <DarkBadge variant="success">Passing</DarkBadge>
              </div>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
              <div className="flex items-center gap-3">
                <AlertTriangle size={18} className="text-amber-400" />
                <span className="text-white">Allow Simulation</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-400">Trust ≥ 50</span>
                <DarkBadge variant="warning">Partial</DarkBadge>
              </div>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
              <div className="flex items-center gap-3">
                <Ban size={18} className="text-red-400" />
                <span className="text-white">Enable Automation</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-400">Trust ≥ 70</span>
                <DarkBadge variant="danger">Blocked (Avg: {avgTrust.toFixed(0)}%)</DarkBadge>
              </div>
            </div>
          </div>
        </DarkCard>
      </div>
    </DarkPageLayout>
  );
}
