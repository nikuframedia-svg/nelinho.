/**
 * Decision primitives — Plan v4 §4 (advisory mode) + §8 (explica sempre).
 *
 * Pages compose these instead of rolling their own suggestion shells.
 * The 5-block explainer (O QUE / PORQUÊ / SE ACEITAR / SE REJEITAR /
 * ALTERNATIVA) and the consequence summary live in `components/dark`
 * and are re-exported here so a page only imports from one place.
 */

export { ConfidenceBadge } from './ConfidenceBadge';
export type { ConfidenceBadgeProps } from './ConfidenceBadge';
export { confidenceBand } from './confidenceBand';
export type { ConfidenceBand } from './confidenceBand';

export { RejectionReasonInput } from './RejectionReasonInput';
export type { RejectionReasonInputProps } from './RejectionReasonInput';

export { SuggestionCard } from './SuggestionCard';
export type { SuggestionCardProps } from './SuggestionCard';

export { ConsequenceBlock, SuggestionExplainer } from '../dark';
export type {
  ConsequenceBlockProps,
  ConsequenceLine,
  ConsequenceSeverity,
  SuggestionExplainerProps,
} from '../dark';
