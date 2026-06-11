/**
 * PlaneadorTab — Q.173.O
 *
 * 3 secções de configuração do planeador:
 *   (a) Planeamento  — categoria 'planning'
 *   (b) Transporte   — categoria 'transporte'
 *   (c) Alertas      — categoria 'alertas'
 *
 * Cada campo lê do GET /v1/config/{category} e grava com POST /v1/config/{category}/{key}.
 * ZERO MOCKS — empty/error states explícitos.
 */

import { useState, useEffect, type ReactNode } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Cpu, Truck, Bell, Save } from 'lucide-react';
import { DarkCard, DarkButton, EmptyState } from '../../../components/dark';
import { SkeletonLoader } from '../../../components/ui/Skeleton';
import { configApi, parsePhaseIds, serializePhaseIds } from '../../../lib/api/configApi';
import { configKeys } from '../../../lib/api/keys';
import { useToastContext } from '../../../components/ToastProvider';

// ─── helper de toggle ─────────────────────────────────────────────────────────

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 ${
        checked ? 'bg-blue-600' : 'bg-white/20'
      }`}
    >
      <span
        className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${
          checked ? 'translate-x-4' : 'translate-x-0'
        }`}
      />
    </button>
  );
}

// ─── Secção Planeamento ───────────────────────────────────────────────────────

