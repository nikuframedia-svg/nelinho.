/**
 * ConfiguracoesPage — /configuracoes · Q.115.O
 *
 * 6 tabs consolidadas:
 *   master       → herda ConfiguracaoPage (Master Data)
 *   regras       → herda RegrasPage (Q.17 logic-as-data)
 *   logica-llm   → link para /regras?tab=prompts
 *   custos       → Revenue Target + Client Priority (Q.115.B)
 *   input        → Wizard 3 passos PT-natural (Q.115.B)
 *   aprendizagem → herda AprendiPage
 *
 * ZERO MOCKS — endpoints faltantes → empty state explícito.
 */

import { lazy, Suspense, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Settings,
  BookOpen,
  Brain,
  Euro,
  MessageSquarePlus,
  ExternalLink,
  ChevronRight,
  CheckCircle2,
} from 'lucide-react';
import { PageHeader, Tabs, DarkCard, DarkButton, DarkBadge, EmptyState, Modal } from '../../components/dark';
import { DarkPageLayout } from '../../layouts';
import { SkeletonLoader } from '../../components/ui/Skeleton';
import {
  revenueTargetApi,
  clientPriorityApi,
  userInputApi,
  type RevenueTarget,
  type ClientPriority,
  type UserInputStatus,
} from '../../lib/api';
import {
  revenueTargetKeys,
  clientPriorityKeys,
  userInputKeys,
} from '../../lib/api/keys';
import { useToastContext } from '../../components/ToastProvider';

// Páginas herdadas — lazy para não bloquear o bundle inicial
const ConfiguracaoPage = lazy(() => import('../configuracao/ConfiguracaoPage'));
const RegrasPage = lazy(() => import('../admin/RegrasPage'));
const AprendiPage = lazy(() => import('../aprendi/AprendiPage'));

// ─── tipos locais ──────────────────────────────────────────────────────────────

const TAB_IDS = ['master', 'regras', 'logica-llm', 'custos', 'input', 'aprendizagem'] as const;
type TabId = (typeof TAB_IDS)[number];

function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

const TABS = [
  { id: 'master', label: 'Master Data', icon: <Settings size={13} /> },
  { id: 'regras', label: 'Regras', icon: <BookOpen size={13} /> },
  { id: 'logica-llm', label: 'Lógica LLM', icon: <Brain size={13} /> },
  { id: 'custos', label: 'Custos & Objectivos', icon: <Euro size={13} /> },
  { id: 'input', label: 'Input', icon: <MessageSquarePlus size={13} /> },
  { id: 'aprendizagem', label: 'Aprendizagem', icon: <Brain size={13} /> },
] as const;

// ─── Tab: Custos & Objectivos ─────────────────────────────────────────────────

