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
export function transformApiToPhaseRisks(apiData: any): PhaseRisk[] {
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
 * Generate SPOF alerts from phase risks
 */
export function generateSPOFAlertsFromRisks(phaseRisks: PhaseRisk[]): SPOFAlert[] {
  // ZERO MOCKS: `/factory/skills-risk` dá risco POR FASE mas não a identidade
  // do operador apto. Não inventamos nomes ("Funcionário apto N"): o alerta
  // descreve a FASE; o operador fica "não identificado" até haver dados reais.
  return phaseRisks
    .filter(p => p.isSPOF || p.aptosActive <= 2)
    .slice(0, 5)
    .map((p) => ({
      phaseId: p.phaseId,
      phaseName: p.phaseName,
      employeeId: '',
      employeeName: 'Operador apto (não identificado)',
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
  // ZERO MOCKS: o endpoint não dá os links operador↔fase, por isso NÃO
  // inventamos nós "Funcionário N" nem arestas de aptidão. O grafo mostra só
  // as fases reais (e o seu risco); quando o ETL expuser as aptidões reais,
  // os operadores entram aqui com identidade verdadeira.
  const nodes = phaseRisks.map(p => ({
    id: `phase-${p.phaseId}`,
    type: 'phase' as const,
    label: p.phaseName,
    data: { id: p.phaseId, name: p.phaseName, description: '' },
    riskLevel: p.riskLevel as any,
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
 * Generate training recommendations from phase risks
 */
export function generateTrainingRecommendationsFromRisks(phaseRisks: PhaseRisk[]): TrainingRecommendation[] {
  const criticalPhases = phaseRisks.filter(p => p.isSPOF || p.riskLevel === 'critical' || p.riskLevel === 'high');
  
  // ZERO MOCKS: a recomendação é POR FASE ("formar +1 operador para esta
  // fase"). Não inventamos o operador a formar ("Funcionário N") — fica vazio
  // até o ETL dar as aptidões reais; o render mostra só a fase-alvo.
  return criticalPhases.slice(0, 3).map((phase, idx) => ({
    id: `rec-${idx + 1}`,
    priority: phase.isSPOF ? 'critical' : 'high',
    employee: {
      id: '',
      name: '',
      currentPhases: [] as string[],
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