function SecPlaneamento(): ReactNode {
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const q = useQuery({
    queryKey: configKeys.category('planning'),
    queryFn: () => configApi.getCategory('planning'),
  });

  // ── estado local do rascunho ──────────────────────────────────────────────
  const [scope, setScope] = useState('boats_only');
  const [useCpsat, setUseCpsat] = useState(true);
  const [useQueueTime, setUseQueueTime] = useState(false);
  const [planCap, setPlanCap] = useState('');
  const [autoReplanCap, setAutoReplanCap] = useState('');
  const [autoReplanTimeLimit, setAutoReplanTimeLimit] = useState('');
  const [repairPhaseIds, setRepairPhaseIds] = useState('');
  const [initialised, setInitialised] = useState(false);

  useEffect(() => {
    if (q.data && !initialised) {
      const d = q.data;
      setScope(String(d['scope'] ?? 'boats_only'));
      setUseCpsat(d['cpo.use_cpsat_global'] === true || d['cpo.use_cpsat_global'] === 'true');
      // ausente = default REAL do motor (true) — mostrar OFF seria mentir
      // e um "Guardar" cego escreveria false (one-piece-flow) sem intenção.
      const rawQueue = d['cpo.use_queue_time'];
      setUseQueueTime(rawQueue == null ? true : rawQueue === true || rawQueue === 'true');
      const cap = d['plan_cap'];
      setPlanCap(cap != null && cap !== 0 ? String(cap) : '');
      const rCap = d['auto_replan_plan_cap'];
      setAutoReplanCap(rCap != null ? String(rCap) : '');
      const tl = d['auto_replan_time_limit_s'];
      setAutoReplanTimeLimit(tl != null ? String(tl) : '');
      const rIds = d['repair.phase_ids'];
      if (Array.isArray(rIds)) {
        setRepairPhaseIds(rIds.join(', '));
      } else if (typeof rIds === 'string') {
        setRepairPhaseIds(rIds);
      }
      setInitialised(true);
    }
  }, [q.data, initialised]);

  const mut = useMutation({
    mutationFn: async () => {
      const d = q.data ?? {};
      const saves: Promise<unknown>[] = [];

      if (scope !== String(d['scope'] ?? 'boats_only')) {
        saves.push(configApi.setKey('planning', 'scope', { value: scope, data_type: 'string' }));
      }
      const cpsatVal = d['cpo.use_cpsat_global'] === true || d['cpo.use_cpsat_global'] === 'true';
      if (useCpsat !== cpsatVal) {
        saves.push(configApi.setKey('planning', 'cpo.use_cpsat_global', { value: useCpsat, data_type: 'bool' }));
      }
      const rawQ = d['cpo.use_queue_time'];
      const queueVal = rawQ == null ? true : rawQ === true || rawQ === 'true';
      if (useQueueTime !== queueVal) {
        saves.push(configApi.setKey('planning', 'cpo.use_queue_time', { value: useQueueTime, data_type: 'bool' }));
      }
      // Campo vazio = "não definir" (fica no default) — NUNCA gravar 0
      // implícito (0 tem semântica própria: plan_cap 0 = todos os barcos).
      if (planCap !== '') {
        const capNum = parseInt(planCap, 10);
        if (!Number.isNaN(capNum) && capNum !== Number(d['plan_cap'] ?? NaN)) {
          saves.push(configApi.setKey('planning', 'plan_cap', { value: capNum, data_type: 'int' }));
        }
      }
      if (autoReplanCap !== '') {
        const rCapNum = parseInt(autoReplanCap, 10);
        if (!Number.isNaN(rCapNum) && rCapNum !== Number(d['auto_replan_plan_cap'] ?? NaN)) {
          saves.push(configApi.setKey('planning', 'auto_replan_plan_cap', { value: rCapNum, data_type: 'int' }));
        }
      }
      const tlNum = autoReplanTimeLimit === '' ? null : parseFloat(autoReplanTimeLimit);
      if (tlNum !== null && tlNum !== Number(d['auto_replan_time_limit_s'])) {
        saves.push(configApi.setKey('planning', 'auto_replan_time_limit_s', { value: tlNum, data_type: 'float' }));
      }
      const ids = parsePhaseIds(repairPhaseIds);
      const currentIds = Array.isArray(d['repair.phase_ids']) ? (d['repair.phase_ids'] as number[]) : [];
      if (JSON.stringify(ids) !== JSON.stringify(currentIds)) {
        saves.push(configApi.setKey('planning', 'repair.phase_ids', { value: serializePhaseIds(ids), data_type: 'json' }));
      }

      if (saves.length === 0) return;
      await Promise.all(saves);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configKeys.category('planning') });
      toast.success('Configuração do planeamento guardada');
    },
    onError: () => {
      toast.error('Erro ao guardar configuração do planeamento');
    },
  });

  if (q.isLoading) return <SkeletonLoader count={5} />;
  if (q.isError) {
    return (
      <EmptyState
        title="Erro ao carregar configuração de planeamento"
        hint="Verifica a ligação ao backend."
        action={<DarkButton size="sm" onClick={() => q.refetch()}>Tentar novamente</DarkButton>}
      />
    );
  }

  const repairIdsValid = repairPhaseIds.trim() === '' || parsePhaseIds(repairPhaseIds).length > 0;

  return (
    <DarkCard>
      <div className="flex items-center gap-2 mb-4">
        <Cpu size={15} className="text-blue-400" />
        <h3 className="text-sm font-semibold text-text-dark-primary">Planeamento</h3>
      </div>

      <div className="space-y-5">
        {/* scope */}
        <div>
          <label className="block text-xs font-medium text-text-dark-secondary mb-1">
            Âmbito do plano
          </label>
          <select
            className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-1.5 text-xs w-full max-w-xs"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
          >
            <option value="boats_only">boats_only — só barcos (recomendado)</option>
            <option value="boats_and_molds">boats_and_molds — barcos + moldes</option>
            <option value="all">all — tudo (muito lento)</option>
          </select>
          <p className="text-xs text-text-dark-tertiary mt-1">
            boats_only usa a view v_of_is_boat (critério NELO real).
          </p>
        </div>

        {/* cpo.use_cpsat_global */}
        <div className="flex items-center gap-3">
          <Toggle checked={useCpsat} onChange={setUseCpsat} />
          <div>
            <span className="text-xs font-medium text-text-dark-secondary">Optimizador global CP-SAT</span>
            <p className="text-xs text-text-dark-tertiary">
              OR-Tools CP-SAT (makespan real). Desligar reverte para o greedy (5-10× pior).
            </p>
          </div>
        </div>

        {/* cpo.use_queue_time */}
        <div className="flex items-center gap-3">
          <Toggle checked={useQueueTime} onChange={setUseQueueTime} />
          <div>
            <span className="text-xs font-medium text-text-dark-secondary">Fila inter-fase mediana</span>
            <p className="text-xs text-text-dark-tertiary">
              On = mediana real por fase (Q.160). Off = one-piece-flow (0 espera de fila).
            </p>
          </div>
        </div>

        {/* plan_cap */}
        <div>
          <label className="block text-xs font-medium text-text-dark-secondary mb-1">
            Cap interativo (plan_cap)
          </label>
          <input
            type="number"
            min={0}
            className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-1.5 text-xs w-32"
            placeholder="default 200"
            value={planCap}
            onChange={(e) => setPlanCap(e.target.value)}
          />
          <p className="text-xs text-text-dark-tertiary mt-1">
            Vazio ou 0 usa o default (200 barcos). Aumentar pode tornar o plano interativo lento.
          </p>
        </div>

        {/* auto_replan_plan_cap */}
        <div>
          <label className="block text-xs font-medium text-text-dark-secondary mb-1">
            Cap do robô (auto_replan_plan_cap)
          </label>
          <input
            type="number"
            min={0}
            className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-1.5 text-xs w-32"
            placeholder="0 = todos"
            value={autoReplanCap}
            onChange={(e) => setAutoReplanCap(e.target.value)}
          />
          <p className="text-xs text-text-dark-tertiary mt-1">0 significa sem limite (o robô planeia todos os barcos).</p>
        </div>

        {/* auto_replan_time_limit_s */}
        <div>
          <label className="block text-xs font-medium text-text-dark-secondary mb-1">
            Tempo limite do robô (s)
          </label>
          <input
            type="number"
            min={10}
            max={600}
            className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-1.5 text-xs w-32"
            placeholder="ex: 300"
            value={autoReplanTimeLimit}
            onChange={(e) => setAutoReplanTimeLimit(e.target.value)}
          />
          <p className="text-xs text-text-dark-tertiary mt-1">
            Limite do solver (segundos). Deve ser inferior ao job_timeout do Arq (1200s).
          </p>
        </div>

        {/* repair.phase_ids */}
        <div>
          <label className="block text-xs font-medium text-text-dark-secondary mb-1">
            Fases de reparação (repair.phase_ids)
          </label>
          <input
            type="text"
            className={`bg-white text-slate-900 placeholder:text-slate-400 border rounded px-3 py-1.5 text-xs w-64 ${
              repairIdsValid ? 'border-slate-300' : 'border-red-400'
            }`}
            placeholder="ex: 14, 76, 77"
            value={repairPhaseIds}
            onChange={(e) => setRepairPhaseIds(e.target.value)}
          />
          {!repairIdsValid && (
            <p className="text-xs text-red-400 mt-1">IDs inválidos — usa números separados por vírgula.</p>
          )}
          <p className="text-xs text-text-dark-tertiary mt-1">
            A view de produção da NELO (v_of_em_producao) exclui sempre {'{14, 76, 77}'} — reparações.
          </p>
        </div>
      </div>

      <div className="mt-5 flex justify-end">
        <DarkButton
          size="sm"
          disabled={mut.isPending || !repairIdsValid}
          onClick={() => mut.mutate()}
        >
          {mut.isPending ? 'A guardar…' : <><Save size={12} className="mr-1" />Guardar planeamento</>}
        </DarkButton>
      </div>
    </DarkCard>
  );
}

