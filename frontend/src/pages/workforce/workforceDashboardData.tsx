// Decomposto de WorkforceDashboard.tsx (Q.60.AB).
import type { PhaseRisk, SPOFAlert, TrainingRecommendation, GraphNode, GraphEdge } from '../../components/workforce';

// Type for dependency graph data
export interface DependencyGraphData {
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
interface PhaseRiskRaw {
  fase_id?: string | number;
  id?: string | number;
  fase_nome?: string;
  name?: string;
  active_workers?: number;
  aptos_count?: number;
  backlog_hours?: number;
  risk_score?: number;
}
interface PhaseRiskApiData {
  data?: { phases_with_risk?: PhaseRiskRaw[] };
}
export function transformApiToPhaseRisks(apiData: PhaseRiskApiData | unknown): PhaseRisk[] {
  const typed = apiData as PhaseRiskApiData;
  // If we have phases from the API, transform them
  if (typed?.data?.phases_with_risk) {
    return typed.data.phases_with_risk.map((p) => {
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
 * Generate SPOF alerts from phase risks
 */
export function generateSPOFAlertsFromRisks(phaseRisks: PhaseRisk[]): SPOFAlert[] {
  return phaseRisks
    .filter(p => p.isSPOF || p.aptosActive <= 2)
    .slice(0, 5)
    .map((p, idx) => ({
      phaseId: p.phaseId,
      phaseName: p.phaseName,
      employeeId: `emp-${p.phaseId}-1`,
      employeeName: `Funcionário apto ${idx + 1}`,
      backlogHours: p.backlogHours,
      ordersAffected: p.ordersAtRisk,
      estimatedDailyCost: Math.floor(p.backlogHours * 5.54 / 8),
      riskLevel: p.riskLevel === 'critical' ? 'critical' : 'high',
    }));
}

/**
 * Generate dependency graph from phase and employee data
 */
export function generateDependencyGraphFromData(phaseRisks: PhaseRisk[], employeesCount: number): DependencyGraphData {
  const nodes = [
    ...phaseRisks.map(p => ({
      id: `phase-${p.phaseId}`,
      type: 'phase' as const,
      label: p.phaseName,
      data: { id: p.phaseId, name: p.phaseName, description: '' },
      riskLevel: p.riskLevel as any,
      size: 25,
    })),
    ...Array.from({ length: Math.min(employeesCount, 10) }, (_, i) => ({
      id: `emp-${i}`,
      type: 'employee' as const,
      label: `Funcionário ${i + 1}`,
      data: { id: `emp-${i}`, name: `Funcionário ${i + 1}`, isActive: true, aptitudes: [] },
      size: 18,
    })),
  ];

  // Generate edges (employee-to-phase connections)
  const edges = phaseRisks.flatMap((p, pIdx) => 
    Array.from({ length: Math.min(p.aptosActive, 3) }, (_, eIdx) => ({
      id: `e-${pIdx}-${eIdx}`,
      source: `emp-${(pIdx + eIdx) % Math.min(employeesCount, 10)}`,
      target: `phase-${p.phaseId}`,
      type: 'aptitude' as const,
    }))
  );

  return {
    nodes,
    edges,
    metadata: {
      totalEmployees: employeesCount,
      totalPhases: phaseRisks.length,
      totalLinks: edges.length,
      spofNodes: phaseRisks.filter(p => p.isSPOF).map(p => `phase-${p.phaseId}`),
      criticalPaths: phaseRisks.filter(p => p.isSPOF).map(p => [`phase-${p.phaseId}`, `emp-0`]),
    },
  };
}

/**
 * Generate training recommendations from phase risks
 */
export function generateTrainingRecommendationsFromRisks(phaseRisks: PhaseRisk[]): TrainingRecommendation[] {
  const criticalPhases = phaseRisks.filter(p => p.isSPOF || p.riskLevel === 'critical' || p.riskLevel === 'high');
  
  return criticalPhases.slice(0, 3).map((phase, idx) => ({
    id: `rec-${idx + 1}`,
    priority: phase.isSPOF ? 'critical' : 'high',
    employee: {
      id: `emp-${idx + 1}`,
      name: `Funcionário ${idx + 1}`,
      currentPhases: ['Fase Base'],
    },
    targetPhase: {
      id: phase.phaseId,
      name: phase.phaseName,
    },
    reasoning: [
      `${phase.phaseName} tem apenas ${phase.aptosActive} funcionário(s) apto(s)${phase.isSPOF ? ' (SPOF crítico)' : ''}`,
      `Backlog de ${phase.backlogHours.toFixed(0)}h em risco`,
      phase.isSPOF ? 'Elimina o maior risco operacional' : 'Reduz risco de single dependency',
    ],
    expectedImpact: {
      spofEliminated: phase.isSPOF,
      riskReduction: phase.isSPOF ? 35 : 20,
      backlogSecured: phase.backlogHours,
    },
    estimatedCost: {
      hours: 40,
      cost: 40 * 5.54,
    },
    trustIndex: 55,
  }));
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════
