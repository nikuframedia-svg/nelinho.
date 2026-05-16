/**
 * Workforce Operations Dashboard
 * ================================
 * 
 * The main workforce operations dashboard - "Decision OS for Workforce"
 * 
 * This is the killer feature that transforms workforce data into actionable insights:
 * - Risk Surface visualization
 * - SPOF alerts
 * - Dependency graph
 * - Simulation capabilities
 * - Training recommendations
 * 
 * Data Sources:
 * - FuncionariosFasesAptos (902 records)
 * - Funcionarios (301 employees)
 * - Fases (71 phases)
 * - FasesOrdemFabrico (backlog data)
 */

import { useState, useMemo, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, Link } from 'react-router-dom';
import {
  Users,
  AlertTriangle,
  Network,
  Play,
  GraduationCap,
  Shield,
  Info,
  TrendingDown,
  ArrowRight,
  RefreshCw,
  Zap,
  BarChart3,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkButton, DarkStatCard } from '../../components/dark';
import { TrustBadge } from '../../components/capabilities/TrustGate';
import { factoryApi } from '../../lib/factoryApi';
import { workforceApi } from '../../lib/workforceApi';

// PALANTIR-LEVEL COMPONENTS
import { ModuleErrorBoundary, ScenarioTemplatesGallery } from '../../components/palantir';
import {
  RiskHeatmap,
  SPOFAlertPanel,
  DependencyGraph,
  WorkforceSimulator,
  CascadeImpactView,
  ScenarioComparisonMatrix,
} from '../../components/workforce';
import type {
  PhaseRisk,
  SPOFAlert,
  TrainingRecommendation,
  CascadeImpact,
  WorkforceDelta,
  SimulationResult,
  GraphNode,
  GraphEdge,
} from '../../components/workforce';

// Type for dependency graph data
interface DependencyGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata: {
    totalEmployees: number;
    totalPhases: number;
    totalLinks: number;
    spofNodes: string[];
    criticalPaths: string[][];
  };
}

// ═══════════════════════════════════════════════════════════════════════════════
// DATA TRANSFORMERS - Convert API data to component format
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Transform skills risk API data to PhaseRisk format for components
 * Now using REAL DATA from the ingested Excel file!
 */
function transformApiToPhaseRisks(apiData: any): PhaseRisk[] {
  // If we have phases from the API, transform them
  if (apiData?.data?.phases_with_risk) {
    return apiData.data.phases_with_risk.map((p: any) => {
      const aptosActive = p.active_workers || p.aptos_count || 1;
      const backlog = p.backlog_hours || 0;
      const riskScore = p.risk_score || Math.max(0, Math.min(100, 100 - (aptosActive * 15) + (backlog / 50)));
      const riskLevel: PhaseRisk['riskLevel'] = riskScore >= 80 ? 'critical' : riskScore >= 60 ? 'high' : riskScore >= 40 ? 'medium' : riskScore >= 20 ? 'low' : 'ok';

      return {
        phaseId: String(p.fase_id || p.id),
        phaseName: p.fase_nome || p.name || `Fase ${p.fase_id}`,
        aptosCount: p.aptos_count || aptosActive,
        aptosActive,
        backlogHours: backlog,
        backlogDays: backlog / 8,
        riskScore,
        riskLevel,
        isSPOF: aptosActive <= 1,
        employees: [],
        ordersAtRisk: Math.floor(backlog / 10),
      };
    });
  }
  
  // ZERO MOCKS: when the API returns only a summary (counts, no per-
  // phase telemetry), we do NOT synthesize phases via Math.random().
  // Inventing aptos/backlog values would render fake "risk scores"
  // the operator would treat as real. Return empty so the consumer
  // shows the "telemetry incomplete" banner.
  return [];
}

/**
 * Generate SPOF alerts from phase risks.
 *
 * ZERO MOCKS: the alert carries only real phase-level telemetry (apt-worker
 * count, backlog, orders). Employee identity is intentionally NOT fabricated
 * from an index — `/v1/factory/skills-risk` does not return per-phase
 * employees, so `employeeName`/`employeeId`/`estimatedDailyCost` stay
 * undefined and the panel degrades to a phase-level view.
 */
