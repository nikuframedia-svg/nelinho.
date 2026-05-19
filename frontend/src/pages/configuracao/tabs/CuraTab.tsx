// ConfiguracaoPage · CuraTab (Q.60.U). ZERO MOCKS — endpoints reais.
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Beaker, Loader2, Save } from 'lucide-react';
import { DarkBadge, EmptyState } from '../../../components/dark';
import { phaseGapsApi, type PhaseGap } from '../../../lib/api';
import { useToastContext } from '../../../components/ToastProvider';
import { ConfigCard, SectionHeader } from '../configuracaoShared';

export function CuraTab() {
  const queryClient = useQueryClient();
  const toast = useToastContext();
  const { data, isLoading, error } = useQuery({
    queryKey: ['phase-gaps'],
    queryFn: () => phaseGapsApi.list(),
    staleTime: 60_000,
  });

  const gaps: PhaseGap[] = data?.items ?? [];
  const [edits, setEdits] = useState<Record<string, string>>({});

  const keyOf = (g: PhaseGap) => `${g.from_phase_code}→${g.to_phase_code}`;

  const updateMutation = useMutation({
    mutationFn: (payload: {
      from: string;
      to: string;
      min_gap_hours: number;
      reason: string;
    }) =>
      phaseGapsApi.update(payload.from, payload.to, {
        min_gap_hours: payload.min_gap_hours,
        reason: payload.reason,
      }),
    onSuccess: () => {
      toast.success('Transição de cura actualizada.');
      queryClient.invalidateQueries({ queryKey: ['phase-gaps'] });
    },
    onError: (err) => toast.error(`Erro: ${(err as Error).message}`),
  });

  const handleSave = (g: PhaseGap) => {
    const raw = edits[keyOf(g)] ?? '';
    const parsed = Number.parseFloat(raw);
    if (raw === '' || Number.isNaN(parsed)) {
      toast.info('Indica um valor numérico válido.');
      return;
    }
    if (parsed === g.min_gap_hours) {
      toast.info('Nada para guardar.');
      return;
    }
    const reason = window.prompt(
      'Porque é que estás a alterar este tempo de cura? (mínimo 10 caracteres)',
    );
    if (!reason || reason.trim().length < 10) {
      toast.error('Razão obrigatória — mínimo 10 caracteres.');
      return;
    }
    updateMutation.mutate({
      from: g.from_phase_code,
      to: g.to_phase_code,
      min_gap_hours: parsed,
      reason: reason.trim(),
    });
  };

  return (
    <ConfigCard>
      <div
        style={{ padding: '14px 18px', borderBottom: '1px solid var(--bd-1)' }}
      >
        <SectionHeader
          icon={<Beaker size={14} />}
          title="Cura / Secagem · transições min_gap_hours"
          subtitle="Não são filas — são química. Cura de resina e secagem de tinta têm tempos mínimos físicos."
        />
      </div>
      <div className="p-[18px]">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={20} className="text-accent-500 animate-spin" />
          </div>
        ) : error ? (
          <p className="text-sm text-status-red py-3">
            Falha ao carregar: {(error as Error).message}
          </p>
        ) : gaps.length === 0 ? (
          <EmptyState
            title="Sem transições de cura"
            hint="O seed NELO_CURING_GAPS_SEED tem 16 transições. Se a lista está vazia, corre o bootstrap."
          />
        ) : (
          <div className="space-y-2">
            {gaps.map((g) => (
              <div
                key={keyOf(g)}
                className="grid grid-cols-[1fr_120px_90px_90px] items-center gap-3 py-2"
                style={{ borderBottom: '1px solid var(--bd-1)' }}
              >
                <div>
                  <div className="text-[12.5px] text-text-dark-primary">
                    {g.from_phase_code} → {g.to_phase_code}
                  </div>
                  <div className="text-[10.5px] text-text-dark-tertiary mt-0.5">
                    {g.reason ?? 'sem nota'} ·{' '}
                    {g.n_observations != null
                      ? `${g.n_observations} obs.`
                      : 'seed'}
                  </div>
                </div>
                <input
                  type="number"
                  step="0.5"
                  defaultValue={g.min_gap_hours}
                  onChange={(e) =>
                    setEdits((s) => ({ ...s, [keyOf(g)]: e.target.value }))
                  }
                  className="w-full px-2.5 py-1.5 rounded-md text-[12px] tabular-nums bg-white text-slate-900 placeholder:text-slate-400 border border-bd-2 focus:outline-none focus:border-accent-500"
                />
                <DarkBadge
                  variant={g.source === 'db' ? 'accent' : 'neutral'}
                  size="sm"
                >
                  {g.source === 'db' ? 'editado' : 'seed'}
                </DarkBadge>
                <button
                  type="button"
                  onClick={() => handleSave(g)}
                  disabled={updateMutation.isPending}
                  className="inline-flex items-center justify-center gap-1 px-2 py-1.5 rounded-md bg-accent-500 text-white hover:bg-accent-400 text-[11px] font-medium disabled:opacity-50 transition-colors"
                >
                  <Save size={11} />
                  Guardar
                </button>
              </div>
            ))}
            <p className="text-[10.5px] text-text-dark-tertiary mt-2">
              Cada alteração exige razão ≥10 caracteres e grava audit. O CPO
              apanha o novo valor no próximo <code>/v1/plan/cpo/schedule</code>.
            </p>
          </div>
        )}
      </div>
    </ConfigCard>
  );
}

// ═══ Tab Trust ═══════════════════════════════════════════════════════════════
