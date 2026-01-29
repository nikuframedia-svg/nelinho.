/**
 * Universal Inspector Component
 * ==============================
 * 
 * Allows inspection of any value in the UI.
 * Shows lineage, trust, formula, and how to improve.
 * 
 * Usage:
 * <UniversalInspector value={someValue} metricId="backlog_hours">
 *   {children}
 * </UniversalInspector>
 */

import React, { useState, useRef, useEffect } from 'react';
import { 
  Info, 
  Shield, 
  AlertTriangle, 
  XCircle, 
  ChevronRight,
  GitBranch,
  Calculator,
  Lightbulb,
  Copy,
  Check,
} from 'lucide-react';

interface TrustInfo {
  index: number;
  coverage?: number;
  status: 'OK' | 'WARNING' | 'DEGRADED' | 'BLOCKED';
  warnings?: string[];
}

interface Lineage {
  source: string;
  table?: string;
  query_hash?: string;
  data_version?: string;
  ingestion_id?: string;
}

interface ExplainInfo {
  formula?: string;
  formula_human?: string;
  assumptions?: string[];
  forbidden_claims?: string[];
}

interface InspectorData {
  value: number | string | null;
  unit?: string;
  semantic_label?: string;
  trust?: TrustInfo;
  lineage?: Lineage;
  explain?: ExplainInfo;
  how_to_improve?: string[];
}

interface UniversalInspectorProps {
  data: InspectorData;
  metricId?: string;
  children: React.ReactNode;
  position?: 'top' | 'bottom' | 'left' | 'right';
}

