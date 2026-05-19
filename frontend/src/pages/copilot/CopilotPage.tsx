/**
 * CopilotPage — /copilot · chat fullscreen 3 colunas (Q.52.N)
 * ============================================================
 *
 * Reconstrói o copiloto como página inteira (o protótipo NELO,
 * page-copilot.jsx, abandona o drawer). Três colunas:
 *   - esquerda  · histórico de conversas (GET /api/copilot/conversations)
 *   - centro    · chat com pills de modo + mensagens + input
 *   - direita   · rail de contexto (fontes/acções da última resposta)
 *
 * ZERO MOCKS — todos os dados vêm da API:
 *   POST /api/copilot/ask                          — pergunta (conversa nova)
 *   POST /api/copilot/conversations/{id}/messages  — pergunta (conversa BD)
 *   GET  /api/copilot/conversations                — histórico
 *   GET  /api/copilot/conversations/{id}/messages  — mensagens de uma conversa
 *   POST /api/copilot/action                       — executar acção sugerida
 *
 * As conversas persistidas exigem auth (JWT). Sem token, o histórico
 * vem vazio e a página explica-o — o chat continua a funcionar via o
 * endpoint dev de `ask` (mesmo fallback do CopilotDrawer legacy).
 *
 * Esta página NÃO está registada em App.tsx — o wiring de rotas é da
 * Onda 2 (Q.52.S). Aqui só se constrói o componente.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Sparkles, Plus, Search, Send, MessageSquare } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { copilotApi } from '../../lib/api';
import type { CopilotResponse } from '../../lib/copilot-types';
import { CopilotChatMessage } from '../../components/copilot/CopilotChatMessage';
import { CopilotContextRail } from '../../components/copilot/CopilotContextRail';
import {
  COPILOT_MODES,
  nowLabel,
  type ChatMessage,
  type CopilotMode,
} from '../../components/copilot/copilotPageHelpers';

let msgSeq = 0;
const nextId = () => `m-${Date.now()}-${msgSeq++}`;

export default function CopilotPage() {
  const queryClient = useQueryClient();
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [mode, setMode] = useState<CopilotMode>('factual');
  const [input, setInput] = useState('');
  const [search, setSearch] = useState('');
  /** Mensagens da conversa em curso (sessão local — espelha o servidor). */
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // ─── Histórico de conversas ───────────────────────────────────────────
  const conversationsQuery = useQuery({
    queryKey: ['copilot', 'conversations'],
    queryFn: () => copilotApi.listConversations({ limit: 50 }),
    refetchOnWindowFocus: false,
  });
  const conversations = useMemo(
    () => conversationsQuery.data ?? [],
    [conversationsQuery.data],
  );
  const filteredConversations = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, search]);

  // ─── Mensagens da conversa seleccionada ───────────────────────────────
  const messagesQuery = useQuery({
    queryKey: ['copilot', 'conversation', activeConversation],
    queryFn: () => copilotApi.getConversationMessages(activeConversation!, { limit: 100 }),
    enabled: !!activeConversation,
    refetchOnWindowFocus: false,
  });

  // Quando uma conversa da BD carrega, hidrata o estado local.
  useEffect(() => {
    if (!activeConversation || !messagesQuery.data) return;
    setMessages(
      messagesQuery.data.map((m) => ({
        id: m.id,
        role: m.role === 'user' ? 'user' : 'copilot',
        text:
          m.content_text ||
          (m.content_structured as CopilotResponse | null)?.summary ||
          '',
        when: new Date(m.created_at).toLocaleTimeString('pt-PT', {
          hour: '2-digit',
          minute: '2-digit',
        }),
        response: (m.content_structured as CopilotResponse | null) ?? undefined,
      })),
    );
  }, [activeConversation, messagesQuery.data]);

  // Auto-scroll ao fundo a cada nova mensagem.
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // ─── Mutation: enviar pergunta ────────────────────────────────────────
  const askMutation = useMutation({
    mutationFn: (userQuery: string) => {
      const payload = { user_query: userQuery, include_citations: true };
      // Conversa persistida → endpoint da conversa. Senão → /ask (com
      // fallback dev embutido em copilotApi.ask).
      return activeConversation
        ? copilotApi.sendMessage(activeConversation, payload)
        : copilotApi.ask(payload);
    },
    onSuccess: (resp: CopilotResponse) => {
      setMessages((prev) => {
        const withoutTyping = prev.filter((m) => !m.typing);
        return [
          ...withoutTyping,
          {
            id: nextId(),
            role: 'copilot',
            text: resp.summary,
            when: nowLabel(),
            response: resp,
          },
        ];
      });
      if (activeConversation) {
        queryClient.invalidateQueries({
          queryKey: ['copilot', 'conversation', activeConversation],
        });
      }
      queryClient.invalidateQueries({ queryKey: ['copilot', 'conversations'] });
    },
    onError: (err: Error) => {
      setMessages((prev) => {
        const withoutTyping = prev.filter((m) => !m.typing);
        return [
          ...withoutTyping,
          {
            id: nextId(),
            role: 'copilot',
            text: `Não consegui responder: ${err.message || 'erro desconhecido'}. Tenta de novo daqui a pouco.`,
            when: nowLabel(),
          },
        ];
      });
    },
  });

  // ─── Mutation: executar acção sugerida ────────────────────────────────
  const lastResponse = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].response) return messages[i].response ?? null;
    }
    return null;
  }, [messages]);

  const actionMutation = useMutation({
    mutationFn: (action: CopilotResponse['actions'][number]) => {
      const suggestionId = lastResponse?.suggestion_id ?? '';
      return copilotApi.action({
        action_type: action.action_type,
        suggestion_id: suggestionId,
        payload: action.payload,
      });
    },
    onSuccess: () => {
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: 'copilot',
          text: 'Acção registada. Vê o estado no inbox de decisões.',
          when: nowLabel(),
        },
      ]);
    },
    onError: (err: Error) => {
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: 'copilot',
          text: `A acção falhou: ${err.message || 'erro desconhecido'}.`,
          when: nowLabel(),
        },
      ]);
    },
  });

  const send = () => {
    const text = input.trim();
    if (!text || askMutation.isPending) return;
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: 'user', text, when: nowLabel() },
      { id: nextId(), role: 'copilot', text: '', when: nowLabel(), typing: true },
    ]);
    setInput('');
    askMutation.mutate(text);
  };

  const newConversation = () => {
    setActiveConversation(null);
    setMessages([]);
    setInput('');
  };

  const activeMode = COPILOT_MODES.find((m) => m.id === mode)!;
  const activeTitle =
    conversations.find((c) => c.id === activeConversation)?.title ?? 'Nova conversa';

  const labelSm: React.CSSProperties = {
    fontSize: 10.5,
    color: 'var(--fg-3)',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    fontWeight: 600,
  };
  const railBox: React.CSSProperties = {
    background: 'var(--bg-1)',
    border: '1px solid var(--bd-1)',
    borderRadius: 'var(--r-lg)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    minHeight: 0,
  };

  return (
    <DarkPageLayout
      breadcrumbs={[{ label: 'Sistema' }, { label: 'Copilot' }]}
      title="Copilot"
      subtitle="Conversa profunda com o sistema · histórico · modos · fontes citáveis"
      icon={<Sparkles className="h-6 w-6" />}
    >
      <div
        className="grid gap-3.5"
        style={{
          gridTemplateColumns: '260px 1fr 280px',
          height: 'calc(100vh - 180px)',
        }}
      >
        {/* ─── Coluna 1 · histórico ────────────────────────────────── */}
        <div style={railBox}>
          <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--bd-1)' }}>
            <div className="flex items-center justify-between gap-2 mb-2">
              <div style={labelSm}>Conversas</div>
              <button
                type="button"
                onClick={newConversation}
                title="Nova conversa"
                className="inline-flex items-center justify-center rounded-md border border-bd-1 bg-bg-2 text-fg-2 hover:border-accent"
                style={{ width: 24, height: 24 }}
              >
                <Plus size={13} />
              </button>
            </div>
            <div
              className="flex items-center gap-1.5 rounded-md border border-bd-1 bg-bg-2"
              style={{ padding: '6px 10px' }}
            >
              <Search size={11} className="text-fg-3 shrink-0" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Procurar conversa…"
                className="flex-1 bg-transparent border-none outline-none text-fg-0 placeholder:text-fg-3"
                style={{ fontSize: 11.5 }}
              />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto" style={{ padding: 6 }}>
            {conversationsQuery.isLoading ? (
              <p className="text-xs text-fg-3 text-center py-6">A carregar…</p>
            ) : conversations.length === 0 ? (
              <div className="text-center py-8 px-3">
                <MessageSquare className="h-6 w-6 text-fg-3 mx-auto mb-2" />
                <p className="text-xs text-fg-3 leading-relaxed">
                  Sem conversas guardadas. O histórico persistente precisa de
                  sessão iniciada — entretanto podes conversar à mesma na coluna
                  do meio.
                </p>
              </div>
            ) : filteredConversations.length === 0 ? (
              <p className="text-xs text-fg-3 text-center py-6">
                Nenhuma conversa corresponde à pesquisa.
              </p>
            ) : (
              filteredConversations.map((c) => {
                const active = activeConversation === c.id;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => {
                      setActiveConversation(c.id);
                      setMessages([]);
                    }}
                    className={`w-full text-left rounded-md mb-0.5 transition-colors ${
                      active ? 'bg-bg-3' : 'hover:bg-bg-2'
                    }`}
                    style={{ padding: '9px 10px' }}
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <MessageSquare size={10} className="text-fg-3" />
                      <span
                        className="text-fg-3"
                        style={{ fontSize: 9.5, marginLeft: 'auto' }}
                      >
                        {c.last_message_at
                          ? new Date(c.last_message_at).toLocaleDateString('pt-PT')
                          : new Date(c.created_at).toLocaleDateString('pt-PT')}
                      </span>
                    </div>
                    <div
                      className="text-fg-1 truncate"
                      style={{ fontSize: 12, lineHeight: 1.4 }}
                    >
                      {c.title || 'Conversa sem título'}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* ─── Coluna 2 · chat ─────────────────────────────────────── */}
        <div style={railBox}>
          {/* Cabeçalho + pills de modo */}
          <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--bd-1)' }}>
            <div className="flex items-center gap-2 mb-2.5">
              <Sparkles size={14} className="text-accent" />
              <span className="text-fg-0 font-medium" style={{ fontSize: 13 }}>
                {activeTitle}
              </span>
            </div>
            <div className="flex gap-1 flex-wrap">
              {COPILOT_MODES.map((m) => {
                const active = mode === m.id;
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setMode(m.id)}
                    title={m.hint}
                    className="inline-flex items-center gap-1.5 transition-colors"
                    style={{
                      padding: '4px 10px',
                      borderRadius: 999,
                      fontSize: 11,
                      fontWeight: 500,
                      background: active ? 'var(--bg-3)' : 'transparent',
                      border: `1px solid ${active ? 'var(--bd-2)' : 'transparent'}`,
                      color: active ? 'var(--fg-0)' : 'var(--fg-2)',
                      cursor: 'pointer',
                    }}
                  >
                    {m.icon}
                    {m.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Mensagens */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto flex flex-col gap-4"
            style={{ padding: 22 }}
          >
            {activeConversation && messagesQuery.isLoading && messages.length === 0 ? (
              <p className="text-sm text-fg-3 text-center py-10">
                A carregar a conversa…
              </p>
            ) : messages.length === 0 ? (
              <div className="text-center py-16 px-6 m-auto">
                <Sparkles className="h-9 w-9 text-fg-3 mx-auto mb-3" />
                <h3 className="text-base font-medium text-fg-1 mb-1">
                  Pergunta o que quiseres ao sistema
                </h3>
                <p className="text-sm text-fg-3 leading-relaxed">
                  Estás em modo <strong>{activeMode.label.toLowerCase()}</strong> —{' '}
                  {activeMode.hint}. O copiloto consulta dados ao vivo e responde
                  com fontes citáveis.
                </p>
              </div>
            ) : (
              messages.map((m) => (
                <CopilotChatMessage
                  key={m.id}
                  message={m}
                  onAction={(a) => actionMutation.mutate(a)}
                  actionPending={actionMutation.isPending}
                />
              ))
            )}
          </div>

          {/* Input */}
          <div style={{ padding: 14, borderTop: '1px solid var(--bd-1)' }}>
            <div
              className="flex items-center gap-2 rounded-md border border-bd-2 bg-bg-2"
              style={{ padding: '8px 8px 8px 14px' }}
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') send();
                }}
                placeholder={`Pergunta em modo ${activeMode.label.toLowerCase()}…`}
                disabled={askMutation.isPending}
                className="flex-1 bg-white text-slate-900 placeholder:text-slate-400 border border-bd-1 rounded-md outline-none focus:border-accent"
                style={{ fontSize: 13, padding: '6px 10px' }}
              />
              <button
                type="button"
                onClick={send}
                disabled={!input.trim() || askMutation.isPending}
                className="grid place-items-center rounded-md disabled:opacity-50"
                style={{
                  width: 30,
                  height: 30,
                  background: input.trim() ? 'var(--accent)' : 'var(--bg-3)',
                  border: 'none',
                  color: input.trim() ? '#fff' : 'var(--fg-3)',
                  cursor: input.trim() ? 'pointer' : 'default',
                }}
              >
                <Send size={13} />
              </button>
            </div>
            <p className="text-fg-4 mt-1.5" style={{ fontSize: 10 }}>
              O copiloto consulta dados ao vivo · pode chamar simulações ·
              respostas com fontes citáveis.
            </p>
          </div>
        </div>

        {/* ─── Coluna 3 · contexto ─────────────────────────────────── */}
        <CopilotContextRail
          lastResponse={lastResponse}
          onAction={(a) => actionMutation.mutate(a)}
          actionPending={actionMutation.isPending}
        />
      </div>
    </DarkPageLayout>
  );
}
