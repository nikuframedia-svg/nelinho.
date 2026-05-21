// SettingsPage · LearningSettingsPanel (Q.60.R).
import { useState } from 'react';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { learningApi } from '../../../lib/api';
import { DarkBadge, DarkButton, DarkCard, DarkInput } from '../../../components/dark';

export function LearningSettingsPanel() {
  const STALE = 5 * 60 * 1000; // 5min
  const [showHistory, setShowHistory] = useState(false);
  const pairsQ = useQuery({
    queryKey: ['learning', 'pairs'],
    queryFn: () => learningApi.pairs({ window_days: 90, min_reason_len: 10 }),
    staleTime: STALE,
    retry: false,
  });
  const rulesQ = useQuery({
    queryKey: ['learning', 'rules'],
    queryFn: () => learningApi.rules(),
    staleTime: STALE,
    retry: false,
  });
  const weightsQ = useQuery({
    queryKey: ['learning', 'weights'],
    queryFn: () => learningApi.weights(),
    staleTime: STALE,
    retry: false,
  });
  const historyQ = useQuery({
    queryKey: ['learning', 'weights', 'history'],
    queryFn: () => learningApi.weightHistory(12),
    staleTime: STALE,
    retry: false,
    enabled: showHistory,
  });
  const adapterQ = useQuery({
    queryKey: ['learning', 'adapter'],
    queryFn: () => learningApi.adapter(),
    staleTime: STALE,
    retry: false,
  });
  const queryClient = useQueryClient();
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [promoteVersion, setPromoteVersion] = useState('');
  const [promoteReason, setPromoteReason] = useState('');
  const [promoteBy, setPromoteBy] = useState('');
  const [rollbackOpen, setRollbackOpen] = useState(false);
  const [rollbackReason, setRollbackReason] = useState('');
  const [rollbackBy, setRollbackBy] = useState('');
  const promoteMut = useMutation({
    mutationFn: () =>
      learningApi.promoteAdapter(promoteVersion.trim(), {
        reason: promoteReason.trim(),
        decided_by: promoteBy.trim() || 'unknown',
      }),
    onSuccess: () => {
      setPromoteOpen(false);
      setPromoteReason('');
      setPromoteVersion('');
      setPromoteBy('');
      queryClient.invalidateQueries({ queryKey: ['learning', 'adapter'] });
    },
  });
  const rollbackMut = useMutation({
    mutationFn: () =>
      learningApi.rollbackAdapter({
        reason: rollbackReason.trim(),
        decided_by: rollbackBy.trim() || 'unknown',
      }),
    onSuccess: () => {
      setRollbackOpen(false);
      setRollbackReason('');
      setRollbackBy('');
      queryClient.invalidateQueries({ queryKey: ['learning', 'adapter'] });
    },
  });
  const adapter = adapterQ.data;

  const pairs = pairsQ.data;
  const rules = rulesQ.data;
  const weights = weightsQ.data;

  const ruleConfirmed = rules?.by_status?.confirmed ?? 0;
  const ruleDetected = rules?.by_status?.detected ?? 0;
  const ruleRejected = rules?.by_status?.rejected ?? 0;
  const reEmit = rules?.rules_re_emitted_count ?? 0;

  const eligible = pairs?.eligible_for_dpo ?? 0;
  const ablToday = pairs?.abl_pairs_today ?? 0;
  const dpoBadge: { variant: 'success' | 'warning' | 'neutral'; label: string } =
    eligible >= 500
      ? { variant: 'success', label: 'PRONTO' }
      : eligible >= 100
        ? { variant: 'warning', label: 'A ACUMULAR' }
        : { variant: 'neutral', label: 'BOOTSTRAP' };

  const weightsTrained = weights?.status === 'trained';
  const weightsBadge: { variant: 'success' | 'warning' | 'neutral'; label: string } =
    weightsTrained
      ? { variant: 'success', label: 'TREINADOS' }
      : weights?.status === 'never_trained'
        ? { variant: 'neutral', label: 'DEFAULTS' }
        : { variant: 'warning', label: weights?.status?.toUpperCase() ?? 'DESCONHECIDO' };

  const trainedAt = weights?.trained_at
    ? new Date(weights.trained_at).toLocaleString('pt-PT')
    : '—';
  const detectorAt = rules?.last_detector_run_at
    ? new Date(rules.last_detector_run_at).toLocaleString('pt-PT')
    : '—';

  return (
    <DarkCard title="Aprendizagem" subtitle="Plan v4 §22-§27 · Camadas 1-4 · Sprint R.1 (visibilidade)">
      <div className="space-y-3 mt-4">

        {/* Camada 1 */}
        <div className="bg-slate-800/40 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-slate-200 font-medium">Camada 1 — Regras explícitas</p>
            {rulesQ.isLoading ? (
              <DarkBadge variant="neutral" size="sm">A carregar…</DarkBadge>
            ) : reEmit > 0 ? (
              <DarkBadge variant="warning" size="sm" dot>{reEmit} re-emitidas</DarkBadge>
            ) : (
              <DarkBadge variant="success" size="sm" dot>OK</DarkBadge>
            )}
          </div>
          <div className="grid grid-cols-3 gap-3 mt-2">
            <div>
              <p className="text-2xl font-bold text-slate-100">{ruleConfirmed}</p>
              <p className="text-xs text-slate-400">Confirmadas</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-amber-400">{ruleDetected}</p>
              <p className="text-xs text-slate-400">Em revisão</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-500">{ruleRejected}</p>
              <p className="text-xs text-slate-400">Rejeitadas</p>
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-3">
            Última passagem do detector: <span className="text-slate-300">{detectorAt}</span>
          </p>
          <a
            href="/admin/learned-rules"
            className="text-xs text-accent underline mt-2 inline-block"
          >
            Ver e aprovar regras aprendidas →
          </a>
        </div>

        {/* Camada 2 */}
        <div className="bg-slate-800/40 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-slate-200 font-medium">Camada 2 — Pesos adaptativos</p>
            {weightsQ.isLoading ? (
              <DarkBadge variant="neutral" size="sm">A carregar…</DarkBadge>
            ) : (
              <DarkBadge variant={weightsBadge.variant} size="sm" dot>{weightsBadge.label}</DarkBadge>
            )}
          </div>
          <div className="grid grid-cols-4 gap-2 mt-2 text-xs">
            {weights && Object.entries(weights.current_weights).map(([key, value]) => {
              const def = weights.default_weights[key] ?? 0;
              const mult = weights.multipliers[key] ?? 1;
              const arrow = mult > 1.05 ? '↑' : mult < 0.95 ? '↓' : '→';
              const colour = mult > 1.05 ? 'text-emerald-400' : mult < 0.95 ? 'text-rose-400' : 'text-slate-300';
              return (
                <div key={key}>
                  <p className="text-slate-400">{key.replace('w_', '')}</p>
                  <p className={`font-mono ${colour}`}>
                    {value.toFixed(2)} {arrow} ({mult.toFixed(2)}×)
                  </p>
                  <p className="text-slate-600">def {def.toFixed(2)}</p>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-slate-500 mt-3">
            Treinado com <span className="text-slate-300">{weights?.pairs_used ?? 0}</span> pares ·
            blend {((weights?.blend_learned_pct ?? 0.7) * 100).toFixed(0)}% aprendido /
            {(100 - (weights?.blend_learned_pct ?? 0.7) * 100).toFixed(0)}% default ·
            min pares: {weights?.min_pairs_threshold ?? 50} ·
            último retrain: <span className="text-slate-300">{trainedAt}</span>
          </p>
          <button
            type="button"
            className="text-xs text-accent underline mt-2"
            onClick={() => setShowHistory(true)}
          >
            Ver histórico (12 retrains) →
          </button>
        </div>

        {/* Camada 3 */}
        <div className="bg-slate-800/40 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-slate-200 font-medium">Camada 3 — DPO no LLM (fine-tune)</p>
            {pairsQ.isLoading ? (
              <DarkBadge variant="neutral" size="sm">A carregar…</DarkBadge>
            ) : (
              <DarkBadge variant={dpoBadge.variant} size="sm" dot>{dpoBadge.label}</DarkBadge>
            )}
          </div>
          <div className="grid grid-cols-3 gap-3 mt-2">
            <div>
              <p className="text-2xl font-bold text-slate-100">{eligible}</p>
              <p className="text-xs text-slate-400">Pares elegíveis (≥{pairs?.min_reason_len ?? 10} chars)</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-300">{pairs?.total_pairs ?? 0}</p>
              <p className="text-xs text-slate-400">Total de pares</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-300">{pairs?.last_30d?.eligible ?? 0}</p>
              <p className="text-xs text-slate-400">Elegíveis últimos 30d</p>
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-3">
            Bootstrap: precisa de ≥500 pares elegíveis para fine-tune QLoRA on-prem (Sprint R.5).
            Pares vêm de <code>rejected_alternatives</code> nos commits CPO + ABL (Sprint R.3).
          </p>
          <div className="mt-3 pt-3 border-t border-slate-700 text-xs">
            {adapter?.active_version ? (
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-slate-300">
                    Adapter activo: <code className="text-accent">{adapter.active_version}</code>
                  </p>
                  <p className="text-slate-500 mt-1">
                    Promovido por <span className="text-slate-300">{adapter.promoted_by ?? '—'}</span>
                    {' '}em{' '}
                    <span className="text-slate-300">
                      {adapter.promoted_at ? new Date(adapter.promoted_at).toLocaleString('pt-PT') : '—'}
                    </span>
                  </p>
                  {adapter.intent_match_rate !== null && (
                    <p className="text-slate-500 mt-1">
                      intent_match: <span className="text-slate-300">{((adapter.intent_match_rate ?? 0) * 100).toFixed(1)}%</span>
                      {' · safety: '}
                      <span className="text-slate-300">{adapter.safety_violations_count ?? 0}</span>
                    </p>
                  )}
                </div>
                <div className="flex flex-col gap-2">
                  <button
                    type="button"
                    className="text-xs text-accent underline"
                    onClick={() => setPromoteOpen(true)}
                  >
                    Promover novo →
                  </button>
                  {adapter.has_previous && (
                    <button
                      type="button"
                      className="text-xs text-rose-400 underline"
                      onClick={() => setRollbackOpen(true)}
                    >
                      Rollback ↩
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <p className="text-slate-500">Sem adapter activo — base model em uso.</p>
                <button
                  type="button"
                  className="text-xs text-accent underline"
                  onClick={() => setPromoteOpen(true)}
                >
                  Promover candidato →
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Camada 4 */}
        <div className="bg-slate-800/40 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm text-slate-200 font-medium">Camada 4 — ABLkit (loop contínuo)</p>
            {pairsQ.isLoading ? (
              <DarkBadge variant="neutral" size="sm">A carregar…</DarkBadge>
            ) : ablToday > 0 ? (
              <DarkBadge variant="success" size="sm" dot>ACTIVA</DarkBadge>
            ) : (
              <DarkBadge variant="warning" size="sm" dot>STUB (R.3 pendente)</DarkBadge>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3 mt-2">
            <div>
              <p className="text-2xl font-bold text-slate-100">{ablToday}</p>
              <p className="text-xs text-slate-400">Divergências hoje</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-300">—</p>
              <p className="text-xs text-slate-400">Acumuladas (Sprint R.3)</p>
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-3">
            Cada divergência kernel-vs-LLM produz um triplet <code>{`{prompt, chosen, rejected}`}</code>
            alimentado à Camada 3. Activado pelo job <code>_abl_feedback_job</code> (Sprint R.3).
          </p>
        </div>

        <p className="text-xs text-slate-500 mt-2">
          Override do gestor SEMPRE ganha (Plan v4 §11.3).
          Endpoints expostos: <code>/v1/governance/learning/{`{pairs,rules,weights}`}</code>.
        </p>
      </div>

      {showHistory && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setShowHistory(false)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-xl max-w-5xl w-full max-h-[85vh] overflow-y-auto p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-100">
                  Histórico de pesos adaptativos (Camada 2)
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                  Últimos 12 retrains com explicação determinística por KPI (Sprint R.4).
                </p>
              </div>
              <button
                type="button"
                className="text-slate-400 hover:text-slate-100"
                onClick={() => setShowHistory(false)}
              >
                Fechar ✕
              </button>
            </div>

            {historyQ.isLoading && (
              <p className="text-sm text-slate-400">A carregar histórico…</p>
            )}
            {historyQ.isError && (
              <p className="text-sm text-rose-400">
                Erro a carregar histórico. Tente outra vez.
              </p>
            )}
            {historyQ.data && historyQ.data.entries.length === 0 && (
              <p className="text-sm text-slate-400">
                Sem retrains gravados ainda. O job corre domingos 02:00 UTC.
              </p>
            )}
            {historyQ.data && historyQ.data.entries.length > 0 && (
              <div className="space-y-3">
                {historyQ.data.entries.map((entry, idx) => {
                  const dt = entry.trained_at
                    ? new Date(entry.trained_at).toLocaleString('pt-PT')
                    : entry.valid_from
                      ? new Date(entry.valid_from).toLocaleString('pt-PT')
                      : '—';
                  return (
                    <div
                      key={`${entry.trained_at}-${idx}`}
                      className="bg-slate-800/40 rounded-lg p-3"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm font-medium text-slate-200">
                          {dt}
                        </p>
                        <DarkBadge
                          variant={entry.status === 'trained' ? 'success' : 'neutral'}
                          size="sm"
                          dot
                        >
                          {entry.status ?? 'unknown'} · {entry.pairs_used} pares
                        </DarkBadge>
                      </div>
                      {entry.explanations && entry.explanations.length > 0 ? (
                        <ul className="space-y-1">
                          {entry.explanations.map((ex) => (
                            <li key={ex.kpi} className="text-xs text-slate-300">
                              {/* ZERO XSS: render as plain text. The previous
                                  implementation used dangerouslySetInnerHTML
                                  with a regex that left ex.human_text exposed
                                  to attacker-controlled HTML. */}
                              {ex.human_text.replace(/\*\*([^*]+)\*\*/g, '$1')}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-xs text-slate-500 italic">
                          Sem explicações neste retrain (anterior a R.4).
                        </p>
                      )}
                      {entry.warnings && entry.warnings.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-slate-700">
                          <p className="text-xs text-amber-400 font-medium">
                            ⚠ {entry.warnings.length} contradição{entry.warnings.length > 1 ? 'ões' : ''} com regras confirmadas
                          </p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {promoteOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setPromoteOpen(false)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-xl max-w-md w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-semibold text-slate-100 mb-1">
              Promover candidato LoRA
            </h2>
            <p className="text-xs text-slate-400 mb-4">
              Sprint R.5.3 — promove um adapter como activo. Razão obrigatória ≥20 chars (audit).
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-300">Versão do candidato</label>
                <DarkInput
                  value={promoteVersion}
                  onChange={(e) => setPromoteVersion(e.target.value)}
                  placeholder="gemma4-8b-nelo-2026-04-25"
                />
              </div>
              <div>
                <label className="text-xs text-slate-300">Decidido por</label>
                <DarkInput
                  value={promoteBy}
                  onChange={(e) => setPromoteBy(e.target.value)}
                  placeholder="luis"
                />
              </div>
              <div>
                <label className="text-xs text-slate-300">Razão (≥20 chars)</label>
                <DarkInput
                  value={promoteReason}
                  onChange={(e) => setPromoteReason(e.target.value)}
                  placeholder="ex: candidato passou eval +5pp, sem violações"
                />
                <p className="text-xs text-slate-500 mt-1">
                  {promoteReason.trim().length}/20 chars mínimos
                </p>
              </div>
              {promoteMut.isError && (
                <p className="text-xs text-rose-400">
                  {(promoteMut.error as Error)?.message ?? 'Erro a promover.'}
                </p>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <DarkButton
                  variant="secondary"
                  onClick={() => setPromoteOpen(false)}
                >
                  Cancelar
                </DarkButton>
                <DarkButton
                  variant="primary"
                  disabled={
                    !promoteVersion.trim()
                    || promoteReason.trim().length < 20
                    || promoteMut.isPending
                  }
                  onClick={() => promoteMut.mutate()}
                >
                  {promoteMut.isPending ? 'A promover…' : 'Promover'}
                </DarkButton>
              </div>
            </div>
          </div>
        </div>
      )}

      {rollbackOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setRollbackOpen(false)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-xl max-w-md w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-semibold text-slate-100 mb-1">
              Rollback do adapter activo
            </h2>
            <p className="text-xs text-slate-400 mb-4">
              Restaura a versão anterior. Razão obrigatória ≥20 chars.
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-300">Decidido por</label>
                <DarkInput
                  value={rollbackBy}
                  onChange={(e) => setRollbackBy(e.target.value)}
                  placeholder="luis"
                />
              </div>
              <div>
                <label className="text-xs text-slate-300">Razão (≥20 chars)</label>
                <DarkInput
                  value={rollbackReason}
                  onChange={(e) => setRollbackReason(e.target.value)}
                  placeholder="ex: regressão de OTD após promote"
                />
                <p className="text-xs text-slate-500 mt-1">
                  {rollbackReason.trim().length}/20 chars mínimos
                </p>
              </div>
              {rollbackMut.isError && (
                <p className="text-xs text-rose-400">
                  {(rollbackMut.error as Error)?.message ?? 'Erro a fazer rollback.'}
                </p>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <DarkButton
                  variant="secondary"
                  onClick={() => setRollbackOpen(false)}
                >
                  Cancelar
                </DarkButton>
                <DarkButton
                  variant="primary"
                  disabled={
                    rollbackReason.trim().length < 20
                    || rollbackMut.isPending
                  }
                  onClick={() => rollbackMut.mutate()}
                >
                  {rollbackMut.isPending ? 'A reverter…' : 'Rollback'}
                </DarkButton>
              </div>
            </div>
          </div>
        </div>
      )}
    </DarkCard>
  );
}
