/**
 * MelhoresPorFaseTab — Q.155.C · /configuracoes?tab=melhores
 *
 * Define MANUALMENTE, por fase, os melhores operadores (ordenados por rank). O
 * CPO usa esta lista para pôr os barcos mais complexos nas mãos destes (Q.155.D).
 * A afinidade histórica (com shrinkage) aparece como SUGESTÃO. Adicionar por nome
 * pede confirmação (nome + código). Avisa quando o operador não é capaz da fase
 * (axioma 5 — preferir não o torna elegível). ZERO MOCKS, dark, PT-PT.
 */
import { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowUp, ArrowDown, X, Plus, Star, AlertTriangle } from 'lucide-react';
import { DarkCard, DarkButton, DarkBadge, EmptyState, Modal } from '../../../components/dark';
import { SkeletonLoader } from '../../../components/ui/Skeleton';
import { useToastContext } from '../../../components/ToastProvider';
import {
  phasePreferredApi,
  employeesApi,
  entityApi,
  type PreferredSuggestionItem,
} from '../../../lib/api';
import { phasePreferredKeys, coreKeys, entityKeys } from '../../../lib/api/keys';

interface DraftOp {
  employee_code: string;
  employee_name: string;
  note: string | null;
}

interface EmployeeOpt {
  employee_code: string;
  employee_name: string;
}

