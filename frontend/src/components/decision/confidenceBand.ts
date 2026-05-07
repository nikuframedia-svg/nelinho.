import type { Confidence } from '../../types/decision';

export type ConfidenceBand = 'alta' | 'media' | 'baixa';

export function confidenceBand(value: Confidence): ConfidenceBand {
  if (value >= 0.8) return 'alta';
  if (value >= 0.5) return 'media';
  return 'baixa';
}
