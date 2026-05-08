/**
 * CausalChainCard — diagnóstico causal em 5 caixas (Aristóteles + Reichenbach).
 *
 * Output do ERRO-TREE (Q.15.D.1) / Reichenbach common-cause (Q.15.D.2/3) /
 * Mill's method (Q.15.D.4) / CausalChain emission (Q.15.D.5).
 *
 *   PERGUNTA: o que se pretende explicar
 *   CAUSA-RAIZ: hipótese causal mais provável + confidence (0..1)
 *   MECANISMO: cadeia causa→efeito em N passos
 *   EVIDÊNCIA: dados que suportam a cadeia
 *   RECOMENDAÇÃO: acção concreta + alternatives
 *
 * Plan v4 §6 / FRONTEND_DESIGN_PROMPT §5.3.
 * Sprint Q.18.UI.A.
 */

import type { ReactNode } from 'react';
import {
  HelpCircle,
  Target,
  GitBranch,
  Database,
  Wrench,
} from 'lucide-react';
import { ApprovalButtons } from './ApprovalButtons';

export interface CausalChainCardProps {
  question: string;
  root_cause: string;
  /** 0..1 — pintado de verde (>0.8), amarelo (0.5-0.8), vermelho (<0.5). */
  confidence: number;
  mechanism: string[];
  evidence: string[];
  recommendation: string;
  alternatives?: string[];
  onAcceptRecommendation?: (reason?: string) => void | Promise<void>;
  onReject?: (reason: string) => void | Promise<void>;
  className?: string;
}

function confidenceColor(conf: number): string {
  if (conf >= 0.80) return 'text-success';
  if (conf >= 0.50) return 'text-warning';
  return 'text-danger';
}

function confidenceLabel(conf: number): string {
  if (conf >= 0.80) return 'Alta';
  if (conf >= 0.50) return 'Média';
  return 'Baixa';
}

export function CausalChainCard({
  question,
  root_cause,
  confidence,
  mechanism,
  evidence,
  recommendation,
  alternatives,
  onAcceptRecommendation,
  onReject,
  className = '',
}: CausalChainCardProps): ReactNode {
  const confColor = confidenceColor(confidence);
  return (
    <article
      className={`
        flex flex-col gap-4 p-5 rounded-xl
        bg-gradient-to-br from-dark-800 to-dark-700
        border border-primary-500/20 shadow-card
        ${className}
      `}
    >
      {/* PERGUNTA */}
      <div className="flex items-start gap-2">
        <HelpCircle className="w-5 h-5 shrink-0 mt-0.5 text-primary-400" />
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-text-dark-tertiary">
            Pergunta
          </span>
          <p className="text-base font-medium text-text-dark-primary leading-snug">
            {question}
          </p>
        </div>
      </div>

      {/* CAUSA-RAIZ + confidence */}
      <div className="flex items-start gap-2 px-3 py-2.5 rounded-md bg-primary-500/10 border border-primary-500/30">
        <Target className="w-5 h-5 shrink-0 mt-0.5 text-primary-300" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-primary-300">
              Causa-raiz
            </span>
            <span
              className={`text-xs font-semibold tabular-nums ${confColor}`}
              title={`Confidence ${(confidence * 100).toFixed(1)}%`}
            >
              Confiança {confidenceLabel(confidence)} ({(confidence * 100).toFixed(0)}%)
            </span>
          </div>
          <p className="text-sm text-text-dark-primary mt-1">{root_cause}</p>
        </div>
      </div>

      {/* MECANISMO */}
      {mechanism.length > 0 ? (
        <div className="flex items-start gap-2">
          <GitBranch className="w-5 h-5 shrink-0 mt-0.5 text-accent-400" />
          <div className="flex-1 min-w-0">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-dark-tertiary">
              Mecanismo
            </span>
            <ol className="mt-1 flex flex-col gap-1 text-sm text-text-dark-secondary">
              {mechanism.map((step, idx) => (
                <li
                  key={`mech-${idx}`}
                  className="flex items-start gap-2 leading-snug"
                >
                  <span className="shrink-0 inline-flex items-center justify-center w-5 h-5 rounded-full bg-accent-500/20 text-accent-300 text-[10px] font-bold tabular-nums">
                    {idx + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      ) : null}

      {/* EVIDÊNCIA */}
      {evidence.length > 0 ? (
        <div className="flex items-start gap-2">
          <Database className="w-5 h-5 shrink-0 mt-0.5 text-warning" />
          <div className="flex-1 min-w-0">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-dark-tertiary">
              Evidência
            </span>
            <ul className="mt-1 flex flex-col gap-1 text-sm text-text-dark-secondary">
              {evidence.map((e, idx) => (
                <li
                  key={`ev-${idx}`}
                  className="flex items-start gap-2 leading-snug"
                >
                  <span className="shrink-0 mt-1.5 w-1 h-1 rounded-full bg-warning" />
                  <span>{e}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}

      {/* RECOMENDAÇÃO + alternatives */}
      <div className="flex items-start gap-2 px-3 py-2.5 rounded-md bg-success/10 border border-success/30">
        <Wrench className="w-5 h-5 shrink-0 mt-0.5 text-success" />
        <div className="flex-1 min-w-0">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-success">
            Recomendação
          </span>
          <p className="text-sm text-text-dark-primary mt-1">{recommendation}</p>
          {alternatives && alternatives.length > 0 ? (
            <div className="mt-2 flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-wider text-text-dark-tertiary">
                Ou em alternativa:
              </span>
              {alternatives.map((alt, idx) => (
                <span
                  key={`alt-${idx}`}
                  className="text-xs text-text-dark-secondary leading-snug"
                >
                  · {alt}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      {/* Aprovação (opt) */}
      {onAcceptRecommendation && onReject ? (
        <ApprovalButtons
          onAccept={onAcceptRecommendation}
          onReject={onReject}
          acceptLabel="Aceitar recomendação"
          rejectLabel="Discordo"
          requireReason="on_reject"
        />
      ) : null}
    </article>
  );
}