export function MelhoresPorFaseTab() {
  const toast = useToastContext();
  const queryClient = useQueryClient();
  const [phaseId, setPhaseId] = useState<string>('');
  const [draft, setDraft] = useState<DraftOp[]>([]);
  const [loadedPhase, setLoadedPhase] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [pending, setPending] = useState<EmployeeOpt | null>(null); // confirmação add-by-name

  const phasesQuery = useQuery({
    queryKey: phasePreferredKeys.phases(),
    queryFn: () => phasePreferredApi.listPhases(),
    staleTime: 10 * 60_000,
  });

  const preferredQuery = useQuery({
    queryKey: phasePreferredKeys.forPhase(phaseId),
    queryFn: () => phasePreferredApi.get(phaseId),
    enabled: Boolean(phaseId),
  });

  // capable_worker_ids reutilizados da config de fase (Q.135) p/ is_capable dos adds manuais.
  const configQuery = useQuery({
    queryKey: entityKeys.faseConfig(phaseId),
    queryFn: () => entityApi.phaseConfig.get(phaseId),
    enabled: Boolean(phaseId),
  });

  // Q.159 — só operadores ATIVOS (~107) para curar "melhores por fase".
  const employeesQuery = useQuery({
    queryKey: coreKeys.employeesActiveForPlanEditor(),
    queryFn: () => employeesApi.list({ limit: 1000, active_only: true }),
    staleTime: 10 * 60_000,
  });

  const capableSet = useMemo(() => {
    const ids = configQuery.data?.baselines?.capable_worker_ids ?? [];
    return new Set(ids.map(String));
  }, [configQuery.data]);

  const empOptions = useMemo<EmployeeOpt[]>(() => {
    const rows = (employeesQuery.data ?? []) as Array<{
      employee_code?: string;
      employee_name?: string;
      status?: string;
    }>;
    return rows
      .filter((e) => e.employee_code && e.employee_name && e.status === 'ACTIVE')
      .map((e) => ({
        employee_code: String(e.employee_code),
        employee_name: String(e.employee_name),
      }))
      .sort((a, b) => a.employee_name.localeCompare(b.employee_name, 'pt'));
  }, [employeesQuery.data]);

  // Sincroniza o draft a partir do servidor quando muda de fase / chegam dados.
  useEffect(() => {
    if (preferredQuery.data && preferredQuery.data.phase_id === phaseId && loadedPhase !== phaseId) {
      setDraft(
        preferredQuery.data.curated.map((c) => ({
          employee_code: c.employee_code,
          employee_name: c.employee_name,
          note: c.note,
        })),
      );
      setLoadedPhase(phaseId);
    }
  }, [preferredQuery.data, phaseId, loadedPhase]);

  const draftCodes = useMemo(() => new Set(draft.map((d) => d.employee_code)), [draft]);

  const dirty = useMemo(() => {
    const server = (preferredQuery.data?.curated ?? []).map((c) => c.employee_code);
    const local = draft.map((d) => d.employee_code);
    return JSON.stringify(server) !== JSON.stringify(local);
  }, [preferredQuery.data, draft]);

  const mutation = useMutation({
    mutationFn: () =>
      phasePreferredApi.put(
        phaseId,
        draft.map((d) => ({ employee_code: d.employee_code, note: d.note })),
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: phasePreferredKeys.forPhase(phaseId) });
      setLoadedPhase(null); // força re-sync do draft a partir do servidor
      toast.success('Melhores da fase guardados.');
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : 'Erro ao guardar.');
    },
  });

  function move(idx: number, dir: -1 | 1) {
    setDraft((prev) => {
      const next = [...prev];
      const j = idx + dir;
      if (j < 0 || j >= next.length) return prev;
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    });
  }
  function remove(code: string) {
    setDraft((prev) => prev.filter((d) => d.employee_code !== code));
  }
  function addOp(code: string, nameFallback: string) {
    if (draftCodes.has(code)) return;
    const emp = empOptions.find((e) => e.employee_code === code);
    setDraft((prev) => [
      ...prev,
      { employee_code: code, employee_name: emp?.employee_name ?? nameFallback, note: null },
    ]);
  }

  const phases = phasesQuery.data ?? [];
  const suggestions: PreferredSuggestionItem[] = (preferredQuery.data?.suggestions ?? []).filter(
    (s) => !draftCodes.has(s.employee_code),
  );
  const searchMatches = search.trim()
    ? empOptions
        .filter(
          (e) =>
            !draftCodes.has(e.employee_code) &&
            (e.employee_name.toLowerCase().includes(search.toLowerCase()) ||
              e.employee_code.includes(search.trim())),
        )
        .slice(0, 8)
    : [];

  return (
    <div className="flex flex-col gap-4">
      <DarkCard>
        <h3 className="text-sm font-semibold text-text-dark-primary mb-1">Melhores operadores por fase</h3>
        <p className="text-xs text-text-dark-tertiary mb-3">
          Escolhe a fase e define a ordem dos melhores. O planeamento (CPO) coloca os barcos mais
          complexos nas mãos destes operadores.
        </p>
        <label className="block text-xs text-text-dark-secondary mb-1">Fase de produção</label>
        <select
          value={phaseId}
          onChange={(e) => {
            setPhaseId(e.target.value);
            setLoadedPhase(null);
            setSearch('');
          }}
          className="bg-white text-slate-900 placeholder:text-slate-400 rounded-md px-3 py-2 text-sm w-full max-w-md border border-white/10"
        >
          <option value="">— escolhe uma fase —</option>
          {phases.map((p) => (
            <option key={p.phase_id} value={p.phase_id}>
              {p.phase_name} ({p.phase_id})
            </option>
          ))}
        </select>
      </DarkCard>

      {!phaseId && (
        <EmptyState title="Sem fase escolhida" hint="Escolhe uma fase acima para definir os melhores." size="sm" />
      )}

      {phaseId && (preferredQuery.isLoading || configQuery.isLoading) && <SkeletonLoader count={4} />}

      {phaseId && preferredQuery.data && (
        <div className="grid gap-4 lg:grid-cols-2">
          {/* ── Curados (ordenados por rank) ── */}
          <DarkCard>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-text-dark-primary">
                Melhores (curado) · {draft.length}
              </h3>
              <DarkButton size="sm" disabled={!dirty || mutation.isPending} onClick={() => mutation.mutate()}>
                {mutation.isPending ? 'A guardar…' : 'Guardar'}
              </DarkButton>
            </div>

            {draft.length === 0 ? (
              <EmptyState
                title="Sem melhores definidos"
                hint="Adiciona das sugestões ou por nome. Sem lista, o CPO usa a afinidade."
                size="sm"
                mascot={false}
              />
            ) : (
              <ul className="flex flex-col gap-1.5">
                {draft.map((d, idx) => {
                  const capable = capableSet.size === 0 ? true : capableSet.has(d.employee_code);
                  return (
                    <li
                      key={d.employee_code}
                      className="flex items-center gap-2 rounded-md px-2.5 py-1.5"
                      style={{ background: 'var(--bg-2)' }}
                    >
                      <span className="text-[11px] tabular-nums w-5 text-text-dark-tertiary">#{idx + 1}</span>
                      <Star size={13} className={idx === 0 ? 'text-amber-300' : 'text-slate-600'} />
                      <span className="flex-1 min-w-0 text-sm text-text-dark-primary truncate">
                        {d.employee_name}
                        <span className="text-text-dark-tertiary text-xs tabular-nums"> {d.employee_code}</span>
                      </span>
                      {!capable && (
                        <DarkBadge variant="warning">
                          <AlertTriangle size={10} /> não capaz
                        </DarkBadge>
                      )}
                      <button
                        type="button"
                        aria-label="subir"
                        disabled={idx === 0}
                        onClick={() => move(idx, -1)}
                        className="text-text-dark-tertiary hover:text-text-dark-primary disabled:opacity-30"
                      >
                        <ArrowUp size={14} />
                      </button>
                      <button
                        type="button"
                        aria-label="descer"
                        disabled={idx === draft.length - 1}
                        onClick={() => move(idx, 1)}
                        className="text-text-dark-tertiary hover:text-text-dark-primary disabled:opacity-30"
                      >
                        <ArrowDown size={14} />
                      </button>
                      <button
                        type="button"
                        aria-label="remover"
                        onClick={() => remove(d.employee_code)}
                        className="text-text-dark-tertiary hover:text-rose-300"
                      >
                        <X size={14} />
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}

            {/* Adicionar por nome */}
            <div className="mt-3 relative">
              <label className="block text-xs text-text-dark-secondary mb-1">Adicionar por nome</label>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Escreve o nome do colaborador…"
                className="bg-white text-slate-900 placeholder:text-slate-400 rounded-md px-3 py-2 text-sm w-full border border-white/10"
              />
              {searchMatches.length > 0 && (
                <ul
                  className="absolute z-10 mt-1 w-full rounded-md border border-white/10 shadow-lg max-h-56 overflow-auto"
                  style={{ background: 'var(--bg-1)' }}
                >
                  {searchMatches.map((e) => (
                    <li key={e.employee_code}>
                      <button
                        type="button"
                        onClick={() => {
                          setPending(e);
                          setSearch('');
                        }}
                        className="w-full text-left px-3 py-1.5 text-sm text-text-dark-secondary hover:bg-white/10 flex items-center gap-2"
                      >
                        <Plus size={12} className="text-text-dark-tertiary" />
                        <span className="flex-1">{e.employee_name}</span>
                        <span className="text-xs tabular-nums text-text-dark-tertiary">{e.employee_code}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </DarkCard>

          {/* ── Sugestões (afinidade histórica, shrunk) ── */}
          <DarkCard>
            <h3 className="text-sm font-semibold text-text-dark-primary mb-1">Sugestões (afinidade)</h3>
            <p className="text-xs text-text-dark-tertiary mb-2">
              Do histórico real, ponderado por nº de amostras. Clica para adicionar.
            </p>
            {suggestions.length === 0 ? (
              <EmptyState title="Sem sugestões" hint="Sem afinidade registada (ou já estão todos curados)." size="sm" mascot={false} />
            ) : (
              <ul className="flex flex-col gap-1.5">
                {suggestions.map((s) => (
                  <li key={s.employee_code}>
                    <button
                      type="button"
                      onClick={() => addOp(s.employee_code, s.employee_name)}
                      className="w-full flex items-center gap-2 rounded-md px-2.5 py-1.5 text-left hover:bg-white/10"
                      style={{ background: 'var(--bg-2)' }}
                    >
                      <Plus size={13} className="text-emerald-300" />
                      <span className="flex-1 min-w-0 text-sm text-text-dark-primary truncate">
                        {s.employee_name}
                        <span className="text-text-dark-tertiary text-xs tabular-nums"> {s.employee_code}</span>
                      </span>
                      {!s.is_capable && <DarkBadge variant="warning">não capaz</DarkBadge>}
                      <DarkBadge variant="neutral">{s.score.toFixed(2)}</DarkBadge>
                      <span className="text-[11px] text-text-dark-tertiary tabular-nums">n={s.sample_count}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </DarkCard>
        </div>
      )}

      {/* Modal de confirmação do add-by-name */}
      <Modal
        open={pending !== null}
        onClose={() => setPending(null)}
        title="Confirmar colaborador"
        footer={
          <>
            <DarkButton variant="secondary" size="sm" onClick={() => setPending(null)}>
              Cancelar
            </DarkButton>
            <DarkButton
              size="sm"
              onClick={() => {
                if (pending) addOp(pending.employee_code, pending.employee_name);
                setPending(null);
              }}
            >
              Sim, é este
            </DarkButton>
          </>
        }
      >
        {pending && (
          <div className="text-sm text-text-dark-secondary">
            É mesmo este colaborador?
            <div className="mt-2 rounded-md px-3 py-2" style={{ background: 'var(--bg-2)' }}>
              <span className="text-text-dark-primary font-medium">{pending.employee_name}</span>
              <span className="text-text-dark-tertiary tabular-nums"> · {pending.employee_code}</span>
            </div>
            {capableSet.size > 0 && !capableSet.has(pending.employee_code) && (
              <p className="mt-2 text-xs text-amber-300 flex items-center gap-1">
                <AlertTriangle size={12} /> Não é capaz desta fase — o CPO não o vai atribuir (axioma 5).
              </p>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