function generateSPOFAlertsFromRisks(phaseRisks: PhaseRisk[]): SPOFAlert[] {
  return phaseRisks
    .filter(p => p.isSPOF || p.aptosActive <= 2)
    .slice(0, 5)
    .map(p => {
      const realEmployee = p.employees[0];
      return {
        phaseId: p.phaseId,
        phaseName: p.phaseName,
        aptosActive: p.aptosActive,
        backlogHours: p.backlogHours,
        ordersAffected: p.ordersAtRisk,
        riskLevel: p.riskLevel === 'critical' ? 'critical' : ('high' as const),
        ...(realEmployee
          ? { employeeId: realEmployee.id, employeeName: realEmployee.name }
          : {}),
      };
    });
}

/**
 * Generate the dependency graph from phase risk data.
 *
 * ZERO MOCKS: only real phase nodes are emitted. Employee nodes and
 * employee→phase aptitude edges are NOT synthesized from an index —
 * `/v1/factory/skills-risk` carries no per-phase employee identity, so the
 * graph ships with empty edges and `DependencyGraph` renders an explicit
 * "telemetria incompleta" empty state.
 */
function generateDependencyGraphFromData(phaseRisks: PhaseRisk[], employeesCount: number): DependencyGraphData {
  const nodes: GraphNode[] = phaseRisks.map(p => ({
    id: `phase-${p.phaseId}`,
    type: 'phase' as const,
    label: p.phaseName,
    data: { id: p.phaseId, name: p.phaseName, description: '' },
    riskLevel: p.riskLevel,
    size: 25,
  }));

  return {
    nodes,
    edges: [],
    metadata: {
      totalEmployees: employeesCount,
      totalPhases: phaseRisks.length,
      totalLinks: 0,
      spofNodes: phaseRisks.filter(p => p.isSPOF).map(p => `phase-${p.phaseId}`),
      criticalPaths: [],
    },
  };
}

/**
 * Generate training recommendations from phase risks.
 *
 * ZERO MOCKS: a training recommendation names *who* to cross-train. Phase
 * risk data carries no employee identity, so we cannot honestly produce one
 * from an index — return empty and let the consumer show an explicit empty
 * state. Recommendations with real employees come from
 * `workforceApi.getTrainingRecommendations()` once that telemetry exists.
 */
