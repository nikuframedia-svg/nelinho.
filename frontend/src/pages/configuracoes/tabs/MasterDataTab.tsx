/**
 * MasterDataTab — 4 sub-secções de acções destrutivas (Q.115.X5).
 *
 * 1. Ordens de fabrico — cancelar OF
 * 2. Encomendas       — cancelar encomenda
 * 3. Barcos/modelos   — retirar barco
 * 4. Operadores       — desactivar operador
 *
 * Cada acção exige modal de confirmação com razão ≥10c.
 * ZERO MOCKS — endpoints faltantes → empty state explícito.
 */
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ClipboardList,
  ShoppingCart,
  Anchor,
  Users,
  AlertTriangle,
} from 'lucide-react';
import { DarkCard, DarkButton, DarkBadge, EmptyState } from '../../../components/dark';
import { SkeletonLoader } from '../../../components/ui/Skeleton';
import { ConfirmDestructiveModal } from '../../../components/configuracoes/ConfirmDestructiveModal';
import { cancelActionsApi } from '../../../lib/api/masterDataApi';
import {
  masterDataKeys,
  workforceKeys,
} from '../../../lib/api/keys';
import { useToastContext } from '../../../components/ToastProvider';

// ─── helpers ──────────────────────────────────────────────────────────────────

function shortTraceId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}

function parseApiError(err: unknown): { is409: boolean; is422: boolean; is404: boolean; msg: string } {
  const msg = err instanceof Error ? err.message : String(err);
  return {
    is409: msg.includes('409') || msg.toLowerCase().includes('already'),
    is422: msg.includes('422'),
    is404: msg.includes('404'),
    msg,
  };
}

// ─── Sub-secção 1: Ordens de fabrico ─────────────────────────────────────────

const STATUS_OF_VARIANT: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'neutral'> = {
  active: 'success',
  pending: 'warning',
  cancelled: 'danger',
  completed: 'neutral',
};

