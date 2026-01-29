/**
 * Data Repair Suggestions Component
 * ===================================
 * 
 * Displays actionable suggestions for improving data quality.
 * Used when metrics are blocked or have low trust.
 * 
 * Usage:
 * <DataRepairSuggestions 
 *   metricId="oee_real"
 *   suggestions={[...]}
 *   onAccept={(id) => handleAccept(id)}
 * />
 */

import { useState } from 'react';
import { 
  Lightbulb, 
  Wrench,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Play,
  Clock,
  TrendingUp,
  ExternalLink,
  ArrowRight,
} from 'lucide-react';

interface Suggestion {
  id: string;
  title: string;
  description: string;
  action_type: 'data_improvement' | 'process_change' | 'training' | 'integration';
  estimated_impact?: {
    trust_increase?: number;
    coverage_increase?: number;
    time_to_implement?: string;
  };
  difficulty: 'easy' | 'medium' | 'hard';
  priority: 'high' | 'medium' | 'low';
  steps?: string[];
  required_data?: string[];
}

interface DataRepairSuggestionsProps {
  metricId?: string;
  metricName?: string;
  currentTrust?: number;
  blockedReason?: string;
  suggestions: Suggestion[];
  onAccept?: (suggestionId: string) => void;
  onDismiss?: (suggestionId: string) => void;
  compact?: boolean;
}

