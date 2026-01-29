import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { 
  Sparkles, 
  CheckCircle2,
  TrendingUp,
  Loader2,
  Eye,
} from 'lucide-react';
import { copilotApi, decisionsApi } from '../lib/api';
import { Button } from './ui/Button';
import { SandboxVisualizer } from './SandboxVisualizer';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/Dialog';

interface Recommendation {
  priority?: number;
  category?: string;
  title: string;
  description: string;
  impact_metric?: string;
  impact_value?: number;
  affected_phases?: string[];
  suggested_actions?: string[];
  data_evidence?: Record<string, any>;
  action_type?: string; // "INCREASE_SS", "ADJUST_PRICE", etc.
  target?: string; // SKU ID, product ID, etc.
  risk_level?: 'LOW' | 'MEDIUM' | 'HIGH';
  estimated_impact?: Record<string, number>; // { kpi_otd: 0.02, inventory_level: -50 }
}

interface SuggestionsPanelProps {
  className?: string;
}

export function SuggestionsPanel({ className }: SuggestionsPanelProps) {
  const [selectedSuggestion, setSelectedSuggestion] = useState<Recommendation | null>(null);
  const [isSandboxModalOpen, setIsSandboxModalOpen] = useState(false);
  const [sandboxResult, setSandboxResult] = useState<any>(null);

  // Fetch recommendations
  const { data: recommendations, isLoading } = useQuery<Recommendation[]>({
    queryKey: ['copilot', 'recommendations'],
    queryFn: () => copilotApi.getRecommendations(),
    staleTime: 10 * 60 * 1000, // 10 minutos
    retry: false,
  });

  // Sandbox execution mutation
  const sandboxMutation = useMutation({
    mutationFn: (data: {
      action_type: string;
      target?: string;
      params?: Record<string, any>;
      capture_state?: string[];
    }) => copilotApi.executeSandbox(data),
    onSuccess: (result) => {
      setSandboxResult(result);
      setIsSandboxModalOpen(true);
    },
  });

  // Decision proposal mutation
  const proposeMutation = useMutation({
    mutationFn: (data: {
      title: string;
      action_type: string;
      target: string;
      sandbox_result?: Record<string, any>;
      before_state: Record<string, any>;
      after_state?: Record<string, any>;
    }) => decisionsApi.propose(data),
    onSuccess: () => {
      alert('Decision proposal created successfully! View it in the Decision Ledger.');
      setIsSandboxModalOpen(false);
    },
  });

  const handlePreviewInSandbox = async (suggestion: Recommendation) => {
    if (!suggestion.action_type) {
      alert('This suggestion does not have an action type defined.');
      return;
    }

    setSelectedSuggestion(suggestion);
    try {
      await sandboxMutation.mutateAsync({
        action_type: suggestion.action_type,
        target: suggestion.target,
        params: suggestion.data_evidence || {},
        capture_state: ['kpis', 'inventory', 'schedules'],
      });
    } catch (err) {
      alert('Failed to preview in sandbox: ' + (err as Error).message);
    }
  };

  const handleApproveAndExecute = async (suggestion: Recommendation) => {
    if (!sandboxResult || !selectedSuggestion) {
      alert('Please preview in sandbox first to see the impact.');
      return;
    }

    if (!window.confirm(`Create decision proposal for "${suggestion.title}"?`)) {
      return;
    }

    try {
      await proposeMutation.mutateAsync({
        title: suggestion.title,
        action_type: suggestion.action_type || 'GENERIC_ACTION',
        target: suggestion.target || 'UNKNOWN',
        sandbox_result: sandboxResult,
        before_state: sandboxResult.before_state,
        after_state: sandboxResult.after_state,
      });
    } catch (err) {
      alert('Failed to propose decision: ' + (err as Error).message);
    }
  };

  const getRiskBadge = (riskLevel?: string) => {
    const badges: Record<string, { bg: string; text: string }> = {
      LOW: { bg: 'bg-emerald-100', text: 'text-emerald-700' },
      MEDIUM: { bg: 'bg-amber-100', text: 'text-amber-700' },
      HIGH: { bg: 'bg-red-100', text: 'text-red-700' },
    };
    return badges[riskLevel || 'MEDIUM'] || badges.MEDIUM;
  };

  const getCategoryColor = (category?: string) => {
    switch (category) {
      case 'QUALITY':
        return 'from-red-400 to-red-600';
      case 'PERFORMANCE':
        return 'from-amber-400 to-amber-600';
      case 'MAINTENANCE':
        return 'from-blue-400 to-blue-600';
      case 'STANDARD_WORK':
        return 'from-purple-400 to-purple-600';
      default:
        return 'from-slate-400 to-slate-600';
    }
  };

  if (isLoading) {
    return (
      <div className={`bg-white rounded-2xl p-6 border border-slate-200 ${className || ''}`}>
        <div className="flex items-center gap-2 text-slate-500">
          <Loader2 size={20} className="animate-spin" />
          <span>Loading AI suggestions...</span>
        </div>
      </div>
    );
  }

  if (!recommendations || recommendations.length === 0) {
    return (
      <div className={`bg-white rounded-2xl p-6 border border-slate-200 ${className || ''}`}>
        <div className="text-center py-8">
          <Sparkles size={48} className="text-slate-300 mx-auto mb-2" />
          <p className="text-slate-500">No AI suggestions available at this time.</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className={`bg-white rounded-2xl p-6 border border-slate-200 ${className || ''}`}>
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center">
            <Sparkles size={20} className="text-white" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-[#1a2744]">AI Suggestions</h3>
            <p className="text-sm text-slate-500">Actionable recommendations based on data analysis</p>
          </div>
        </div>

        <div className="space-y-4">
          {recommendations.slice(0, 5).map((suggestion, index) => {
            const riskBadge = getRiskBadge(suggestion.risk_level);
            return (
              <div
                key={index}
                className="border border-slate-200 rounded-xl p-4 hover:border-slate-300 transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-start gap-3 flex-1">
                    <div
                      className={`w-8 h-8 rounded-full bg-gradient-to-br ${getCategoryColor(
                        suggestion.category
                      )} flex items-center justify-center text-white font-bold text-sm flex-shrink-0`}
                    >
                      {suggestion.priority || index + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="font-semibold text-[#1a2744] mb-1">{suggestion.title}</h4>
                      <p className="text-sm text-slate-600 leading-relaxed">{suggestion.description}</p>
                    </div>
                  </div>
                  {suggestion.risk_level && (
                    <span className={`px-2 py-1 rounded text-xs font-medium ${riskBadge.bg} ${riskBadge.text}`}>
                      {suggestion.risk_level} RISK
                    </span>
                  )}
                </div>

                {/* Impact Preview */}
                {suggestion.estimated_impact && Object.keys(suggestion.estimated_impact).length > 0 && (
                  <div className="mb-3 pl-11">
                    <p className="text-xs font-semibold text-slate-700 mb-1">Estimated Impact:</p>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(suggestion.estimated_impact).map(([metric, value]) => (
                        <div key={metric} className="flex items-center gap-1 text-xs">
                          <TrendingUp size={12} className={value >= 0 ? 'text-emerald-600' : 'text-red-600'} />
                          <span className="text-slate-600">
                            {metric}: {value >= 0 ? '+' : ''}{typeof value === 'number' ? value.toFixed(2) : value}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex items-center gap-2 pl-11">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handlePreviewInSandbox(suggestion)}
                    disabled={sandboxMutation.isPending || !suggestion.action_type}
                    loading={sandboxMutation.isPending && selectedSuggestion === suggestion}
                    icon={<Eye size={14} />}
                  >
                    Preview in Sandbox
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleApproveAndExecute(suggestion)}
                    disabled={proposeMutation.isPending || !sandboxResult}
                    loading={proposeMutation.isPending}
                    icon={<CheckCircle2 size={14} />}
                  >
                    Approve & Propose
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Sandbox Visualizer Modal */}
      {selectedSuggestion && sandboxResult && (
        <Dialog open={isSandboxModalOpen} onOpenChange={setIsSandboxModalOpen}>
          <DialogContent className="sm:max-w-[900px] max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Sandbox Preview: {selectedSuggestion.title}</DialogTitle>
            </DialogHeader>
            <SandboxVisualizer
              beforeState={sandboxResult.before_state}
              afterState={sandboxResult.after_state}
              deltas={sandboxResult.deltas}
              actualImpact={sandboxResult.actual_impact}
              onPropose={() => handleApproveAndExecute(selectedSuggestion)}
              isProposing={proposeMutation.isPending}
            />
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}



