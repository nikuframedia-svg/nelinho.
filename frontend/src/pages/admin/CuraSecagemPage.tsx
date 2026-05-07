/**
 * CuraSecagemPage — Sprint X.3 (Plan v4 §4.7 / L2 lacuna).
 *
 * Tabela editável das 16 transições mandatórias de cura/secagem. Cada
 * linha mostra fase de origem, fase de destino, horas mínimas e a
 * proveniência (seed canónico vs override em DB para o tenant).
 *
 * Editar uma linha abre o ConfigParam (PR-X2) com:
 *   - Razão obrigatória ≥10 chars (espelha constraint backend)
 *   - Aviso sobre química real
 *   - Após gravar, invalida ['phase-gaps'] e o CPO usa o novo valor
 *     na próxima execução de schedule.
 *
 * Página standalone em /admin/cura-secagem (não toca SettingsPage 1.870 L).
 */

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, FlaskConical, Loader2, RefreshCw, Save, ServerCrash, X } from 'lucide-react';
import { phaseGapsApi, type PhaseGap } from '../../lib/api';
import { DarkPageLayout } from '../../layouts';
import { DarkBadge, DarkButton, DarkCard, DarkInput } from '../../components/dark';

const REASON_MIN = 10;

function fmtPhaseCode(code: string): string {
  // "LAMINAGEM_INFUSAO" → "Laminagem infusão" (rough — keep ASCII for now,
  // full pt-PT phase glossary is out of scope for this PR).
  return code
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/, (c) => c.toUpperCase());
}

function reasonLabel(reason?: string | null): { label: string; tone: 'info' | 'warning' | 'success' | 'neutral' } {
  if (!reason) return { label: '—', tone: 'neutral' };
  const lower = reason.toLowerCase();
  if (lower.includes('curing_resin')) return { label: 'Cura resina', tone: 'warning' };
  if (lower.includes('curing_glue')) return { label: 'Cura cola', tone: 'warning' };
  if (lower.includes('drying_paint')) return { label: 'Secagem tinta', tone: 'info' };
  if (lower.includes('drying_varnish')) return { label: 'Secagem verniz', tone: 'info' };
  if (lower.includes('drying')) return { label: 'Secagem', tone: 'info' };
  if (lower.includes('curing_infusion')) return { label: 'Cura infusão', tone: 'warning' };
  if (reason.length > 32) return { label: reason.slice(0, 30) + '…', tone: 'success' };
  return { label: reason, tone: 'success' };
}

function PhaseGapRow({ gap }: { gap: PhaseGap }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [hours, setHours] = useState<string>(String(gap.min_gap_hours));
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const updateMutation = useMutation({
    mutationFn: () =>
      phaseGapsApi.update(gap.from_phase_code, gap.to_phase_code, {
        min_gap_hours: Number(hours),
        reason: reason.trim(),
      }),
    onSuccess: () => {
      setEditing(false);
      setReason('');
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['phase-gaps'] });
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : String(err));
    },
  });

  const numericHours = Number(hours);
  const validHours = Number.isFinite(numericHours) && numericHours > 0 && numericHours <= 72;
  const validReason = reason.trim().length >= REASON_MIN;
  const canSave = validHours && validReason && !updateMutation.isPending;
  const seedReason = reasonLabel(gap.reason);
  const isOverridden = gap.source === 'db';

  return (
    <>
      <tr className="border-b border-slate-800 hover:bg-slate-800/30">
        <td className="px-3 py-2 text-slate-200">
          {fmtPhaseCode(gap.from_phase_code)}
          <div className="text-[10px] font-mono text-slate-500">{gap.from_phase_code}</div>
        </td>
        <td className="px-3 py-2 text-slate-200">
          {fmtPhaseCode(gap.to_phase_code)}
          <div className="text-[10px] font-mono text-slate-500">{gap.to_phase_code}</div>
        </td>
        <td className="px-3 py-2 font-mono text-slate-100 text-right">
          {gap.min_gap_hours.toFixed(1)} h
        </td>
        <td className="px-3 py-2">
          <DarkBadge variant={seedReason.tone}>{seedReason.label}</DarkBadge>
        </td>
        <td className="px-3 py-2 text-slate-400 font-mono text-xs">
          {gap.n_observations ?? '—'}
        </td>
        <td className="px-3 py-2">
          {isOverridden ? (
            <DarkBadge variant="warning">Override</DarkBadge>
          ) : (
            <DarkBadge variant="neutral">Seed</DarkBadge>
          )}
        </td>
        <td className="px-3 py-2 text-right">
          <DarkButton
            variant="secondary"
            onClick={() => setEditing((v) => !v)}
            disabled={updateMutation.isPending}
          >
            {editing ? (
              <>
                <X className="w-3.5 h-3.5" /> Fechar
              </>
            ) : (
              'Editar'
            )}
          </DarkButton>
        </td>
      </tr>
      {editing ? (
        <tr key={`${gap.from_phase_code}-${gap.to_phase_code}-edit`}>
          <td colSpan={7} className="bg-slate-900/60 p-4 border-b border-slate-800">
            <div className="flex flex-col gap-3">
              <div className="flex items-start gap-2 text-amber-200 text-xs">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <strong>Química real.</strong> Estes tempos são cura de
                  resina/cola e secagem de tinta/verniz. Mudanças sem
                  evidência empírica podem produzir defeitos. Cada edição
                  requer razão registada (alimenta a aprendizagem).
                </div>
              </div>
              <div className="flex flex-wrap items-end gap-3">
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] uppercase tracking-wider text-slate-400">
                    Novas horas mínimas
                  </label>
                  <DarkInput
                    type="number"
                    min={0.5}
                    max={72}
                    step={0.5}
                    value={hours}
                    onChange={(e) => setHours(e.target.value)}
                    disabled={updateMutation.isPending}
                  />
                </div>
                <div className="flex-1 min-w-[300px] flex flex-col gap-1">
                  <label className="text-[11px] uppercase tracking-wider text-slate-400">
                    Razão (mín. {REASON_MIN} chars)
                  </label>
                  <textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    disabled={updateMutation.isPending}
                    rows={2}
                    placeholder="Ex: novo verniz exige tempo extra de polimerização — testado lab Q3"
                    className={`w-full rounded-md border bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500/40 disabled:opacity-60 ${
                      reason.length === 0 || validReason
                        ? 'border-slate-700/70'
                        : 'border-amber-500/60'
                    }`}
                  />
                </div>
              </div>
              {error ? <div className="text-xs text-rose-300">{error}</div> : null}
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-slate-500">
                  {validReason
                    ? '✓ Razão suficiente'
                    : `Faltam ${Math.max(0, REASON_MIN - reason.trim().length)} caracteres`}
                  {' · '}
                  {validHours ? '✓ Horas válidas (0.5 – 72)' : '⚠ Horas fora do intervalo válido'}
                </span>
                <DarkButton
                  variant="primary"
                  disabled={!canSave}
                  onClick={() => updateMutation.mutate()}
                >
                  {updateMutation.isPending ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Save className="w-3.5 h-3.5" />
                  )}
                  Guardar gap
                </DarkButton>
              </div>
            </div>
          </td>
        </tr>
      ) : null}
    </>
  );
}

