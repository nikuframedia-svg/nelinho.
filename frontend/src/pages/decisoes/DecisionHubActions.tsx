/**
 * DecisionHubActions — a "teia" de ligações de uma decisão (Q.118.D).
 * ===================================================================
 *
 * Torna o cartão de decisão um HUB: liga a decisão ao resto do sistema, tudo
 * com endpoints reais e degradação honesta (esconde o que não existe).
 *
 *   • ícone por action_type
 *   • Ver plano   → /overall?commit_sha= (o plano CPO da decisão)
 *   • €           → GET /v1/profit/preview?schedule_commit_id= (delta € vs baseline)
 *   • Explicar    → abre o copiloto com pergunta pré-preenchida (copilot:open)
 *
 * O € e o Ver plano só aparecem quando a decisão tem commit_sha real.
 */

import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Calendar, BookOpen, Inbox, Euro, Sparkles, ExternalLink } from 'lucide-react';
import { marginPreviewApi, coerceEur, MARGIN_CONFIDENCE_LABEL } from '../../lib/api';
import { profitKeys } from '../../lib/api/keys';
import type { DecisionRun } from '../../lib/api';

function actionIcon(actionType: string) {
  if (actionType === 'execute_runbook') return <BookOpen size={13} />;
  if (actionType.includes('SCHEDULE') || actionType.includes('PLAN')) return <Calendar size={13} />;
  return <Inbox size={13} />;
}

function openCopilot(query: string) {
  window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
}

const PILL: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 5,
  fontSize: 11.5,
  padding: '4px 10px',
  borderRadius: 8,
  background: 'var(--bg-2)',
  border: '1px solid var(--bd-2)',
  color: 'var(--fg-1)',
  cursor: 'pointer',
  textDecoration: 'none',
};

export function DecisionHubActions({ decision }: { decision: DecisionRun }) {
  const sb = (decision.sandbox_result ?? {}) as { commit_sha?: string };
  const commitSha = (sb.commit_sha ?? '').trim();

  const marginQuery = useQuery({
    queryKey: profitKeys.preview(commitSha),
    queryFn: () => marginPreviewApi.get(commitSha),
    enabled: commitSha.length > 0,
    retry: false, // 404 (commit n/d) → não retry, esconde
    staleTime: 60_000,
  });

  const delta = coerceEur(marginQuery.data?.delta_eur);

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2" data-testid="decision-hub-actions">
      <span
        style={{
          ...PILL,
          cursor: 'default',
          background: 'transparent',
          border: 'none',
          color: 'var(--fg-3)',
          paddingLeft: 0,
        }}
      >
        {actionIcon(decision.action_type)}
        {decision.action_type}
      </span>

      {commitSha ? (
        <Link to={`/overall?commit_sha=${encodeURIComponent(commitSha)}`} style={PILL}>
          <Calendar size={13} />
          Ver plano
          <ExternalLink size={11} />
        </Link>
      ) : null}

      {commitSha && marginQuery.isSuccess && delta != null ? (
        <span
          style={{
            ...PILL,
            cursor: 'default',
            color: delta >= 0 ? 'var(--green)' : 'var(--red)',
            borderColor: delta >= 0 ? 'var(--green-bd)' : 'var(--red-bd)',
            background: delta >= 0 ? 'var(--green-bg)' : 'var(--red-bg)',
          }}
          title={`Margem prevista vs baseline · confiança ${marginQuery.data?.confidence}`}
        >
          <Euro size={13} />
          {delta >= 0 ? '+' : ''}
          {delta.toFixed(0)} € · {MARGIN_CONFIDENCE_LABEL[marginQuery.data?.confidence ?? ''] ?? marginQuery.data?.confidence}
        </span>
      ) : null}

      <button
        type="button"
        style={PILL}
        onClick={() =>
          openCopilot(`Porque é que esta decisão foi proposta: "${decision.title}"?`)
        }
      >
        <Sparkles size={13} />
        Explicar
      </button>
    </div>
  );
}
