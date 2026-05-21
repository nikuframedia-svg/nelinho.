/**
 * SimulacoesPage — /simulacoes (Q.52.M).
 *
 * Reconstrução fiel do design NELO.html (page-simulacoes.jsx):
 *   • Tab "Histórico" — KPIs + lista de twin scenarios + detalhe
 *     baseline-vs-simulação. Tudo ligado a `GET /v1/twin/scenarios`.
 *   • Tab "Crise · agora" — 6 cenários de crise pré-definidos que
 *     correm no digital twin (criar + apply-delta + simulate).
 *
 * "Nova simulação" cria um twin scenario real. ZERO MOCKS: o histórico
 * vem da API; quando não há scenarios mostra um empty state honesto.
 *
 * Sprint Q.52.M.
 */

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  FlaskConical,
  History,
  Loader2,
  Plus,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { DarkPageLayout } from '../../layouts';
import { DarkButton } from '../../components/dark';
import { KPIBig } from '../../components/dark/KPIBig';
import { Sheet } from '../../components/dark/Sheet';
import { Segmented } from '../../components/dark/Segmented';
import { EmptyState } from '../../components/dark/EmptyState';
import { twinApi } from '../../lib/api';
import { useToastContext } from '../../components/ToastProvider';
import { Tag } from '../../components/simulacoes/atoms';
import { SimDetail } from '../../components/simulacoes/SimDetail';
import { CrisisSimulator } from '../../components/simulacoes/CrisisSimulator';
import type { TwinScenario } from '../../components/simulacoes/types';

type MainTab = 'historico' | 'crise';

function SimCard({
  scenario,
  active,
  onClick,
}: {
  scenario: TwinScenario;
  active: boolean;
  onClick: () => void;
}): ReactNode {
  const simulated = !!scenario.simulation_result;
  return (
    <div
      onClick={onClick}
      style={{
        padding: '14px 16px',
        background: active ? 'var(--bg-3)' : 'var(--bg-1)',
        border: `1px solid ${active ? 'var(--bd-3)' : 'var(--bd-1)'}`,
        borderRadius: 'var(--r-md)',
        cursor: 'pointer',
        marginBottom: 8,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 8,
        }}
      >
        <div
          style={{ display: 'flex', alignItems: 'center', gap: 8 }}
        >
          <Tag
            tone={
              scenario.status === 'SOLVED'
                ? 'green'
                : simulated
                  ? 'blue'
                  : 'yellow'
            }
            size="sm"
          >
            {scenario.status ?? 'DRAFT'}
          </Tag>
          <span
            className="mono"
            style={{ fontSize: 10.5, color: 'var(--fg-3)' }}
          >
            {scenario.id.slice(0, 8)}
          </span>
        </div>
        <span style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>
          {scenario.created_at
            ? new Date(scenario.created_at).toLocaleDateString('pt-PT')
            : '—'}
        </span>
      </div>
      <div
        style={{
          fontSize: 13,
          color: 'var(--fg-0)',
          fontWeight: 500,
          marginBottom: 4,
        }}
      >
        {scenario.title}
      </div>
      {scenario.description ? (
        <div style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
          {scenario.description}
        </div>
      ) : null}
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-3)',
          marginTop: 8,
        }}
      >
        {Array.isArray(scenario.deltas) ? scenario.deltas.length : 0}{' '}
        {Array.isArray(scenario.deltas) && scenario.deltas.length === 1
          ? 'delta'
          : 'deltas'}{' '}
        · {simulated ? 'simulado' : 'por simular'}
      </div>
    </div>
  );
}

function TabPill({
  active,
  onClick,
  icon,
  label,
  badge,
}: {
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
  label: string;
  badge?: number;
}): ReactNode {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '8px 14px',
        background: 'transparent',
        border: 'none',
        borderBottom: `1.5px solid ${
          active ? 'var(--fg-0)' : 'transparent'
        }`,
        color: active ? 'var(--fg-0)' : 'var(--fg-2)',
        fontSize: 12.5,
        fontWeight: active ? 600 : 500,
        cursor: 'pointer',
      }}
    >
      {icon}
      {label}
      {badge !== undefined ? (
        <span
          style={{
            background: 'var(--accent)',
            color: '#fff',
            fontSize: 9.5,
            fontWeight: 600,
            padding: '0 5px',
            borderRadius: 999,
            minWidth: 16,
            textAlign: 'center',
            height: 14,
            lineHeight: '14px',
          }}
        >
          {badge}
        </span>
      ) : null}
    </button>
  );
}

