/**
 * Quality Analysis Page
 * =====================
 * 
 * Displays quality metrics from Factory Data Product semantic queries.
 * Uses real API data - NO mock data.
 * 
 * Data Source: /v1/factory/semantic/queries/quality
 * Trust Index: 67% (OrdemFabricoErros - 41.5% missing FaseOfCulpada)
 */

import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, AlertTriangle, ArrowRight, Loader2, Shield, Info, Ban } from 'lucide-react';
import { factoryApi } from '../../lib/factoryApi';
import { DarkPageLayout } from '../../layouts';
import { 
  DarkCard, 
  DarkStatCard, 
  DarkTable, 
  DarkTableHead, 
  DarkTableBody, 
  DarkTableRow, 
  DarkTableHeader, 
  DarkTableCell, 
  DarkBadge 
} from '../../components/dark';
import { NoDataState } from '../../components/ui';
import { BarChart } from '../../components/charts';

// ═══════════════════════════════════════════════════════════════════════════════
// TRUST BADGE COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function TrustBadge({ confidence, label }: { confidence: number; label?: string }) {
  const getColor = () => {
    if (confidence >= 70) return 'bg-emerald-500/20 text-emerald-400';
    if (confidence >= 50) return 'bg-amber-500/20 text-amber-400';
    if (confidence >= 30) return 'bg-orange-500/20 text-orange-400';
    return 'bg-red-500/20 text-red-400';
  };

  return (
    <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium ${getColor()}`}>
      <Shield size={12} />
      <span>{confidence.toFixed(0)}%</span>
      {label && <span className="opacity-70">({label})</span>}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// DATA SOURCE NOTICE
// ═══════════════════════════════════════════════════════════════════════════════

function DataSourceNotice({ 
  confidence, 
  semanticLabel, 
  warnings 
}: { 
  confidence: number; 
  semanticLabel?: string;
  warnings?: string[];
}) {
  return (
    <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-xl mb-6">
      <div className="flex items-start gap-3">
        <Info className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-1">
            <h4 className="text-sm font-medium text-blue-400">Data Source: Factory Data Product</h4>
            <TrustBadge confidence={confidence} />
          </div>
          {semanticLabel && (
            <p className="text-xs text-slate-400 italic mb-2">{semanticLabel}</p>
          )}
          {warnings && warnings.length > 0 && (
            <ul className="text-xs text-amber-400/80 space-y-1">
              {warnings.map((w, i) => (
                <li key={i} className="flex items-start gap-1">
                  <AlertTriangle size={10} className="mt-0.5 flex-shrink-0" />
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// BLOCKED METRIC NOTICE
// ═══════════════════════════════════════════════════════════════════════════════

function BlockedMetricNotice() {
  return (
    <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
      <div className="flex items-start gap-2">
        <Ban size={16} className="text-red-400 mt-0.5 flex-shrink-0" />
        <div>
          <p className="text-xs text-red-300 font-medium">Some Quality Metrics Unavailable</p>
          <p className="text-xs text-red-400/80 mt-1">
            FPY, Rework Rate, Scrap Rate, and Inspection Pass Rate require additional data 
            (quantity_ok, quantity_rework, quantity_scrap) not available in current data source.
          </p>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function QualityPage() {
  // Fetch quality data from semantic query
  const { 
    data: qualityResponse, 
    isLoading, 
    error,
    refetch 
  } = useQuery({
    queryKey: ['factory', 'semantic', 'quality'],
    queryFn: () => factoryApi.getQuality(),
    staleTime: 60000,
    retry: 2,
  });

  // Process error data by type for the chart
  const errorsByType = useMemo(() => {
    if (!qualityResponse?.data?.by_type) return [];
    return qualityResponse.data.by_type.map((item: any) => ({
      name: item.error_type || 'Unknown',
      count: item.count || 0,
      percentage: item.percentage || 0,
    }));
  }, [qualityResponse]);

  // Process error data by phase
  const errorsByPhase = useMemo(() => {
    if (!qualityResponse?.data?.by_phase) return [];
    return qualityResponse.data.by_phase.slice(0, 10).map((item: any) => ({
      name: item.fase_nome || 'Unknown',
      value: item.count || 0,
    }));
  }, [qualityResponse]);

  // Error state
  if (error) {
    return (
      <DarkPageLayout title="Quality Analysis" icon={<CheckCircle2 size={20} />}>
        <DarkCard className="border-red-500/30 bg-red-500/10">
          <div className="flex items-center gap-3 text-red-400">
            <AlertTriangle size={20} />
            <div>
              <p className="font-medium">Error loading quality data</p>
              <p className="text-sm text-red-400/80">{(error as Error).message}</p>
            </div>
          </div>
          <button 
            onClick={() => refetch()}
            className="mt-4 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded text-sm transition-colors"
          >
            Retry
          </button>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <DarkPageLayout title="Quality Analysis" icon={<CheckCircle2 size={20} />}>
        <DarkCard className="text-center py-12">
          <Loader2 className="animate-spin mx-auto text-teal-400" size={32} />
          <p className="text-slate-400 mt-4">Loading quality data from semantic queries...</p>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  // No data state
  if (!qualityResponse?.data) {
    return (
      <DarkPageLayout title="Quality Analysis" icon={<CheckCircle2 size={20} />}>
        <NoDataState 
          title="No quality data available" 
          message="Quality metrics have not been loaded yet. Run the data ingestion pipeline first." 
        />
      </DarkPageLayout>
    );
  }

  const { data, data_confidence, semantic_label, warnings } = qualityResponse;
  const totalErrors = data.total_errors || 0;

  return (
    <DarkPageLayout
      title="Quality Analysis"
      subtitle="Error analysis from OrdemFabricoErros"
      icon={<CheckCircle2 size={20} />}
    >
      {/* Data Source Notice with Trust */}
      <DataSourceNotice 
        confidence={data_confidence || 67} 
        semanticLabel={semantic_label}
        warnings={warnings}
      />

      {/* Blocked Metrics Notice */}
      <div className="mb-6">
        <BlockedMetricNotice />
      </div>

      {/* Main Stats - Only show what we CAN calculate */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <DarkStatCard
          icon={<AlertTriangle size={20} />}
          iconBg="bg-red-500/20"
          label="Total Errors Registered"
          value={totalErrors.toLocaleString('pt-PT')}
          subtitle={
            <TrustBadge confidence={data_confidence || 67} label="theoretical" />
          }
          size="lg"
        />
        <DarkStatCard
          icon={<CheckCircle2 size={20} />}
          iconBg="bg-amber-500/20"
          label="Error Types"
          value={errorsByType.length.toString()}
          subtitle="Distinct categories"
          size="lg"
        />
        <DarkStatCard
          icon={<CheckCircle2 size={20} />}
          iconBg="bg-purple-500/20"
          label="Phases with Errors"
          value={errorsByPhase.length.toString()}
          subtitle="From OrdemFabricoErros"
          size="lg"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* Errors by Phase Chart */}
        <DarkCard title="Errors by Phase (Top 10)">
          {errorsByPhase.length > 0 ? (
            <div className="h-64 mt-4">
              <BarChart data={errorsByPhase} color="#f59e0b" />
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-slate-500">
              <p>No phase error data available</p>
            </div>
          )}
          <div className="mt-2 flex justify-end">
            <TrustBadge confidence={data_confidence || 67} label="41.5% missing FaseOfCulpada" />
          </div>
        </DarkCard>

        {/* Error Types Distribution Table */}
        <DarkCard title="Error Types Distribution" padding="none">
          {errorsByType.length > 0 ? (
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>Error Type</DarkTableHeader>
                  <DarkTableHeader align="right">Count</DarkTableHeader>
                  <DarkTableHeader align="right">Percentage</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {errorsByType.map((errorType: any) => (
                  <DarkTableRow key={errorType.name}>
                    <DarkTableCell className="text-white font-medium">
                      {errorType.name}
                    </DarkTableCell>
                    <DarkTableCell align="right" className="font-mono">
                      {errorType.count.toLocaleString('pt-PT')}
                    </DarkTableCell>
                    <DarkTableCell align="right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-20 h-2 bg-slate-700 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-teal-500 rounded-full" 
                            style={{ width: `${errorType.percentage}%` }} 
                          />
                        </div>
                        <span className="text-xs text-slate-400 w-12 text-right">
                          {errorType.percentage.toFixed(1)}%
                        </span>
                      </div>
                    </DarkTableCell>
                  </DarkTableRow>
                ))}
              </DarkTableBody>
            </DarkTable>
          ) : (
            <div className="p-8 text-center text-slate-500">
              <AlertTriangle size={24} className="mx-auto mb-2 opacity-50" />
              <p>No error type data available</p>
            </div>
          )}
        </DarkCard>
      </div>

      {/* Data Quality Warning */}
      <DarkCard title="Data Quality Notes" className="mb-6">
        <div className="space-y-3">
          <div className="flex items-center justify-between p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <div className="flex items-center gap-3">
              <AlertTriangle size={18} className="text-amber-400" />
              <div>
                <p className="font-medium text-white">FaseOfCulpada Coverage: 58.5%</p>
                <p className="text-sm text-slate-400">
                  41.5% of errors don't have the responsible phase identified
                </p>
              </div>
            </div>
            <DarkBadge variant="warning">Warning</DarkBadge>
          </div>
          <div className="flex items-center justify-between p-3 rounded-lg bg-slate-800 border border-slate-700">
            <div className="flex items-center gap-3">
              <Info size={18} className="text-slate-400" />
              <div>
                <p className="font-medium text-white">Data Source: OrdemFabricoErros</p>
                <p className="text-sm text-slate-400">
                  {totalErrors.toLocaleString('pt-PT')} error records from Folha_IA_extra.xlsx
                </p>
              </div>
            </div>
            <DarkBadge variant="neutral">Info</DarkBadge>
          </div>
        </div>
      </DarkCard>

      {/* Links */}
      <div className="flex items-center gap-4 pt-4 border-t border-slate-700">
        <p className="text-sm text-slate-400">Related pages:</p>
        <Link 
          to="/profit/oee" 
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/20 text-red-400 font-medium text-sm"
        >
          <Ban size={14} />
          OEE (Blocked)
        </Link>
        <Link 
          to="/profit/kpis" 
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-500/20 hover:bg-teal-500/30 text-teal-400 font-medium text-sm transition-colors"
        >
          All KPIs <ArrowRight size={16} />
        </Link>
        <Link 
          to="/explain" 
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 font-medium text-sm transition-colors"
        >
          Explain Metrics <ArrowRight size={16} />
        </Link>
      </div>
    </DarkPageLayout>
  );
}