function generateTrainingRecommendationsFromRisks(_phaseRisks: PhaseRisk[]): TrainingRecommendation[] {
  return [];
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function WorkforceDashboard() {
  const navigate = useNavigate();
  const [selectedPhaseId, setSelectedPhaseId] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'heatmap' | 'graph' | 'scenarios'>('heatmap');
  const [showSimulator, setShowSimulator] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);

  // Fetch skills risk data from API
  const { data: skillsRiskData, isLoading: isLoadingSkillsRisk } = useQuery({
    queryKey: ['skills-risk'],
    queryFn: () => factoryApi.getSkillsRisk(),
  });

  // Fetch scenario comparison from API
  const { data: scenarioComparison, isLoading: isLoadingScenarios } = useQuery({
    queryKey: ['workforce-scenarios'],
    queryFn: () => workforceApi.compareScenarios(['baseline', 'train-2', 'train-4', 'hire-1']),
    enabled: activeView === 'scenarios',
  });

  // Transform REAL API data to component formats
  const phaseRisks = useMemo(() => transformApiToPhaseRisks(skillsRiskData), [skillsRiskData]);
  const spofAlerts = useMemo(() => generateSPOFAlertsFromRisks(phaseRisks), [phaseRisks]);
  const employeesCount = skillsRiskData?.data?.employees_count || skillsRiskData?.data?.total_employees || 301;
  const dependencyGraph = useMemo(() => generateDependencyGraphFromData(phaseRisks, employeesCount), [phaseRisks, employeesCount]);
  const trainingRecommendations = useMemo(() => generateTrainingRecommendationsFromRisks(phaseRisks), [phaseRisks]);

  // Sprint Q.12 — Detect synthetic fallback (sem `phases_with_risk`
  // estamos a gerar fases com Math.random()). Sinalizar ao operador
  // em vez de apresentar dados inventados como reais.
  const isSyntheticData = useMemo(() => {
    if (isLoadingSkillsRisk) return false;
    return !skillsRiskData?.data?.phases_with_risk && phaseRisks.length > 0;
  }, [skillsRiskData, phaseRisks.length, isLoadingSkillsRisk]);

  // Calculate summary stats
  const summary = useMemo(() => {
    const totalPhases = phaseRisks.length;
    const phasesAtRisk = phaseRisks.filter(p => p.riskLevel === 'critical' || p.riskLevel === 'high').length;
    const spofCount = phaseRisks.filter(p => p.isSPOF).length;
    const avgRiskScore = phaseRisks.reduce((sum, p) => sum + p.riskScore, 0) / totalPhases;
    const totalBacklogAtRisk = phaseRisks.filter(p => p.isSPOF).reduce((sum, p) => sum + p.backlogHours, 0);
    
    return {
      totalPhases,
      phasesAtRisk,
      spofCount,
      avgRiskScore,
      totalBacklogAtRisk,
    };
  }, [phaseRisks]);

  // Cascade impact for selected phase
  const cascadeImpact = useMemo((): CascadeImpact | null => {
    if (!selectedPhaseId) return null;
    const phase = phaseRisks.find(p => p.phaseId === selectedPhaseId);
    if (!phase) return null;

    return {
      sourcePhase: phase.phaseId,
      sourcePhaseName: phase.phaseName,
      triggerEmployee: phase.employees[0]?.id,
      triggerEmployeeName: phase.employees[0]?.name,
      levels: [
        {
          level: 1,
          type: 'workforce',
          title: 'WORKFORCE',
          items: [
            { label: 'Funcionários aptos activos', value: phase.aptosActive, severity: phase.isSPOF ? 'critical' : undefined },
            { label: 'Se indisponível', value: 'FASE PARA', severity: 'critical' },
          ],
        },
        {
          level: 2,
          type: 'production',
          title: 'PRODUÇÃO',
          items: [
            { label: 'Backlog teórico', value: `${phase.backlogHours}h` },
            { label: 'Ordens em aberto', value: phase.ordersAtRisk },
            { label: 'Ordens críticas (>30d)', value: Math.floor(phase.ordersAtRisk * 0.25), severity: 'high' },
          ],
        },
        {
          level: 3,
          type: 'downstream',
          title: 'FASES A JUSANTE',
          items: [
            { label: 'Acabamento bloqueado', value: `+${Math.floor(phase.ordersAtRisk * 1.2)} ordens` },
            { label: 'Pintura bloqueada', value: `+${Math.floor(phase.ordersAtRisk * 0.8)} ordens` },
            { label: 'Total downstream', value: `${Math.floor(phase.ordersAtRisk * 3)} ordens em risco`, severity: 'high' },
          ],
        },
        {
          level: 4,
          type: 'economic',
          title: 'IMPACTO ECONÓMICO (TEÓRICO)',
          items: [
            { label: 'Custo backlog em risco', value: `€${(phase.backlogHours * 5.54).toFixed(0)}` },
            { label: 'Custo downstream', value: `€${(phase.backlogHours * 5.54 * 2).toFixed(0)}` },
            { label: '⚠️ NÃO INCLUI', value: 'custo real, penalidades, cliente' },
          ],
        },
      ],
      totalOrdersAffected: phase.ordersAtRisk * 3,
      totalBacklogAffected: phase.backlogHours,
      estimatedDailyCost: phase.backlogHours * 5.54 / 8,
      trustIndex: 55,
      warnings: [
        'Não inclui ausências planeadas (férias, formação)',
        'Não considera flexibilidade de turnos',
        'Custos são teóricos (€5.54/h mediana)',
      ],
    };
  }, [selectedPhaseId, phaseRisks]);

  // Simulation handler
  const handleSimulate = useCallback(async (deltas: WorkforceDelta[]): Promise<SimulationResult> => {
    // Simulate the impact of deltas
    const trainingCount = deltas.filter(d => d.type === 'add_training').length;
    
    return {
      scenarioId: `scenario-${Date.now()}`,
      scenarioName: `Cenário ${new Date().toLocaleDateString()}`,
      baseline: {
        spofCount: summary.spofCount,
        avgRiskScore: summary.avgRiskScore,
        totalBacklogAtRisk: summary.totalBacklogAtRisk,
        phasesAtRisk: summary.phasesAtRisk,
      },
      simulated: {
        spofCount: Math.max(0, summary.spofCount - trainingCount),
        avgRiskScore: Math.max(0, summary.avgRiskScore - trainingCount * 15),
        totalBacklogAtRisk: Math.max(0, summary.totalBacklogAtRisk - trainingCount * 50),
        phasesAtRisk: Math.max(0, summary.phasesAtRisk - Math.floor(trainingCount / 2)),
      },
      deltas,
      impact: {
        spofChange: -trainingCount,
        riskChange: -trainingCount * 15,
        backlogChange: -trainingCount * 50,
        phasesChange: -Math.floor(trainingCount / 2),
      },
      estimatedCost: {
        trainingHours: trainingCount * 40,
        costPerHour: 5.54,
        totalCost: trainingCount * 40 * 5.54,
      },
      recommendations: [
        'Cenário aprovado para reduzir risco operacional',
        `${trainingCount} SPOF(s) seriam eliminados`,
      ],
      trustIndex: 55,
    };
  }, [summary]);

  const handlePhaseClick = (phaseId: string) => {
    setSelectedPhaseId(phaseId === selectedPhaseId ? null : phaseId);
  };

  const handleSimulatePhase = (phaseId: string) => {
    setSelectedPhaseId(phaseId);
    setShowSimulator(true);
  };

  // Trust index from API or default
  const trustIndex = skillsRiskData?.data_confidence ?? 55;

  return (
    <ModuleErrorBoundary moduleName="Workforce Operations">
    <DarkPageLayout
      title="Workforce Operations"
      subtitle="Decision Operating System para Gestão de Competências"
      icon={<Users size={20} />}
      actions={
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 rounded-lg">
            <Shield size={14} className={trustIndex >= 60 ? 'text-emerald-400' : 'text-amber-400'} />
            <span className="text-sm text-slate-400">Trust Global: <span className="text-white font-medium">{trustIndex}%</span></span>
          </div>
          <DarkButton variant="secondary" icon={<RefreshCw size={16} />} size="sm">
            Actualizar
          </DarkButton>
        </div>
      }
    >
      {/* Synthetic-data banner — só aparece quando o endpoint não retorna `phases_with_risk` */}
      {isSyntheticData && (
        <div className="mb-6 bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-amber-400 text-sm mb-1">
                Dados sintéticos — API workforce não retornou risco real
              </h3>
              <p className="text-xs text-slate-400">
                As fases mostradas abaixo são geradas a partir do total de skills/fases conhecido,
                mas os <strong>nomes, números e níveis de risco são placeholder</strong>.
                Ingestir o Excel NELO ou verificar o endpoint <code className="bg-slate-800 px-1 rounded">/factory/skills-risk</code>.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <DarkStatCard
          icon={<Users size={18} />}
          label="Fases Totais"
          value={summary.totalPhases}
          size="sm"
        />
        <DarkStatCard
          icon={<AlertTriangle size={18} />}
          iconBg="bg-red-500/20"
          label="Fases em Risco"
          value={summary.phasesAtRisk}
          size="sm"
        />
        <DarkStatCard
          icon={<Zap size={18} />}
          iconBg="bg-orange-500/20"
          label="SPOFs Críticos"
          value={summary.spofCount}
          size="sm"
        />
        <DarkStatCard
          icon={<BarChart3 size={18} />}
          iconBg="bg-amber-500/20"
          label="Risk Score Médio"
          value={`${summary.avgRiskScore.toFixed(0)}%`}
          size="sm"
        />
        <DarkStatCard
          icon={<TrendingDown size={18} />}
          iconBg="bg-purple-500/20"
          label="Backlog em Risco"
          value={`${summary.totalBacklogAtRisk}h`}
          size="sm"
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-3 gap-6 mb-6">
        {/* Left Column - Visualization */}
        <div className="col-span-2 space-y-6">
          {/* View Toggle */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 bg-slate-800 rounded-lg p-1">
              <button
                onClick={() => setActiveView('heatmap')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeView === 'heatmap'
                    ? 'bg-slate-700 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <BarChart3 size={14} className="inline mr-2" />
                Superfície de Risco
              </button>
              <button
                onClick={() => setActiveView('graph')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeView === 'graph'
                    ? 'bg-slate-700 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Network size={14} className="inline mr-2" />
                Grafo de Dependências
              </button>
              <button
                onClick={() => setActiveView('scenarios')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeView === 'scenarios'
                    ? 'bg-slate-700 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <BarChart3 size={14} className="inline mr-2" />
                Comparar Cenários
              </button>
            </div>
            <Link
              to="/workforce/simulator"
              className="flex items-center gap-2 text-sm text-accent hover:text-accent-light transition-colors"
            >
              <Play size={14} />
              Abrir Simulador
              <ArrowRight size={12} />
            </Link>
          </div>

          {/* Visualization */}
          {activeView === 'heatmap' && (
            <RiskHeatmap
              data={phaseRisks}
              onPhaseClick={handlePhaseClick}
              onSimulate={handleSimulatePhase}
              trustIndex={trustIndex}
              isLoading={isLoadingSkillsRisk}
            />
          )}
          {activeView === 'graph' && (
            <DependencyGraph
              graph={dependencyGraph}
              onNodeClick={(nodeId, nodeType) => {
                if (nodeType === 'phase') handlePhaseClick(nodeId);
              }}
              onSimulate={handleSimulatePhase}
              highlightSpof={true}
              trustIndex={trustIndex}
              isLoading={isLoadingSkillsRisk}
            />
          )}
          {activeView === 'scenarios' && (
            <ScenarioComparisonMatrix
              comparison={scenarioComparison || null}
              isLoading={isLoadingScenarios}
              onExportPDF={() => {
                // TODO: Implement PDF export
                console.log('Export PDF');
              }}
              onApproveScenario={(scenarioId) => {
                console.log('Approve scenario:', scenarioId);
                navigate('/twin');
              }}
            />
          )}

          {/* Cascade Impact */}
          {selectedPhaseId && (
            <CascadeImpactView
              impact={cascadeImpact}
              onSimulateMitigation={() => setShowSimulator(true)}
            />
          )}
        </div>

        {/* Right Column - Alerts & Recommendations */}
        <div className="space-y-6">
          {/* SPOF Alerts */}
          <SPOFAlertPanel
            alerts={spofAlerts}
            onSimulate={handleSimulatePhase}
            onViewDetails={handlePhaseClick}
            trustIndex={trustIndex}
            compact
          />

          {/* Training Recommendations Preview */}
          <DarkCard 
            title="🎓 Recomendações de Formação"
            subtitle="Ordenadas por impacto"
            action={
              <Link to="/workforce/training" className="text-xs text-accent hover:text-accent-light flex items-center gap-1">
                Ver todas <ArrowRight size={10} />
              </Link>
            }
          >
            <div className="space-y-3">
              {trainingRecommendations.length === 0 && (
                <div className="p-4 bg-slate-800/50 rounded-lg border border-slate-700/50 text-center">
                  <p className="text-sm text-slate-300 font-medium mb-1">
                    Sem recomendações de formação
                  </p>
                  <p className="text-xs text-slate-500">
                    Requer telemetria de aptidões por funcionário. Ingerir o Excel
                    NELO para gerar recomendações nominais.
                  </p>
                </div>
              )}
              {trainingRecommendations.slice(0, 2).map((rec, index) => (
                <div
                  key={rec.id}
                  className="p-3 bg-slate-800/50 rounded-lg border border-slate-700/50 hover:border-slate-600 transition-colors cursor-pointer"
                  onClick={() => handleSimulatePhase(rec.targetPhase.id)}
                >
                  <div className="flex items-start justify-between mb-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      rec.priority === 'critical' ? 'bg-red-500/20 text-red-400' : 'bg-orange-500/20 text-orange-400'
                    }`}>
                      #{index + 1} {rec.priority.toUpperCase()}
                    </span>
                    <TrustBadge trustIndex={rec.trustIndex} size="sm" showLabel={false} />
                  </div>
                  <p className="text-sm text-white mb-1">
                    <span className="text-cyan-400">{rec.employee.name}</span>
                    {' → '}
                    <span className="text-indigo-400">{rec.targetPhase.name}</span>
                  </p>
                  <p className="text-xs text-slate-400">
                    {rec.expectedImpact.spofEliminated ? '✓ Elimina SPOF' : `↓ -${rec.expectedImpact.riskReduction}% risco`}
                    {' • '}
                    ~€{rec.estimatedCost.cost.toFixed(0)}
                  </p>
                </div>
              ))}
            </div>
          </DarkCard>

          {/* Quick Actions */}
          <DarkCard title="⚡ Acções Rápidas">
            <div className="space-y-2">
              <button
                onClick={() => setShowSimulator(true)}
                className="w-full flex items-center gap-3 p-3 bg-gradient-to-r from-purple-500/20 to-pink-500/20 hover:from-purple-500/30 hover:to-pink-500/30 border border-purple-500/30 rounded-lg text-left transition-colors"
              >
                <Play size={18} className="text-purple-400" />
                <div>
                  <p className="text-sm font-medium text-white">Simular Cenário</p>
                  <p className="text-xs text-slate-400">Cross-training, contratação, ausência</p>
                </div>
              </button>
              <Link
                to="/workforce/training"
                className="w-full flex items-center gap-3 p-3 bg-slate-800/50 hover:bg-slate-800 border border-slate-700 rounded-lg text-left transition-colors"
              >
                <GraduationCap size={18} className="text-emerald-400" />
                <div>
                  <p className="text-sm font-medium text-white">Plano de Formação</p>
                  <p className="text-xs text-slate-400">Ver todas as recomendações</p>
                </div>
              </Link>
              <Link
                to="/explain/skills_risk_score"
                className="w-full flex items-center gap-3 p-3 bg-slate-800/50 hover:bg-slate-800 border border-slate-700 rounded-lg text-left transition-colors"
              >
                <Info size={18} className="text-amber-400" />
                <div>
                  <p className="text-sm font-medium text-white">Explicar Métricas</p>
                  <p className="text-xs text-slate-400">Como são calculados os riscos</p>
                </div>
              </Link>
              <button
                onClick={() => setShowTemplates(!showTemplates)}
                className="w-full flex items-center gap-3 p-3 bg-gradient-to-r from-blue-500/20 to-cyan-500/20 hover:from-blue-500/30 hover:to-cyan-500/30 border border-blue-500/30 rounded-lg text-left transition-colors"
              >
                <BarChart3 size={18} className="text-blue-400" />
                <div>
                  <p className="text-sm font-medium text-white">Cenários Pré-definidos</p>
                  <p className="text-xs text-slate-400">Templates para simulação rápida</p>
                </div>
              </button>
            </div>
          </DarkCard>
        </div>
      </div>

      {/* PALANTIR: Scenario Templates Gallery */}
      {showTemplates && (
        <DarkCard 
          title="📊 Cenários Pré-definidos" 
          subtitle="Escolhe um template para começar rapidamente"
          className="mt-6"
        >
          <ScenarioTemplatesGallery 
            onSelectTemplate={() => {
              setShowTemplates(false);
              setShowSimulator(true);
              // Template will pre-populate the simulator
            }}
          />
        </DarkCard>
      )}

      {/* Simulator Modal */}
      {showSimulator && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-5xl max-h-[90vh] overflow-y-auto m-4">
            <div className="relative">
              <button
                onClick={() => setShowSimulator(false)}
                className="absolute -top-2 -right-2 z-10 p-2 bg-slate-800 hover:bg-slate-700 rounded-full text-slate-400 hover:text-white transition-colors"
              >
                ✕
              </button>
              <WorkforceSimulator
                baseline={{
                  spofCount: summary.spofCount,
                  avgRiskScore: summary.avgRiskScore,
                  totalBacklogAtRisk: summary.totalBacklogAtRisk,
                  phasesAtRisk: summary.phasesAtRisk,
                }}
                phases={phaseRisks.map(p => ({ id: p.phaseId, name: p.phaseName, riskLevel: p.riskLevel }))}
                employees={[
                  { id: 'emp-1', name: 'Maria Santos', currentPhases: ['Laminagem', 'Acabamento'] },
                  { id: 'emp-2', name: 'Pedro Ferreira', currentPhases: ['Laminagem', 'Pintura'] },
                  { id: 'emp-3', name: 'Ana Costa', currentPhases: ['Polimento'] },
                  { id: 'emp-4', name: 'Carlos Lima', currentPhases: ['Montagem', 'Acabamento'] },
                  { id: 'emp-5', name: 'João Silva', currentPhases: ['Rotomoldagem'] },
                ]}
                onSimulate={handleSimulate}
                onSave={(result) => {
                  console.log('Saving scenario:', result);
                  setShowSimulator(false);
                }}
                onApprove={(result) => {
                  console.log('Approving scenario:', result);
                  navigate('/twin');
                }}
                trustIndex={trustIndex}
              />
            </div>
          </div>
        </div>
      )}

      {/* Footer Warning */}
      <div className="mt-6 p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl">
        <div className="flex items-start gap-3">
          <Info size={16} className="text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-amber-400 font-medium mb-1">
              ⚠️ Dados Teóricos — Trust Index: {trustIndex}%
            </p>
            <p className="text-xs text-amber-300/70">
              Esta análise é baseada em FuncionariosFasesAptos (aptidões teóricas) e FasesOrdemFabrico (backlog).
              Não inclui: horas reais trabalhadas, ausências, férias, turnos, ou flexibilidade operacional.
              Os custos são estimativas baseadas na mediana de €5.54/h do ValorHora.
            </p>
          </div>
        </div>
      </div>
    </DarkPageLayout>
    </ModuleErrorBoundary>
  );
}

export default WorkforceDashboard;