export function UniversalInspector({
  data,
  metricId,
  children,
  position = 'bottom',
}: UniversalInspectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current && 
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Copy to clipboard
  const copyLineage = () => {
    const text = JSON.stringify(data.lineage, null, 2);
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Trust status styling
  const getTrustColor = (status?: string) => {
    switch (status) {
      case 'OK': return 'text-emerald-500 bg-emerald-500/10';
      case 'WARNING': return 'text-amber-500 bg-amber-500/10';
      case 'DEGRADED': return 'text-orange-500 bg-orange-500/10';
      case 'BLOCKED': return 'text-red-500 bg-red-500/10';
      default: return 'text-gray-400 bg-gray-500/10';
    }
  };

  const getTrustIcon = (status?: string) => {
    switch (status) {
      case 'OK': return <Shield className="w-4 h-4" />;
      case 'WARNING': return <AlertTriangle className="w-4 h-4" />;
      case 'DEGRADED': return <AlertTriangle className="w-4 h-4" />;
      case 'BLOCKED': return <XCircle className="w-4 h-4" />;
      default: return <Info className="w-4 h-4" />;
    }
  };

  // Position classes
  const positionClasses = {
    top: 'bottom-full mb-2',
    bottom: 'top-full mt-2',
    left: 'right-full mr-2',
    right: 'left-full ml-2',
  };

  return (
    <div ref={containerRef} className="relative inline-block">
      {/* Trigger - wraps children */}
      <div 
        className="cursor-help group relative"
        onClick={() => setIsOpen(!isOpen)}
      >
        {children}
        
        {/* Small indicator */}
        <span className="absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <Info className="w-3 h-3 text-blue-400" />
        </span>
      </div>

      {/* Inspector Panel */}
      {isOpen && (
        <div
          ref={panelRef}
          className={`
            absolute z-50 w-80 
            bg-gray-900 border border-gray-700 rounded-lg shadow-xl
            ${positionClasses[position]}
          `}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
            <div className="flex items-center gap-2">
              <Info className="w-4 h-4 text-blue-400" />
              <span className="font-medium text-white text-sm">
                {metricId || 'Value Inspector'}
              </span>
            </div>
            {data.trust && (
              <span className={`
                flex items-center gap-1 px-2 py-1 rounded text-xs font-medium
                ${getTrustColor(data.trust.status)}
              `}>
                {getTrustIcon(data.trust.status)}
                {data.trust.status}
              </span>
            )}
          </div>

          {/* Content */}
          <div className="p-4 space-y-4 max-h-96 overflow-y-auto">
            {/* Value & Semantic Label */}
            <div>
              <div className="text-2xl font-bold text-white">
                {data.value ?? 'N/A'}
                {data.unit && (
                  <span className="text-sm font-normal text-gray-400 ml-1">
                    {data.unit}
                  </span>
                )}
              </div>
              {data.semantic_label && (
                <p className="text-xs text-amber-400 mt-1">
                  ⚠️ {data.semantic_label}
                </p>
              )}
            </div>

            {/* Trust Section */}
            {data.trust && (
              <div className="space-y-2">
                <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wide flex items-center gap-1">
                  <Shield className="w-3 h-3" /> Trust
                </h4>
                <div className="bg-gray-800 rounded p-3 space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Index</span>
                    <span className="text-white font-medium">{data.trust.index}%</span>
                  </div>
                  {data.trust.coverage !== undefined && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Coverage</span>
                      <span className="text-white font-medium">{data.trust.coverage}%</span>
                    </div>
                  )}
                  {/* Trust bar */}
                  <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div 
                      className={`h-full ${
                        data.trust.index >= 80 ? 'bg-emerald-500' :
                        data.trust.index >= 60 ? 'bg-amber-500' :
                        data.trust.index >= 40 ? 'bg-orange-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${data.trust.index}%` }}
                    />
                  </div>
                  {/* Warnings */}
                  {data.trust.warnings && data.trust.warnings.length > 0 && (
                    <div className="space-y-1 pt-2">
                      {data.trust.warnings.map((w, i) => (
                        <p key={i} className="text-xs text-amber-400 flex items-start gap-1">
                          <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                          {w}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Lineage Section */}
            {data.lineage && (
              <div className="space-y-2">
                <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wide flex items-center gap-1">
                  <GitBranch className="w-3 h-3" /> Lineage
                </h4>
                <div className="bg-gray-800 rounded p-3 space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Source</span>
                    <span className="text-blue-400 font-mono text-xs">
                      {data.lineage.source}
                    </span>
                  </div>
                  {data.lineage.table && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Table</span>
                      <span className="text-blue-400 font-mono text-xs">
                        {data.lineage.table}
                      </span>
                    </div>
                  )}
                  {data.lineage.query_hash && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Query Hash</span>
                      <span className="text-gray-300 font-mono text-xs">
                        {data.lineage.query_hash.slice(0, 8)}...
                      </span>
                    </div>
                  )}
                  <button
                    onClick={copyLineage}
                    className="w-full mt-2 flex items-center justify-center gap-1 text-xs text-gray-400 hover:text-white transition-colors"
                  >
                    {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    {copied ? 'Copied!' : 'Copy lineage'}
                  </button>
                </div>
              </div>
            )}

            {/* Formula Section */}
            {data.explain && (
              <div className="space-y-2">
                <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wide flex items-center gap-1">
                  <Calculator className="w-3 h-3" /> Formula
                </h4>
                <div className="bg-gray-800 rounded p-3">
                  {data.explain.formula && (
                    <code className="text-xs text-emerald-400 block mb-2">
                      {data.explain.formula}
                    </code>
                  )}
                  {data.explain.formula_human && (
                    <p className="text-xs text-gray-300">
                      {data.explain.formula_human}
                    </p>
                  )}
                  {data.explain.assumptions && data.explain.assumptions.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-gray-700">
                      <p className="text-xs text-gray-400 mb-1">Assumptions:</p>
                      <ul className="space-y-1">
                        {data.explain.assumptions.map((a, i) => (
                          <li key={i} className="text-xs text-gray-300 flex items-start gap-1">
                            <ChevronRight className="w-3 h-3 mt-0.5 flex-shrink-0" />
                            {a}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Forbidden Claims */}
            {data.explain?.forbidden_claims && data.explain.forbidden_claims.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-medium text-red-400 uppercase tracking-wide flex items-center gap-1">
                  <XCircle className="w-3 h-3" /> Forbidden Claims
                </h4>
                <div className="bg-red-950/50 border border-red-900 rounded p-3">
                  <ul className="space-y-1">
                    {data.explain.forbidden_claims.map((c, i) => (
                      <li key={i} className="text-xs text-red-300 flex items-start gap-1">
                        <XCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                        {c}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* How to Improve */}
            {data.how_to_improve && data.how_to_improve.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-medium text-emerald-400 uppercase tracking-wide flex items-center gap-1">
                  <Lightbulb className="w-3 h-3" /> How to Improve
                </h4>
                <div className="bg-emerald-950/50 border border-emerald-900 rounded p-3">
                  <ul className="space-y-2">
                    {data.how_to_improve.map((action, i) => (
                      <li key={i} className="text-xs text-emerald-300 flex items-start gap-2">
                        <span className="bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded font-medium">
                          {i + 1}
                        </span>
                        {action}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default UniversalInspector;