export function DataRepairSuggestions({
  metricName,
  currentTrust,
  blockedReason,
  suggestions,
  onAccept,
  onDismiss,
  compact = false,
}: DataRepairSuggestionsProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [acceptedIds, setAcceptedIds] = useState<Set<string>>(new Set());

  // Difficulty colors
  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'easy': return 'text-emerald-400 bg-emerald-400/10';
      case 'medium': return 'text-amber-400 bg-amber-400/10';
      case 'hard': return 'text-red-400 bg-red-400/10';
      default: return 'text-gray-400 bg-gray-400/10';
    }
  };

  // Priority colors
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'text-red-400';
      case 'medium': return 'text-amber-400';
      case 'low': return 'text-blue-400';
      default: return 'text-gray-400';
    }
  };

  // Action type icons
  const getActionIcon = (actionType: string) => {
    switch (actionType) {
      case 'data_improvement': return <Wrench className="w-4 h-4" />;
      case 'process_change': return <TrendingUp className="w-4 h-4" />;
      case 'training': return <Lightbulb className="w-4 h-4" />;
      case 'integration': return <ExternalLink className="w-4 h-4" />;
      default: return <Lightbulb className="w-4 h-4" />;
    }
  };

  const handleAccept = (id: string) => {
    setAcceptedIds(new Set([...acceptedIds, id]));
    onAccept?.(id);
  };

  // Sort by priority
  const sortedSuggestions = [...suggestions].sort((a, b) => {
    const priorityOrder = { high: 0, medium: 1, low: 2 };
    return priorityOrder[a.priority] - priorityOrder[b.priority];
  });

  if (compact) {
    return (
      <div className="space-y-2">
        {sortedSuggestions.slice(0, 3).map((suggestion) => (
          <div 
            key={suggestion.id}
            className="flex items-center gap-2 p-2 bg-gray-800 rounded text-sm"
          >
            <span className={getPriorityColor(suggestion.priority)}>•</span>
            <span className="text-gray-300 flex-1 truncate">{suggestion.title}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded ${getDifficultyColor(suggestion.difficulty)}`}>
              {suggestion.difficulty}
            </span>
          </div>
        ))}
        {suggestions.length > 3 && (
          <p className="text-xs text-gray-500 text-center">
            +{suggestions.length - 3} more suggestions
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700 bg-gradient-to-r from-emerald-950/50 to-gray-900">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-emerald-500/20 rounded">
              <Lightbulb className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-sm font-medium text-white">
                Data Improvement Suggestions
              </h3>
              {metricName && (
                <p className="text-xs text-gray-400">for {metricName}</p>
              )}
            </div>
          </div>
          <span className="text-xs text-gray-400">
            {suggestions.length} suggestion{suggestions.length !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Blocked Reason Banner */}
        {blockedReason && (
          <div className="mt-3 p-2 bg-red-950/50 border border-red-900/50 rounded flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-red-300">{blockedReason}</p>
          </div>
        )}

        {/* Current Trust */}
        {currentTrust !== undefined && (
          <div className="mt-3 flex items-center gap-2">
            <span className="text-xs text-gray-400">Current Trust:</span>
            <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
              <div 
                className={`h-full ${
                  currentTrust >= 80 ? 'bg-emerald-500' :
                  currentTrust >= 60 ? 'bg-amber-500' :
                  currentTrust >= 40 ? 'bg-orange-500' : 'bg-red-500'
                }`}
                style={{ width: `${currentTrust}%` }}
              />
            </div>
            <span className="text-xs font-medium text-white">{currentTrust}%</span>
          </div>
        )}
      </div>

      {/* Suggestions List */}
      <div className="divide-y divide-gray-800">
        {sortedSuggestions.map((suggestion) => {
          const isExpanded = expandedId === suggestion.id;
          const isAccepted = acceptedIds.has(suggestion.id);

          return (
            <div 
              key={suggestion.id}
              className={`transition-colors ${isAccepted ? 'bg-emerald-950/20' : ''}`}
            >
              {/* Suggestion Header */}
              <div 
                className="px-4 py-3 cursor-pointer hover:bg-gray-800/50 transition-colors"
                onClick={() => setExpandedId(isExpanded ? null : suggestion.id)}
              >
                <div className="flex items-start gap-3">
                  {/* Icon */}
                  <div className={`p-1.5 rounded mt-0.5 ${
                    suggestion.action_type === 'data_improvement' 
                      ? 'bg-purple-500/20 text-purple-400' 
                      : 'bg-blue-500/20 text-blue-400'
                  }`}>
                    {getActionIcon(suggestion.action_type)}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-medium text-white truncate">
                        {suggestion.title}
                      </h4>
                      {isAccepted && (
                        <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      )}
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">
                      {suggestion.description}
                    </p>

                    {/* Tags */}
                    <div className="flex items-center gap-2 mt-2">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${getDifficultyColor(suggestion.difficulty)}`}>
                        {suggestion.difficulty}
                      </span>
                      <span className={`text-xs ${getPriorityColor(suggestion.priority)}`}>
                        {suggestion.priority} priority
                      </span>
                      {suggestion.estimated_impact?.trust_increase && (
                        <span className="text-xs text-emerald-400">
                          +{suggestion.estimated_impact.trust_increase}% trust
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Expand Icon */}
                  <button className="p-1 text-gray-400 hover:text-white">
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4" />
                    ) : (
                      <ChevronDown className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>

              {/* Expanded Content */}
              {isExpanded && (
                <div className="px-4 pb-4 space-y-4">
                  {/* Steps */}
                  {suggestion.steps && suggestion.steps.length > 0 && (
                    <div className="pl-10">
                      <h5 className="text-xs font-medium text-gray-400 mb-2">
                        Implementation Steps
                      </h5>
                      <ol className="space-y-2">
                        {suggestion.steps.map((step, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                            <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center bg-gray-800 rounded-full text-xs text-gray-400">
                              {i + 1}
                            </span>
                            {step}
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}

                  {/* Required Data */}
                  {suggestion.required_data && suggestion.required_data.length > 0 && (
                    <div className="pl-10">
                      <h5 className="text-xs font-medium text-gray-400 mb-2">
                        Required Data
                      </h5>
                      <div className="flex flex-wrap gap-2">
                        {suggestion.required_data.map((data, i) => (
                          <span 
                            key={i}
                            className="px-2 py-1 bg-gray-800 rounded text-xs text-gray-300 font-mono"
                          >
                            {data}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Impact & Time */}
                  {suggestion.estimated_impact && (
                    <div className="pl-10 flex items-center gap-4">
                      {suggestion.estimated_impact.time_to_implement && (
                        <div className="flex items-center gap-1 text-xs text-gray-400">
                          <Clock className="w-3 h-3" />
                          {suggestion.estimated_impact.time_to_implement}
                        </div>
                      )}
                      {suggestion.estimated_impact.coverage_increase && (
                        <div className="flex items-center gap-1 text-xs text-emerald-400">
                          <TrendingUp className="w-3 h-3" />
                          +{suggestion.estimated_impact.coverage_increase}% coverage
                        </div>
                      )}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="pl-10 flex gap-2">
                    {!isAccepted ? (
                      <>
                        <button
                          onClick={() => handleAccept(suggestion.id)}
                          className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-sm font-medium transition-colors"
                        >
                          <Play className="w-3 h-3" />
                          Accept & Start
                        </button>
                        <button
                          onClick={() => onDismiss?.(suggestion.id)}
                          className="flex items-center gap-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded text-sm transition-colors"
                        >
                          Dismiss
                        </button>
                      </>
                    ) : (
                      <div className="flex items-center gap-2 text-emerald-400 text-sm">
                        <CheckCircle className="w-4 h-4" />
                        Accepted - Track progress in Tasks
                        <ArrowRight className="w-3 h-3" />
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default DataRepairSuggestions;


