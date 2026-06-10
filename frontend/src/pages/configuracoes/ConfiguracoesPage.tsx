/**
 * ConfiguracoesPage — /configuracoes · Q.115.O
 *
 * 6 tabs consolidadas:
 *   master       → herda ConfiguracaoPage (Master Data)
 *   regras       → herda RegrasPage (Q.17 logic-as-data)
 *   logica-llm   → link para /llm?tab=regras
 *   custos       → Revenue Target + Client Priority (Q.115.B)
 *   input        → Wizard 3 passos PT-natural (Q.115.B)
 *   aprendizagem → herda AprendiPage
 *
 * ZERO MOCKS — endpoints faltantes → empty state explícito.
 */

import { lazy, Suspense, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { MasterDataTab } from './tabs/MasterDataTab';
import { EquipaNiveisTab } from './tabs/EquipaNiveisTab';
import { MelhoresPorFaseTab } from './tabs/MelhoresPorFaseTab';
import {
  Settings,
  BookOpen,
  Brain,
  Euro,
  MessageSquarePlus,
  ExternalLink,
  ChevronRight,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Users,
  Star,
} from 'lucide-react';
import { PageHeader, Tabs, DarkCard, DarkButton, DarkBadge, EmptyState, Modal } from '../../components/dark';
import { DarkPageLayout } from '../../layouts';
import { SkeletonLoader } from '../../components/ui/Skeleton';
import {
  revenueTargetApi,
  clientPriorityApi,
  userInputApi,
  runbookApi,
  learningPlanApi,
  type RevenueTarget,
  type ClientPriority,
  type UserInputStatus,
  type Runbook,
  type PlanVsActualReport,
} from '../../lib/api';
import { learningAffinitiesApi, preferenceRulesApi, type PreferenceRule } from '../../lib/api/planApi';
import { CentroAprendizagem } from '../../components/configuracoes/CentroAprendizagem';
import {
  revenueTargetKeys,
  clientPriorityKeys,
  userInputKeys,
  learningKeys,
  runbookKeys,
  governanceKeys,
} from '../../lib/api/keys';
import { useToastContext } from '../../components/ToastProvider';

// RegrasPage carregada em lazy — bundle split
const RegrasPage = lazy(() => import('../admin/RegrasPage'));

// ─── tipos locais ──────────────────────────────────────────────────────────────

const TAB_IDS = ['master', 'regras', 'logica-llm', 'custos', 'input', 'aprendizagem', 'equipa', 'melhores'] as const;
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
  { id: 'equipa', label: 'Equipa', icon: <Users size={13} /> },
  { id: 'melhores', label: 'Melhores por fase', icon: <Star size={13} /> },
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
  const [editForm, setEditForm] = useState<{ priority: number; reason: string }>({ priority: 1, reason: '' });
  const [prioritySearch, setPrioritySearch] = useState('');
  const [priorityFilter, setPriorityFilter] = useState<number | null>(null);

  const updatePriorityMutation = useMutation({
    mutationFn: ({ clienteId, priority, reason }: { clienteId: string; priority: number; reason: string }) =>
      clientPriorityApi.update(clienteId, { priority, reason }),
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
    const matchSearch = prioritySearch === '' || p.client_id.toLowerCase().includes(prioritySearch.toLowerCase());
    const matchFilter = priorityFilter === null || p.priority === priorityFilter;
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
              className="w-full bg-bg-2 text-fg-0 placeholder:text-fg-3 border border-bd-2 rounded px-3 py-2 text-sm"
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
              className="w-full bg-bg-2 text-fg-0 placeholder:text-fg-3 border border-bd-2 rounded px-3 py-2 text-sm"
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
            className="bg-bg-2 text-fg-0 placeholder:text-fg-3 border border-bd-2 rounded px-3 py-1.5 text-xs w-48"
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
                  <tr key={p.client_id} className="border-b border-white/5 hover:bg-white/5">
                    <td className="py-2 font-mono text-text-dark-secondary">{p.client_id}</td>
                    <td className="py-2 text-center">
                      {editingId === p.client_id ? (
                        <select
                          className="bg-bg-2 text-fg-0 border border-bd-2 rounded px-1 py-0.5 text-xs"
                          value={editForm.priority}
                          onChange={(e) => setEditForm((f) => ({ ...f, priority: Number(e.target.value) }))}
                        >
                          {[1, 2, 3, 4, 5].map((v) => <option key={v} value={v}>{v}</option>)}
                        </select>
                      ) : (
                        <DarkBadge variant={PRIORITY_VARIANT[p.priority] ?? 'neutral'}>
                          {p.priority}
                        </DarkBadge>
                      )}
                    </td>
                    <td className="py-2 pl-4 text-text-dark-tertiary">
                      {editingId === p.client_id ? (
                        <textarea
                          className="bg-bg-2 text-fg-0 placeholder:text-fg-3 border border-bd-2 rounded px-2 py-1 text-xs w-full resize-none"
                          rows={2}
                          value={editForm.reason}
                          onChange={(e) => setEditForm((f) => ({ ...f, reason: e.target.value }))}
                        />
                      ) : (
                        p.reason ?? <span className="italic">—</span>
                      )}
                    </td>
                    <td className="py-2 text-right text-text-dark-tertiary">
                      {new Date(p.updated_at).toLocaleDateString('pt-PT')}
                    </td>
                    <td className="py-2 text-right">
                      {editingId === p.client_id ? (
                        <div className="flex gap-1 justify-end">
                          <DarkButton
                            size="sm"
                            disabled={updatePriorityMutation.isPending}
                            onClick={() =>
                              updatePriorityMutation.mutate({
                                clienteId: p.client_id,
                                priority: editForm.priority,
                                reason: editForm.reason,
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
                            setEditingId(p.client_id);
                            setEditForm({ priority: p.priority, reason: p.reason ?? '' });
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

/** Mapeia a label visível para o slug que o backend aceita. */
const WHERE_SLUG: Record<WherePage, 'decisoes' | 'overall' | 'llm' | 'configuracoes'> = {
  'Decisões': 'decisoes',
  'Planeamento (Overall)': 'overall',
  'LLM (Chat / KPIs / Regras)': 'llm',
  'Configurações': 'configuracoes',
};

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
        where_page: WHERE_SLUG[wherePage!],
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
              className="w-full bg-bg-2 text-fg-0 placeholder:text-fg-3 border border-bd-2 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              className="w-full bg-bg-2 text-fg-0 placeholder:text-fg-3 border border-bd-2 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
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
            href="/llm?tab=regras"
            className="inline-flex items-center gap-1.5 text-sm text-blue-400 hover:underline"
          >
            Ver Regras LLM <ExternalLink size={13} />
          </a>
        </div>
      </div>
    </DarkCard>
  );
}

// ─── Tab: Aprendizagem — 4 secções reais (Q.115.X4) ─────────────────────────

// ── helpers de badge ────────────────────────────────────────────────────

function accuracyVariant(pct: number): 'success' | 'warning' | 'danger' {
  if (pct >= 80) return 'success';
  if (pct >= 60) return 'warning';
  return 'danger';
}

function scoreVariant(score: number): 'success' | 'warning' | 'danger' {
  if (score >= 0.7) return 'success';
  if (score >= 0.4) return 'warning';
  return 'danger';
}

const PREF_TYPE_LABEL: Record<string, string> = {
  temporal_block: 'Bloqueio temporal',
  tradeoff_preference: 'Tradeoff',
  operator_affinity: 'Afinidade operador',
  phase_threshold: 'Limiar de fase',
};

const PREF_STATUS_VARIANT: Record<string, 'success' | 'warning' | 'neutral'> = {
  confirmed: 'success',
  detected: 'warning',
  rejected: 'neutral',
};

function TabAprendizagem() {
  const toast = useToastContext();
  const queryClient = useQueryClient();

  // ── Secção 1: Acerto do plano (Q.115.V) ─────────────────────────────
  const planQuery = useQuery({
    queryKey: learningKeys.planVsActual({ days: 7 }),
    queryFn: () => learningPlanApi.planVsActual({ days: 7 }),
    refetchInterval: 30_000,
  });

  const [planExpanded, setPlanExpanded] = useState(false);

  // ── Secção 2: Afinidades operador-fase (Q.115.G) ─────────────────────
  const [phaseFilter, setPhaseFilter] = useState('');
  const [operatorFilter, setOperatorFilter] = useState('');

  const affinityQuery = useQuery({
    queryKey: learningKeys.affinities({ top: 20 }),
    queryFn: () => learningAffinitiesApi.list({ top: 20 }),
    refetchInterval: 30_000,
  });

  const affinities = affinityQuery.data ?? [];

  const allPhases = [...new Set(affinities.map((a) => a.phase_id + '|' + a.phase_name))];
  const allOperators = [...new Set(affinities.map((a) => a.operator_id + '|' + a.operator_name))];

  const filteredAffinities = affinities.filter((a) => {
    const matchPhase = !phaseFilter || a.phase_id === phaseFilter;
    const matchOp = !operatorFilter || a.operator_id === operatorFilter;
    return matchPhase && matchOp;
  });

  // ── Secção 3: Preference rules (existente) ────────────────────────────
  const prefRulesQuery = useQuery({
    queryKey: governanceKeys.preferenceRules(),
    queryFn: () => preferenceRulesApi.list({ limit: 100 }),
    refetchInterval: 5 * 60_000,
  });

  // ── Secção 4: Runbooks aprendidos (Q.115.H) ───────────────────────────
  const runbooksQuery = useQuery({
    queryKey: runbookKeys.list(),
    queryFn: () => runbookApi.list(),
    refetchInterval: 5 * 60_000,
  });

  const learnedRunbooks = (runbooksQuery.data ?? []).filter((r) => r.source === 'learned');

  const [expandedRunbook, setExpandedRunbook] = useState<string | null>(null);

  const approveRunbookMutation = useMutation({
    mutationFn: (runbookId: string) =>
      runbookApi.approve(runbookId, { approved_by: 'admin' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: runbookKeys.all });
      toast.success('Runbook aprovado');
    },
    onError: () => {
      toast.error('Erro ao aprovar runbook');
    },
  });

  // Q.118.L — fechar a Camada 1: confirmar/rejeitar preferências detectadas.
  const confirmRuleMutation = useMutation({
    mutationFn: (id: string) => preferenceRulesApi.confirm(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: governanceKeys.preferenceRules() });
      toast.success('Preferência confirmada — passa a influenciar o planeamento');
    },
    onError: () => toast.error('Erro ao confirmar preferência'),
  });
  const rejectRuleMutation = useMutation({
    mutationFn: (id: string) =>
      preferenceRulesApi.reject(id, { reason: 'Rejeitada pelo gestor' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: governanceKeys.preferenceRules() });
      toast.success('Preferência rejeitada');
    },
    onError: () => toast.error('Erro ao rejeitar preferência'),
  });

  const planData: PlanVsActualReport | undefined = planQuery.data;

  return (
    <div className="space-y-8">

      {/* ── Secção 0: Centro de aprendizagem (camadas 2/3 + pares) Q.118.M ── */}
      <CentroAprendizagem />

      {/* ── Secção 1: Acerto do plano ── */}
      <DarkCard>
        <h3 className="text-sm font-semibold text-text-dark-primary mb-1">Acerto do plano</h3>
        <p className="text-xs text-text-dark-tertiary mb-4">Desvio plan vs. actual — últimos 7 dias.</p>

        {planQuery.isLoading && <SkeletonLoader count={2} />}
        {planQuery.isError && (
          <EmptyState
            title="Erro ao carregar acerto do plano"
            hint="Verifica a ligação ao backend."
            action={<DarkButton size="sm" onClick={() => planQuery.refetch()}>Tentar novamente</DarkButton>}
          />
        )}
        {planQuery.isSuccess && planData && planData.sample_size === 0 && (
          <EmptyState
            title="Sem histórico suficiente"
            hint="ETL FasesOf precisa de SQLSERVER_ENABLED=true."
          />
        )}
        {planQuery.isSuccess && planData && planData.sample_size > 0 && (
          <div>
            <div className="flex items-end gap-4 mb-3">
              <div className="text-5xl font-bold font-mono text-text-dark-primary">
                {planData.plan_accuracy_pct.toFixed(1)}%
              </div>
              <div className="pb-1">
                <DarkBadge variant={accuracyVariant(planData.plan_accuracy_pct)}>
                  {accuracyVariant(planData.plan_accuracy_pct) === 'success' ? 'Bom' :
                   accuracyVariant(planData.plan_accuracy_pct) === 'warning' ? 'Aceitável' : 'A melhorar'}
                </DarkBadge>
              </div>
              <p className="text-xs text-text-dark-tertiary pb-1">
                últimos 7 dias · {planData.sample_size} ops
              </p>
            </div>
            <DarkButton
              size="sm"
              variant="ghost"
              onClick={() => setPlanExpanded((v) => !v)}
            >
              {planExpanded ? <><ChevronUp size={12} className="mr-1" />Fechar</> : <><ChevronDown size={12} className="mr-1" />Detalhes por fase</>}
            </DarkButton>
            {planExpanded && planData.deltas_by_phase.length > 0 && (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-white/10 text-text-dark-tertiary">
                      <th className="pb-2 text-left font-medium">Fase</th>
                      <th className="pb-2 text-right font-medium">Delta (min)</th>
                      <th className="pb-2 text-right font-medium">Amostras</th>
                    </tr>
                  </thead>
                  <tbody>
                    {planData.deltas_by_phase.map((d) => (
                      <tr key={d.phase_id} className="border-b border-white/5 hover:bg-white/5">
                        <td className="py-1.5 text-text-dark-secondary">{d.phase_name}</td>
                        <td className="py-1.5 text-right font-mono text-text-dark-primary">
                          {d.avg_delta_duration_min > 0 ? '+' : ''}{d.avg_delta_duration_min.toFixed(1)}
                        </td>
                        <td className="py-1.5 text-right text-text-dark-tertiary">{d.sample_n}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </DarkCard>

      {/* ── Secção 2: Afinidades operador-fase ── */}
      <DarkCard>
        <h3 className="text-sm font-semibold text-text-dark-primary mb-1">Afinidades operador-fase</h3>
        <p className="text-xs text-text-dark-tertiary mb-4">Top-20 por score. Job diário às 03:30 UTC.</p>

        {/* filtros */}
        <div className="flex gap-3 mb-4 flex-wrap">
          <select
            className="bg-bg-2 text-fg-0 placeholder:text-fg-3 border border-bd-2 rounded px-3 py-1.5 text-xs"
            value={phaseFilter}
            onChange={(e) => setPhaseFilter(e.target.value)}
          >
            <option value="">Todas as fases</option>
            {allPhases.map((p) => {
              const [id, name] = p.split('|');
              return <option key={id} value={id}>{name}</option>;
            })}
          </select>
          <select
            className="bg-bg-2 text-fg-0 placeholder:text-fg-3 border border-bd-2 rounded px-3 py-1.5 text-xs"
            value={operatorFilter}
            onChange={(e) => setOperatorFilter(e.target.value)}
          >
            <option value="">Todos os operadores</option>
            {allOperators.map((o) => {
              const [id, name] = o.split('|');
              return <option key={id} value={id}>{name}</option>;
            })}
          </select>
        </div>

        {affinityQuery.isLoading && <SkeletonLoader count={4} />}
        {affinityQuery.isError && (
          <EmptyState
            title="Erro ao carregar afinidades"
            hint="Verifica a ligação ao backend."
            action={<DarkButton size="sm" onClick={() => affinityQuery.refetch()}>Tentar novamente</DarkButton>}
          />
        )}
        {affinityQuery.isSuccess && filteredAffinities.length === 0 && (
          <EmptyState
            title="Job de afinidades ainda não correu"
            hint="Agendado 03:30 UTC diário."
          />
        )}
        {affinityQuery.isSuccess && filteredAffinities.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/10 text-text-dark-tertiary">
                  <th className="pb-2 text-left font-medium">Operador</th>
                  <th className="pb-2 text-left font-medium">Fase</th>
                  <th className="pb-2 text-center font-medium">Score</th>
                  <th className="pb-2 text-right font-medium">Amostra</th>
                </tr>
              </thead>
              <tbody>
                {filteredAffinities.map((a) => (
                  <tr key={`${a.operator_id}-${a.phase_id}`} className="border-b border-white/5 hover:bg-white/5">
                    <td className="py-1.5 text-text-dark-secondary">{a.operator_name}</td>
                    <td className="py-1.5 text-text-dark-tertiary">{a.phase_name}</td>
                    <td className="py-1.5 text-center">
                      <DarkBadge variant={scoreVariant(a.score)}>
                        {a.score.toFixed(2)}
                      </DarkBadge>
                    </td>
                    <td className="py-1.5 text-right text-text-dark-tertiary">{a.sample_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DarkCard>

      {/* ── Secção 3: Preference rules detectadas ── */}
      <DarkCard>
        <h3 className="text-sm font-semibold text-text-dark-primary mb-1">Preference rules detectadas</h3>
        <p className="text-xs text-text-dark-tertiary mb-4">Regras inferidas a partir de padrões de decisão.</p>

        {prefRulesQuery.isLoading && <SkeletonLoader count={3} />}
        {prefRulesQuery.isError && (
          <EmptyState
            title="Erro ao carregar preference rules"
            hint="Verifica a ligação ao backend."
            action={<DarkButton size="sm" onClick={() => prefRulesQuery.refetch()}>Tentar novamente</DarkButton>}
          />
        )}
        {prefRulesQuery.isSuccess && (prefRulesQuery.data ?? []).length === 0 && (
          <EmptyState
            title="Nenhuma preferência detectada ainda"
            hint="O detector corre diariamente sobre o histórico de aprovações."
          />
        )}
        {prefRulesQuery.isSuccess && (prefRulesQuery.data ?? []).length > 0 && (
          <div className="space-y-2">
            {(prefRulesQuery.data ?? []).map((r: PreferenceRule) => (
              <div
                key={r.id}
                className="flex items-start gap-3 p-3 rounded-lg bg-white/5 border border-white/10"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <DarkBadge variant="info">
                      {PREF_TYPE_LABEL[r.type] ?? r.type}
                    </DarkBadge>
                    <DarkBadge variant={PREF_STATUS_VARIANT[r.status] ?? 'neutral'}>
                      {r.status === 'confirmed' ? 'Confirmada' : r.status === 'detected' ? 'Detectada' : 'Rejeitada'}
                    </DarkBadge>
                  </div>
                  <p className="text-xs text-text-dark-secondary">{r.description}</p>
                  {r.confirmed_by && (
                    <p className="text-xs text-text-dark-tertiary mt-0.5">
                      Confirmada por {r.confirmed_by}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {r.status === 'detected' ? (
                    <>
                      <DarkButton
                        size="sm"
                        onClick={() => confirmRuleMutation.mutate(r.id)}
                        disabled={confirmRuleMutation.isPending}
                      >
                        Confirmar
                      </DarkButton>
                      <DarkButton
                        size="sm"
                        variant="ghost"
                        onClick={() => rejectRuleMutation.mutate(r.id)}
                        disabled={rejectRuleMutation.isPending}
                      >
                        Rejeitar
                      </DarkButton>
                    </>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </DarkCard>

      {/* ── Secção 4: Runbooks aprendidos ── */}
      <DarkCard>
        <h3 className="text-sm font-semibold text-text-dark-primary mb-1">Runbooks aprendidos</h3>
        <p className="text-xs text-text-dark-tertiary mb-4">
          Procedimentos inferidos pelo sistema. Confidence ≥0.8 prontos para aprovar.
        </p>

        {runbooksQuery.isLoading && <SkeletonLoader count={3} />}
        {runbooksQuery.isError && (
          <EmptyState
            title="Erro ao carregar runbooks"
            hint="Verifica a ligação ao backend."
            action={<DarkButton size="sm" onClick={() => runbooksQuery.refetch()}>Tentar novamente</DarkButton>}
          />
        )}
        {runbooksQuery.isSuccess && learnedRunbooks.length === 0 && (
          <EmptyState
            title="Sem runbooks aprendidos"
            hint="O job de aprendizagem corre após 10+ entradas de retrabalho com root_cause definido."
          />
        )}
        {runbooksQuery.isSuccess && learnedRunbooks.length > 0 && (
          <div className="space-y-3">
            {learnedRunbooks.map((rb: Runbook) => {
              const isPending = !rb.approved_by;
              const isReadyToApprove = isPending && rb.confidence >= 0.8;
              const isExpanded = expandedRunbook === rb.id;
              return (
                <div
                  key={rb.id}
                  className="p-3 rounded-lg bg-white/5 border border-white/10"
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="text-xs font-mono font-semibold text-text-dark-primary">
                          {rb.error_code}
                        </span>
                        <DarkBadge variant={rb.confidence >= 0.8 ? 'success' : 'warning'}>
                          {(rb.confidence * 100).toFixed(0)}% confiança
                        </DarkBadge>
                        <DarkBadge variant={isPending ? 'warning' : 'success'}>
                          {isPending ? 'Pendente' : 'Aprovado'}
                        </DarkBadge>
                      </div>
                      <p className="text-xs text-text-dark-tertiary truncate">
                        {rb.steps_md.slice(0, 80)}{rb.steps_md.length > 80 ? '…' : ''}
                      </p>
                    </div>
                    <div className="flex gap-2 shrink-0">
                      <DarkButton
                        size="sm"
                        variant="ghost"
                        onClick={() => setExpandedRunbook(isExpanded ? null : rb.id)}
                      >
                        {isExpanded ? 'Fechar' : 'Ver completo'}
                      </DarkButton>
                      {isReadyToApprove && (
                        <DarkButton
                          size="sm"
                          disabled={approveRunbookMutation.isPending}
                          onClick={() => approveRunbookMutation.mutate(rb.id)}
                        >
                          {approveRunbookMutation.isPending ? 'A aprovar…' : 'Aprovar runbook'}
                        </DarkButton>
                      )}
                    </div>
                  </div>
                  {isExpanded && (
                    <div className="mt-3 p-3 bg-black/20 rounded text-xs text-text-dark-secondary font-mono whitespace-pre-wrap">
                      {rb.steps_md}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </DarkCard>

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
        {activeTab === 'master' && <MasterDataTab />}
        {activeTab === 'regras' && (
          <Suspense fallback={<div className="p-4"><SkeletonLoader count={5} /></div>}>
            <RegrasPage />
          </Suspense>
        )}
        {activeTab === 'logica-llm' && <TabLogicaLLM />}
        {activeTab === 'custos' && <TabCustos />}
        {activeTab === 'input' && <TabInput />}
        {activeTab === 'aprendizagem' && <TabAprendizagem />}
        {activeTab === 'equipa' && <EquipaNiveisTab />}
        {activeTab === 'melhores' && <MelhoresPorFaseTab />}
      </div>
    </DarkPageLayout>
  );
}
