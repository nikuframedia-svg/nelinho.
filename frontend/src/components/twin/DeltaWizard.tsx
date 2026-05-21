/**
 * Delta Wizard Component
 * =======================
 * 
 * 3-step wizard for applying changes to scenarios:
 * 1. Select change type and parameters
 * 2. Preview impact (via real API simulation)
 * 3. Confirm and apply
 * 
 * IMPORTANT: Uses real /v1/twin API endpoints.
 * Blocked metrics (OEE, Availability, etc.) are filtered out.
 */

import React, { useState } from 'react';
import { 
  ChevronRight, 
  ChevronLeft,
  Check,
  X,
  Zap,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Play,
  RefreshCw,
  Ban,
  Shield,
  AlertCircle,
} from 'lucide-react';
import { twinApi } from '../../lib/api';

// Q.67.2.A — fetches directos migrados para `lib/api/twinApi.ts`.

// ═══════════════════════════════════════════════════════════════════════════════
// BLOCKED METRICS - Cannot be simulated (no source data)
// Source: src/factory_data_product/config.py
// ═══════════════════════════════════════════════════════════════════════════════

const BLOCKED_METRICS = [
  'oee',
  'oee_real',
  'availability',
  'availability_oee',
  'performance',
  'quality',
  'otd',
  'otd_official',
] as const;

// Delta types supported by backend
type DeltaType = 
  | 'capacity_adjustment'
  | 'standard_time'
  | 'skills_training'
  | 'quality_improvement'
  | 'wip_policy';

interface DeltaConfig {
  type: DeltaType;
  title: string;
  description: string;
  icon: React.ReactNode;
  affectedMetrics: string[];
  fields: {
    key: string;
    label: string;
    type: 'number' | 'select' | 'text';
    min?: number;
    max?: number;
    options?: { value: string; label: string }[];
    suffix?: string;
  }[];
}

const DELTA_CONFIGS: DeltaConfig[] = [
  {
    type: 'capacity_adjustment',
    title: 'Capacity Adjustment',
    description: 'Adjust theoretical capacity for a specific phase',
    icon: <TrendingUp className="w-5 h-5" />,
    affectedMetrics: ['backlog_horas_theoretical', 'bottleneck_count'],
    fields: [
      { key: 'phase_id', label: 'Phase', type: 'select', options: [
        { value: 'all', label: 'All Phases' },
        { value: '1', label: 'Laminação' },
        { value: '2', label: 'Acabamento' },
        { value: '3', label: 'Pintura' },
        { value: '4', label: 'Montagem' },
      ]},
      { key: 'capacity_increase_pct', label: 'Capacity Change', type: 'number', min: -50, max: 100, suffix: '%' },
    ],
  },
  {
    type: 'standard_time',
    title: 'Standard Time Update',
    description: 'Update theoretical standard times',
    icon: <RefreshCw className="w-5 h-5" />,
    affectedMetrics: ['backlog_horas_theoretical', 'cost_theoretical_estimated'],
    fields: [
      { key: 'scope', label: 'Scope', type: 'select', options: [
        { value: 'all', label: 'All Products' },
        { value: 'phase', label: 'Specific Phase' },
      ]},
      { key: 'reduction_pct', label: 'Time Reduction', type: 'number', min: 0, max: 50, suffix: '%' },
    ],
  },
  {
    type: 'skills_training',
    title: 'Skills Training',
    description: 'Add trained employees to phases',
    icon: <Zap className="w-5 h-5" />,
    affectedMetrics: ['skills_at_risk_count'],
    fields: [
      { key: 'phases_trained', label: 'Phases to Train', type: 'number', min: 1, max: 10 },
    ],
  },
  {
    type: 'quality_improvement',
    title: 'Quality Improvement',
    description: 'Reduce error rates through improvements',
    icon: <Check className="w-5 h-5" />,
    affectedMetrics: ['quality_errors_total'],
    fields: [
      { key: 'error_reduction_pct', label: 'Error Reduction', type: 'number', min: 0, max: 50, suffix: '%' },
    ],
  },
  {
    type: 'wip_policy',
    title: 'WIP Policy',
    description: 'Set WIP limits (Kanban)',
    icon: <TrendingDown className="w-5 h-5" />,
    affectedMetrics: ['wip_theoretical'],
    fields: [
      { key: 'wip_limit', label: 'WIP Limit', type: 'number', min: 100, max: 5000 },
    ],
  },
];

interface DeltaWizardProps {
  scenarioId: string;
  onComplete: (delta: { type: string; patch: Record<string, any> }) => void;
  onCancel: () => void;
}

interface MetricImpact {
  metric: string;
  metricLabel: string;
  before: number | null;
  after: number | null;
  change: number | null;
  trustIndex: number;
  status: 'OK' | 'WARNING' | 'BLOCKED' | 'DEGRADED';
  semanticLabel?: string;
}