export default function CuraSecagemPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['phase-gaps'],
    queryFn: () => phaseGapsApi.list(),
    staleTime: 30_000,
  });

  const gaps = data?.items ?? [];

  return (
    <DarkPageLayout
      title="Cura / Secagem"
      subtitle="16 transições mandatórias entre fases. Química real — cada edição é auditada."
      icon={<FlaskConical className="w-6 h-6 text-amber-300" />}
      actions={
        <DarkButton
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ['phase-gaps'] });
            refetch();
          }}
          variant="secondary"
          disabled={isFetching}
        >
          <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          Actualizar
        </DarkButton>
      }
    >
      <div className="flex flex-col gap-4">
        <DarkCard className="border-amber-500/30 bg-amber-500/5 p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-300 shrink-0 mt-0.5" />
          <div className="text-sm text-amber-100">
            <strong className="text-amber-50">Atenção: química real.</strong> Estes
            tempos são cura de resina/cola e secagem de tinta/verniz. O CPO
            scheduler usa-os como restrições mínimas obrigatórias entre
            fases. Encurtá-los pode produzir defeitos no produto final
            (fissuras, descolagem, película mole). Cada edição grava a
            razão no audit trail e alimenta a aprendizagem.
          </div>
        </DarkCard>

        {isLoading ? (
          <DarkCard className="p-10 flex items-center justify-center gap-2 text-slate-300">
            <Loader2 className="w-5 h-5 animate-spin text-sky-300" />
            A carregar transições...
          </DarkCard>
        ) : error ? (
          <DarkCard className="p-10 flex flex-col items-center justify-center gap-3 border-rose-500/30 bg-rose-500/5 text-rose-200">
            <ServerCrash className="w-8 h-8" />
            <div className="text-base font-semibold">
              Não consegui ler as transições.
            </div>
            <div className="text-sm text-rose-200/80 max-w-lg text-center">
              {error instanceof Error ? error.message : String(error)}
            </div>
            <DarkButton onClick={() => refetch()} variant="primary">
              Tentar de novo
            </DarkButton>
          </DarkCard>
        ) : gaps.length === 0 ? (
          <DarkCard className="p-10 flex flex-col items-center gap-2 text-slate-400">
            <FlaskConical className="w-10 h-10 text-slate-600" />
            <div className="text-base text-slate-200">Sem transições registadas.</div>
            <div className="text-sm">
              O backend devolveu uma lista vazia. Verifica
              <code className="mx-1 font-mono text-amber-200">/v1/plan/phase-gaps</code>
              ao vivo.
            </div>
          </DarkCard>
        ) : (
          <DarkCard className="p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 text-[11px] uppercase tracking-wider border-b border-slate-800">
                  <th className="px-3 py-2">De fase</th>
                  <th className="px-3 py-2">Para fase</th>
                  <th className="px-3 py-2 text-right">Horas mínimas</th>
                  <th className="px-3 py-2">Tipo</th>
                  <th className="px-3 py-2">N. obs.</th>
                  <th className="px-3 py-2">Origem</th>
                  <th className="px-3 py-2 text-right">Acção</th>
                </tr>
              </thead>
              <tbody>
                {gaps.map((gap) => (
                  <PhaseGapRow
                    key={`${gap.from_phase_code}-${gap.to_phase_code}`}
                    gap={gap}
                  />
                ))}
              </tbody>
            </table>
            <div className="px-4 py-2 text-[11px] text-slate-500 border-t border-slate-800">
              {gaps.length} transição{gaps.length === 1 ? '' : 'ões'}
              {' · '}
              <span className="text-amber-300">
                {gaps.filter((g) => g.source === 'db').length} override
                {gaps.filter((g) => g.source === 'db').length === 1 ? '' : 's'}
              </span>
              {' · '}
              <span className="text-slate-400">
                {gaps.filter((g) => g.source !== 'db').length} seed
              </span>
            </div>
          </DarkCard>
        )}
      </div>
    </DarkPageLayout>
  );
}