function TabCustos() {
  const toast = useToastContext();
  const queryClient = useQueryClient();

  // Revenue targets
  const revenueQuery = useQuery({
    queryKey: revenueTargetKeys.lists(),
    queryFn: () => revenueTargetApi.list(),
  });

  // Client priority
  const priorityQuery = useQuery({
    queryKey: clientPriorityKeys.lists(),
    queryFn: () => clientPriorityApi.list(),
  });

  // Modal novo objectivo
  const [modalOpen, setModalOpen] = useState(false);
  const [newTarget, setNewTarget] = useState({ effective_from: '', target_eur: '' });
  const [targetError, setTargetError] = useState<string | null>(null);

  const createTargetMutation = useMutation({
    mutationFn: () =>
      revenueTargetApi.create({
        effective_from: newTarget.effective_from,
        target_eur: Number(newTarget.target_eur),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: revenueTargetKeys.all });
      toast.success('Objectivo guardado');
      setModalOpen(false);
      setNewTarget({ effective_from: '', target_eur: '' });
      setTargetError(null);
    },
    onError: (err: Error) => {
      const msg = err.message ?? '';
      if (msg.includes('409') || msg.toLowerCase().includes('duplicate')) {
        setTargetError('Já existe objectivo para esta data');
      } else if (msg.includes('422') || msg.toLowerCase().includes('target')) {
        setTargetError('O valor tem de ser maior que 0');
      } else {
        setTargetError('Erro ao guardar objectivo');
      }
    },
  });

  // Edição inline de prioridade
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<{ prioridade: number; razao: string }>({ prioridade: 1, razao: '' });
  const [prioritySearch, setPrioritySearch] = useState('');
  const [priorityFilter, setPriorityFilter] = useState<number | null>(null);

  const updatePriorityMutation = useMutation({
    mutationFn: ({ clienteId, prioridade, razao }: { clienteId: string; prioridade: number; razao: string }) =>
      clientPriorityApi.update(clienteId, { prioridade, razao }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: clientPriorityKeys.all });
      toast.success('Prioridade actualizada');
      setEditingId(null);
    },
    onError: () => {
      toast.error('Erro ao actualizar prioridade');
    },
  });

  const priorities = priorityQuery.data ?? [];
  const filteredPriorities = priorities.filter((p) => {
    const matchSearch = prioritySearch === '' || p.cliente_id.toLowerCase().includes(prioritySearch.toLowerCase());
    const matchFilter = priorityFilter === null || p.prioridade === priorityFilter;
    return matchSearch && matchFilter;
  });

  const PRIORITY_VARIANT: Record<number, 'danger' | 'warning' | 'info' | 'neutral' | 'success'> = {
    1: 'danger',
    2: 'warning',
    3: 'info',
    4: 'neutral',
    5: 'success',
  };

  return (
    <div className="space-y-8">
      {/* ── Secção A: Objectivo de faturação ── */}
      <DarkCard>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-text-dark-primary">Objectivo de faturação diário</h3>
            <p className="text-xs text-text-dark-tertiary mt-0.5">
              Define a meta diária em €. O CPO usa este valor para avaliar planos.
            </p>
          </div>
          <DarkButton size="sm" onClick={() => setModalOpen(true)}>
            Definir novo objectivo
          </DarkButton>
        </div>

        {revenueQuery.isLoading && <SkeletonLoader count={3} />}
        {revenueQuery.isError && (
          <EmptyState
            title="Erro ao carregar objectivos"
            hint="Verifica a ligação ao backend."
            action={<DarkButton size="sm" onClick={() => revenueQuery.refetch()}>Tentar novamente</DarkButton>}
          />
        )}
        {revenueQuery.isSuccess && (revenueQuery.data ?? []).length === 0 && (
          <EmptyState
            title="Sem objectivos definidos"
            hint="Clica em 'Definir novo objectivo' para criar o primeiro."
          />
        )}
        {revenueQuery.isSuccess && (revenueQuery.data ?? []).length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/10 text-text-dark-tertiary">
                  <th className="pb-2 text-left font-medium">A partir de</th>
                  <th className="pb-2 text-right font-medium">Objectivo (€)</th>
                  <th className="pb-2 text-left font-medium pl-4">Criado por</th>
                </tr>
              </thead>
              <tbody>
                {(revenueQuery.data ?? []).map((t: RevenueTarget) => (
                  <tr key={t.id} className="border-b border-white/5 hover:bg-white/5">
                    <td className="py-2 text-text-dark-secondary">
                      {new Date(t.effective_from).toLocaleDateString('pt-PT')}
                    </td>
                    <td className="py-2 text-right font-mono font-semibold text-text-dark-primary">
                      {t.target_eur.toLocaleString('pt-PT', { style: 'currency', currency: 'EUR' })}
                    </td>
                    <td className="py-2 pl-4 text-text-dark-tertiary">{t.created_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DarkCard>

      {/* Modal novo objectivo */}
      <Modal
        open={modalOpen}
        onClose={() => { setModalOpen(false); setTargetError(null); }}
        title="Definir novo objectivo de faturação"
        footer={
          <div className="flex gap-2 justify-end">
            <DarkButton variant="ghost" onClick={() => { setModalOpen(false); setTargetError(null); }}>
              Cancelar
            </DarkButton>
            <DarkButton
              disabled={!newTarget.effective_from || !newTarget.target_eur || Number(newTarget.target_eur) <= 0 || createTargetMutation.isPending}
              onClick={() => createTargetMutation.mutate()}
            >
              {createTargetMutation.isPending ? 'A guardar…' : 'Guardar'}
            </DarkButton>
          </div>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-text-dark-secondary mb-1">A partir de</label>
            <input
              type="date"
              className="w-full bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-2 text-sm"
              value={newTarget.effective_from}
              onChange={(e) => setNewTarget((p) => ({ ...p, effective_from: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs text-text-dark-secondary mb-1">Objectivo (€)</label>
            <input
              type="number"
              min={1}
              step={100}
              className="w-full bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-2 text-sm"
              placeholder="ex: 32000"
              value={newTarget.target_eur}
              onChange={(e) => setNewTarget((p) => ({ ...p, target_eur: e.target.value }))}
            />
          </div>
          {targetError && (
            <p className="text-xs text-red-400">{targetError}</p>
          )}
        </div>
      </Modal>

      {/* ── Secção B: Prioridade de clientes ── */}
      <DarkCard>
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-text-dark-primary">Prioridade de clientes</h3>
          <p className="text-xs text-text-dark-tertiary mt-0.5">
            Prioridade 1 (mais urgente) a 5 (normal). Afecta a ordem de atribuição de capacidade.
          </p>
        </div>

        {/* filtros */}
        <div className="flex gap-3 mb-4 flex-wrap">
          <input
            type="search"
            placeholder="Pesquisar cliente…"
            className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-1.5 text-xs w-48"
            value={prioritySearch}
            onChange={(e) => setPrioritySearch(e.target.value)}
          />
          <div className="flex gap-1">
            {[null, 1, 2, 3, 4, 5].map((v) => (
              <button
                key={v ?? 'all'}
                onClick={() => setPriorityFilter(v)}
                className={`px-2 py-1 rounded text-xs border transition-colors ${
                  priorityFilter === v
                    ? 'bg-blue-600 border-blue-600 text-white'
                    : 'border-white/20 text-text-dark-tertiary hover:border-white/40'
                }`}
              >
                {v === null ? 'Todos' : v}
              </button>
            ))}
          </div>
        </div>

        {priorityQuery.isLoading && <SkeletonLoader count={4} />}
        {priorityQuery.isError && (
          <EmptyState
            title="Erro ao carregar prioridades"
            hint="Verifica a ligação ao backend."
            action={<DarkButton size="sm" onClick={() => priorityQuery.refetch()}>Tentar novamente</DarkButton>}
          />
        )}
        {priorityQuery.isSuccess && filteredPriorities.length === 0 && (
          <EmptyState
            title="Sem clientes com prioridade definida"
            hint="Os clientes aparecem aqui quando a prioridade for configurada no backend."
          />
        )}
        {priorityQuery.isSuccess && filteredPriorities.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/10 text-text-dark-tertiary">
                  <th className="pb-2 text-left font-medium">Cliente</th>
                  <th className="pb-2 text-center font-medium">Prioridade</th>
                  <th className="pb-2 text-left font-medium pl-4">Razão</th>
                  <th className="pb-2 text-right font-medium">Actualizado</th>
                  <th className="pb-2 w-8"></th>
                </tr>
              </thead>
              <tbody>
                {filteredPriorities.map((p: ClientPriority) => (
                  <tr key={p.id} className="border-b border-white/5 hover:bg-white/5">
                    <td className="py-2 font-mono text-text-dark-secondary">{p.cliente_id}</td>
                    <td className="py-2 text-center">
                      {editingId === p.id ? (
                        <select
                          className="bg-white text-slate-900 border border-slate-300 rounded px-1 py-0.5 text-xs"
                          value={editForm.prioridade}
                          onChange={(e) => setEditForm((f) => ({ ...f, prioridade: Number(e.target.value) }))}
                        >
                          {[1, 2, 3, 4, 5].map((v) => <option key={v} value={v}>{v}</option>)}
                        </select>
                      ) : (
                        <DarkBadge variant={PRIORITY_VARIANT[p.prioridade] ?? 'neutral'}>
                          {p.prioridade}
                        </DarkBadge>
                      )}
                    </td>
                    <td className="py-2 pl-4 text-text-dark-tertiary">
                      {editingId === p.id ? (
                        <textarea
                          className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-2 py-1 text-xs w-full resize-none"
                          rows={2}
                          value={editForm.razao}
                          onChange={(e) => setEditForm((f) => ({ ...f, razao: e.target.value }))}
                        />
                      ) : (
                        p.razao ?? <span className="italic">—</span>
                      )}
                    </td>
                    <td className="py-2 text-right text-text-dark-tertiary">
                      {new Date(p.updated_at).toLocaleDateString('pt-PT')}
                    </td>
                    <td className="py-2 text-right">
                      {editingId === p.id ? (
                        <div className="flex gap-1 justify-end">
                          <DarkButton
                            size="sm"
                            disabled={updatePriorityMutation.isPending}
                            onClick={() =>
                              updatePriorityMutation.mutate({
                                clienteId: p.cliente_id,
                                prioridade: editForm.prioridade,
                                razao: editForm.razao,
                              })
                            }
                          >
                            Guardar
                          </DarkButton>
                          <DarkButton
                            size="sm"
                            variant="ghost"
                            onClick={() => setEditingId(null)}
                          >
                            Cancelar
                          </DarkButton>
                        </div>
                      ) : (
                        <DarkButton
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setEditingId(p.id);
                            setEditForm({ prioridade: p.prioridade, razao: p.razao ?? '' });
                          }}
                        >
                          Editar
                        </DarkButton>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DarkCard>
    </div>
  );
}

// ─── Tab: Input wizard 3 passos ───────────────────────────────────────────────

type WizardStep = 1 | 2 | 3;
type WherePage = 'Decisões' | 'Planeamento (Overall)' | 'LLM (Chat / KPIs / Regras)' | 'Configurações';

const WHERE_OPTIONS: WherePage[] = [
  'Decisões',
  'Planeamento (Overall)',
  'LLM (Chat / KPIs / Regras)',
  'Configurações',
];

const STATUS_VARIANT: Record<UserInputStatus, 'neutral' | 'info' | 'success' | 'danger'> = {
  pending: 'neutral',
  in_progress: 'info',
  done: 'success',
  rejected: 'danger',
};

const STATUS_LABEL: Record<UserInputStatus, string> = {
  pending: 'Pendente',
  in_progress: 'Em curso',
  done: 'Concluído',
  rejected: 'Rejeitado',
};

function TabInput() {
  const toast = useToastContext();
  const queryClient = useQueryClient();

  // Wizard state
  const [step, setStep] = useState<WizardStep>(1);
  const [what, setWhat] = useState('');
  const [wherePage, setWherePage] = useState<WherePage | null>(null);
  const [reason, setReason] = useState('');
  const [backendError, setBackendError] = useState<string | null>(null);

  const whatValid = what.trim().length >= 10;
  const whereValid = wherePage !== null;
  const reasonValid = reason.trim().length >= 30;

  const submitMutation = useMutation({
    mutationFn: () =>
      userInputApi.create({
        what: what.trim(),
        where_page: wherePage!,
        economic_reason: reason.trim(),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userInputKeys.all });
      toast.success('Pedido submetido. O Claude remoto irá analisar amanhã às 7h. Vês o resultado em PR.');
      setStep(1);
      setWhat('');
      setWherePage(null);
      setReason('');
      setBackendError(null);
    },
    onError: (err: Error) => {
      const msg = err.message ?? '';
      if (msg.includes('422')) {
        try {
          const parsed = JSON.parse(msg.replace(/^[^{]*/, ''));
          setBackendError(parsed?.detail ?? 'Validação falhou no servidor');
        } catch {
          setBackendError('Descrição demasiado vaga ou razão económica insuficiente');
        }
      } else {
        setBackendError('Erro ao submeter pedido. Tenta novamente.');
      }
    },
  });

  // Pedidos pendentes (polling 30s)
  const pendingQuery = useQuery({
    queryKey: userInputKeys.list('pending'),
    queryFn: () => userInputApi.list({ status: 'pending' }),
    refetchInterval: 30_000,
  });

  const pendingItems = pendingQuery.data ?? [];

  return (
    <div className="space-y-8 max-w-2xl">
      {/* ── Wizard ── */}
      <DarkCard>
        <h3 className="text-base font-semibold text-text-dark-primary mb-1">
          O que queres mudar no nelinho?
        </h3>
        <p className="text-xs text-text-dark-tertiary mb-5">
          Descreve o que precisas em linguagem natural — o agente remoto analisa e abre um PR.
        </p>

        {/* indicador de passos */}
        <div className="flex items-center gap-2 mb-6">
          {([1, 2, 3] as WizardStep[]).map((s) => (
            <div key={s} className="flex items-center gap-2">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold transition-colors ${
                  step === s
                    ? 'bg-blue-600 text-white'
                    : step > s
                    ? 'bg-green-600 text-white'
                    : 'bg-white/10 text-text-dark-tertiary'
                }`}
              >
                {step > s ? <CheckCircle2 size={14} /> : s}
              </div>
              <span
                className={`text-xs ${
                  step === s ? 'text-text-dark-primary font-medium' : 'text-text-dark-tertiary'
                }`}
              >
                {s === 1 ? 'O quê?' : s === 2 ? 'Onde?' : 'Porquê?'}
              </span>
              {s < 3 && <ChevronRight size={12} className="text-text-dark-tertiary" />}
            </div>
          ))}
        </div>

        {/* Passo 1 */}
        {step === 1 && (
          <div className="space-y-3">
            <label className="block text-sm font-medium text-text-dark-secondary">
              Descreve concretamente o que queres mudar
            </label>
            <textarea
              rows={8}
              className="w-full bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="ex: alterar o objectivo de faturação diária para 5500€"
              value={what}
              onChange={(e) => setWhat(e.target.value)}
            />
            <p className="text-xs text-text-dark-tertiary">
              Mínimo 10 caracteres. Descrições vagas como "qualquer coisa" serão rejeitadas.
            </p>
            <div className="flex justify-end">
              <DarkButton
                disabled={!whatValid}
                onClick={() => setStep(2)}
              >
                Próximo
              </DarkButton>
            </div>
          </div>
        )}

        {/* Passo 2 */}
        {step === 2 && (
          <div className="space-y-3">
            <label className="block text-sm font-medium text-text-dark-secondary mb-3">
              Em que página?
            </label>
            <div className="grid grid-cols-2 gap-3">
              {WHERE_OPTIONS.map((opt) => (
                <button
                  key={opt}
                  onClick={() => setWherePage(opt)}
                  className={`px-4 py-3 rounded-lg border text-sm font-medium text-left transition-colors ${
                    wherePage === opt
                      ? 'border-blue-500 bg-blue-600/20 text-blue-300'
                      : 'border-white/20 text-text-dark-secondary hover:border-white/40'
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
            <div className="flex justify-between pt-2">
              <DarkButton variant="ghost" onClick={() => setStep(1)}>
                Anterior
              </DarkButton>
              <DarkButton disabled={!whereValid} onClick={() => setStep(3)}>
                Próximo
              </DarkButton>
            </div>
          </div>
        )}

        {/* Passo 3 */}
        {step === 3 && (
          <div className="space-y-3">
            <label className="block text-sm font-medium text-text-dark-secondary">
              Explica a razão económica concreta — porque precisas desta mudança?
            </label>
            <textarea
              rows={8}
              className="w-full bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="ex: a faturação subiu 15% no último mês e o objectivo está obsoleto, queremos alinhar com o novo patamar"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
            <p className="text-xs text-text-dark-tertiary">
              Mínimo 30 caracteres. Sê concreto sobre o impacto económico.
            </p>
            {backendError && (
              <p className="text-xs text-red-400">{backendError}</p>
            )}
            <div className="flex justify-between pt-2">
              <DarkButton variant="ghost" onClick={() => setStep(2)}>
                Anterior
              </DarkButton>
              <DarkButton
                disabled={!reasonValid || submitMutation.isPending}
                onClick={() => submitMutation.mutate()}
              >
                {submitMutation.isPending ? 'A submeter…' : 'Submeter'}
              </DarkButton>
            </div>
          </div>
        )}
      </DarkCard>

      {/* ── Pedidos pendentes ── */}
      <DarkCard>
        <h3 className="text-sm font-semibold text-text-dark-primary mb-1">Pedidos pendentes</h3>
        <p className="text-xs text-text-dark-tertiary mb-4">
          Actualiza a cada 30 segundos.
        </p>

        {pendingQuery.isLoading && <SkeletonLoader count={3} />}
        {pendingQuery.isError && (
          <EmptyState
            title="Erro ao carregar pedidos"
            hint="Verifica a ligação ao backend."
            action={<DarkButton size="sm" onClick={() => pendingQuery.refetch()}>Tentar novamente</DarkButton>}
          />
        )}
        {pendingQuery.isSuccess && pendingItems.length === 0 && (
          <EmptyState
            title="Sem pedidos pendentes"
            hint="Os pedidos submetidos aparecem aqui enquanto aguardam análise."
          />
        )}
        {pendingQuery.isSuccess && pendingItems.length > 0 && (
          <div className="space-y-2">
            {pendingItems.map((item) => (
              <div
                key={item.id}
                className="flex items-start gap-3 p-3 rounded-lg bg-white/5 border border-white/10"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-text-dark-primary truncate">{item.what}</p>
                  <p className="text-xs text-text-dark-tertiary mt-0.5">{item.where_page}</p>
                  <p className="text-xs text-text-dark-tertiary">
                    {new Date(item.created_at).toLocaleString('pt-PT')}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <DarkBadge variant={STATUS_VARIANT[item.status as UserInputStatus] ?? 'neutral'}>
                    {STATUS_LABEL[item.status as UserInputStatus] ?? item.status}
                  </DarkBadge>
                  {item.pr_url && (
                    <a
                      href={item.pr_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs text-blue-400 hover:underline"
                    >
                      PR <ExternalLink size={10} />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </DarkCard>
    </div>
  );
}

// ─── Tab: Lógica LLM ──────────────────────────────────────────────────────────

function TabLogicaLLM() {
  return (
    <DarkCard className="max-w-lg">
      <div className="flex items-start gap-3">
        <Brain size={20} className="text-blue-400 mt-0.5 shrink-0" />
        <div>
          <h3 className="text-sm font-semibold text-text-dark-primary mb-1">
            Prompts e versionamento LLM
          </h3>
          <p className="text-sm text-text-dark-secondary mb-4">
            A gestão de prompts (Q.112.C) vive na tab Prompts da página Regras.
            Os prompts são versionados em base de dados e auditados.
          </p>
          <a
            href="/regras?tab=prompts"
            className="inline-flex items-center gap-1.5 text-sm text-blue-400 hover:underline"
          >
            Ver Prompts em /regras <ExternalLink size={13} />
          </a>
        </div>
      </div>
    </DarkCard>
  );
}

// ─── Tab: Aprendizagem (wrapper) ──────────────────────────────────────────────

function TabAprendizagem() {
  return (
    <div>
      <Suspense fallback={<div className="p-6"><SkeletonLoader count={5} /></div>}>
        <AprendiPage />
      </Suspense>
      {/* placeholder Q.115.G */}
      <div className="mt-6 px-6">
        <DarkCard>
          <h3 className="text-sm font-semibold text-text-dark-primary mb-1">
            Afinidades fase-operador
          </h3>
          <p className="text-xs text-text-dark-tertiary">
            A preencher quando Q.115.G estiver implementado.
          </p>
        </DarkCard>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Página principal
// ═══════════════════════════════════════════════════════════════════════════════

export default function ConfiguracoesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const activeTab: TabId = isTabId(tabFromUrl) ? tabFromUrl : 'master';

  const handleTabChange = (id: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', id);
    setSearchParams(next, { replace: true });
  };

  return (
    <DarkPageLayout>
      <PageHeader
        title="Configurações"
        subtitle="Master data, regras, custos, input PT-natural e aprendizagem — tudo num só sítio"
        icon={<Settings size={18} />}
      />

      <div className="px-6 pt-3">
        <Tabs
          tabs={TABS as unknown as { id: string; label: string; icon: React.ReactNode }[]}
          value={activeTab}
          onChange={handleTabChange}
          sticky
        />
      </div>

      <div className="px-6 py-5 page-enter">
        {activeTab === 'master' && (
          <Suspense fallback={<div className="p-4"><SkeletonLoader count={5} /></div>}>
            <ConfiguracaoPage />
          </Suspense>
        )}
        {activeTab === 'regras' && (
          <Suspense fallback={<div className="p-4"><SkeletonLoader count={5} /></div>}>
            <RegrasPage />
          </Suspense>
        )}
        {activeTab === 'logica-llm' && <TabLogicaLLM />}
        {activeTab === 'custos' && <TabCustos />}
        {activeTab === 'input' && <TabInput />}
        {activeTab === 'aprendizagem' && <TabAprendizagem />}
      </div>
    </DarkPageLayout>
  );
}
