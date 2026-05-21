import { TrendingUp, TrendingDown, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { Button } from './ui/Button';

interface SandboxVisualizerProps {
  beforeState: Record<string, any>;
  afterState: Record<string, any>;
  deltas: Record<string, any>;
  actualImpact?: Record<string, any>;
  onPropose?: () => void;
  isProposing?: boolean;
}

export function SandboxVisualizer({
  beforeState,
  afterState,
  deltas,
  actualImpact,
  onPropose,
  isProposing = false,
}: SandboxVisualizerProps) {
  // Helper to format values
  const formatValue = (value: unknown): string => {
    if (typeof value === 'number') {
      return value.toFixed(2);
    }
    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No';
    }
    if (value === null || value === undefined) {
      return '—';
    }
    return String(value);
  };

  // Helper to determine if a delta is positive/negative
  const getDeltaColor = (delta: unknown): 'positive' | 'negative' | 'neutral' => {
    if (typeof delta === 'number') {
      return delta > 0 ? 'positive' : delta < 0 ? 'negative' : 'neutral';
    }
    return 'neutral';
  };

  // Extract KPI changes
  const kpiChanges: Array<{ metric: string; before: unknown; after: unknown; delta: unknown; unit?: string }> = [];
  const commonMetrics = ['kpi_otd', 'oee', 'quality_fpy', 'inventory_level', 'margin', 'availability', 'performance'];

  commonMetrics.forEach((metric) => {
    if (beforeState[metric] !== undefined || afterState[metric] !== undefined) {
      const before = beforeState[metric];
      const after = afterState[metric];
      const delta = deltas[metric] ?? (after !== undefined && before !== undefined ? after - before : undefined);

      kpiChanges.push({
        metric: metric.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
        before,
        after,
        delta,
        unit: metric.includes('_') && metric !== 'inventory_level' ? '%' : '',
      });
    }
  });

  // Extract other changes
  const otherChanges: Array<{ key: string; before: unknown; after: unknown; delta: unknown }> = [];
  Object.keys(beforeState).forEach((key) => {
    if (!commonMetrics.includes(key) && afterState[key] !== undefined) {
      otherChanges.push({
        key,
        before: beforeState[key],
        after: afterState[key],
        delta: deltas[key],
      });
    }
  });

  return (
    <div className="py-4 space-y-6">
      {/* Summary */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <CheckCircle2 size={20} className="text-blue-600 mt-0.5" />
          <div>
            <h4 className="font-semibold text-blue-900 mb-1">Sandbox Execution Successful</h4>
            <p className="text-sm text-blue-700">
              This preview shows the simulated impact. No actual changes have been made to production data.
            </p>
          </div>
        </div>
      </div>

      {/* KPI Impact Table */}
      {kpiChanges.length > 0 && (
        <div>
          <h4 className="font-semibold text-[#1a2744] mb-3">KPI Impact</h4>
          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase">Metric</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-600 uppercase">Before</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-600 uppercase">After</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-600 uppercase">Change</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {kpiChanges.map((change) => {
                  const deltaColor = getDeltaColor(change.delta);
                  return (
                    <tr key={change.metric} className="hover:bg-slate-50">
                      <td className="px-4 py-3 text-sm font-medium text-[#1a2744]">{change.metric}</td>
                      <td className="px-4 py-3 text-sm text-slate-600 text-right">
                        {formatValue(change.before)}{change.unit}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-600 text-right">
                        {formatValue(change.after)}{change.unit}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {change.delta !== undefined && change.delta !== null ? (
                          <div
                            className={`inline-flex items-center gap-1 text-sm font-medium ${
                              deltaColor === 'positive'
                                ? 'text-emerald-600'
                                : deltaColor === 'negative'
                                ? 'text-red-600'
                                : 'text-slate-600'
                            }`}
                          >
                            {deltaColor === 'positive' ? (
                              <TrendingUp size={14} />
                            ) : deltaColor === 'negative' ? (
                              <TrendingDown size={14} />
                            ) : null}
                            {deltaColor === 'positive' ? '+' : ''}
                            {formatValue(change.delta)}
                            {change.unit}
                          </div>
                        ) : (
                          <span className="text-sm text-slate-400">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Before/After Comparison */}
      {(Object.keys(beforeState).length > 0 || Object.keys(afterState).length > 0) && (
        <div>
          <h4 className="font-semibold text-[#1a2744] mb-3">State Comparison</h4>
          <div className="grid grid-cols-2 gap-4">
            <div className="border border-slate-200 rounded-lg p-4">
              <h5 className="text-sm font-semibold text-slate-700 mb-2">Before State</h5>
              <pre className="text-xs bg-slate-50 p-3 rounded border border-slate-200 overflow-x-auto">
                {JSON.stringify(beforeState, null, 2)}
              </pre>
            </div>
            <div className="border border-slate-200 rounded-lg p-4">
              <h5 className="text-sm font-semibold text-slate-700 mb-2">After State</h5>
              <pre className="text-xs bg-slate-50 p-3 rounded border border-slate-200 overflow-x-auto">
                {JSON.stringify(afterState, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Deltas */}
      {Object.keys(deltas).length > 0 && (
        <div>
          <h4 className="font-semibold text-[#1a2744] mb-3">Calculated Deltas</h4>
          <div className="border border-slate-200 rounded-lg p-4 bg-slate-50">
            <pre className="text-xs overflow-x-auto">{JSON.stringify(deltas, null, 2)}</pre>
          </div>
        </div>
      )}

      {/* Actual Impact (if available) */}
      {actualImpact && Object.keys(actualImpact).length > 0 && (
        <div>
          <h4 className="font-semibold text-[#1a2744] mb-3">Actual Impact</h4>
          <div className="border border-emerald-200 bg-emerald-50 rounded-lg p-4">
            <pre className="text-xs overflow-x-auto">{JSON.stringify(actualImpact, null, 2)}</pre>
          </div>
        </div>
      )}

      {/* Risk Assessment */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <AlertTriangle size={20} className="text-amber-600 mt-0.5" />
          <div>
            <h4 className="font-semibold text-amber-900 mb-1">Risk Assessment</h4>
            <ul className="text-sm text-amber-700 space-y-1">
              <li>• Sandbox execution completed successfully</li>
              <li>• All changes can be rolled back within 24 hours</li>
              <li>• Review the KPI impact above before proceeding</li>
              <li>• Decision approval workflow will be required</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Action Button */}
      {onPropose && (
        <div className="flex justify-end pt-2 border-t border-slate-200">
          <Button
            variant="primary"
            onClick={onPropose}
            disabled={isProposing}
            loading={isProposing}
            icon={<CheckCircle2 size={16} />}
          >
            Create Decision Proposal
          </Button>
        </div>
      )}
    </div>
  );
}










