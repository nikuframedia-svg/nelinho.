/**
 * Workforce Simulator Component
 * ===============================
 * 
 * What-If simulator for workforce scenarios.
 * Allows users to simulate:
 * - Cross-training employees
 * - Employee unavailability
 * - New hires
 * 
 * Shows before/after comparison with impact metrics.
 */

import { useState, useMemo } from 'react';
import { 
  Play, 
  Plus, 
  Minus, 
  User, 
  Layers, 
  TrendingDown, 
  ArrowRight,
  Save,
  CheckCircle2,
  AlertTriangle,
  Info,
  Shield,
  X,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import type { 
  WorkforceDelta, 
  SimulationResult, 
} from './types';

interface WorkforceSimulatorProps {
  baseline: {
    spofCount: number;
    avgRiskScore: number;
    totalBacklogAtRisk: number;
    phasesAtRisk: number;
  };
  phases: Array<{ id: string; name: string; riskLevel: string }>;
  employees: Array<{ id: string; name: string; currentPhases: string[] }>;
  onSimulate: (deltas: WorkforceDelta[]) => Promise<SimulationResult>;
  onSave?: (result: SimulationResult) => void;
  onApprove?: (result: SimulationResult) => void;
  trustIndex?: number;
  medianHourlyRate?: number;
}

export function WorkforceSimulator({
  baseline: _baseline, // Used for display purposes, prefix with _ to avoid lint warning
  phases,
  employees,
  onSimulate,
  onSave,
  onApprove,
  trustIndex = 55,
  medianHourlyRate = 5.54,
}: WorkforceSimulatorProps) {
  const [deltas, setDeltas] = useState<WorkforceDelta[]>([]);
  const [isSimulating, setIsSimulating] = useState(false);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [showAddDelta, setShowAddDelta] = useState(false);
  const [newDelta, setNewDelta] = useState<Partial<WorkforceDelta>>({
    type: 'add_training',
  });

  // Calculate estimated training cost
  const estimatedCost = useMemo(() => {
    const trainingDeltas = deltas.filter(d => d.type === 'add_training');
    const trainingHours = trainingDeltas.length * 40; // Assume 40h per training
    return {
      hours: trainingHours,
      cost: trainingHours * medianHourlyRate,
    };
  }, [deltas, medianHourlyRate]);

  const handleAddDelta = () => {
    if (!newDelta.type) return;

    let description = '';
    switch (newDelta.type) {
      case 'add_training':
        const emp = employees.find(e => e.id === newDelta.employeeId);
        const phase = phases.find(p => p.id === newDelta.phaseId);
        description = `Treinar ${emp?.name || 'Funcionário'} para ${phase?.name || 'Fase'}`;
        break;
      case 'remove_employee':
        const empToRemove = employees.find(e => e.id === newDelta.employeeId);
        description = `Simular indisponibilidade de ${empToRemove?.name || 'Funcionário'}`;
        break;
      case 'add_employee':
        const targetPhase = phases.find(p => p.id === newDelta.phaseId);
        description = `Contratar novo funcionário para ${targetPhase?.name || 'Fase'}`;
        break;
      default:
        description = 'Delta personalizado';
    }

    const delta: WorkforceDelta = {
      type: newDelta.type,
      employeeId: newDelta.employeeId,
      phaseId: newDelta.phaseId,
      description,
    };

    setDeltas([...deltas, delta]);
    setNewDelta({ type: 'add_training' });
    setShowAddDelta(false);
  };

  const handleRemoveDelta = (index: number) => {
    setDeltas(deltas.filter((_, i) => i !== index));
    setResult(null);
  };

  const handleSimulate = async () => {
    if (deltas.length === 0) return;

    setIsSimulating(true);
    try {
      const simResult = await onSimulate(deltas);
      setResult(simResult);
    } catch (error) {
      console.error('Simulation failed:', error);
    } finally {
      setIsSimulating(false);
    }
  };

  const handleReset = () => {
    setDeltas([]);
    setResult(null);
  };

  const getDeltaIcon = (type: WorkforceDelta['type']) => {
    switch (type) {
      case 'add_training':
        return <Plus size={14} className="text-emerald-400" />;
      case 'remove_employee':
        return <Minus size={14} className="text-red-400" />;
      case 'add_employee':
        return <User size={14} className="text-cyan-400" />;
      default:
        return <Layers size={14} className="text-slate-400" />;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-green-500/20 to-emerald-500/20 rounded-lg">
              <Play className="text-green-400" size={20} />
            </div>
            <div>
              <h3 className="font-semibold text-white">🎮 Simulador What-If — Workforce</h3>
              <p className="text-xs text-slate-500">Simule cenários de formação, contratação ou ausência</p>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 rounded-lg">
            <Shield size={14} className="text-amber-400" />
            <span className="text-sm text-slate-400">Trust: <span className="text-white">{trustIndex}%</span></span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 divide-x divide-slate-700">
        {/* Left: Delta Builder */}
        <div className="p-6">
          <h4 className="font-medium text-white mb-4 flex items-center gap-2">
            <Plus size={16} className="text-slate-400" />
            Configurar Cenário
          </h4>

          {/* Deltas List */}
          <div className="space-y-2 mb-4 max-h-48 overflow-y-auto">
            {deltas.map((delta, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg border border-slate-700/50"
              >
                <div className="flex items-center gap-3">
                  {getDeltaIcon(delta.type)}
                  <span className="text-sm text-white">{delta.description}</span>
                </div>
                <button
                  onClick={() => handleRemoveDelta(index)}
                  className="p-1 hover:bg-slate-700 rounded transition-colors"
                >
                  <X size={14} className="text-slate-400" />
                </button>
              </div>
            ))}

            {deltas.length === 0 && (
              <div className="text-center py-8 text-slate-500">
                <Layers size={32} className="mx-auto mb-2 opacity-50" />
                <p className="text-sm">Nenhum delta configurado</p>
                <p className="text-xs">Adicione ações para simular</p>
              </div>
            )}
          </div>

          {/* Add Delta Form */}
          {showAddDelta ? (
            <div className="p-4 bg-slate-800/50 rounded-lg border border-slate-700 space-y-3">
              <select
                value={newDelta.type}
                onChange={(e) => setNewDelta({ ...newDelta, type: e.target.value as WorkforceDelta['type'] })}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white text-sm"
              >
                <option value="add_training">Treinar Funcionário</option>
                <option value="remove_employee">Simular Ausência</option>
                <option value="add_employee">Contratar Novo</option>
              </select>

              {(newDelta.type === 'add_training' || newDelta.type === 'remove_employee') && (
                <select
                  value={newDelta.employeeId || ''}
                  onChange={(e) => setNewDelta({ ...newDelta, employeeId: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white text-sm"
                >
                  <option value="">Selecionar funcionário...</option>
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>{emp.name}</option>
                  ))}
                </select>
              )}

              {(newDelta.type === 'add_training' || newDelta.type === 'add_employee') && (
                <select
                  value={newDelta.phaseId || ''}
                  onChange={(e) => setNewDelta({ ...newDelta, phaseId: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white text-sm"
                >
                  <option value="">Selecionar fase...</option>
                  {phases.map((phase) => (
                    <option key={phase.id} value={phase.id}>
                      {phase.name} ({phase.riskLevel})
                    </option>
                  ))}
                </select>
              )}

              <div className="flex items-center gap-2">
                <button
                  onClick={handleAddDelta}
                  disabled={!newDelta.type || (newDelta.type !== 'add_employee' && !newDelta.employeeId)}
                  className="flex-1 px-3 py-2 bg-emerald-500 hover:bg-emerald-600 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
                >
                  Adicionar
                </button>
                <button
                  onClick={() => setShowAddDelta(false)}
                  className="px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors"
                >
                  Cancelar
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowAddDelta(true)}
              className="w-full px-4 py-3 border-2 border-dashed border-slate-600 rounded-lg text-slate-400 hover:border-slate-500 hover:text-white transition-colors flex items-center justify-center gap-2"
            >
              <Plus size={16} />
              Adicionar Delta
            </button>
          )}

          {/* Estimated Cost */}
          {deltas.length > 0 && (
            <div className="mt-4 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
              <p className="text-xs text-amber-400 flex items-center gap-2">
                <Info size={12} />
                Custo estimado: {estimatedCost.hours}h × €{medianHourlyRate}/h = <strong>€{estimatedCost.cost.toFixed(0)}</strong>
              </p>
              <p className="text-[10px] text-amber-400/70 mt-1">
                ⚠️ Estimativa teórica — não inclui materiais, curva de aprendizagem
              </p>
            </div>
          )}

          {/* Actions */}
          <div className="mt-4 flex items-center gap-2">
            <button
              onClick={handleSimulate}
              disabled={deltas.length === 0 || isSimulating}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 disabled:from-slate-600 disabled:to-slate-600 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-all"
            >
              {isSimulating ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Simulando...
                </>
              ) : (
                <>
                  <Play size={16} />
                  Simular Cenário
                </>
              )}
            </button>
            {deltas.length > 0 && (
              <button
                onClick={handleReset}
                className="p-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
              >
                <RefreshCw size={16} />
              </button>
            )}
          </div>
        </div>

        {/* Right: Results */}
        <div className="p-6">
          <h4 className="font-medium text-white mb-4 flex items-center gap-2">
            <TrendingDown size={16} className="text-slate-400" />
            Impacto Simulado
          </h4>

          {result ? (
            <>
              {/* Comparison Table */}
              <div className="bg-slate-800/50 rounded-lg border border-slate-700 overflow-hidden mb-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="px-4 py-2 text-left text-slate-400 font-medium">Métrica</th>
                      <th className="px-4 py-2 text-right text-slate-400 font-medium">Antes</th>
                      <th className="px-4 py-2 text-center text-slate-400">→</th>
                      <th className="px-4 py-2 text-right text-slate-400 font-medium">Depois</th>
                      <th className="px-4 py-2 text-right text-slate-400 font-medium">Delta</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-slate-700/50">
                      <td className="px-4 py-3 text-white">SPOFs</td>
                      <td className="px-4 py-3 text-right text-slate-300 font-mono">{result.baseline.spofCount}</td>
                      <td className="px-4 py-3 text-center"><ArrowRight size={12} className="text-slate-500 mx-auto" /></td>
                      <td className="px-4 py-3 text-right text-white font-mono font-medium">{result.simulated.spofCount}</td>
                      <td className={`px-4 py-3 text-right font-medium ${result.impact.spofChange < 0 ? 'text-emerald-400' : result.impact.spofChange > 0 ? 'text-red-400' : 'text-slate-400'}`}>
                        {result.impact.spofChange > 0 ? '+' : ''}{result.impact.spofChange}
                      </td>
                    </tr>
                    <tr className="border-b border-slate-700/50">
                      <td className="px-4 py-3 text-white">Risk Score</td>
                      <td className="px-4 py-3 text-right text-slate-300 font-mono">{result.baseline.avgRiskScore.toFixed(0)}%</td>
                      <td className="px-4 py-3 text-center"><ArrowRight size={12} className="text-slate-500 mx-auto" /></td>
                      <td className="px-4 py-3 text-right text-white font-mono font-medium">{result.simulated.avgRiskScore.toFixed(0)}%</td>
                      <td className={`px-4 py-3 text-right font-medium ${result.impact.riskChange < 0 ? 'text-emerald-400' : result.impact.riskChange > 0 ? 'text-red-400' : 'text-slate-400'}`}>
                        {result.impact.riskChange > 0 ? '+' : ''}{result.impact.riskChange.toFixed(1)}%
                      </td>
                    </tr>
                    <tr className="border-b border-slate-700/50">
                      <td className="px-4 py-3 text-white">Backlog em Risco</td>
                      <td className="px-4 py-3 text-right text-slate-300 font-mono">{result.baseline.totalBacklogAtRisk.toFixed(0)}h</td>
                      <td className="px-4 py-3 text-center"><ArrowRight size={12} className="text-slate-500 mx-auto" /></td>
                      <td className="px-4 py-3 text-right text-white font-mono font-medium">{result.simulated.totalBacklogAtRisk.toFixed(0)}h</td>
                      <td className={`px-4 py-3 text-right font-medium ${result.impact.backlogChange < 0 ? 'text-emerald-400' : result.impact.backlogChange > 0 ? 'text-red-400' : 'text-slate-400'}`}>
                        {result.impact.backlogChange > 0 ? '+' : ''}{result.impact.backlogChange.toFixed(0)}h
                      </td>
                    </tr>
                    <tr>
                      <td className="px-4 py-3 text-white">Fases em Risco</td>
                      <td className="px-4 py-3 text-right text-slate-300 font-mono">{result.baseline.phasesAtRisk}</td>
                      <td className="px-4 py-3 text-center"><ArrowRight size={12} className="text-slate-500 mx-auto" /></td>
                      <td className="px-4 py-3 text-right text-white font-mono font-medium">{result.simulated.phasesAtRisk}</td>
                      <td className={`px-4 py-3 text-right font-medium ${result.impact.phasesChange < 0 ? 'text-emerald-400' : result.impact.phasesChange > 0 ? 'text-red-400' : 'text-slate-400'}`}>
                        {result.impact.phasesChange > 0 ? '+' : ''}{result.impact.phasesChange}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Recommendations */}
              {result.recommendations.length > 0 && (
                <div className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                  <p className="text-xs text-emerald-400 font-medium mb-2">💡 Recomendações:</p>
                  <ul className="space-y-1">
                    {result.recommendations.map((rec, i) => (
                      <li key={i} className="text-xs text-emerald-300/80 flex items-start gap-2">
                        <CheckCircle2 size={10} className="flex-shrink-0 mt-0.5" />
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Cost Benefit */}
              {result.estimatedCost && (
                <div className="mb-4 p-3 bg-slate-800/50 border border-slate-700 rounded-lg">
                  <p className="text-xs text-slate-400 mb-2">💰 Análise Custo-Benefício:</p>
                  <div className="space-y-1 text-xs">
                    <p className="text-white">
                      Custo estimado: €{result.estimatedCost.totalCost.toFixed(0)} ({result.estimatedCost.trainingHours}h)
                    </p>
                    <p className="text-emerald-400">
                      Backlog securizado: {Math.abs(result.impact.backlogChange).toFixed(0)}h
                    </p>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => onSave?.(result)}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors"
                >
                  <Save size={14} />
                  Guardar
                </button>
                <button
                  onClick={() => onApprove?.(result)}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  <CheckCircle2 size={14} />
                  Aprovar
                </button>
              </div>

              {/* Trust Warning */}
              <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
                <AlertTriangle size={10} />
                Resultados teóricos baseados em Trust {trustIndex}%. Não são garantia de resultado real.
              </div>
            </>
          ) : (
            <div className="h-64 flex flex-col items-center justify-center text-slate-500">
              <TrendingDown size={40} className="mb-3 opacity-50" />
              <p className="text-sm">Configure e execute uma simulação</p>
              <p className="text-xs mt-1">Os resultados aparecerão aqui</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default WorkforceSimulator;