export default function SimulacoesPage(): ReactNode {
  const toast = useToastContext();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<MainTab>('historico');
  const [filter, setFilter] = useState<string>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');

  const {
    data: scenarios = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ['twin', 'scenarios'],
    queryFn: async (): Promise<TwinScenario[]> => {
      const raw = await twinApi.listScenarios();
      return Array.isArray(raw) ? (raw as TwinScenario[]) : [];
    },
  });

  const createMutation = useMutation({
    mutationFn: (data: { title: string; description?: string }) =>
      twinApi.createScenario(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['twin', 'scenarios'] });
      setWizardOpen(false);
      setNewTitle('');
      setNewDescription('');
      toast.success('Simulação criada');
    },
    onError: (err: unknown) =>
      toast.error(
        err instanceof Error ? err.message : 'Falhou criar a simulação',
      ),
  });

  const filtered = useMemo(() => {
    if (filter === 'all') return scenarios;
    return scenarios.filter((s) => (s.status ?? 'DRAFT') === filter);
  }, [scenarios, filter]);

  const selected = useMemo(
    () => scenarios.find((s) => s.id === selectedId) ?? null,
    [scenarios, selectedId],
  );

  const stats = useMemo(() => {
    const simulated = scenarios.filter((s) => !!s.simulation_result).length;
    const solved = scenarios.filter((s) => s.status === 'SOLVED').length;
    const draft = scenarios.filter(
      (s) => (s.status ?? 'DRAFT') === 'DRAFT',
    ).length;
    return { total: scenarios.length, simulated, solved, draft };
  }, [scenarios]);

  return (
    <DarkPageLayout
      title="Simulações"
      subtitle="What-if no digital twin · validação contra os 7 axiomas Spelke · não toca produção"
      icon={<FlaskConical size={20} />}
      actions={
        tab === 'historico' ? (
          <DarkButton
            icon={<Plus size={16} />}
            onClick={() => setWizardOpen(true)}
          >
            Nova simulação
          </DarkButton>
        ) : undefined
      }
    >
      {/* Tabs */}
      <div
        style={{
          display: 'flex',
          gap: 2,
          borderBottom: '1px solid var(--bd-1)',
          marginBottom: 18,
        }}
      >
        <TabPill
          active={tab === 'historico'}
          onClick={() => setTab('historico')}
          icon={<History size={12} />}
          label="Histórico"
        />
        <TabPill
          active={tab === 'crise'}
          onClick={() => setTab('crise')}
          icon={<AlertTriangle size={12} />}
          label="Crise · agora"
          badge={6}
        />
      </div>

      {tab === 'crise' ? (
        <CrisisSimulator />
      ) : (
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 10,
              marginBottom: 18,
            }}
          >
            <KPIBig
              label="Cenários · twin"
              value={stats.total}
              accent="blue"
            />
            <KPIBig
              label="Simulados"
              value={stats.simulated}
              status="green"
              accent="green"
            />
            <KPIBig
              label="Resolvidos"
              value={stats.solved}
              status="accent"
              accent="accent"
            />
            <KPIBig
              label="Por simular"
              value={stats.draft}
              status="yellow"
              accent="yellow"
            />
          </div>

          {error ? (
            <EmptyState
              title="Não foi possível carregar as simulações"
              hint={(error as Error).message}
              mascot={false}
              icon={<AlertTriangle size={28} />}
            />
          ) : isLoading ? (
            <div style={{ textAlign: 'center', padding: 48 }}>
              <Loader2
                size={32}
                className="animate-spin"
                style={{ color: 'var(--accent)' }}
              />
            </div>
          ) : scenarios.length === 0 ? (
            <EmptyState
              title="Ainda não há simulações"
              hint="Cria a primeira simulação ou usa a tab Crise para correr um cenário pré-definido no digital twin."
              icon={<FlaskConical size={28} />}
              action={
                <DarkButton
                  icon={<Plus size={16} />}
                  onClick={() => setWizardOpen(true)}
                >
                  Nova simulação
                </DarkButton>
              }
            />
          ) : (
            <>
              <div style={{ marginBottom: 12 }}>
                <Segmented<string>
                  options={[
                    { value: 'all', label: 'Todas' },
                    { value: 'DRAFT', label: 'Rascunho' },
                    { value: 'SIMULATED', label: 'Simuladas' },
                    { value: 'SOLVED', label: 'Resolvidas' },
                  ]}
                  value={filter}
                  onChange={setFilter}
                />
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1.3fr',
                  gap: 14,
                  minHeight: 480,
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: 10.5,
                      color: 'var(--fg-3)',
                      textTransform: 'uppercase',
                      letterSpacing: 0.4,
                      fontWeight: 600,
                      marginBottom: 8,
                    }}
                  >
                    {filtered.length}{' '}
                    {filtered.length === 1 ? 'simulação' : 'simulações'}
                  </div>
                  {filtered.length === 0 ? (
                    <div
                      style={{
                        padding: 24,
                        textAlign: 'center',
                        color: 'var(--fg-3)',
                        fontSize: 12,
                        background: 'var(--bg-1)',
                        border: '1px solid var(--bd-1)',
                        borderRadius: 'var(--r-md)',
                      }}
                    >
                      Sem simulações neste filtro.
                    </div>
                  ) : (
                    filtered.map((s) => (
                      <SimCard
                        key={s.id}
                        scenario={s}
                        active={s.id === selectedId}
                        onClick={() => setSelectedId(s.id)}
                      />
                    ))
                  )}
                </div>
                <div
                  style={{
                    background: 'var(--bg-1)',
                    border: '1px solid var(--bd-1)',
                    borderRadius: 'var(--r-lg)',
                    overflow: 'hidden',
                    display: 'flex',
                    flexDirection: 'column',
                  }}
                >
                  <SimDetail scenario={selected} />
                </div>
              </div>
            </>
          )}
        </>
      )}

      {/* Nova simulação */}
      <Sheet
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        title="Nova simulação"
        subtitle="What-if · corre no digital twin sandbox, não toca produção"
        width={560}
        footer={
          <>
            <DarkButton
              variant="secondary"
              onClick={() => setWizardOpen(false)}
            >
              Cancelar
            </DarkButton>
            <DarkButton
              icon={<Plus size={16} />}
              loading={createMutation.isPending}
              disabled={newTitle.trim().length === 0}
              onClick={() =>
                createMutation.mutate({
                  title: newTitle.trim(),
                  description: newDescription.trim() || undefined,
                })
              }
            >
              Criar simulação
            </DarkButton>
          </>
        }
      >
        <div
          style={{
            fontSize: 10.5,
            color: 'var(--fg-3)',
            textTransform: 'uppercase',
            letterSpacing: 0.4,
            fontWeight: 600,
            marginBottom: 8,
          }}
        >
          Título
        </div>
        <input
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          placeholder="Ex: E se faltar um laminador na próxima semana"
          className="text-slate-900 placeholder:text-slate-400"
          style={{
            width: '100%',
            padding: '9px 10px',
            background: '#fff',
            border: '1px solid var(--bd-2)',
            borderRadius: 'var(--r-sm)',
            fontSize: 12.5,
            marginBottom: 16,
            outline: 'none',
          }}
        />
        <div
          style={{
            fontSize: 10.5,
            color: 'var(--fg-3)',
            textTransform: 'uppercase',
            letterSpacing: 0.4,
            fontWeight: 600,
            marginBottom: 8,
          }}
        >
          Descrição (opcional)
        </div>
        <textarea
          value={newDescription}
          onChange={(e) => setNewDescription(e.target.value)}
          placeholder="Descreve o cenário em PT-PT…"
          className="text-slate-900 placeholder:text-slate-400"
          style={{
            width: '100%',
            minHeight: 90,
            padding: 11,
            background: '#fff',
            border: '1px solid var(--bd-2)',
            borderRadius: 'var(--r-sm)',
            fontSize: 12.5,
            fontFamily: 'inherit',
            resize: 'vertical',
            outline: 'none',
          }}
        />
        <div
          style={{
            marginTop: 14,
            padding: 12,
            background: 'var(--bg-2)',
            borderRadius: 'var(--r-sm)',
            fontSize: 11.5,
            color: 'var(--fg-2)',
            lineHeight: 1.5,
          }}
        >
          Depois de criar, abre a simulação para aplicar deltas e correr a
          simulação no digital twin. A sandbox valida os 7 axiomas Spelke.
        </div>
      </Sheet>
    </DarkPageLayout>
  );
}
