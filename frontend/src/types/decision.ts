/**
 * Decision / suggestion types — Plan v4 §4 (advisory mode) + §8 (explica
 * sempre) contract on the frontend side. Every system suggestion in the
 * factory carries the same five mandatory blocks (O QUE / PORQUÊ / SE
 * ACEITAR / SE REJEITAR / ALTERNATIVA) plus a confidence score, so any
 * page that surfaces a suggestion (Inbox, Scheduling, Dispatch, Expedição,
 * Operadores) consumes the same shape.
 *
 * Confidence is a normalised 0..1 number. The `confidenceBand` helper in
 * `components/decision/ConfidenceBadge.tsx` maps it to the Alta/Média/
 * Baixa label that operators read on the floor.
 */

export type Confidence = number;

export type SuggestionPriority = 'critical' | 'high' | 'medium' | 'low';

export type SuggestionStatus = 'pending' | 'approved' | 'rejected' | 'expired';

export type SuggestionSource =
  | 'cpo'
  | 'erro_tree'
  | 'rule'
  | 'llm'
  | 'manual'
  | 'seed'
  | 'governance'
  | string;

export interface SuggestionAlternative {
  label: string;
  description?: string;
  consequences?: string[];
}

export interface Suggestion {
  id: string;
  priority: SuggestionPriority;
  title: string;
  what_changed?: string;
  why: string;
  if_accept: string | string[];
  if_reject: string | string[];
  alternative?: SuggestionAlternative | null;
  confidence: Confidence;
  source: SuggestionSource;
  created_at: string;
  context_url?: string;
  status?: SuggestionStatus;
}

export interface DecisionInput {
  suggestion_id: string;
  outcome: 'accept' | 'reject';
  reason?: string;
}

export const REJECTION_REASON_MIN_LENGTH = 8;
