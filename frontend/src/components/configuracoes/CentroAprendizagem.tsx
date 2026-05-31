/**
 * CentroAprendizagem — visibilidade das 4 camadas de aprendizagem (Q.118.M).
 * ===========================================================================
 *
 * Torna visível (e fecha) o loop de aprendizagem que corria sem UI:
 *   • Camada 2 (pesos do GA)   — learningApi.weights()
 *   • Camada 3 (adapter DPO)   — learningApi.adapter() + rollback
 *   • Pares de preferência     — learningApi.pairs() (dataset DPO)
 *
 * Promover adapter exige uma versão candidata (vem do job DPO) — sem fonte de
 * candidato na UI, não há botão de promover (evita botão morto). Rollback é
 * acionável quando há versão anterior. ZERO MOCKS: empty/erro explícitos.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Brain, RotateCcw } from 'lucide-react';
import { DarkCard, DarkBadge, DarkButton } from '../dark';
import { learningApi } from '../../lib/api/governanceApi';
import { useToastContext } from '../ToastProvider';

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-[11px] text-text-dark-tertiary">{label}</div>
      <div className="text-lg font-semibold text-text-dark-primary font-mono">{value}</div>
    </div>
  );
}

export function CentroAprendizagem() {
  const qc = useQueryClient();
  const toast = useToastContext();

  const weights = useQuery({
    queryKey: ['governance', 'learning', 'weights'],
    queryFn: () => learningApi.weights(),
    retry: false,
    refetchOnWindowFocus: false,
  });
  const adapter = useQuery({
    queryKey: ['governance', 'learning', 'adapter'],
    queryFn: () => learningApi.adapter(),
    retry: false,
    refetchOnWindowFocus: false,
  });
  const pairs = useQuery({
    queryKey: ['governance', 'learning', 'pairs'],
    queryFn: () => learningApi.pairs(),
    retry: false,
    refetchOnWindowFocus: false,
  });

  const rollbackM = useMutation({
    mutationFn: () => learningApi.rollbackAdapter({ reason: 'Revertido pelo gestor', decided_by: 'admin' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['governance', 'learning', 'adapter'] });
      toast.success('Adapter revertido para a versão anterior');
    },
    onError: () => toast.error('Erro ao reverter adapter'),
  });

  const w = weights.data;
  const a = adapter.data;
  const p = pairs.data;

  return (
    <DarkCard>
      <div className="flex items-center gap-2 mb-1">
        <Brain size={15} className="text-accent" />
        <h3 className="text-sm font-semibold text-text-dark-primary">Centro de aprendizagem</h3>
      </div>
      <p className="text-xs text-text-dark-tertiary mb-4">
        Como o sistema aprende com as tuas decisões — pesos do planeamento, adapter do copiloto e pares de preferência.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Camada 2 — pesos */}
        <div className="rounded-lg border border-white/10 bg-white/5 p-3">
          <p className="text-[10.5px] uppercase tracking-wide font-semibold text-text-dark-tertiary mb-2">
            Pesos do plano · Camada 2
          </p>
          {weights.isError ? (
            <p className="text-xs text-text-dark-tertiary">Indisponível.</p>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <Stat label="Pares usados" value={w?.pairs_used ?? '—'} />
              <Stat label="% aprendido" value={w ? `${Math.round((w.blend_learned_pct ?? 0))}%` : '—'} />
              <Stat label="Commits" value={w?.commits_scanned ?? '—'} />
              <Stat label="Treinado" value={w?.trained_at ? new Date(w.trained_at).toLocaleDateString('pt-PT') : '—'} />
            </div>
          )}
        </div>

        {/* Camada 3 — adapter DPO */}
        <div className="rounded-lg border border-white/10 bg-white/5 p-3">
          <p className="text-[10.5px] uppercase tracking-wide font-semibold text-text-dark-tertiary mb-2">
            Adapter copiloto · Camada 3
          </p>
          {adapter.isError ? (
            <p className="text-xs text-text-dark-tertiary">Indisponível.</p>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-2">
                <DarkBadge variant={a?.active_version ? 'success' : 'neutral'}>
                  {a?.active_version ? a.active_version : 'nenhum activo'}
                </DarkBadge>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Stat label="Match intenção" value={a?.intent_match_rate != null ? `${Math.round(a.intent_match_rate * 100)}%` : '—'} />
                <Stat label="Violações" value={a?.safety_violations_count ?? '—'} />
              </div>
              {a?.has_previous ? (
                <DarkButton
                  size="sm"
                  variant="ghost"
                  icon={<RotateCcw size={13} />}
                  className="mt-2"
                  onClick={() => rollbackM.mutate()}
                  disabled={rollbackM.isPending}
                >
                  Reverter
                </DarkButton>
              ) : null}
            </>
          )}
        </div>

        {/* Pares de preferência (DPO dataset) */}
        <div className="rounded-lg border border-white/10 bg-white/5 p-3">
          <p className="text-[10.5px] uppercase tracking-wide font-semibold text-text-dark-tertiary mb-2">
            Pares de preferência
          </p>
          {pairs.isError ? (
            <p className="text-xs text-text-dark-tertiary">Indisponível.</p>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <Stat label="Total" value={p?.total_pairs ?? '—'} />
              <Stat label="P/ DPO" value={p?.eligible_for_dpo ?? '—'} />
              <Stat label="30 dias" value={p?.last_30d?.pairs ?? '—'} />
              <Stat label="ABL hoje" value={p?.abl_pairs_today ?? '—'} />
            </div>
          )}
        </div>
      </div>
    </DarkCard>
  );
}