// ─── Secção Transporte ────────────────────────────────────────────────────────

function SecTransporte(): ReactNode {
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const q = useQuery({
    queryKey: configKeys.category('transporte'),
    queryFn: () => configApi.getCategory('transporte'),
  });

  const [capacity, setCapacity] = useState('');
  const [capacityModa, setCapacityModa] = useState('');
  const [initialised, setInitialised] = useState(false);

  useEffect(() => {
    if (q.data && !initialised) {
      setCapacity(q.data['truck.capacity'] != null ? String(q.data['truck.capacity']) : '50');
      setCapacityModa(q.data['truck.capacity_moda'] != null ? String(q.data['truck.capacity_moda']) : '26');
      setInitialised(true);
    }
  }, [q.data, initialised]);

  const mut = useMutation({
    mutationFn: async () => {
      const d = q.data ?? {};
      const saves: Promise<unknown>[] = [];
      const capNum = parseFloat(capacity);
      if (Number.isFinite(capNum) && capNum !== Number(d['truck.capacity'])) {
        saves.push(configApi.setKey('transporte', 'truck.capacity', { value: capNum, data_type: 'int' }));
      }
      const modaNum = parseFloat(capacityModa);
      if (Number.isFinite(modaNum) && modaNum !== Number(d['truck.capacity_moda'])) {
        saves.push(configApi.setKey('transporte', 'truck.capacity_moda', { value: modaNum, data_type: 'int' }));
      }
      if (saves.length === 0) return;
      await Promise.all(saves);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configKeys.category('transporte') });
      toast.success('Configuração de transporte guardada');
    },
    onError: () => {
      toast.error('Erro ao guardar configuração de transporte');
    },
  });

  if (q.isLoading) return <SkeletonLoader count={3} />;
  if (q.isError) {
    return (
      <EmptyState
        title="Erro ao carregar configuração de transporte"
        hint="Verifica a ligação ao backend."
        action={<DarkButton size="sm" onClick={() => q.refetch()}>Tentar novamente</DarkButton>}
      />
    );
  }

  return (
    <DarkCard>
      <div className="flex items-center gap-2 mb-4">
        <Truck size={15} className="text-teal-400" />
        <h3 className="text-sm font-semibold text-text-dark-primary">Transporte</h3>
      </div>

      <div className="space-y-5">
        <div>
          <label className="block text-xs font-medium text-text-dark-secondary mb-1">
            Capacidade CEO (truck.capacity)
          </label>
          <input
            type="number"
            min={1}
            max={200}
            className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-1.5 text-xs w-28"
            value={capacity}
            onChange={(e) => setCapacity(e.target.value)}
          />
          <p className="text-xs text-text-dark-tertiary mt-1">
            Capacidade oficial declarada (contrato/CEO). Usado no CTP.
          </p>
        </div>

        <div>
          <label className="block text-xs font-medium text-text-dark-secondary mb-1">
            Capacidade moda real (truck.capacity_moda)
          </label>
          <input
            type="number"
            min={1}
            max={200}
            className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-1.5 text-xs w-28"
            value={capacityModa}
            onChange={(e) => setCapacityModa(e.target.value)}
          />
          <p className="text-xs text-text-dark-tertiary mt-1">
            Moda observada nos embarques reais (Vila do Conde Q.13.E). Usado na tab Prontos a sair.
          </p>
        </div>
      </div>

      <div className="mt-5 flex justify-end">
        <DarkButton
          size="sm"
          disabled={mut.isPending}
          onClick={() => mut.mutate()}
        >
          {mut.isPending ? 'A guardar…' : <><Save size={12} className="mr-1" />Guardar transporte</>}
        </DarkButton>
      </div>
    </DarkCard>
  );
}

