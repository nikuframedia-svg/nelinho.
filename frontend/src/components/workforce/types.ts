/**
 * Workforce Operations System - Type Definitions
 * ================================================
 * 
 * Core types for the workforce dependency graph and risk analysis.
 * These types model the relationships between:
 * - Employees (Funcionários)
 * - Skills/Aptitudes (FuncionariosFasesAptos)
 * - Phases (Fases)
 * - Production Orders (OrdensFabrico)
 */

// ═══════════════════════════════════════════════════════════════════════════════
// CORE ENTITIES
// ═══════════════════════════════════════════════════════════════════════════════

export interface Employee {
  id: string;
  name: string;
  isActive: boolean;
  valorHora?: number;
  department?: string;
  aptitudes: string[]; // Phase IDs this employee is capable of
}

export interface Phase {
  id: string;
  name: string;
  description?: string;
  numFuncionarios?: number; // Standard number of employees needed
  capacidadeHorasDia?: number; // Theoretical daily capacity
}

export interface Order {
  id: string;
  reference?: string;
  modeloId?: string;
  dataAbertura?: string;
  dataAcabamento?: string | null;
  isOpen: boolean;
}

export interface OrderPhase {
  id: string;
  orderId: string;
  phaseId: string;
  horasPrevistasFinal?: number;
  dataPrevista?: string;
  status: 'pending' | 'in_progress' | 'completed';
}

// ═══════════════════════════════════════════════════════════════════════════════
// RISK ANALYSIS
// ═══════════════════════════════════════════════════════════════════════════════

export type RiskLevel = 'critical' | 'high' | 'medium' | 'low' | 'ok';

export interface PhaseRisk {
  phaseId: string;
  phaseName: string;
  aptosCount: number;
  aptosActive: number;
  backlogHours: number;
  backlogDays: number;
  riskScore: number; // 0-100, higher = more risk
  riskLevel: RiskLevel;
  isSPOF: boolean; // Single Point of Failure (1 employee)
  employees: Array<{
    id: string;
    name: string;
    isActive: boolean;
  }>;
  ordersAtRisk: number;
}

export interface SPOFAlert {
  phaseId: string;
  phaseName: string;
  employeeId: string;
  employeeName: string;
  backlogHours: number;
  ordersAffected: number;
  estimatedDailyCost: number;
  riskLevel: 'critical' | 'high';
}

export interface SkillsRiskSummary {
  totalPhases: number;
  phasesAtRisk: number;
  spofCount: number;
  totalBacklogAtRisk: number;
  riskBreakdown: {
    critical: number;
    high: number;
    medium: number;
    low: number;
    ok: number;
  };
  trustIndex: number;
  dataSource: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// DEPENDENCY GRAPH
// ═══════════════════════════════════════════════════════════════════════════════

export type NodeType = 'phase' | 'employee' | 'order';

export interface GraphNode {
  id: string;
  type: NodeType;
  label: string;
  data: Phase | Employee | Order;
  riskLevel?: RiskLevel;
  size?: number;
  color?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: 'aptitude' | 'assignment' | 'dependency';
  weight?: number;
}

export interface DependencyGraph {
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
// SIMULATION
// ═══════════════════════════════════════════════════════════════════════════════

export type DeltaType = 
  | 'add_training'      // Train employee for new phase
  | 'remove_employee'   // Simulate employee unavailability
  | 'add_employee'      // Simulate hiring
  | 'modify_capacity';  // Change phase capacity

export interface WorkforceDelta {
  type: DeltaType;
  employeeId?: string;
  phaseId?: string;
  params?: Record<string, any>;
  description: string;
}

export interface SimulationResult {
  scenarioId: string;
  scenarioName: string;
  baseline: {
    spofCount: number;
    avgRiskScore: number;
    totalBacklogAtRisk: number;
    phasesAtRisk: number;
  };
  simulated: {
    spofCount: number;
    avgRiskScore: number;
    totalBacklogAtRisk: number;
    phasesAtRisk: number;
  };
  deltas: WorkforceDelta[];
  impact: {
    spofChange: number;
    riskChange: number;
    backlogChange: number;
    phasesChange: number;
  };
  estimatedCost?: {
    trainingHours: number;
    costPerHour: number;
    totalCost: number;
  };
  recommendations: string[];
  trustIndex: number;
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRAINING RECOMMENDATIONS
// ═══════════════════════════════════════════════════════════════════════════════

export interface TrainingRecommendation {
  id: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  employee: {
    id: string;
    name: string;
    currentPhases: string[];
  };
  targetPhase: {
    id: string;
    name: string;
  };
  reasoning: string[];
  expectedImpact: {
    spofEliminated: boolean;
    riskReduction: number; // percentage points
    backlogSecured: number; // hours
  };
  estimatedCost: {
    hours: number;
    cost: number;
  };
  trustIndex: number;
}

// ═══════════════════════════════════════════════════════════════════════════════
// CASCADE IMPACT
// ═══════════════════════════════════════════════════════════════════════════════

export interface CascadeLevel {
  level: number;
  type: 'workforce' | 'production' | 'downstream' | 'economic';
  title: string;
  items: Array<{
    label: string;
    value: string | number;
    severity?: RiskLevel;
  }>;
}

export interface CascadeImpact {
  sourcePhase: string;
  sourcePhaseName: string;
  triggerEmployee?: string;
  triggerEmployeeName?: string;
  levels: CascadeLevel[];
  totalOrdersAffected: number;
  totalBacklogAffected: number;
  estimatedDailyCost: number;
  trustIndex: number;
  warnings: string[];
}

// ═══════════════════════════════════════════════════════════════════════════════
// SCENARIO COMPARISON
// ═══════════════════════════════════════════════════════════════════════════════

export interface ScenarioComparison {
  scenarios: Array<{
    id: string;
    name: string;
    type: 'baseline' | 'training' | 'hiring' | 'custom';
    metrics: {
      // Support both snake_case (from API) and camelCase
      spofCount?: number;
      spof_count?: number;
      avgRiskScore?: number;
      avg_risk_score?: number;
      backlogAtRisk?: number;
      backlog_at_risk?: number;
      estimatedCost?: number;
      estimated_cost?: number;
      paybackDays?: number | null;
      payback_days?: number | null;
    };
    isRecommended?: boolean;
    is_recommended?: boolean;
    recommendationReason?: string;
    recommendation_reason?: string;
  }>;
  trustIndex?: number;
  trust_index?: number;
}

// ═══════════════════════════════════════════════════════════════════════════════
// API RESPONSE TYPES
// ═══════════════════════════════════════════════════════════════════════════════

export interface WorkforceApiResponse<T> {
  data: T;
  dataConfidence: number;
  trustStatus: 'OK' | 'WARNING' | 'BLOCKED' | 'DEGRADED';
  semanticLabel: string;
  metadata?: {
    queryTime: string;
    source: string;
    warnings?: string[];
  };
}


