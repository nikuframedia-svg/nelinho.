import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Factory, Clock, AlertTriangle, Users, TrendingUp, Layers, AlertCircle, Info, RefreshCw, ArrowRight, Zap, Inbox, Database, GitBranch } from 'lucide-react';
import { DarkPageLayout } from '../layouts/DarkPageLayout';
import { DarkCard } from '../components/dark/DarkCard';
import { StatusBadge } from '../components/dark/DarkBadge';
import { DarkButton } from '../components/dark/DarkButton';
import { DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell } from '../components/dark/DarkTable';
import { ExplainDrawer } from '../components/explain';
import { LiveActivityFeed } from '../components/activity/LiveActivityFeed';
import { FocusModeModal } from '../components/focus/FocusModeModal';
import { SchemaDriftAlert, BlockedMetricsWall, ModuleErrorBoundary } from '../components/palantir';
import { useSchemaDrift, useLiveDashboardRefresh } from '../hooks';
import { LiveBadge } from '../components/dashboard/LiveBadge';
import { factoryApi } from '../lib/factoryApi';
import { AlertBanner, TrustBadge, SemanticValueCard, ActionCard, QuickNavCard, type ActionItem, type FocusMetric } from './dashboardComponents';

export function Dashboard() {
  const [explainMetricId, setExplainMetricId] = useState<string | null>(null);
  const [focusMetric, setFocusMetric] = useState<FocusMetric | null>(null);

  // PALANTIR: Schema Drift Detection
  const { drifts, handleAction: handleDriftAction } = useSchemaDrift();

  // Fetch WIP data from REAL API (Excel data!)
  const { data: wipData, isLoading: wipLoading, refetch: refetchWip } = useQuery({
    queryKey: ['factory', 'semantic', 'wip'],
    queryFn: () => factoryApi.getWIP(),
    staleTime: 60000,
    retry: false,
  });

  // Fetch Bottlenecks data from REAL API
  const { data: bottlenecksData, isLoading: bottlenecksLoading, refetch: refetchBottlenecks } = useQuery({
    queryKey: ['factory', 'semantic', 'bottlenecks'],
    queryFn: () => factoryApi.getBottlenecks(),
    staleTime: 60000,
    retry: false,
  });

  // Fetch Quality data from REAL API
  const { data: qualityData, isLoading: qualityLoading, refetch: refetchQuality } = useQuery({
    queryKey: ['factory', 'semantic', 'quality'],
    queryFn: () => factoryApi.getQuality(),
    staleTime: 60000,
    retry: false,
  });

  // Fetch Skills Risk data from REAL API
  const { data: skillsData, isLoading: skillsLoading, refetch: refetchSkills } = useQuery({
    queryKey: ['factory', 'semantic', 'skills-risk'],
    queryFn: () => factoryApi.getSkillsRisk(),
    staleTime: 60000,
    retry: false,
  });

  const handleRefreshAll = () => {
    refetchWip();
    refetchBottlenecks();
    refetchQuality();
    refetchSkills();
  };

  // Sprint D.3 — plug the shared SSE stream into the dashboard. Any
  // relevant event (schedule / MRP / decision / stock / rework …)
  // triggers a debounced refetch; the returned `lastEventAt` feeds the
  // `<LiveBadge />` so the operator sees the stream breathing.
  const liveState = useLiveDashboardRefresh(handleRefreshAll);

  const isLoading = wipLoading || bottlenecksLoading || qualityLoading || skillsLoading;

  // Calculate critical/high counts for alert banner - using REAL data
  const criticalCount = (skillsData?.data?.critical_phases ?? 0) + 
    (bottlenecksData?.data?.bottlenecks?.filter((b: { is_critical?: boolean }) => b.is_critical)?.length ?? 0);
  const highCount = (skillsData?.data?.high_risk_phases ?? 0);

  // Build action items for "O Que Fazer Hoje" - using REAL data
  const actionItems: ActionItem[] = [];

  // Add bottleneck actions from REAL bottleneck data
  if ((bottlenecksData?.data?.bottlenecks?.length ?? 0) > 0 && bottlenecksData) {
    const topBottleneck = bottlenecksData.data.bottlenecks[0];
    if (topBottleneck.is_critical || topBottleneck.bottleneck_score > 50) {
      actionItems.push({
        id: 'bottleneck-1',
        type: 'bottleneck',
        severity: topBottleneck.is_critical ? 'critical' : 'high',
        title: `Gargalo Crítico: ${topBottleneck.fase_nome || topBottleneck.fase_id}`,
        description: `Backlog de ${topBottleneck.backlog_hours?.toFixed(0) || '?'} horas`,
        impact: 'Reduzir backlog em ~20%',
        trustIndex: bottlenecksData.data_confidence ?? 58,
        metricId: 'bottleneck_ranking',
        actionType: 'capacity_adjustment',
      });
    }
  }

  // Add quality actions from REAL quality data
  if (qualityData && (qualityData?.data?.total_errors ?? 0) > 10) {
    const topError = qualityData.data.by_type?.[0] || qualityData.data.top_items?.[0];
    actionItems.push({
      id: 'quality-1',
      type: 'quality',
      severity: qualityData.data.total_errors > 50 ? 'high' : 'medium',
      title: `${qualityData.data.total_errors} Erros de Qualidade`,
      description: topError ? `Top erro: ${topError.error_type || topError.descricao || 'N/A'}` : 'Erros registados no sistema',
      impact: 'Reduzir taxa de retrabalho',
      trustIndex: qualityData.data_confidence ?? 67,
      metricId: 'quality_error_count',
      actionType: 'quality_improvement',
    });
  }

  // Add skills risk actions from REAL skills data
  const criticalPhases = skillsData?.data?.critical_phases ?? skillsData?.data?.phases_at_risk ?? 0;
  if (criticalPhases > 0) {
    actionItems.push({
      id: 'skills-1',
      type: 'skills',
      severity: 'critical',
      title: `${criticalPhases} Fases com Risco de Competências`,
      description: 'Risco de paragem de produção por falta de funcionários aptos',
      impact: 'Garantir continuidade',
      trustIndex: skillsData?.data_confidence ?? 55,
      metricId: 'skills_risk_by_phase',
      actionType: 'skills_training',
    });
  }

  return (
    <ModuleErrorBoundary moduleName="Dashboard">
    <DarkPageLayout
      title="Dashboard"
      subtitle="Superfície de Decisão — Visão geral baseada em dados semânticos"
      actions={
        <div className="flex items-center gap-2">
          <LiveBadge lastEventAt={liveState.lastEventAt} />
          <DarkButton
            variant="secondary"
            size="sm"
            onClick={handleRefreshAll}
            disabled={isLoading}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Atualizar
          </DarkButton>
        </div>
      }
    >
      {/* Alert Banner */}
      <AlertBanner criticalCount={criticalCount} highCount={highCount} />

      {/* PALANTIR: Schema Drift Alert - Floating notification for data changes */}
      {drifts.length > 0 && (
        <SchemaDriftAlert 
          drifts={drifts} 
          onAction={handleDriftAction}
        />
      )}

      {/* Data Source Notice */}
      <div className="mb-6 p-4 bg-accent/10 border border-accent/20 rounded-xl">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-accent mt-0.5 flex-shrink-0" />
          <div>
            <h4 className="text-sm font-medium text-accent mb-1">Fonte de Dados: Factory Data Product</h4>
            <p className="text-xs text-slate-400">
              Todos os valores são calculados a partir dos dados CURATED. 
              Cada métrica inclui um índice de confiança baseado na cobertura e qualidade dos dados.
              <strong className="text-slate-300"> Clique em qualquer métrica para explicação detalhada.</strong>
            </p>
          </div>
        </div>
      </div>

      {/* Main Stats Grid - REAL DATA from Excel! */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <SemanticValueCard
          title="Ordens Abertas"
          metricId="wip_open_orders"
          value={wipData?.data?.open_orders ?? null}
          icon={Factory}
          confidence={wipData?.data_confidence ?? 75}
          semanticLabel={wipData?.semantic_label ?? 'WIP teórico'}
          onExplain={setExplainMetricId}
        />

        <SemanticValueCard
          title="Fases Abertas (Produção)"
          metricId="wip_open_phases"
          value={wipData?.data?.phases_total ?? wipData?.data?.open_phases ?? null}
          icon={Layers}
          confidence={wipData?.data_confidence ?? 75}
          semanticLabel={wipData?.semantic_label ?? 'WIP teórico'}
          onExplain={setExplainMetricId}
        />

        <SemanticValueCard
          title="Horas Previstas (Backlog)"
          metricId="backlog_theoretical_hours"
          value={wipData?.data?.total_hours_pending ? Math.round(wipData.data.total_hours_pending) : null}
          unit="h"
          icon={Clock}
          confidence={wipData?.data_confidence ?? 75}
          semanticLabel={wipData?.semantic_label ?? 'WIP teórico'}
          onExplain={setExplainMetricId}
        />

        <SemanticValueCard
          title="OEE"
          metricId="oee_real"
          value={null}
          icon={TrendingUp}
          confidence={0}
          semanticLabel=""
          isBlocked={true}
          blockedReason="OEE requer dados de paragens de máquina e tempos de ciclo que não existem."
          onExplain={setExplainMetricId}
          canSimulate={false}
        />
      </div>

      {/* "O Que Fazer Hoje" Section */}
      {actionItems.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5 text-accent" />
              <h3 className="text-lg font-semibold text-white">O Que Fazer Hoje</h3>
              <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">
                {actionItems.length} acções
              </span>
            </div>
            <Link 
              to="/ops-inbox" 
              className="text-xs text-accent hover:text-accent-light flex items-center gap-1 transition-colors"
            >
              Ver todas <ArrowRight size={12} />
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {actionItems.slice(0, 3).map((action) => (
              <ActionCard 
                key={action.id} 
                action={action} 
                onExplain={setExplainMetricId}
              />
            ))}
          </div>
        </div>
      )}

      {/* Secondary Stats - REAL DATA */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <SemanticValueCard
          title="Erros Registados"
          metricId="quality_error_count"
          value={qualityData?.data?.total_errors ?? null}
          icon={AlertTriangle}
          confidence={qualityData?.data_confidence ?? 75}
          semanticLabel={qualityData?.semantic_label ?? 'Análise de qualidade'}
          onExplain={setExplainMetricId}
        />

        <SemanticValueCard
          title="Fases em Risco (Skills)"
          metricId="skills_risk_by_phase"
          value={skillsData?.data?.phases_count ?? skillsData?.data?.phases_at_risk ?? null}
          icon={Users}
          confidence={skillsData?.data_confidence ?? 75}
          semanticLabel={skillsData?.semantic_label ?? 'Risco de competências'}
          onExplain={setExplainMetricId}
        />

        <SemanticValueCard
          title="Bottlenecks"
          metricId="bottleneck_ranking"
          value={bottlenecksData?.data?.bottlenecks?.length ?? null}
          icon={AlertCircle}
          confidence={bottlenecksData?.data_confidence ?? 75}
          semanticLabel={bottlenecksData?.semantic_label ?? 'Gargalos teóricos'}
          onExplain={setExplainMetricId}
        />
      </div>

      {/* Two Column Layout - Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Bottlenecks Table */}
        <DarkCard
          title="Top Bottlenecks"
          subtitle="Fases com maior backlog teórico"
          icon={<AlertCircle className="w-5 h-5" />}
          footer={
            bottlenecksData && (
              <div className="flex items-center gap-2">
                <TrustBadge value={bottlenecksData.data_confidence} />
                <span className="text-xs text-slate-500">{bottlenecksData.semantic_label}</span>
              </div>
            )
          }
        >
          {bottlenecksLoading ? (
            <div className="animate-pulse space-y-2">
              {[1,2,3,4,5].map(i => (
                <div key={i} className="h-10 bg-slate-700/50 rounded" />
              ))}
            </div>
          ) : (bottlenecksData?.data?.bottlenecks?.length ?? 0) > 0 && bottlenecksData ? (
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>#</DarkTableHeader>
                  <DarkTableHeader>Fase</DarkTableHeader>
                  <DarkTableHeader align="right">Backlog</DarkTableHeader>
                  <DarkTableHeader align="right">Status</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {bottlenecksData.data.bottlenecks.slice(0, 5).map((b: { fase_id?: string; fase_nome?: string; backlog_hours?: number; backlog_days?: number; bottleneck_score?: number; is_critical?: boolean }, idx: number) => (
                  <DarkTableRow key={b.fase_id || idx}>
                    <DarkTableCell>
                      <span className="text-slate-500">{idx + 1}</span>
                    </DarkTableCell>
                    <DarkTableCell>
                      <span className="font-medium text-white">{b.fase_nome || b.fase_id}</span>
                    </DarkTableCell>
                    <DarkTableCell align="right">
                      <span className="font-mono">{b.backlog_hours?.toFixed(0) ?? b.backlog_days?.toFixed(1) ?? '—'}</span>
                      <span className="text-slate-500 text-xs ml-1">{b.backlog_hours !== undefined ? 'h' : 'dias'}</span>
                    </DarkTableCell>
                    <DarkTableCell align="right">
                      {b.is_critical || (b.bottleneck_score && b.bottleneck_score > 70) ? (
                        <StatusBadge status="error" />
                      ) : (
                        <StatusBadge status="completed" />
                      )}
                    </DarkTableCell>
                  </DarkTableRow>
                ))}
              </DarkTableBody>
            </DarkTable>
          ) : (
            <div className="text-center py-8 text-slate-500">
              <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>Sem dados de bottlenecks</p>
              <p className="text-xs mt-1">Os dados serão carregados da API</p>
            </div>
          )}
        </DarkCard>

        {/* Quality Issues Table */}
        <DarkCard
          title="Top Erros de Qualidade"
          subtitle="Erros mais frequentes registados"
          icon={<AlertTriangle className="w-5 h-5" />}
          footer={
            qualityData && (
              <div className="flex items-center gap-2">
                <TrustBadge value={qualityData.data_confidence} />
                <span className="text-xs text-slate-500">{qualityData.semantic_label}</span>
              </div>
            )
          }
        >
          {qualityLoading ? (
            <div className="animate-pulse space-y-2">
              {[1,2,3,4,5].map(i => (
                <div key={i} className="h-10 bg-slate-700/50 rounded" />
              ))}
            </div>
          ) : qualityData && ((qualityData?.data?.by_type?.length ?? 0) > 0 || (qualityData?.data?.top_items?.length ?? 0) > 0) ? (
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>Erro</DarkTableHeader>
                  <DarkTableHeader align="right">Ocorrências</DarkTableHeader>
                  <DarkTableHeader align="right">%</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {(qualityData.data.by_type || qualityData.data.top_items || []).slice(0, 5).map((item: { error_type?: string; descricao?: string; count: number; percentage?: number; fase_culpada_pct?: number }, idx: number) => (
                  <DarkTableRow key={idx}>
                    <DarkTableCell>
                      <span className="font-medium text-white truncate block max-w-[200px]" title={item.error_type || item.descricao}>
                        {item.error_type || item.descricao || 'N/A'}
                      </span>
                    </DarkTableCell>
                    <DarkTableCell align="right">
                      <span className="font-mono">{item.count?.toLocaleString('pt-PT')}</span>
                    </DarkTableCell>
                    <DarkTableCell align="right">
                      <span className="font-mono">{(item.percentage ?? item.fase_culpada_pct)?.toFixed(1) ?? '—'}%</span>
                    </DarkTableCell>
                  </DarkTableRow>
                ))}
              </DarkTableBody>
            </DarkTable>
          ) : (
            <div className="text-center py-8 text-slate-500">
              <AlertTriangle className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>Sem dados de qualidade</p>
              <p className="text-xs mt-1">Os dados serão carregados da API</p>
            </div>
          )}
        </DarkCard>
      </div>

      {/* PALANTIR: Blocked Metrics Preview */}
      <div className="mb-6">
        <BlockedMetricsWall compact maxItems={4} />
      </div>

      {/* Quick Navigation + Live Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 border-t border-slate-700/50 pt-6">
        {/* Quick Navigation */}
        <div className="lg:col-span-2">
          <h3 className="text-sm font-medium text-slate-400 mb-4">Navegação Rápida</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <QuickNavCard
              title="Twin Sandbox"
              description="Simular cenários what-if"
              icon={GitBranch}
              to="/twin"
              color="purple"
            />
            <QuickNavCard
              title="Data Quality Center"
              description="Trust index e quarentena"
              icon={Database}
              to="/admin/data-quality"
              color="amber"
            />
            <QuickNavCard
              title="Ops Inbox"
              description="Fila de excepções"
              icon={Inbox}
              to="/inbox"
              color="danger"
            />
          </div>
        </div>

        {/* Live Activity Feed */}
        <div className="lg:col-span-1">
          <LiveActivityFeed 
            maxItems={5}
            showHeader={true}
            compact={false}
          />
        </div>
      </div>

      {/* Explain Drawer */}
      <ExplainDrawer 
        open={!!explainMetricId} 
        onClose={() => setExplainMetricId(null)} 
        metricId={explainMetricId || ''} 
      />

      {/* Focus Mode Modal */}
      <FocusModeModal
        isOpen={!!focusMetric}
        onClose={() => setFocusMetric(null)}
        metric={focusMetric ? {
          id: focusMetric.id,
          label: focusMetric.label,
          value: focusMetric.value,
          unit: focusMetric.unit,
          trustIndex: focusMetric.trustIndex,
          coverage: focusMetric.coverage,
          semanticLabel: focusMetric.semanticLabel,
          trend: focusMetric.trend,
          sparklineData: focusMetric.sparklineData,
        } : null}
        onExplain={(metricId) => {
          setFocusMetric(null);
          setExplainMetricId(metricId);
        }}
        onSimulate={(_metricId) => {
          setFocusMetric(null);
          // Navigate to Twin will be handled by the modal
        }}
      />
    </DarkPageLayout>
    </ModuleErrorBoundary>
  );
}
