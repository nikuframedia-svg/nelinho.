/**
 * Citation Panel Component
 * ========================
 * 
 * Displays citations from Copilot responses.
 * Each citation shows: source_type, reference, confidence, snippet.
 * 
 * Source: src/copilot/schemas.py Citation
 */

import { useState } from 'react';
import {
  BookOpen,
  Database,
  Calculator,
  Search,
  ChevronDown,
  ChevronUp,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Info,
} from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

export interface Citation {
  source_type: 'semantic_query' | 'explain_api' | 'entity_lookup' | 'calculation';
  source_ref: string;
  confidence: number;
  snippet?: string;
}

interface CitationPanelProps {
  citations: Citation[];
  variant?: 'panel' | 'inline' | 'compact';
  className?: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

function getSourceIcon(sourceType: Citation['source_type']) {
  switch (sourceType) {
    case 'semantic_query':
      return <Database size={14} />;
    case 'explain_api':
      return <BookOpen size={14} />;
    case 'entity_lookup':
      return <Search size={14} />;
    case 'calculation':
      return <Calculator size={14} />;
    default:
      return <Info size={14} />;
  }
}

function getSourceLabel(sourceType: Citation['source_type']) {
  switch (sourceType) {
    case 'semantic_query':
      return 'Semantic Query';
    case 'explain_api':
      return 'Explain API';
    case 'entity_lookup':
      return 'Entity Lookup';
    case 'calculation':
      return 'Calculation';
    default:
      return 'Unknown';
  }
}

function getConfidenceStyle(confidence: number) {
  if (confidence >= 0.8) return { color: 'text-emerald-400', bg: 'bg-emerald-500/20', label: 'High' };
  if (confidence >= 0.5) return { color: 'text-amber-400', bg: 'bg-amber-500/20', label: 'Medium' };
  return { color: 'text-red-400', bg: 'bg-red-500/20', label: 'Low' };
}

// ═══════════════════════════════════════════════════════════════════════════════
// SINGLE CITATION ITEM
// ═══════════════════════════════════════════════════════════════════════════════

function CitationItem({ citation, expanded = false }: { citation: Citation; expanded?: boolean }) {
  const [isExpanded, setIsExpanded] = useState(expanded);
  const confidence = getConfidenceStyle(citation.confidence);

  return (
    <div className="border border-slate-700/50 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-slate-800/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`p-1.5 rounded ${confidence.bg} ${confidence.color}`}>
            {getSourceIcon(citation.source_type)}
          </div>
          <div className="text-left">
            <p className="text-sm text-white font-medium">
              {getSourceLabel(citation.source_type)}
            </p>
            <p className="text-xs text-slate-400 truncate max-w-xs">
              {citation.source_ref}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs ${confidence.bg} ${confidence.color}`}>
            <Shield size={10} />
            <span>{Math.round(citation.confidence * 100)}%</span>
          </div>
          {isExpanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
        </div>
      </button>
      
      {isExpanded && (
        <div className="p-3 bg-slate-800/30 border-t border-slate-700/50">
          <div className="space-y-3">
            <div>
              <p className="text-xs text-slate-500 mb-1">Source Reference</p>
              <code className="text-xs text-blue-300 bg-slate-900 px-2 py-1 rounded block overflow-x-auto">
                {citation.source_ref}
              </code>
            </div>
            {citation.snippet && (
              <div>
                <p className="text-xs text-slate-500 mb-1">Data Snippet</p>
                <pre className="text-xs text-slate-300 bg-slate-900 px-3 py-2 rounded overflow-x-auto">
                  {citation.snippet}
                </pre>
              </div>
            )}
            <div className="flex items-center gap-4 text-xs text-slate-500">
              <span>Confidence: {confidence.label} ({Math.round(citation.confidence * 100)}%)</span>
              <span>Type: {getSourceLabel(citation.source_type)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function CitationPanel({
  citations,
  variant = 'panel',
  className = '',
}: CitationPanelProps) {
  if (!citations || citations.length === 0) {
    return null;
  }

  // Calculate overall confidence
  const avgConfidence = citations.reduce((acc, c) => acc + c.confidence, 0) / citations.length;
  const overallStyle = getConfidenceStyle(avgConfidence);

  // Compact variant - just show count
  if (variant === 'compact') {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <BookOpen size={14} className="text-blue-400" />
        <span className="text-xs text-slate-400">{citations.length} citations</span>
        <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] ${overallStyle.bg} ${overallStyle.color}`}>
          <Shield size={8} />
          {Math.round(avgConfidence * 100)}%
        </div>
      </div>
    );
  }

  // Inline variant - show badges
  if (variant === 'inline') {
    return (
      <div className={`flex flex-wrap items-center gap-2 ${className}`}>
        {citations.map((citation, idx) => {
          const style = getConfidenceStyle(citation.confidence);
          return (
            <div
              key={idx}
              className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs ${style.bg} ${style.color}`}
              title={`${getSourceLabel(citation.source_type)}: ${citation.source_ref}`}
            >
              {getSourceIcon(citation.source_type)}
              <span>{Math.round(citation.confidence * 100)}%</span>
            </div>
          );
        })}
      </div>
    );
  }

  // Panel variant (default)
  return (
    <div className={`bg-slate-800/30 border border-slate-700/50 rounded-xl ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-700/50">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/20 rounded-lg">
            <BookOpen size={18} className="text-blue-400" />
          </div>
          <div>
            <h4 className="font-medium text-white">Evidence Citations</h4>
            <p className="text-xs text-slate-400">{citations.length} sources referenced</p>
          </div>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${overallStyle.bg}`}>
          {avgConfidence >= 0.8 ? (
            <CheckCircle2 size={16} className={overallStyle.color} />
          ) : avgConfidence >= 0.5 ? (
            <AlertTriangle size={16} className={overallStyle.color} />
          ) : (
            <AlertTriangle size={16} className={overallStyle.color} />
          )}
          <span className={`text-sm font-medium ${overallStyle.color}`}>
            {overallStyle.label} Confidence
          </span>
        </div>
      </div>

      {/* Citations List */}
      <div className="p-4 space-y-2">
        {citations.map((citation, idx) => (
          <CitationItem key={idx} citation={citation} expanded={citations.length === 1} />
        ))}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 bg-slate-900/30 border-t border-slate-700/50 rounded-b-xl">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Info size={12} />
          <span>All Copilot responses require evidence citations. Responses without evidence are blocked.</span>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// INSUFFICIENT EVIDENCE WARNING
// ═══════════════════════════════════════════════════════════════════════════════

export function InsufficientEvidenceWarning({ className = '' }: { className?: string }) {
  return (
    <div className={`p-4 bg-red-500/10 border border-red-500/30 rounded-xl ${className}`}>
      <div className="flex items-start gap-3">
        <div className="p-2 bg-red-500/20 rounded-lg">
          <AlertTriangle size={20} className="text-red-400" />
        </div>
        <div>
          <h4 className="font-medium text-red-300">Insufficient Evidence</h4>
          <p className="text-sm text-slate-400 mt-1">
            This response could not be verified with sufficient evidence from the data sources.
            The content has been blocked to prevent potential misinformation.
          </p>
          <p className="text-xs text-slate-500 mt-2">
            Copilot requires at least one citation with confidence ≥ 50% to display a response.
          </p>
        </div>
      </div>
    </div>
  );
}

export default CitationPanel;

