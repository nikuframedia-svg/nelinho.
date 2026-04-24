/**
 * LearnedRulesPage (Sprint E.2)
 * ==============================
 *
 * `/admin/learned-rules` — operator review surface for Camada 1
 * preferences. Shows every `PreferenceRule` the nightly detector has
 * persisted, filtered by status and type. The operator can:
 *
 *  • Confirm a rule → the CPO engine starts honouring it (Sprint E.4).
 *  • Reject a rule with a mandatory reason → the detector logs it as
 *    human-reviewed so it never re-raises the same pattern.
 *  • Edit a detected rule's description / predicate / confidence before
 *    confirming (narrow scope, re-word, adjust threshold).
 *
 * No mocks — every interaction calls the /v1/governance/preference-rules
 * API. Mutations invalidate the list query so the view refreshes after
 * each action.
 */

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Brain,
  CheckCircle2,
  XCircle,
  Pencil,
  Info,
  AlertCircle,
  ChevronDown,
  RefreshCw,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import {
  DarkCard,
  DarkButton,
  DarkBadge,
  DarkTable,
  DarkTableHead,
  DarkTableBody,
  DarkTableRow,
  DarkTableHeader,
  DarkTableCell,
  DarkPillButton,
} from '../../components/dark';
import {
  preferenceRulesApi,
  type PreferenceRule,
  type PreferenceRuleStatus,
  type PreferenceRuleType,
} from '../../lib/api';

// ─── UI helpers ───────────────────────────────────────────────────────────

const TYPE_LABELS: Record<PreferenceRuleType, string> = {
  temporal_block: 'Bloqueio temporal',
  tradeoff_preference: 'Preferência de trade-off',
  operator_affinity: 'Afinidade de operador',
  phase_threshold: 'Threshold de fase',
};

const STATUS_BADGE: Record<
  PreferenceRuleStatus,
  { label: string; variant: 'info' | 'success' | 'warning' | 'neutral' }
