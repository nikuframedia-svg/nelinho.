/**
 * RuleCard — item da lista de regras (Q.52.L).
 *
 * Port do `RuleCard` do protótipo NELO: id mono + tag de estado + tag
 * "stubbed" condicional, descrição PT-PT, contador de disparos. Os
 * axiomas declarados aparecem como mini-tags mono. Selecção destaca o
 * cartão (bg-3 + borda accent).
 */

import type { ReactNode } from 'react';
import { Activity, Sparkles } from 'lucide-react';
import { DarkBadge } from '../dark';
import type { YamlPolicyRule } from '../../lib/api';
import { STATUS_VARIANTS, STATUS_LABELS, EVENT_LABELS, stubbedActions } from './ruleHelpers';

export interface RuleCardProps {
  rule: YamlPolicyRule;
  active: boolean;
  onSelect: () => void;
}

export function RuleCard({ rule, active, onSelect }: RuleCardProps): ReactNode {
  const stubbed = stubbedActions(rule);
  const axioms = rule.payload.constraints?.axioms_required ?? [];
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full text-left rounded-lg border px-4 py-3 transition-all mb-2 ${
        active
          ? 'border-accent bg-bg-3'
          : 'border-bd-1 bg-bg-1 hover:border-bd-2 hover:bg-bg-2'
      }`}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-mono text-xs text-fg-3 shrink-0">{rule.rule_id}</span>
          <DarkBadge variant={STATUS_VARIANTS[rule.status]}>
            {STATUS_LABELS[rule.status]}
          </DarkBadge>
          {stubbed.length > 0 && <DarkBadge variant="warning">stubbed</DarkBadge>}
        </div>
        {rule.fire_count > 0 && (
          <span className="text-xs text-fg-3 shrink-0 inline-flex items-center gap-1">
            <Sparkles size={11} />
            {rule.fire_count}×
          </span>
        )}
      </div>
      <p className="text-sm text-fg-0 leading-snug line-clamp-2 mb-2">{rule.description}</p>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-fg-3 inline-flex items-center gap-1">
          <Activity size={11} />
          {EVENT_LABELS[rule.event_type] ?? rule.event_type}
        </span>
        {axioms.map((a) => (
          <span
            key={a}
            className="font-mono text-fg-3 bg-bg-2 border border-bd-1 rounded px-1.5"
            style={{ fontSize: 9.5 }}
          >
            {a}
          </span>
        ))}
      </div>
    </button>
  );
}