function SeccaoOrdensFabrico() {
  const toast = useToastContext();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [modalOfId, setModalOfId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: masterDataKeys.workOrders(),
    queryFn: () => cancelActionsApi.listWorkOrders(),
  });

  const cancelMutation = useMutation({
    mutationFn: ({ ofId, reason }: { ofId: string; reason: string }) =>
      cancelActionsApi.cancelWorkOrder(ofId, reason),
    onSuccess: (data, vars) => {
      queryClient.invalidateQueries({ queryKey: masterDataKeys.workOrders() });
      toast.success(`OF ${vars.ofId} cancelada · trace_id=${shortTraceId(data.audit_trace_id)}`);
      setModalOfId(null);
    },
    onError: (err, vars) => {
      const { is409, is404 } = parseApiError(err);
      if (is409) {
        toast.error(`OF ${vars.ofId} já cancelada`);
        setModalOfId(null);
      } else if (is404) {
        toast.error(`OF ${vars.ofId} não encontrada`);
        setModalOfId(null);
      }
      // 422 tratado pelo ConfirmDestructiveModal (re-lança o erro)
    },
  });

  const items = query.data ?? [];
  const filtered = search
    ? items.filter(
        (o) =>
          o.of_id.toLowerCase().includes(search.toLowerCase()) ||
          o.modelo.toLowerCase().includes(search.toLowerCase()) ||
          o.cliente.toLowerCase().includes(search.toLowerCase()),
      )
    : items;

  const selectedOf = items.find((o) => o.of_id === modalOfId);

  async function handleConfirm(reason: string) {
    if (!modalOfId) return;
    await cancelActionsApi.cancelWorkOrder(modalOfId, reason).then((data) => {
      queryClient.invalidateQueries({ queryKey: masterDataKeys.workOrders() });
      toast.success(`OF ${modalOfId} cancelada · trace_id=${shortTraceId(data.audit_trace_id)}`);
      setModalOfId(null);
    }).catch((err: unknown) => {
      const { is409, is404 } = parseApiError(err);
      if (is409) {
        toast.error(`OF ${modalOfId} já cancelada`);
        setModalOfId(null);
        return;
      }
      if (is404) {
        toast.error(`OF ${modalOfId} não encontrada`);
        setModalOfId(null);
        return;
      }
      throw err; // deixa o modal mostrar o erro
    });
  }

  return (
    <DarkCard>
      <div className="flex items-start gap-3 mb-4">
        <ClipboardList size={16} className="text-blue-400 mt-0.5 shrink-0" />
        <div>
          <h3 className="text-sm font-semibold text-text-dark-primary">Ordens de fabrico</h3>
          <p className="text-xs text-text-dark-tertiary mt-0.5">
            Cancela uma OF activa. Acção irreversível — exige razão.
          </p>
        </div>
      </div>

      <input
        type="search"
        placeholder="Pesquisar OF, modelo ou cliente…"
        className="w-full max-w-xs bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-1.5 text-xs mb-4"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {query.isLoading && <SkeletonLoader count={4} />}
      {query.isError && (
        <EmptyState
          title="Erro ao carregar ordens de fabrico"
          hint="Verifica a ligação ao backend."
          action={<DarkButton size="sm" onClick={() => query.refetch()}>Tentar novamente</DarkButton>}
        />
      )}
      {query.isSuccess && filtered.length === 0 && (
        <EmptyState
          title="Sem ordens de fabrico activas"
          hint={search ? 'Sem resultados para a pesquisa.' : 'Não existem OFs activas neste momento.'}
        />
      )}
      {query.isSuccess && filtered.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/10 text-text-dark-tertiary">
                <th className="pb-2 text-left font-medium">OF</th>
                <th className="pb-2 text-left font-medium">Modelo</th>
                <th className="pb-2 text-left font-medium">Cliente</th>
                <th className="pb-2 text-left font-medium">Fase actual</th>
                <th className="pb-2 text-center font-medium">Estado</th>
                <th className="pb-2 w-20"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((o) => (
                <tr key={o.of_id} className="border-b border-white/5 hover:bg-white/5">
                  <td className="py-2 font-mono text-text-dark-primary">{o.of_id}</td>
                  <td className="py-2 text-text-dark-secondary">{o.modelo}</td>
                  <td className="py-2 text-text-dark-tertiary">{o.cliente}</td>
                  <td className="py-2 text-text-dark-tertiary">{o.fase_actual}</td>
                  <td className="py-2 text-center">
                    <DarkBadge variant={STATUS_OF_VARIANT[o.status] ?? 'neutral'}>
                      {o.status}
                    </DarkBadge>
                  </td>
                  <td className="py-2 text-right">
                    <button
                      onClick={() => setModalOfId(o.of_id)}
                      className="px-2 py-1 rounded text-xs font-medium bg-red-900/40 text-red-400 hover:bg-red-900/60 border border-red-800/40 transition-colors"
                    >
                      Cancelar OF
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modalOfId && (
        <ConfirmDestructiveModal
          isOpen
          title="Cancelar Ordem de Fabrico"
          description={`Confirmar cancelamento de OF ${modalOfId}?${selectedOf ? ` (${selectedOf.modelo} · ${selectedOf.cliente})` : ''}`}
          entityId={modalOfId}
          onClose={() => setModalOfId(null)}
          onConfirm={handleConfirm}
        />
      )}
    </DarkCard>
  );
}

// ─── Sub-secção 2: Encomendas ─────────────────────────────────────────────────

function SeccaoEncomendas() {
  const toast = useToastContext();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [modalId, setModalId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: masterDataKeys.encomendas(),
    queryFn: () => cancelActionsApi.listEncomendas(),
  });

  const items = query.data ?? [];
  const filtered = search
    ? items.filter(
        (e) =>
          e.encomenda_id.toLowerCase().includes(search.toLowerCase()) ||
          e.cliente.toLowerCase().includes(search.toLowerCase()),
      )
    : items;

  async function handleConfirm(reason: string) {
    if (!modalId) return;
    await cancelActionsApi.cancelEncomenda(modalId, reason).then((data) => {
      queryClient.invalidateQueries({ queryKey: masterDataKeys.encomendas() });
      toast.success(`Encomenda ${modalId} cancelada · trace_id=${shortTraceId(data.audit_trace_id)}`);
      setModalId(null);
    }).catch((err: unknown) => {
      const { is409, is404 } = parseApiError(err);
      if (is409) {
        toast.error(`Encomenda ${modalId} já cancelada`);
        setModalId(null);
        return;
      }
      if (is404) {
        toast.error(`Encomenda ${modalId} não encontrada`);
        setModalId(null);
        return;
      }
      throw err;
    });
  }

  return (
    <DarkCard>
      <div className="flex items-start gap-3 mb-4">
        <ShoppingCart size={16} className="text-purple-400 mt-0.5 shrink-0" />
        <div>
          <h3 className="text-sm font-semibold text-text-dark-primary">Encomendas</h3>
          <p className="text-xs text-text-dark-tertiary mt-0.5">
            Cancela uma encomenda activa. Acção irreversível — exige razão.
          </p>
        </div>
      </div>

      <input
        type="search"
        placeholder="Pesquisar encomenda ou cliente…"
        className="w-full max-w-xs bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-1.5 text-xs mb-4"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {query.isLoading && <SkeletonLoader count={4} />}
      {query.isError && (
        <EmptyState
          title="Erro ao carregar encomendas"
          hint="Endpoint /v1/encomendas indisponível ou lista via ERP (read-only)."
          action={<DarkButton size="sm" onClick={() => query.refetch()}>Tentar novamente</DarkButton>}
        />
      )}
      {query.isSuccess && filtered.length === 0 && (
        <EmptyState
          title={search ? 'Sem resultados para a pesquisa' : 'Lista de encomendas via ERP (read-only)'}
          hint={search ? 'Ajusta o termo de pesquisa.' : 'Não existem encomendas activas ou endpoint ainda não disponível.'}
        />
      )}
      {query.isSuccess && filtered.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/10 text-text-dark-tertiary">
                <th className="pb-2 text-left font-medium">ID</th>
                <th className="pb-2 text-left font-medium">Cliente</th>
                <th className="pb-2 text-left font-medium">Data</th>
                <th className="pb-2 text-right font-medium">Total (€)</th>
                <th className="pb-2 w-24"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => (
                <tr key={e.encomenda_id} className="border-b border-white/5 hover:bg-white/5">
                  <td className="py-2 font-mono text-text-dark-primary">{e.encomenda_id}</td>
                  <td className="py-2 text-text-dark-secondary">{e.cliente}</td>
                  <td className="py-2 text-text-dark-tertiary">
                    {new Date(e.data).toLocaleDateString('pt-PT')}
                  </td>
                  <td className="py-2 text-right font-mono text-text-dark-primary">
                    {e.total_eur.toLocaleString('pt-PT', { style: 'currency', currency: 'EUR' })}
                  </td>
                  <td className="py-2 text-right">
                    <button
                      onClick={() => setModalId(e.encomenda_id)}
                      className="px-2 py-1 rounded text-xs font-medium bg-red-900/40 text-red-400 hover:bg-red-900/60 border border-red-800/40 transition-colors"
                    >
                      Cancelar encomenda
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modalId && (
        <ConfirmDestructiveModal
          isOpen
          title="Cancelar Encomenda"
          description={`Confirmar cancelamento da encomenda ${modalId}?`}
          entityId={modalId}
          onClose={() => setModalId(null)}
          onConfirm={handleConfirm}
        />
      )}
    </DarkCard>
  );
}

// ─── Sub-secção 3: Barcos/modelos ─────────────────────────────────────────────

function SeccaoBarcos() {
  const toast = useToastContext();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [showRetired, setShowRetired] = useState(false);
  const [modalBoatId, setModalBoatId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: masterDataKeys.boats(showRetired),
    queryFn: () => cancelActionsApi.listBoats(showRetired),
  });

  const items = query.data ?? [];
  const filtered = search
    ? items.filter(
        (b) =>
          b.boat_id.toLowerCase().includes(search.toLowerCase()) ||
          b.modelo_nome.toLowerCase().includes(search.toLowerCase()),
      )
    : items;

  async function handleConfirm(reason: string) {
    if (!modalBoatId) return;
    await cancelActionsApi.retireBoat(modalBoatId, reason).then((data) => {
      queryClient.invalidateQueries({ queryKey: masterDataKeys.boats(showRetired) });
      queryClient.invalidateQueries({ queryKey: masterDataKeys.boats(!showRetired) });
      toast.success(`Barco ${modalBoatId} retirado · trace_id=${shortTraceId(data.audit_trace_id)}`);
      setModalBoatId(null);
    }).catch((err: unknown) => {
      const { is409, is404 } = parseApiError(err);
      if (is409) {
        toast.error(`Barco ${modalBoatId} já retirado`);
        setModalBoatId(null);
        return;
      }
      if (is404) {
        toast.error(`Barco ${modalBoatId} não encontrado`);
        setModalBoatId(null);
        return;
      }
      throw err;
    });
  }

  return (
    <DarkCard>
      <div className="flex items-start gap-3 mb-4">
        <Anchor size={16} className="text-teal-400 mt-0.5 shrink-0" />
        <div>
          <h3 className="text-sm font-semibold text-text-dark-primary">Barcos / Modelos</h3>
          <p className="text-xs text-text-dark-tertiary mt-0.5">
            Retira um modelo do catálogo activo. Acção irreversível — exige razão.
          </p>
        </div>
      </div>

      <div className="flex gap-3 mb-4 flex-wrap items-center">
        <input
          type="search"
          placeholder="Pesquisar barco ou modelo…"
          className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-1.5 text-xs w-56"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <label className="flex items-center gap-2 text-xs text-text-dark-secondary cursor-pointer select-none">
          <input
            type="checkbox"
            className="rounded"
            checked={showRetired}
            onChange={(e) => setShowRetired(e.target.checked)}
          />
          Mostrar retirados
        </label>
      </div>

      {query.isLoading && <SkeletonLoader count={4} />}
      {query.isError && (
        <EmptyState
          title="Erro ao carregar barcos"
          hint="Verifica a ligação ao backend."
          action={<DarkButton size="sm" onClick={() => query.refetch()}>Tentar novamente</DarkButton>}
        />
      )}
      {query.isSuccess && filtered.length === 0 && (
        <EmptyState
          title="Sem barcos disponíveis"
          hint={search ? 'Sem resultados para a pesquisa.' : 'Não existem modelos neste momento.'}
        />
      )}
      {query.isSuccess && filtered.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/10 text-text-dark-tertiary">
                <th className="pb-2 text-left font-medium">ID</th>
                <th className="pb-2 text-left font-medium">Modelo</th>
                <th className="pb-2 text-left font-medium">Estado</th>
                <th className="pb-2 w-20"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((b) => {
                const isRetired = b.retired_at !== null;
                return (
                  <tr
                    key={b.boat_id}
                    className={`border-b border-white/5 hover:bg-white/5 ${isRetired ? 'opacity-50' : ''}`}
                  >
                    <td className="py-2 font-mono text-text-dark-primary">{b.boat_id}</td>
                    <td className="py-2 text-text-dark-secondary">{b.modelo_nome}</td>
                    <td className="py-2">
                      {isRetired ? (
                        <DarkBadge variant="neutral">
                          Retirado em {new Date(b.retired_at!).toLocaleDateString('pt-PT')}
                        </DarkBadge>
                      ) : (
                        <DarkBadge variant="success">Activo</DarkBadge>
                      )}
                    </td>
                    <td className="py-2 text-right">
                      {!isRetired && (
                        <button
                          onClick={() => setModalBoatId(b.boat_id)}
                          className="px-2 py-1 rounded text-xs font-medium bg-red-900/40 text-red-400 hover:bg-red-900/60 border border-red-800/40 transition-colors"
                        >
                          Retirar barco
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {modalBoatId && (
        <ConfirmDestructiveModal
          isOpen
          title="Retirar Barco / Modelo"
          description={`Confirmar retirada do barco ${modalBoatId}?`}
          entityId={modalBoatId}
          onClose={() => setModalBoatId(null)}
          onConfirm={handleConfirm}
        />
      )}
    </DarkCard>
  );
}

// ─── Sub-secção 4: Operadores ─────────────────────────────────────────────────

function SeccaoOperadores() {
  const toast = useToastContext();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [modalEmpId, setModalEmpId] = useState<string | null>(null);
  const [opsWarning, setOpsWarning] = useState<number | null>(null);

  const query = useQuery({
    queryKey: masterDataKeys.employees(showInactive),
    queryFn: () => cancelActionsApi.listEmployees(showInactive),
  });

  const items = query.data ?? [];
  const filtered = search
    ? items.filter(
        (e) =>
          e.employee_id.toLowerCase().includes(search.toLowerCase()) ||
          e.nome.toLowerCase().includes(search.toLowerCase()) ||
          e.role.toLowerCase().includes(search.toLowerCase()),
      )
    : items;

  async function handleConfirm(reason: string) {
    if (!modalEmpId) return;
    await cancelActionsApi.deactivateEmployee(modalEmpId, reason).then((data) => {
      queryClient.invalidateQueries({ queryKey: masterDataKeys.employees(showInactive) });
      queryClient.invalidateQueries({ queryKey: masterDataKeys.employees(!showInactive) });
      queryClient.invalidateQueries({ queryKey: workforceKeys.all });
      if (data.warning_ops_planeadas && data.warning_ops_planeadas > 0) {
        setOpsWarning(data.warning_ops_planeadas);
      }
      toast.success(`Operador ${modalEmpId} desactivado · trace_id=${shortTraceId(data.audit_trace_id)}`);
      setModalEmpId(null);
    }).catch((err: unknown) => {
      const { is409, is404 } = parseApiError(err);
      if (is409) {
        toast.error(`Operador ${modalEmpId} já inactivo`);
        setModalEmpId(null);
        return;
      }
      if (is404) {
        toast.error(`Operador ${modalEmpId} não encontrado`);
        setModalEmpId(null);
        return;
      }
      throw err;
    });
  }

  return (
    <DarkCard>
      <div className="flex items-start gap-3 mb-4">
        <Users size={16} className="text-orange-400 mt-0.5 shrink-0" />
        <div>
          <h3 className="text-sm font-semibold text-text-dark-primary">Operadores</h3>
          <p className="text-xs text-text-dark-tertiary mt-0.5">
            Desactiva um operador. O CPO vai recalcular o plano.
          </p>
        </div>
      </div>

      {opsWarning !== null && (
        <div className="flex items-start gap-2 p-3 mb-4 rounded-lg bg-yellow-900/20 border border-yellow-700/40">
          <AlertTriangle size={14} className="text-yellow-400 mt-0.5 shrink-0" />
          <p className="text-xs text-yellow-300">
            Operador tinha <strong>{opsWarning}</strong> {opsWarning === 1 ? 'operação planeada' : 'operações planeadas'}.
            O sistema vai recalcular o plano automaticamente.
          </p>
          <button
            onClick={() => setOpsWarning(null)}
            className="ml-auto text-yellow-400 hover:text-yellow-300 text-xs"
          >
            ✕
          </button>
        </div>
      )}

      <div className="flex gap-3 mb-4 flex-wrap items-center">
        <input
          type="search"
          placeholder="Pesquisar operador…"
          className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-1.5 text-xs w-56"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <label className="flex items-center gap-2 text-xs text-text-dark-secondary cursor-pointer select-none">
          <input
            type="checkbox"
            className="rounded"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
          />
          Mostrar inactivos
        </label>
      </div>

      {query.isLoading && <SkeletonLoader count={4} />}
      {query.isError && (
        <EmptyState
          title="Erro ao carregar operadores"
          hint="Verifica a ligação ao backend."
          action={<DarkButton size="sm" onClick={() => query.refetch()}>Tentar novamente</DarkButton>}
        />
      )}
      {query.isSuccess && filtered.length === 0 && (
        <EmptyState
          title="Sem operadores"
          hint={search ? 'Sem resultados para a pesquisa.' : 'Não existem operadores neste momento.'}
        />
      )}
      {query.isSuccess && filtered.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/10 text-text-dark-tertiary">
                <th className="pb-2 text-left font-medium">ID</th>
                <th className="pb-2 text-left font-medium">Nome</th>
                <th className="pb-2 text-left font-medium">Função</th>
                <th className="pb-2 text-center font-medium">Estado</th>
                <th className="pb-2 w-24"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => (
                <tr
                  key={e.employee_id}
                  className={`border-b border-white/5 hover:bg-white/5 ${!e.active ? 'opacity-50' : ''}`}
                >
                  <td className="py-2 font-mono text-text-dark-primary">{e.employee_id}</td>
                  <td className="py-2 text-text-dark-secondary">{e.nome}</td>
                  <td className="py-2 text-text-dark-tertiary">{e.role}</td>
                  <td className="py-2 text-center">
                    <DarkBadge variant={e.active ? 'success' : 'neutral'}>
                      {e.active ? 'Activo' : 'Inactivo'}
                    </DarkBadge>
                  </td>
                  <td className="py-2 text-right">
                    {e.active && (
                      <button
                        onClick={() => setModalEmpId(e.employee_id)}
                        className="px-2 py-1 rounded text-xs font-medium bg-red-900/40 text-red-400 hover:bg-red-900/60 border border-red-800/40 transition-colors"
                      >
                        Desactivar operador
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modalEmpId && (
        <ConfirmDestructiveModal
          isOpen
          title="Desactivar Operador"
          description={`Confirmar desactivação do operador ${modalEmpId}? O CPO vai recalcular o plano.`}
          entityId={modalEmpId}
          onClose={() => setModalEmpId(null)}
          onConfirm={handleConfirm}
        />
      )}
    </DarkCard>
  );
}

// ─── Componente principal ─────────────────────────────────────────────────────

export function MasterDataTab() {
  return (
    <div className="space-y-8">
      <SeccaoOrdensFabrico />
      <SeccaoEncomendas />
      <SeccaoBarcos />
      <SeccaoOperadores />
    </div>
  );
}