> = {
  detected: { label: 'Para revisão', variant: 'info' },
  confirmed: { label: 'Confirmada', variant: 'success' },
  rejected: { label: 'Rejeitada', variant: 'neutral' },
};

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const colour =
    pct >= 85 ? 'bg-emerald-500' : pct >= 70 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-1.5 bg-bg-elevated rounded-full overflow-hidden">
        <div className={`h-full ${colour}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-text-tertiary tabular-nums w-10 text-right">
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

// ─── Action modal (shared shell) ──────────────────────────────────────────

type ActionMode = 'confirm' | 'reject' | 'edit';

interface ReviewModalProps {
  rule: PreferenceRule;
  mode: ActionMode;
  onClose: () => void;
  onSubmit: (payload: ReviewPayload) => void;
  submitting: boolean;
}

type ReviewPayload =
  | { mode: 'confirm'; review_notes?: string }
  | { mode: 'reject'; reason: string }
  | {
      mode: 'edit';
      description?: string;
      predicate?: Record<string, unknown>;
      confidence?: number;
    };

function ReviewModal({
  rule,
  mode,
  onClose,
  onSubmit,
  submitting,
}: ReviewModalProps) {
  const [notes, setNotes] = useState('');
  const [reason, setReason] = useState('');
  const [editDescription, setEditDescription] = useState(rule.description);
  const [editConfidence, setEditConfidence] = useState(rule.confidence);
  const [predicateText, setPredicateText] = useState(
    JSON.stringify(rule.predicate ?? {}, null, 2),
  );
  const [predicateError, setPredicateError] = useState<string | null>(null);

  const disabled =
    submitting ||
    (mode === 'reject' && reason.trim().length === 0) ||
    (mode === 'edit' && predicateError !== null);

  function handleSubmit() {
    if (mode === 'confirm') {
      onSubmit({ mode: 'confirm', review_notes: notes.trim() || undefined });
      return;
    }
    if (mode === 'reject') {
      onSubmit({ mode: 'reject', reason: reason.trim() });
      return;
    }
    // mode === 'edit'
    let predicate: Record<string, unknown> | undefined;
    try {
      predicate = JSON.parse(predicateText);
    } catch {
      setPredicateError('JSON inválido');
      return;
    }
    onSubmit({
      mode: 'edit',
      description:
        editDescription !== rule.description ? editDescription : undefined,
      predicate,
      confidence:
        editConfidence !== rule.confidence ? editConfidence : undefined,
    });
  }

  const title =
    mode === 'confirm'
      ? 'Confirmar regra'
      : mode === 'reject'
      ? 'Rejeitar regra'
      : 'Editar regra';

  return (
    <>
      <div className="fixed inset-0 bg-black/60 z-[200]" onClick={onClose} />
      <div className="fixed inset-0 z-[201] flex items-center justify-center p-4">
        <div className="bg-bg-card border border-border-subtle rounded-xl shadow-2xl w-full max-w-xl p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold text-text-white">{title}</h2>
              <p className="text-sm text-text-tertiary mt-1">
                {rule.description}
              </p>
            </div>
            <DarkBadge variant={STATUS_BADGE[rule.status].variant}>
              {STATUS_BADGE[rule.status].label}
            </DarkBadge>
          </div>

          {mode === 'confirm' && (
            <label className="block">
              <span className="text-sm text-text-secondary">
                Notas (opcional)
              </span>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder="Ex: padrão consistente durante 3 semanas"
                className="mt-1 w-full rounded-lg bg-bg-elevated border border-border-subtle px-3 py-2 text-sm text-text-white focus:outline-none focus:border-accent"
              />
            </label>
          )}

          {mode === 'reject' && (
            <label className="block">
              <span className="text-sm text-text-secondary">
                Razão <span className="text-red-400">*</span>
              </span>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
                required
                placeholder="Ex: detector apanhou um período de férias, não é um padrão recorrente"
                className="mt-1 w-full rounded-lg bg-bg-elevated border border-border-subtle px-3 py-2 text-sm text-text-white focus:outline-none focus:border-accent"
              />
              <span className="block text-xs text-text-tertiary mt-1">
                Fica registada no audit trail e impede que a regra volte a ser
                sugerida pelo mesmo sinal.
              </span>
            </label>
          )}

          {mode === 'edit' && (
            <div className="space-y-4">
              <label className="block">
                <span className="text-sm text-text-secondary">Descrição</span>
                <input
                  type="text"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  className="mt-1 w-full rounded-lg bg-bg-elevated border border-border-subtle px-3 py-2 text-sm text-text-white focus:outline-none focus:border-accent"
                />
              </label>
              <label className="block">
                <span className="text-sm text-text-secondary">
                  Confiança ({Math.round(editConfidence * 100)}%)
                </span>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={editConfidence}
                  onChange={(e) =>
                    setEditConfidence(parseFloat(e.target.value))
                  }
                  className="mt-1 w-full accent-accent"
                />
              </label>
              <label className="block">
                <span className="text-sm text-text-secondary">
                  Predicate (JSON)
                </span>
                <textarea
                  value={predicateText}
                  onChange={(e) => {
                    setPredicateText(e.target.value);
                    try {
                      JSON.parse(e.target.value);
                      setPredicateError(null);
                    } catch {
                      setPredicateError('JSON inválido');
                    }
                  }}
                  rows={6}
                  spellCheck={false}
                  className={`mt-1 w-full font-mono text-xs rounded-lg bg-bg-elevated border px-3 py-2 text-text-white focus:outline-none ${
                    predicateError
                      ? 'border-red-500'
                      : 'border-border-subtle focus:border-accent'
                  }`}
                />
                {predicateError && (
                  <span className="block text-xs text-red-400 mt-1">
                    {predicateError}
                  </span>
                )}
              </label>
            </div>
          )}

          <div className="flex items-center justify-end gap-2 mt-6">
            <DarkButton variant="ghost" size="sm" onClick={onClose}>
              Cancelar
            </DarkButton>
            <DarkButton
              variant={mode === 'reject' ? 'danger' : 'primary'}
              size="sm"
              onClick={handleSubmit}
              disabled={disabled}
            >
              {submitting ? 'A gravar…' : title}
            </DarkButton>
          </div>
        </div>
      </div>
    </>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────

export function LearnedRulesPage() {
  const [statusFilter, setStatusFilter] =
    useState<PreferenceRuleStatus>('detected');
  const [typeFilter, setTypeFilter] = useState<PreferenceRuleType | 'all'>(
    'all',
  );
  const [activeRule, setActiveRule] = useState<PreferenceRule | null>(null);
  const [activeMode, setActiveMode] = useState<ActionMode | null>(null);

  const queryClient = useQueryClient();

  const { data: rules, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['preference-rules', statusFilter, typeFilter],
    queryFn: () =>
      preferenceRulesApi.list({
        status: statusFilter,
        type: typeFilter === 'all' ? undefined : typeFilter,
        limit: 200,
      }),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['preference-rules'] });

  const confirmMut = useMutation({
    mutationFn: ({
      id,
      review_notes,
    }: {
      id: string;
      review_notes?: string;
    }) => preferenceRulesApi.confirm(id, { review_notes }),
    onSuccess: () => invalidate(),
  });

  const rejectMut = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      preferenceRulesApi.reject(id, { reason }),
    onSuccess: () => invalidate(),
  });

  const patchMut = useMutation({
    mutationFn: ({
      id,
      ...payload
    }: {
      id: string;
      description?: string;
      predicate?: Record<string, unknown>;
      confidence?: number;
    }) => preferenceRulesApi.patch(id, payload),
    onSuccess: () => invalidate(),
  });

  const submitting =
    confirmMut.isPending || rejectMut.isPending || patchMut.isPending;

  const counts = useMemo(() => {
    return {
      total: rules?.length ?? 0,
      detected: rules?.filter((r) => r.status === 'detected').length ?? 0,
    };
  }, [rules]);

  function handleSubmit(payload: ReviewPayload) {
    if (!activeRule) return;
    const id = activeRule.id;
    if (payload.mode === 'confirm') {
      confirmMut.mutate(
        { id, review_notes: payload.review_notes },
        { onSuccess: () => closeModal() },
      );
    } else if (payload.mode === 'reject') {
      rejectMut.mutate(
        { id, reason: payload.reason },
        { onSuccess: () => closeModal() },
      );
    } else {
      patchMut.mutate(
        {
          id,
          description: payload.description,
          predicate: payload.predicate as Record<string, unknown> | undefined,
          confidence: payload.confidence,
        },
        { onSuccess: () => closeModal() },
      );
    }
  }

  function closeModal() {
    setActiveRule(null);
    setActiveMode(null);
  }

  return (
    <DarkPageLayout
      title="Regras Aprendidas"
      subtitle="Revisão das preferências que o detector Camada 1 extraiu dos commits"
      icon={<Brain size={20} />}
      actions={
        <DarkButton
          variant="secondary"
          size="sm"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <RefreshCw
            className={`w-4 h-4 mr-2 ${isFetching ? 'animate-spin' : ''}`}
          />
          Atualizar
        </DarkButton>
      }
    >
      <DarkCard className="mb-6 bg-accent/10 border-accent/20">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-accent/20 rounded-lg flex-shrink-0">
            <Info size={18} className="text-accent" />
          </div>
          <div>
            <h4 className="text-sm font-medium text-accent">
              Como funciona o ciclo de aprendizagem
            </h4>
            <p className="text-xs text-text-tertiary mt-1">
              Todas as noites o <code className="text-accent">PreferenceRuleDetector</code>{' '}
              analisa os commits rejeitados e extrai padrões. Uma regra só entra no
              motor depois de ser <b>confirmada</b> aqui. Regras rejeitadas ficam
              em audit e não voltam a ser propostas.
            </p>
          </div>
        </div>
      </DarkCard>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {(['detected', 'confirmed', 'rejected'] as PreferenceRuleStatus[]).map(
            (s) => (
              <DarkPillButton
                key={s}
                active={statusFilter === s}
                onClick={() => setStatusFilter(s)}
              >
                {STATUS_BADGE[s].label}
              </DarkPillButton>
            ),
          )}
        </div>
        <div className="relative">
          <select
            value={typeFilter}
            onChange={(e) =>
              setTypeFilter(e.target.value as PreferenceRuleType | 'all')
            }
            className="appearance-none bg-bg-secondary border border-border-subtle rounded-full px-4 py-1.5 pr-8 text-sm text-text-white focus:outline-none focus:border-accent"
          >
            <option value="all">Todos os tipos</option>
            {(Object.entries(TYPE_LABELS) as [PreferenceRuleType, string][]).map(
              ([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ),
            )}
          </select>
          <ChevronDown
            size={14}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-text-tertiary pointer-events-none"
          />
        </div>
        <span className="text-xs text-text-tertiary ml-auto">
          {counts.total} regra{counts.total === 1 ? '' : 's'}
          {statusFilter === 'detected' && counts.detected > 0
            ? ` · ${counts.detected} por rever`
            : ''}
        </span>
      </div>

      {/* Table */}
      <DarkCard padding="none">
        {isLoading ? (
          <div className="p-12 text-center text-text-tertiary text-sm">
            A carregar regras…
          </div>
        ) : isError ? (
          <div className="p-12 text-center">
            <AlertCircle className="mx-auto mb-3 text-red-400" size={32} />
            <p className="text-sm text-text-tertiary">
              Não consegui ler as regras. Tenta actualizar.
            </p>
          </div>
        ) : !rules || rules.length === 0 ? (
          <div className="p-12 text-center">
            <Brain className="mx-auto mb-3 text-text-tertiary opacity-50" size={32} />
            <p className="text-sm text-text-tertiary">
              Sem regras neste filtro. O detector corre uma vez por dia às 03:00 UTC.
            </p>
          </div>
        ) : (
          <DarkTable>
            <DarkTableHead>
              <DarkTableRow>
                <DarkTableHeader>Tipo</DarkTableHeader>
                <DarkTableHeader>Descrição</DarkTableHeader>
                <DarkTableHeader>Confiança</DarkTableHeader>
                <DarkTableHeader>Commits</DarkTableHeader>
                <DarkTableHeader>Revisão</DarkTableHeader>
                <DarkTableHeader align="right">Acções</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {rules.map((rule) => (
                <DarkTableRow key={rule.id}>
                  <DarkTableCell>
                    <DarkBadge variant="info" size="sm">
                      {TYPE_LABELS[rule.type]}
                    </DarkBadge>
                  </DarkTableCell>
                  <DarkTableCell>
                    <div className="text-sm text-text-white">
                      {rule.description}
                    </div>
                    {Object.keys(rule.predicate ?? {}).length > 0 && (
                      <div className="text-xs text-text-tertiary mt-0.5 truncate max-w-md font-mono">
                        {JSON.stringify(rule.predicate)}
                      </div>
                    )}
                  </DarkTableCell>
                  <DarkTableCell>
                    <ConfidenceBar value={rule.confidence} />
                  </DarkTableCell>
                  <DarkTableCell>
                    <span className="text-xs text-text-tertiary">
                      {rule.detected_from_commits.length}
                    </span>
                  </DarkTableCell>
                  <DarkTableCell>
                    {rule.status !== 'detected' && rule.review_notes ? (
                      <span
                        className="text-xs text-text-tertiary truncate max-w-[180px] block"
                        title={rule.review_notes}
                      >
                        {rule.review_notes}
                      </span>
                    ) : (
                      <span className="text-xs text-text-tertiary">—</span>
                    )}
                  </DarkTableCell>
                  <DarkTableCell align="right">
                    {rule.status === 'detected' ? (
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => {
                            setActiveRule(rule);
                            setActiveMode('confirm');
                          }}
                          className="p-1.5 hover:bg-emerald-500/10 rounded-lg text-emerald-400 transition-colors"
                          title="Confirmar"
                        >
                          <CheckCircle2 size={16} />
                        </button>
                        <button
                          onClick={() => {
                            setActiveRule(rule);
                            setActiveMode('edit');
                          }}
                          className="p-1.5 hover:bg-accent/10 rounded-lg text-accent transition-colors"
                          title="Editar"
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          onClick={() => {
                            setActiveRule(rule);
                            setActiveMode('reject');
                          }}
                          className="p-1.5 hover:bg-red-500/10 rounded-lg text-red-400 transition-colors"
                          title="Rejeitar"
                        >
                          <XCircle size={16} />
                        </button>
                      </div>
                    ) : (
                      <DarkBadge
                        variant={STATUS_BADGE[rule.status].variant}
                        size="sm"
                      >
                        {STATUS_BADGE[rule.status].label}
                      </DarkBadge>
                    )}
                  </DarkTableCell>
                </DarkTableRow>
              ))}
            </DarkTableBody>
          </DarkTable>
        )}
      </DarkCard>

      {activeRule && activeMode && (
        <ReviewModal
          rule={activeRule}
          mode={activeMode}
          onClose={closeModal}
          onSubmit={handleSubmit}
          submitting={submitting}
        />
      )}
    </DarkPageLayout>
  );
}

export default LearnedRulesPage;