// ─── Secção Alertas ───────────────────────────────────────────────────────────

function SecAlertas(): ReactNode {
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const q = useQuery({
    queryKey: configKeys.category('alertas'),
    queryFn: () => configApi.getCategory('alertas'),
  });

  const [bottleneckDays, setBottleneckDays] = useState('');
  const [qualityEvents, setQualityEvents] = useState('');
  const [deliveryWindow, setDeliveryWindow] = useState('');
  const [initialised, setInitialised] = useState(false);

  useEffect(() => {
    if (q.data && !initialised) {
      setBottleneckDays(q.data['bottleneck.days_threshold'] != null ? String(q.data['bottleneck.days_threshold']) : '');
      setQualityEvents(q.data['quality.events_threshold'] != null ? String(q.data['quality.events_threshold']) : '');
      setDeliveryWindow(q.data['delivery_risk.window_days'] != null ? String(q.data['delivery_risk.window_days']) : '');
      setInitialised(true);
    }
  }, [q.data, initialised]);

  const mut = useMutation({
    mutationFn: async () => {
      const d = q.data ?? {};
      const saves: Promise<unknown>[] = [];
      const bdNum = parseFloat(bottleneckDays);
      if (Number.isFinite(bdNum) && bdNum !== Number(d['bottleneck.days_threshold'])) {
        saves.push(configApi.setKey('alertas', 'bottleneck.days_threshold', { value: bdNum, data_type: 'float' }));
      }
      const qeNum = parseFloat(qualityEvents);
      if (Number.isFinite(qeNum) && qeNum !== Number(d['quality.events_threshold'])) {
        saves.push(configApi.setKey('alertas', 'quality.events_threshold', { value: qeNum, data_type: 'int' }));
      }
      const dwNum = parseFloat(deliveryWindow);
      if (Number.isFinite(dwNum) && dwNum !== Number(d['delivery_risk.window_days'])) {
        saves.push(configApi.setKey('alertas', 'delivery_risk.window_days', { value: dwNum, data_type: 'int' }));
      }
      if (saves.length === 0) return;
      await Promise.all(saves);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configKeys.category('alertas') });
      toast.success('Configuração de alertas guardada');
    },
    onError: () => {
      toast.error('Erro ao guardar configuração de alertas');
    },
  });

  if (q.isLoading) return <SkeletonLoader count={3} />;
  if (q.isError) {
    return (
      <EmptyState
        title="Erro ao carregar configuração de alertas"
        hint="Verifica a ligação ao backend."
        action={<DarkButton size="sm" onClick={() => q.refetch()}>Tentar novamente</DarkButton>}
      />
    );
  }

  return (
    <DarkCard>
      <div className="flex items-center gap-2 mb-4">
        <Bell size={15} className="text-yellow-400" />
        <h3 className="text-sm font-semibold text-text-dark-primary">Alertas</h3>
      </div>

      <div className="space-y-5">
        <div>
          <label className="block text-xs font-medium text-text-dark-secondary mb-1">
            Gargalo — dias de alerta (bottleneck.days_threshold)
          </label>
          <input
            type="number"
            min={1}
            className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-1.5 text-xs w-28"
            placeholder="ex: 3"
            value={bottleneckDays}
            onChange={(e) => setBottleneckDays(e.target.value)}
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-text-dark-secondary mb-1">
            Qualidade — limite de eventos (quality.events_threshold)
          </label>
          <input
            type="number"
            min={1}
            className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-1.5 text-xs w-28"
            placeholder="ex: 5"
            value={qualityEvents}
            onChange={(e) => setQualityEvents(e.target.value)}
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-text-dark-secondary mb-1">
            Risco de entrega — janela (delivery_risk.window_days)
          </label>
          <input
            type="number"
            min={1}
            className="bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-1.5 text-xs w-28"
            placeholder="ex: 7"
            value={deliveryWindow}
            onChange={(e) => setDeliveryWindow(e.target.value)}
          />
        </div>
      </div>

      <div className="mt-5 flex justify-end">
        <DarkButton
          size="sm"
          disabled={mut.isPending}
          onClick={() => mut.mutate()}
        >
          {mut.isPending ? 'A guardar…' : <><Save size={12} className="mr-1" />Guardar alertas</>}
        </DarkButton>
      </div>
    </DarkCard>
  );
}

// ─── export ───────────────────────────────────────────────────────────────────

export function PlaneadorTab(): ReactNode {
  return (
    <div className="space-y-6 max-w-2xl">
      <SecPlaneamento />
      <SecTransporte />
      <SecAlertas />
    </div>
  );
}
