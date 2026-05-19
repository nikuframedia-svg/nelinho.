/**
 * CopilotMessage
 * ==============
 * 
 * Renders a single Copilot response with:
 * - Summary with intent badge
 * - Warnings banner
 * - Facts with citations and trust badges
 * - Citation warning banner (if facts lack citations)
 * - Actions with simulate buttons
 * - Expandable citations panel
 */

import { useState } from 'react';
import { ChevronDown, AlertTriangle, Shield, AlertOctagon, Ban } from 'lucide-react';
import type { CopilotResponse } from '../../lib/api';
import { CopilotCitations } from './CopilotCitations';
import { CopilotActions } from './CopilotActions';
import { CopilotMascot } from './CopilotMascot';

interface CopilotMessageProps {
  response: CopilotResponse;
  /** Q.18.ZIP.A — Mostrar header com Nelinho mascote em cima do summary. Default true. */
  showMascot?: boolean;
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRUST BADGE COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function TrustBadge({ index }: { index: number }) {
  const getStyle = () => {
    if (index >= 70) return 'bg-emerald-100 text-emerald-700 border-emerald-200';
    if (index >= 50) return 'bg-amber-100 text-amber-700 border-amber-200';
    return 'bg-red-100 text-red-700 border-red-200';
  };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${getStyle()}`}>
      <Shield size={10} />
      {index}%
    </span>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// CITATION WARNING BANNER
// ═══════════════════════════════════════════════════════════════════════════════

function CitationWarningBanner({ factsWithoutCitations }: { factsWithoutCitations: number }) {
  if (factsWithoutCitations === 0) return null;

  return (
    <div className="bg-gradient-to-r from-red-50 to-orange-50 border border-red-200/60 rounded-xl p-3 mb-4">
      <div className="flex items-start gap-2">
        <div className="w-6 h-6 rounded-lg bg-red-100 flex items-center justify-center flex-shrink-0">
          <AlertOctagon size={14} className="text-red-600" />
        </div>
        <div>
          <p className="text-sm font-semibold text-red-800">
            {factsWithoutCitations} facto{factsWithoutCitations > 1 ? 's' : ''} sem evidência
          </p>
          <p className="text-xs text-red-600/80 mt-0.5">
            Factos sem citações podem não ser fiáveis. Verifique antes de tomar decisões.
          </p>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// FACT CARD WITH TRUST
// ═══════════════════════════════════════════════════════════════════════════════

function FactCard({ 
  fact, 
}: { 
  fact: { text: string; citations?: Array<{ label: string; source_type: string; confidence?: number; trust_index?: number }> }; 
}) {
  const factCitations = fact.citations || [];
  const hasCitations = factCitations.length > 0;
  
  // Calculate average trust from citations
  const avgTrust = hasCitations 
    ? Math.round(factCitations.reduce((acc, c) => acc + (c.trust_index || c.confidence || 0) * 100, 0) / factCitations.length)
    : 0;

  return (
    <div className={`rounded-xl p-4 border shadow-sm hover:shadow-md transition-shadow duration-200 ${
      hasCitations 
        ? 'bg-slate-50/80 border-slate-200/60' 
        : 'bg-red-50/50 border-red-200/60'
    }`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <p className="text-sm text-slate-800 leading-relaxed flex-1">{fact.text || '(Sem texto)'}</p>
        {hasCitations ? (
          <TrustBadge index={avgTrust} />
        ) : (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700 border border-red-200">
            <Ban size={10} />
            Sem evidência
          </span>
        )}
      </div>
      
      {hasCitations && (
        <div className="mt-3 pt-3 border-t border-slate-200/60 flex flex-wrap gap-1.5">
          {factCitations.map((citation, cIdx) => (
            <span
              key={cIdx}
              className="text-xs px-2.5 py-1 bg-white border border-slate-200 rounded-md text-slate-700 font-medium shadow-sm citation-highlight"
              title={`${citation.label} (${citation.source_type}) - ${((citation.trust_index || citation.confidence || 0) * 100).toFixed(0)}% trust`}
            >
              {citation.label}
              {(citation.trust_index || citation.confidence) && (
                <span className={`ml-1 ${
                  (citation.trust_index || citation.confidence || 0) >= 0.7 ? 'text-emerald-600' :
                  (citation.trust_index || citation.confidence || 0) >= 0.5 ? 'text-amber-600' :
                  'text-red-600'
                }`}>
                  {((citation.trust_index || citation.confidence || 0) * 100).toFixed(0)}%
                </span>
              )}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function CopilotMessage({ response, showMascot = true }: CopilotMessageProps) {
  const [showCitations, setShowCitations] = useState(false);

  // Safe fallbacks
  const warnings = response.warnings || [];
  const hasWarnings = warnings.length > 0;
  const facts = response.facts || [];
  const actions = response.actions || [];

  // Count facts without citations
  const factsWithoutCitations = facts.filter(f => !f.citations || f.citations.length === 0).length;
  const totalCitations = facts.reduce((acc, f) => acc + (f.citations?.length || 0), 0);

  return (
    <div className="space-y-4">
      {/* Q.18.ZIP.A — Avatar Nelinho identifica visualmente que a resposta é do Copilot */}
      {showMascot ? (
        <div className="flex items-center gap-2 -mb-1">
          <CopilotMascot size="sm" className="shrink-0" />
          <span className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
            Nelinho · Copilot
          </span>
        </div>
      ) : null}

      {/* Summary */}
      <div>
        <p className="font-semibold text-slate-900 mb-2 leading-relaxed text-base">
          {response.summary || '(Sem resumo)'}
        </p>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs px-2 py-1 bg-slate-100 text-slate-600 rounded-md font-medium">
            {response.intent}
          </span>
          <span className="text-xs text-slate-400">
            {response.meta?.latency_ms || 0}ms
          </span>
          {response.meta?.validation_passed === false && (
            <span className="text-xs px-2 py-1 bg-red-100 text-red-600 rounded-md font-medium">
              Validação falhou
            </span>
          )}
        </div>
      </div>

      {/* Citation Warning Banner */}
      <CitationWarningBanner factsWithoutCitations={factsWithoutCitations} />

      {/* Warnings */}
      {hasWarnings && (
        <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/60 rounded-xl p-4 shadow-sm">
          {warnings.map((warning, idx) => (
            <div key={idx} className="flex items-start gap-3 text-yellow-800">
              <div className="w-6 h-6 rounded-lg bg-yellow-200/60 flex items-center justify-center flex-shrink-0 mt-0.5">
                <AlertTriangle size={14} className="text-yellow-700" />
              </div>
              <div className="flex-1">
                <p className="font-semibold text-sm mb-1">{warning.code}</p>
                <p className="text-xs leading-relaxed text-yellow-700/80">{warning.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Facts with Trust Badges */}
      {facts.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-bold text-slate-800 uppercase tracking-wide flex items-center gap-2">
            Factos
            {factsWithoutCitations > 0 && (
              <span className="text-xs font-normal text-red-600">
                ({factsWithoutCitations} sem evidência)
              </span>
            )}
          </h4>
          {facts.map((fact, idx) => (
            <FactCard key={idx} fact={fact} />
          ))}
        </div>
      )}

      {/* Q.35.4.1 — render único: o CopilotActions é a única secção de
          acções (Simular / Dry-run / Executar por acção). */}
      <CopilotActions actions={actions} suggestionId={response.suggestion_id} />

      {/* Citations Accordion */}
      {totalCitations > 0 && (
        <div className="border-t border-slate-200/60 pt-3">
          <button
            onClick={() => setShowCitations(!showCitations)}
            className="flex items-center justify-between w-full text-sm text-slate-600 hover:text-slate-900 transition-colors duration-150 group"
          >
            <span className="font-medium">Evidências ({totalCitations})</span>
            <div className={`transition-transform duration-200 ${showCitations ? 'rotate-180' : ''}`}>
              <ChevronDown size={18} className="text-slate-400 group-hover:text-slate-600" />
            </div>
          </button>
          
          {showCitations && (
            <div className="mt-3 animate-in slide-in-from-top-2 duration-200">
              <CopilotCitations response={response} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
