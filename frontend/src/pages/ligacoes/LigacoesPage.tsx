/**
 * LigacoesPage — /ligacoes · estado das ligações em tempo real.
 *
 * Q.53.L. Mostra:
 *   - saúde do RealtimeBridge (GET /v1/realtime/health);
 *   - canais disponíveis × tópicos Kafka (GET /v1/realtime/channels);
 *   - stream SSE ao vivo dos eventos (hook useRealtimeEvents).
 *
 * O utilizador escolhe que canais subscrever; a stream liga-se e os
 * eventos aparecem em tempo real. ZERO MOCKS — sem bridge, sem eventos,
 * a página mostra o estado honesto (offline / a aguardar).
 *
 * A rota desta página é registada à parte (App.tsx, fora deste território).
 */

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Radio,
  RefreshCw,
  Wifi,
  WifiOff,
  Activity,
  CircleDot,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkBadge, EmptyState } from '../../components/dark';
import { ligacoesApi } from './ligacoesApi';
import { useRealtimeEvents } from '../../hooks/useRealtimeEvents';

export default function LigacoesPage() {
  const healthQuery = useQuery({
    queryKey: ['ligacoes', 'health'],
    queryFn: () => ligacoesApi.health(),
    refetchInterval: 15_000,
    retry: 0,
  });
  const channelsQuery = useQuery({
    queryKey: ['ligacoes', 'channels'],
    queryFn: () => ligacoesApi.channels(),
    retry: 0,
  });

  const channelNames = useMemo(
    () => Object.keys(channelsQuery.data ?? {}).sort(),
    [channelsQuery.data],
  );

  // Canais subscritos pelo utilizador para a stream SSE ao vivo.
  const [subscribed, setSubscribed] = useState<string[]>([]);
  const streamEnabled = subscribed.length > 0;

  const { events, connected, lastHeartbeat, reconnectAttempts, clear } =
    useRealtimeEvents({ channels: subscribed, enabled: streamEnabled });

  const toggleChannel = (name: string) => {
    setSubscribed((prev) =>
      prev.includes(name)
        ? prev.filter((c) => c !== name)
        : [...prev, name],
    );
  };

  const health = healthQuery.data;

  return (
    <DarkPageLayout
      breadcrumbs={[{ label: 'Sistema' }, { label: 'Ligações' }]}
      title="Ligações"
      subtitle="Bridge de tempo real · canais · stream de eventos ao vivo"
      icon={<Radio className="h-6 w-6" />}
      actions={
        <button
          type="button"
          onClick={() => {
            healthQuery.refetch();
            channelsQuery.refetch();
          }}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-fg-2 hover:bg-white/5 hover:text-fg-0 border border-bd-1 text-xs font-medium transition-colors"
        >
          <RefreshCw size={13} />
          Atualizar
        </button>
      }
    >
      <div className="flex flex-col gap-3.5">
        {/* Saúde do bridge */}
        <div
          style={{
            background: 'var(--bg-1)',
            border: '1px solid var(--bd-1)',
            borderRadius: 'var(--r-lg)',
            padding: 18,
          }}
        >
          {healthQuery.isLoading ? (
            <p className="text-sm text-fg-3">A consultar o bridge…</p>
          ) : healthQuery.isError || !health ? (
            <div className="flex items-center gap-2.5">
              <WifiOff size={18} className="text-red" />
              <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-0)' }}>
                Bridge inacessível
              </span>
              <DarkBadge variant="danger">offline</DarkBadge>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between gap-3 mb-3">
                <div className="flex items-center gap-2.5">
                  {health.healthy ? (
                    <Wifi size={18} className="text-green" />
                  ) : (
                    <WifiOff size={18} className="text-red" />
                  )}
                  <span
                    style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-0)' }}
                  >
                    RealtimeBridge
                  </span>
                  <DarkBadge variant={health.healthy ? 'success' : 'danger'}>
                    {health.healthy ? 'saudável' : 'indisponível'}
                  </DarkBadge>
                </div>
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 10,
                }}
              >
                <Stat
                  label="Arrancado"
                  value={health.started ? 'Sim' : 'Não'}
                />
                <Stat label="Subscritores" value={String(health.subscribers)} />
                <Stat label="Tópicos" value={String(health.total_topics)} />
              </div>
              {!health.healthy && (
                <p className="text-[11px] text-fg-3 mt-3">
                  O bridge está indisponível (Kafka inacessível) — a stream de
                  eventos vai recair em polling.
                </p>
              )}
            </>
          )}
        </div>

        {/* Canais + subscrição */}
        <div
          style={{
            background: 'var(--bg-1)',
            border: '1px solid var(--bd-1)',
            borderRadius: 'var(--r-lg)',
            padding: 18,
          }}
        >
          <div
            style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}
            className="mb-1"
          >
            Canais
          </div>
          <p className="text-[11px] text-fg-3 mb-3">
            Escolhe os canais a subscrever — a stream ao vivo liga-se
            automaticamente.
          </p>
          {channelsQuery.isLoading ? (
            <p className="text-sm text-fg-3">A carregar canais…</p>
          ) : channelsQuery.isError ? (
            <p className="text-sm text-danger">
              Erro a carregar /v1/realtime/channels.
            </p>
          ) : channelNames.length === 0 ? (
            <EmptyState
              title="Sem canais disponíveis"
              hint="O bridge não declarou nenhum canal."
              icon={<Radio size={28} />}
            />
          ) : (
            <div className="flex flex-col gap-2">
              {channelNames.map((name) => {
                const topics = channelsQuery.data?.[name] ?? [];
                const active = subscribed.includes(name);
                return (
                  <button
                    key={name}
                    type="button"
                    onClick={() => toggleChannel(name)}
                    className="text-left rounded-md transition-colors"
                    style={{
                      padding: '10px 12px',
                      background: active ? 'var(--accent-bg)' : 'var(--bg-2)',
                      border: `1px solid ${active ? 'var(--accent-bd)' : 'var(--bd-1)'}`,
                      cursor: 'pointer',
                    }}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        style={{
                          width: 12,
                          height: 12,
                          borderRadius: 4,
                          border: `1px solid ${active ? 'var(--accent)' : 'var(--bd-2)'}`,
                          background: active ? 'var(--accent)' : 'transparent',
                          flexShrink: 0,
                        }}
                      />
                      <span
                        style={{
                          fontSize: 12.5,
                          fontWeight: 500,
                          color: 'var(--fg-0)',
                        }}
                      >
                        {name}
                      </span>
                      <DarkBadge variant="neutral">
                        {topics.length} tópico{topics.length === 1 ? '' : 's'}
                      </DarkBadge>
                    </div>
                    <div
                      className="font-mono"
                      style={{
                        fontSize: 10,
                        color: 'var(--fg-3)',
                        marginLeft: 20,
                      }}
                    >
                      {topics.join(' · ') || 'sem tópicos'}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Stream ao vivo */}
        <div
          style={{
            background: 'var(--bg-1)',
            border: '1px solid var(--bd-1)',
            borderRadius: 'var(--r-lg)',
            overflow: 'hidden',
          }}
        >
          <div
            className="flex items-center justify-between gap-3"
            style={{
              padding: '12px 16px',
              borderBottom: '1px solid var(--bd-1)',
            }}
          >
            <div className="flex items-center gap-2">
              <Activity size={14} className="text-accent" />
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}>
                Eventos ao vivo
              </span>
              {streamEnabled && (
                <DarkBadge variant={connected ? 'success' : 'warning'}>
                  {connected ? 'ligado' : 'a ligar…'}
                </DarkBadge>
              )}
            </div>
            <div className="flex items-center gap-2">
              {streamEnabled && lastHeartbeat && (
                <span className="text-[10px] text-fg-3">
                  último sinal{' '}
                  {lastHeartbeat.toLocaleTimeString('pt-PT', {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                  })}
                </span>
              )}
              {events.length > 0 && (
                <button
                  type="button"
                  onClick={clear}
                  className="text-[10px] text-fg-3 hover:text-fg-1 border border-bd-1 rounded px-2 py-0.5"
                >
                  limpar
                </button>
              )}
            </div>
          </div>

          {!streamEnabled ? (
            <div className="py-10 text-center text-xs text-fg-3 px-6">
              Subscreve pelo menos um canal acima para abrir a stream de
              eventos em tempo real.
            </div>
          ) : reconnectAttempts > 0 && !connected ? (
            <div className="py-10 text-center text-xs text-fg-3 px-6">
              A reconectar à stream… (tentativa {reconnectAttempts})
            </div>
          ) : events.length === 0 ? (
            <div className="py-10 text-center text-xs text-fg-3 px-6">
              Ligado — à espera de eventos nos canais {subscribed.join(', ')}.
            </div>
          ) : (
            <div
              className="flex flex-col"
              style={{ maxHeight: 360, overflowY: 'auto' }}
            >
              {[...events].reverse().map((ev, i) => (
                <div
                  key={`${ev.event_id ?? 'ev'}-${i}`}
                  className="flex items-start gap-2.5"
                  style={{
                    padding: '9px 16px',
                    borderBottom: '1px solid var(--bd-1)',
                  }}
                >
                  <CircleDot size={11} className="text-accent mt-0.5 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className="font-mono"
                        style={{
                          fontSize: 11.5,
                          color: 'var(--fg-0)',
                          fontWeight: 500,
                        }}
                      >
                        {ev.event_type}
                      </span>
                      {ev.source_module && (
                        <span style={{ fontSize: 9.5, color: 'var(--fg-3)' }}>
                          {ev.source_module}
                        </span>
                      )}
                      {ev.timestamp && (
                        <span
                          style={{
                            fontSize: 9.5,
                            color: 'var(--fg-4)',
                            marginLeft: 'auto',
                          }}
                        >
                          {new Date(ev.timestamp).toLocaleTimeString('pt-PT')}
                        </span>
                      )}
                    </div>
                    <pre
                      className="font-mono"
                      style={{
                        fontSize: 10,
                        color: 'var(--fg-3)',
                        marginTop: 3,
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                      }}
                    >
                      {JSON.stringify(ev.payload)}
                    </pre>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </DarkPageLayout>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        background: 'var(--bg-2)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-sm)',
        padding: '10px 12px',
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
        }}
      >
        {label}
      </div>
      <div
        className="tabular"
        style={{ fontSize: 18, fontWeight: 600, color: 'var(--fg-0)', marginTop: 2 }}
      >
        {value}
      </div>
    </div>
  );
}