interface SimulationResult {
  scenario_id: string;
  status: string;
  kpis: Record<string, any>;
  comparison?: Record<string, any>;
  simulated_at: string;
  blocked_metrics?: string[];
}

export function DeltaWizard({
  scenarioId,
  onComplete,
  onCancel,
}: DeltaWizardProps) {
  const [step, setStep] = useState(1);
  const [selectedType, setSelectedType] = useState<DeltaType | null>(null);
  const [fieldValues, setFieldValues] = useState<Record<string, any>>({});
  const [isSimulating, setIsSimulating] = useState(false);
  const [impactPreview, setImpactPreview] = useState<MetricImpact[] | null>(null);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [blockedMetricsInSimulation, setBlockedMetricsInSimulation] = useState<string[]>([]);

  // Get selected config
  const selectedConfig = DELTA_CONFIGS.find(c => c.type === selectedType);

  // Handle field change
  const handleFieldChange = (key: string, value: any) => {
    setFieldValues(prev => ({ ...prev, [key]: value }));
  };

  // Real API simulation
  const simulateImpact = async () => {
    if (!selectedType) return;

    setIsSimulating(true);
    setSimulationError(null);
    setBlockedMetricsInSimulation([]);

    try {
      // Step 1: Apply delta to scenario (tenant/user/trace_id via request()).
      await twinApi.applyDelta(scenarioId, {
        entity_type: selectedType,
        entity_key: fieldValues.phase_id || fieldValues.scope || 'all',
        patch: fieldValues,
      });

      // Step 2: Run simulation.
      const result = (await twinApi.simulate(scenarioId)) as SimulationResult;
      
      // Step 3: Process results - filter out blocked metrics
      const impacts: MetricImpact[] = [];
      const blocked: string[] = [];
      
      // Process KPIs from result
      const kpis = result.kpis || {};
      
      for (const [metric, data] of Object.entries(kpis)) {
        // Skip metadata fields
        if (metric.startsWith('_')) continue;
        
        // Check if metric is blocked
        const isBlocked = BLOCKED_METRICS.some(bm => 
          metric.toLowerCase().includes(bm.toLowerCase())
        ) || (typeof data === 'object' && data?.status === 'BLOCKED');
        
        if (isBlocked) {
          blocked.push(metric);
          continue;
        }
        
        // Extract metric data
        if (typeof data === 'object' && data !== null) {
          const beforeValue = result.comparison?.[metric]?.baseline ?? data.value;
          const afterValue = data.value;
          const change = beforeValue && afterValue 
            ? ((afterValue - beforeValue) / beforeValue) * 100 
            : null;
          
          impacts.push({
            metric,
            metricLabel: metric.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
            before: beforeValue,
            after: afterValue,
            change,
            trustIndex: data.trust_index || 0,
            status: data.status || 'OK',
            semanticLabel: data.semantic_label,
          });
        }
      }
      
      setImpactPreview(impacts);
      setBlockedMetricsInSimulation(blocked);
      setStep(2);
      
    } catch (error) {
      console.error('Simulation error:', error);
      setSimulationError(error instanceof Error ? error.message : 'Simulation failed');
    } finally {
      setIsSimulating(false);
    }
  };

  // Handle complete
  const handleComplete = () => {
    if (!selectedType) return;
    
    onComplete({
      type: selectedType,
      patch: fieldValues,
    });
  };

  // Get trust badge color
  const getTrustColor = (trust: number) => {
    if (trust >= 70) return 'bg-emerald-500/20 text-emerald-400';
    if (trust >= 50) return 'bg-amber-500/20 text-amber-400';
    if (trust >= 30) return 'bg-orange-500/20 text-orange-400';
    return 'bg-red-500/20 text-red-400';
  };

  // Render step 1: Select type and configure
  const renderStep1 = () => (
    <div className="space-y-6">
      {/* Type Selection */}
      <div>
        <h4 className="text-sm font-medium text-gray-400 mb-3">Select Change Type</h4>
        <div className="grid grid-cols-2 gap-3">
          {DELTA_CONFIGS.map(config => (
            <button
              key={config.type}
              onClick={() => {
                setSelectedType(config.type);
                setFieldValues({});
                setSimulationError(null);
              }}
              className={`
                p-4 rounded-lg border text-left transition-all
                ${selectedType === config.type 
                  ? 'border-blue-500 bg-blue-950/50' 
                  : 'border-gray-700 bg-gray-800 hover:border-gray-600'
                }
              `}
            >
              <div className={`
                inline-flex items-center justify-center w-8 h-8 rounded mb-2
                ${selectedType === config.type ? 'bg-blue-500/20 text-blue-400' : 'bg-gray-700 text-gray-400'}
              `}>
                {config.icon}
              </div>
              <h5 className="text-sm font-medium text-white">{config.title}</h5>
              <p className="text-xs text-gray-400 mt-1">{config.description}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {config.affectedMetrics.map(m => (
                  <span key={m} className="text-[10px] px-1.5 py-0.5 bg-gray-700 text-gray-300 rounded">
                    {m.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Blocked Metrics Notice */}
      <div className="p-3 bg-red-950/30 border border-red-900/50 rounded flex items-start gap-2">
        <Ban className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-xs text-red-300 font-medium">Blocked Metrics Cannot Be Simulated</p>
          <p className="text-xs text-red-400/80 mt-1">
            OEE, Availability, Performance, Quality, OTD - no source data available.
            Only theoretical metrics from available data can be simulated.
          </p>
        </div>
      </div>

      {/* Configuration Fields */}
      {selectedConfig && (
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-gray-400">Configure Parameters</h4>
          {selectedConfig.fields.map(field => (
            <div key={field.key}>
              <label className="block text-xs text-gray-400 mb-1">{field.label}</label>
              {field.type === 'number' ? (
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={field.min}
                    max={field.max}
                    value={fieldValues[field.key] || ''}
                    onChange={(e) => handleFieldChange(field.key, parseFloat(e.target.value))}
                    className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm focus:outline-none focus:border-blue-500"
                  />
                  {field.suffix && (
                    <span className="text-sm text-gray-400">{field.suffix}</span>
                  )}
                </div>
              ) : field.type === 'select' ? (
                <select
                  value={fieldValues[field.key] || ''}
                  onChange={(e) => handleFieldChange(field.key, e.target.value)}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm focus:outline-none focus:border-blue-500"
                >
                  <option value="">Select...</option>
                  {field.options?.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={fieldValues[field.key] || ''}
                  onChange={(e) => handleFieldChange(field.key, e.target.value)}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm focus:outline-none focus:border-blue-500"
                />
              )}
            </div>
          ))}
        </div>
      )}

      {/* Simulation Error */}
      {simulationError && (
        <div className="p-3 bg-red-950/50 border border-red-900/50 rounded flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs text-red-300 font-medium">Simulation Error</p>
            <p className="text-xs text-red-400/80 mt-1">{simulationError}</p>
          </div>
        </div>
      )}
    </div>
  );

  // Render step 2: Preview impact
  const renderStep2 = () => (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-amber-400">
        <AlertTriangle className="w-4 h-4" />
        <h4 className="text-sm font-medium">Impact Preview (From API Simulation)</h4>
      </div>

      {/* Blocked Metrics in this Simulation */}
      {blockedMetricsInSimulation.length > 0 && (
        <div className="p-3 bg-red-950/30 border border-red-900/50 rounded">
          <div className="flex items-center gap-2 mb-2">
            <Ban className="w-4 h-4 text-red-400" />
            <span className="text-xs text-red-300 font-medium">
              {blockedMetricsInSimulation.length} Blocked Metrics (Not Shown)
            </span>
          </div>
          <div className="flex flex-wrap gap-1">
            {blockedMetricsInSimulation.map(m => (
              <span key={m} className="text-[10px] px-1.5 py-0.5 bg-red-900/30 text-red-400 rounded">
                {m}
              </span>
            ))}
          </div>
        </div>
      )}

      {impactPreview && impactPreview.length > 0 ? (
        <div className="space-y-3">
          {impactPreview.map((impact, i) => (
            <div key={i} className="p-4 bg-gray-800 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-300">{impact.metricLabel}</span>
                  {impact.semanticLabel && (
                    <span className="text-[10px] text-gray-500 italic">({impact.semanticLabel})</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded flex items-center gap-1 ${getTrustColor(impact.trustIndex)}`}>
                    <Shield className="w-3 h-3" />
                    {impact.trustIndex}%
                  </span>
                </div>
              </div>
              
              <div className="flex items-center gap-4">
                <div className="text-center">
                  <p className="text-xs text-gray-500">Before</p>
                  <p className="text-lg font-semibold text-white">
                    {impact.before !== null ? impact.before.toLocaleString() : '—'}
                  </p>
                </div>
                
                <ChevronRight className="w-4 h-4 text-gray-600" />
                
                <div className="text-center">
                  <p className="text-xs text-gray-500">After</p>
                  <p className="text-lg font-semibold text-white">
                    {impact.after !== null ? Math.round(impact.after).toLocaleString() : '—'}
                  </p>
                </div>
                
                {impact.change !== null && (
                  <div className={`ml-auto text-sm font-medium ${
                    impact.change > 0 ? 'text-red-400' : 'text-emerald-400'
                  }`}>
                    {impact.change > 0 ? '+' : ''}{impact.change.toFixed(1)}%
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-400">
          <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No impact data available for allowed metrics</p>
          <p className="text-xs mt-1">All affected metrics may be blocked</p>
        </div>
      )}

      {/* Warning */}
      <div className="p-3 bg-amber-950/50 border border-amber-900/50 rounded flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-amber-300">
          These are theoretical estimates based on available data. 
          Trust indices reflect data quality limitations from Folha_IA_extra.xlsx.
          Blocked metrics (OEE, Availability, etc.) cannot be simulated.
        </p>
      </div>
    </div>
  );

  // Render step 3: Confirm
  const renderStep3 = () => (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-emerald-400">
        <Check className="w-4 h-4" />
        <h4 className="text-sm font-medium">Confirm Changes</h4>
      </div>

      {/* Summary */}
      <div className="p-4 bg-gray-800 rounded-lg space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400">Change Type</span>
          <span className="text-sm text-white font-medium">{selectedConfig?.title}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400">Scenario ID</span>
          <span className="text-xs text-gray-300 font-mono">{scenarioId.slice(0, 8)}...</span>
        </div>
        
        {Object.entries(fieldValues).map(([key, value]) => {
          const field = selectedConfig?.fields.find(f => f.key === key);
          return (
            <div key={key} className="flex items-center justify-between">
              <span className="text-xs text-gray-400">{field?.label || key}</span>
              <span className="text-sm text-white">
                {value}
                {field?.suffix}
              </span>
            </div>
          );
        })}
      </div>

      {/* Impact Summary */}
      {impactPreview && impactPreview.length > 0 && (
        <div className="p-4 bg-emerald-950/30 border border-emerald-900/50 rounded-lg">
          <h5 className="text-xs text-emerald-400 font-medium mb-2">Expected Impact (Theoretical)</h5>
          <div className="space-y-1">
            {impactPreview.map((impact, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-gray-300">{impact.metricLabel}</span>
                  <span className={`text-[10px] px-1 rounded ${getTrustColor(impact.trustIndex)}`}>
                    {impact.trustIndex}%
                  </span>
                </div>
                {impact.change !== null && (
                  <span className={impact.change > 0 ? 'text-red-400' : 'text-emerald-400'}>
                    {impact.change > 0 ? '+' : ''}{impact.change.toFixed(1)}%
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Blocked Metrics Reminder */}
      {blockedMetricsInSimulation.length > 0 && (
        <div className="p-3 bg-gray-800 border border-gray-700 rounded flex items-start gap-2">
          <Ban className="w-4 h-4 text-gray-500 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-gray-400">
            {blockedMetricsInSimulation.length} blocked metrics were excluded from simulation.
            These require additional data sources to simulate.
          </p>
        </div>
      )}
    </div>
  );

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-700">
        <h3 className="text-lg font-semibold text-white">Apply Delta to Scenario</h3>
        <p className="text-sm text-gray-400 mt-1">
          Step {step} of 3: {step === 1 ? 'Configure' : step === 2 ? 'Preview' : 'Confirm'}
        </p>
        
        {/* Progress */}
        <div className="flex items-center gap-2 mt-4">
          {[1, 2, 3].map(s => (
            <div key={s} className="flex items-center">
              <div className={`
                w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium
                ${s < step ? 'bg-emerald-500 text-white' :
                  s === step ? 'bg-blue-500 text-white' :
                  'bg-gray-700 text-gray-400'
                }
              `}>
                {s < step ? <Check className="w-4 h-4" /> : s}
              </div>
              {s < 3 && (
                <div className={`w-12 h-0.5 ${s < step ? 'bg-emerald-500' : 'bg-gray-700'}`} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        {step === 1 && renderStep1()}
        {step === 2 && renderStep2()}
        {step === 3 && renderStep3()}
      </div>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-gray-700 flex items-center justify-between">
        <button
          onClick={step === 1 ? onCancel : () => setStep(step - 1)}
          className="flex items-center gap-1 px-4 py-2 text-gray-400 hover:text-white transition-colors"
        >
          {step === 1 ? (
            <>
              <X className="w-4 h-4" />
              Cancel
            </>
          ) : (
            <>
              <ChevronLeft className="w-4 h-4" />
              Back
            </>
          )}
        </button>

        {step === 1 && (
          <button
            onClick={simulateImpact}
            disabled={!selectedType || isSimulating}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded font-medium transition-colors"
          >
            {isSimulating ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Simulating via API...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Simulate Impact
              </>
            )}
          </button>
        )}

        {step === 2 && (
          <button
            onClick={() => setStep(3)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded font-medium transition-colors"
          >
            Continue
            <ChevronRight className="w-4 h-4" />
          </button>
        )}

        {step === 3 && (
          <button
            onClick={handleComplete}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded font-medium transition-colors"
          >
            <Check className="w-4 h-4" />
            Apply Delta
          </button>
        )}
      </div>
    </div>
  );
}

export default DeltaWizard;
