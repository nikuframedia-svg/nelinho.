import { useState, useEffect, useRef } from 'react';
import { X, Send, Bot, Plus, History, Loader2, Archive, ArchiveRestore } from 'lucide-react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { copilotApi } from '../../lib/api';
import type { CopilotResponse } from '../../lib/api';
import { CopilotMessage } from './CopilotMessage';

interface CopilotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  initialQuery?: string | null;
  openedViaFab?: boolean;
}

interface Message {
  id: string;
  role: 'user' | 'copilot';
  content: string | CopilotResponse;
  timestamp: Date;
}

export function CopilotDrawer({ isOpen, onClose, initialQuery, openedViaFab = false }: CopilotDrawerProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [modelStatus, setModelStatus] = useState<'ONLINE' | 'OFFLINE'>('ONLINE');
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [showConversationsList, setShowConversationsList] = useState(false);
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Health check
  const { data: health } = useQuery({
    queryKey: ['copilot', 'health'],
    queryFn: () => copilotApi.health(),
    refetchInterval: 30000, // 30s
  });

  // List conversations - apenas tentar se houver token (caso contrário, silenciar erro)
  const token = typeof window !== 'undefined' ? (localStorage.getItem('auth_token') || localStorage.getItem('token')) : null;
  const { data: conversations, refetch: refetchConversations, error: conversationsError } = useQuery({
    queryKey: ['copilot', 'conversations', showArchived],
    queryFn: () => copilotApi.listConversations({ limit: 20, archived: showArchived }),
    enabled: isOpen && !!token, // Apenas tentar se houver token
    retry: false, // Não retry em 401 (não autorizado)
  });

  // Archive conversation mutation
  const archiveConversationMutation = useMutation({
    mutationFn: (conversationId: string) => {
      return copilotApi.archiveConversation(conversationId);
    },
    onSuccess: () => {
      // Refetch conversations after archiving
      refetchConversations();
      // If current conversation was archived, clear it
      // (This will be handled in the useEffect below)
    },
  });

  // Handle archive mutation success
  useEffect(() => {
    if (archiveConversationMutation.isSuccess && archiveConversationMutation.data) {
      const archived = archiveConversationMutation.data.is_archived;
      const conversationId = archiveConversationMutation.data.id;
      
      // If current conversation was archived, switch to non-archived view
      if (archived && conversationId === currentConversationId && showArchived) {
        // Don't clear current conversation, just switch view
        setShowArchived(false);
      }
    }
  }, [archiveConversationMutation.isSuccess, archiveConversationMutation.data, currentConversationId, showArchived]);

  // Handle conversations error (React Query v5 pattern)
  useEffect(() => {
    if (conversationsError) {
      // Silenciar erros de autenticação - não são críticos para o chat
      const error = conversationsError as any;
      if (error?.status !== 401 && error?.status !== 403) {
        console.error('Erro ao carregar conversas:', conversationsError);
      }
    }
  }, [conversationsError]);

  // Create conversation mutation
  const createConversationMutation = useMutation({
    mutationFn: (title?: string) => {
      console.log('[COPILOT] createConversationMutation iniciado com título:', title);
      return copilotApi.createConversation(title || "Nova conversa");
    },
  });

  // Handle createConversationMutation success (React Query v5 pattern)
  useEffect(() => {
    if (createConversationMutation.isSuccess && createConversationMutation.data) {
      const data = createConversationMutation.data;
      console.log('[COPILOT] createConversationMutation.onSuccess chamado:', data);
      console.log('[COPILOT] Estado de mensagens ANTES de criar conversa:', messages.length);
      setCurrentConversationId(data.id);
      // NÃO limpar mensagens - preservar as mensagens existentes (incluindo a resposta do COPILOT)
      // setMessages([]); // REMOVIDO - estava a limpar a resposta do COPILOT
      setInput('');
      // Limpar localStorage antigo quando criar nova conversa na BD
      localStorage.removeItem('copilot_messages');
      localStorage.setItem('copilot_current_conversation_id', data.id);
      refetchConversations();
      console.log('[COPILOT] Estado de mensagens DEPOIS de criar conversa:', messages.length);
      // Focar no input após criar conversa
      setTimeout(() => {
        inputRef.current?.focus();
      }, 100);
    }
  }, [createConversationMutation.isSuccess, createConversationMutation.data, messages.length, refetchConversations]);

  // Handle createConversationMutation error (React Query v5 pattern)
  useEffect(() => {
    if (createConversationMutation.isError && createConversationMutation.error) {
      const error = createConversationMutation.error as any;
      // Se erro 401, apenas limpar estado e continuar sem conversa (mas NÃO limpar mensagens!)
      if (error?.status === 401) {
        console.warn('[COPILOT] Não autorizado para criar conversas, continuando sem conversa na BD');
        setCurrentConversationId(null);
        // NÃO limpar mensagens - preservar a resposta do COPILOT
        // setMessages([]); // REMOVIDO - estava a limpar a resposta do COPILOT
        setInput('');
        localStorage.removeItem('copilot_current_conversation_id');
      } else {
        console.error('[COPILOT] Erro ao criar conversa:', error);
      }
    }
  }, [createConversationMutation.isError, createConversationMutation.error]);

  // Load conversation messages
  const { data: conversationMessages, refetch: refetchMessages } = useQuery({
    queryKey: ['copilot', 'conversation', currentConversationId, 'messages'],
    queryFn: () => copilotApi.getConversationMessages(currentConversationId!),
    enabled: !!currentConversationId && isOpen,
  });

  // Load messages when conversation changes (mas não sobrescrever se acabámos de adicionar mensagens)
  useEffect(() => {
    if (conversationMessages && currentConversationId && !isSendingMessage) {
      console.log('[COPILOT] useEffect: Tentando carregar mensagens da conversa. Mensagens locais:', messages.length);
      // Só carregar se não estivermos no meio de uma mutation (para não sobrescrever mensagens novas)
      // E apenas se não houver mensagens locais (para não sobrescrever mensagens que acabámos de adicionar)
      if (messages.length === 0) {
        console.log('[COPILOT] Carregando mensagens da conversa (nenhuma mensagem local)');
        const loadedMessages: Message[] = conversationMessages.map((msg) => {
          // Garantir que content_structured tem estrutura válida ou usar content_text
          let content: string | CopilotResponse = msg.content_text;
          if (msg.content_structured) {
            // Validar que content_structured tem estrutura básica de CopilotResponse
            const structured = msg.content_structured as any;
            if (structured && typeof structured === 'object' && structured.summary !== undefined) {
              // Garantir que tem todas as propriedades obrigatórias com fallbacks
              content = {
                suggestion_id: structured.suggestion_id || msg.id,
                correlation_id: structured.correlation_id || msg.id,
                type: structured.type || 'ANSWER',
                intent: structured.intent || 'generic',
                summary: structured.summary || '',
                facts: structured.facts || [],
                actions: structured.actions || [],
                warnings: structured.warnings || [],
                meta: structured.meta || {},
              } as CopilotResponse;
            }
          }
          return {
            id: msg.id,
            role: msg.role as 'user' | 'copilot',
            content: content,
            timestamp: new Date(msg.created_at),
          };
        });
        console.log('[COPILOT] Mensagens carregadas da conversa:', loadedMessages.length);
        setMessages(loadedMessages);
      } else {
        console.log('[COPILOT] Não carregando mensagens - já existem mensagens locais:', messages.length);
      }
    }
  }, [conversationMessages, currentConversationId, isSendingMessage, messages.length]);

  useEffect(() => {
    if (health) {
      setModelStatus(health.ollama === 'online' ? 'ONLINE' : 'OFFLINE');
    }
  }, [health]);

  // Load conversation ID from localStorage on open
  useEffect(() => {
    if (isOpen && !currentConversationId) {
      const savedConversationId = localStorage.getItem('copilot_current_conversation_id');
      if (savedConversationId) {
        setCurrentConversationId(savedConversationId);
        // Tentar carregar mensagens desta conversa
        copilotApi.getConversationMessages(savedConversationId)
          .then(data => {
            if (data && data.length > 0) {
              setMessages(data.map(m => ({
                id: m.id,
                role: m.role as 'user' | 'copilot',
                content: m.content_structured || m.content_text,
                timestamp: new Date(m.created_at),
              })));
            }
          })
          .catch(e => {
            console.error("Failed to load conversation messages:", e);
            // Se falhar, limpar localStorage e começar do zero
            localStorage.removeItem('copilot_current_conversation_id');
            setCurrentConversationId(null);
          });
      }
    }
  }, [isOpen, currentConversationId]);

  // Mensagem inicial quando aberto via FAB (apenas se não há conversa e não há mensagens)
  useEffect(() => {
    if (isOpen && openedViaFab && !initialQuery && !currentConversationId && messages.length === 0 && !conversationMessages) {
      // Mensagem inicial automática quando aberto via FAB (apenas se não houver conversa ativa)
      const welcomeMessage: Message = {
        id: 'welcome-' + Date.now(),
        role: 'copilot',
        content: 'Queres que te explique algum insight ou analisar algo da operação?',
        timestamp: new Date(),
      };
      setMessages([welcomeMessage]);
    }
  }, [isOpen, openedViaFab, initialQuery, currentConversationId, messages.length, conversationMessages]);

  const askMutation = useMutation({
    mutationFn: async (query: string) => {
      setIsSendingMessage(true);
      // Onda fix-copilot: idempotency_key (UUID v4) por mutate evita duplicação
      // backend caso o browser faça retry no timeout (~20s default fetch).
      const idempotency_key =
        (typeof crypto !== 'undefined' && 'randomUUID' in crypto)
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      try {
        if (currentConversationId) {
          try {
            return await copilotApi.sendMessage(currentConversationId, {
              user_query: query,
              idempotency_key,
            });
          } catch (error: any) {
            if (error?.status === 401) {
              setCurrentConversationId(null);
              return await copilotApi.ask({ user_query: query, idempotency_key });
            }
            throw error;
          }
        }
        return await copilotApi.ask({ user_query: query, idempotency_key });
      } finally {
        setIsSendingMessage(false);
      }
    },
    // Onda fix-copilot Bug A: lógica em onSuccess/onError (correm 1×) em vez de
    // useEffect com deps mutáveis (refetchMessages/createConversationMutation
    // mudam de identidade em cada render → re-disparam o effect → setMessages
    // adicionava a resposta 2× no UI, agravado por StrictMode em dev).
    onSuccess: (response, query) => {
      if (!response || typeof response !== 'object' || !(response as any).suggestion_id) {
        const errorMsg: Message = {
          id: `error-${Date.now()}`,
          role: 'copilot',
          content: {
            suggestion_id: `error-${Date.now()}`,
            correlation_id: `error-${Date.now()}`,
            type: 'ERROR',
            intent: 'generic',
            summary: 'Resposta inválida do COPILOT. Tenta novamente.',
            facts: [],
            actions: [],
            warnings: [{ code: 'VALIDATION_FAILED', message: 'Resposta inválida' }],
            meta: { model: 'unknown', tokens: 0, latency_ms: 0, validation_passed: false },
          } as CopilotResponse,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMsg]);
        return;
      }

      const copilotMsg: Message = {
        id: (response as CopilotResponse).suggestion_id,
        role: 'copilot',
        content: response as CopilotResponse,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, copilotMsg]);

      if (!currentConversationId && query) {
        const title = query.substring(0, 50) || 'Nova conversa';
        createConversationMutation.mutate(title);
      } else if (currentConversationId) {
        refetchMessages();
        refetchConversations();
      }
    },
    onError: (error: any) => {
      let userMessage = 'Ocorreu um erro ao comunicar com o COPILOT. Tenta novamente.';
      let warningCode: 'MODEL_OFFLINE' | 'VALIDATION_FAILED' = 'MODEL_OFFLINE';

      if (error?.response?.data?.warnings) {
        const warnings = error.response.data.warnings;
        const validationWarning = warnings.find((w: any) => w.code === 'VALIDATION_FAILED');
        if (validationWarning) {
          userMessage = validationWarning.message || 'Não consegui validar a resposta do COPILOT. Tenta novamente.';
          warningCode = 'VALIDATION_FAILED';
        }
      } else if (error?.response?.data?.summary) {
        userMessage = error.response.data.summary;
        if (error.response.data.warnings && error.response.data.warnings.length > 0) {
          warningCode = error.response.data.warnings[0].code as any;
        }
      } else if (error?.message) {
        const errorMsg = error.message;
        if (errorMsg.includes('validation error') || errorMsg.includes('ValidationError') || errorMsg.includes('pydantic')) {
          userMessage = 'Não consegui validar a resposta do COPILOT. Tenta novamente.';
          warningCode = 'VALIDATION_FAILED';
        } else if (errorMsg.includes('network') || errorMsg.includes('fetch') || errorMsg.includes('timeout')) {
          userMessage = 'Erro de ligação ao COPILOT. Verifica a tua ligação à internet.';
        } else if (errorMsg.includes('500') || errorMsg.includes('Internal Server Error')) {
          userMessage = 'O serviço COPILOT está temporariamente indisponível. Tenta novamente mais tarde.';
        }
      }

      const errorMsg: Message = {
        id: `error-${Date.now()}`,
        role: 'copilot',
        content: {
          suggestion_id: `error-${Date.now()}`,
          correlation_id: `error-${Date.now()}`,
          type: 'ERROR',
          intent: 'generic',
          summary: userMessage,
          facts: [],
          actions: [],
          warnings: [{ code: warningCode, message: userMessage }],
          meta: { model: 'unknown', tokens: 0, latency_ms: 0, validation_passed: false },
        } as CopilotResponse,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    },
  });

  // Onda fix-copilot Bug B: useRef guard garante single-fire mesmo com StrictMode
  // duplo-mount em dev. Comparar valor cached vs novo initialQuery faz o reset
  // implícito quando user fecha drawer e abre com query diferente.
  const autoSentForQueryRef = useRef<string | null>(null);
  useEffect(() => {
    if (isOpen && initialQuery && autoSentForQueryRef.current !== initialQuery) {
      autoSentForQueryRef.current = initialQuery;
      setInput(initialQuery);
      askMutation.mutate(initialQuery);
    }
    if (!isOpen) {
      autoSentForQueryRef.current = null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, initialQuery]);

  const handleSend = () => {
    const query = input.trim();
    if (!query || isSendingMessage || askMutation.isPending) {
      console.log('[COPILOT] handleSend bloqueado:', { query: !!query, isSendingMessage, isPending: askMutation.isPending });
      return;
    }
    
    console.log('[COPILOT] handleSend chamado para query:', query);
    console.log('[COPILOT] Estado de mensagens ANTES de adicionar user msg:', messages.length);
    
    // Adicionar mensagem do user imediatamente (antes da resposta)
    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query,
      timestamp: new Date(),
    };
    setMessages((prev) => {
      const newMessages = [...prev, userMsg];
      console.log('[COPILOT] Mensagem do user adicionada. Total:', newMessages.length);
      return newMessages;
    });
    setInput(''); // Limpar input imediatamente para melhor UX
    
    // Enviar pergunta ao COPILOT
    console.log('[COPILOT] Chamando askMutation.mutate');
    askMutation.mutate(query);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages change or new message arrives
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isSendingMessage]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-end p-0 sm:p-4 md:p-6">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div 
        className="relative w-full sm:max-w-2xl h-full sm:h-auto sm:max-h-[90vh] bg-white flex flex-col sm:rounded-2xl"
        style={{
          boxShadow: '0 16px 48px rgba(0, 0, 0, 0.12), 0 4px 16px rgba(0, 0, 0, 0.08)',
          background: 'linear-gradient(to bottom, #ffffff 0%, #fafbfc 100%)',
          overflow: 'hidden',
          height: '100dvh', // Use dynamic viewport height for mobile
          maxHeight: '100dvh',
          marginLeft: showConversationsList ? '320px' : '0',
          transition: 'margin-left 200ms ease-out',
        }}
      >
        {/* Header - Fixed */}
        <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 bg-gradient-to-r from-[#1a2744] to-[#2d4a7c] text-white border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/10 backdrop-blur-sm flex items-center justify-center ring-2 ring-white/20">
              <Bot size={22} className="text-white" />
            </div>
            <div>
              <h2 className="font-bold text-xl tracking-tight">COPILOT</h2>
              <div className="flex items-center gap-2 text-sm text-white/80">
                <span className={`w-2.5 h-2.5 rounded-full ${modelStatus === 'ONLINE' ? 'bg-green-400 shadow-sm shadow-green-400/50' : 'bg-red-400'}`} />
                <span className="font-medium">{modelStatus}</span>
                {health && (
                  <>
                    <span className="text-white/50">•</span>
                    <span className="text-white/60 text-xs">{health.embeddings_model}</span>
                  </>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (!createConversationMutation.isPending) {
                  createConversationMutation.mutate(undefined);
                }
              }}
              disabled={createConversationMutation.isPending}
              className="p-2 hover:bg-white/10 rounded-lg transition-all duration-150 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Nova conversa"
              title="Nova conversa"
            >
              {createConversationMutation.isPending ? (
                <Loader2 size={18} className="text-white/80 animate-spin" />
              ) : (
                <Plus size={18} className="text-white/80" />
              )}
            </button>
            <button
              onClick={() => setShowConversationsList(!showConversationsList)}
              className={`p-2 rounded-lg transition-all duration-150 hover:scale-105 relative ${
                showConversationsList 
                  ? 'bg-white/20 hover:bg-white/25' 
                  : 'hover:bg-white/10'
              }`}
              aria-label="Ver histórico de conversas"
              title={showConversationsList ? "Fechar histórico" : "Ver histórico de conversas (mostra todas as conversas anteriores)"}
            >
              <History size={18} className="text-white/80" />
              {/* Badge com número de conversas se houver */}
              {conversations && conversations.length > 0 && (
                <span className="absolute -top-1 -right-1 w-5 h-5 bg-blue-400 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                  {conversations.length > 9 ? '9+' : conversations.length}
                </span>
              )}
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/10 rounded-lg transition-all duration-150 hover:scale-105"
              aria-label="Fechar"
            >
              <X size={20} className="text-white/80" />
            </button>
          </div>
        </div>

        {/* Conversations List Sidebar */}
        {showConversationsList && (
          <div className="absolute left-0 top-0 bottom-0 w-80 bg-white border-r border-slate-200 z-10 shadow-xl flex flex-col">
            <div className="p-4 border-b border-slate-200 flex flex-col gap-2 flex-shrink-0">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-slate-900">Conversas</h3>
                <button
                  onClick={() => setShowConversationsList(false)}
                  className="p-1 hover:bg-slate-100 rounded transition-colors duration-150"
                  aria-label="Fechar lista de conversas"
                >
                  <X size={18} className="text-slate-600" />
                </button>
              </div>
              {/* Archive filter toggle */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowArchived(!showArchived)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                    showArchived
                      ? 'bg-slate-100 text-slate-900 border border-slate-300'
                      : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                  }`}
                  aria-label={showArchived ? "Mostrar conversas ativas" : "Mostrar conversas arquivadas"}
                >
                  {showArchived ? (
                    <>
                      <ArchiveRestore size={14} />
                      Arquivadas
                    </>
                  ) : (
                    <>
                      <Archive size={14} />
                      Ativas
                    </>
                  )}
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {conversationsError && (conversationsError as any).status === 401 ? (
                <div className="text-center mt-8 p-4">
                  <History size={32} className="text-slate-300 mx-auto mb-2" />
                  <p className="text-sm text-slate-500 mb-2">
                    Autenticação necessária para ver conversas antigas.
                  </p>
                  <p className="text-xs text-slate-400">
                    Inicia sessão para aceder ao histórico de conversas.
                  </p>
                </div>
              ) : conversationsError ? (
                <div className="text-center mt-8 p-4">
                  <p className="text-sm text-red-600 mb-2">
                    Erro ao carregar conversas.
                  </p>
                  <button
                    onClick={() => refetchConversations()}
                    className="text-xs text-blue-600 hover:text-blue-800 underline"
                  >
                    Tentar novamente
                  </button>
                </div>
              ) : !conversations || conversations.length === 0 ? (
                <div className="text-center mt-8 p-4">
                  <History size={32} className="text-slate-300 mx-auto mb-2" />
                  <p className="text-sm text-slate-500 mb-2">Nenhuma conversa ainda.</p>
                  <p className="text-xs text-slate-400">
                    As tuas conversas aparecerão aqui.
                  </p>
                </div>
              ) : (
                conversations.map((conv) => {
                  const isActive = conv.id === currentConversationId;
                  return (
                    <div
                      key={conv.id}
                      className={`w-full p-3 rounded-lg transition-all duration-150 flex items-center justify-between group ${
                        isActive
                          ? 'bg-gradient-to-r from-blue-50 to-blue-100 text-blue-800 font-semibold border border-blue-200 shadow-sm'
                          : 'bg-white hover:bg-slate-50 text-slate-700 border border-transparent hover:border-slate-200'
                      }`}
                    >
                      <button
                        onClick={() => {
                          setCurrentConversationId(conv.id);
                          localStorage.setItem('copilot_current_conversation_id', conv.id);
                          // Carregar mensagens desta conversa
                          copilotApi.getConversationMessages(conv.id)
                            .then(data => {
                              const loadedMessages: Message[] = data.map((m) => {
                                let content: string | CopilotResponse = m.content_text;
                                if (m.content_structured) {
                                  const structured = m.content_structured as any;
                                  if (structured && typeof structured === 'object' && structured.summary !== undefined) {
                                    content = {
                                      suggestion_id: structured.suggestion_id || m.id,
                                      correlation_id: structured.correlation_id || m.id,
                                      type: structured.type || 'ANSWER',
                                      intent: structured.intent || 'generic',
                                      summary: structured.summary || '',
                                      facts: structured.facts || [],
                                      actions: structured.actions || [],
                                      warnings: structured.warnings || [],
                                      meta: structured.meta || {},
                                    } as CopilotResponse;
                                  }
                                }
                                return {
                                  id: m.id,
                                  role: m.role as 'user' | 'copilot',
                                  content: content,
                                  timestamp: new Date(m.created_at),
                                };
                              });
                              setMessages(loadedMessages);
                            })
                            .catch(e => {
                              console.error("Failed to load conversation messages:", e);
                              setMessages([]);
                            });
                          setShowConversationsList(false);
                        }}
                        className="flex-1 text-left flex items-center gap-2"
                      >
                        {conv.is_archived && (
                          <Archive size={12} className="text-slate-400 flex-shrink-0" />
                        )}
                        <span className="truncate flex-1 text-sm">{conv.title}</span>
                        <span className={`text-xs ml-2 flex-shrink-0 ${
                          isActive ? 'text-blue-600' : 'text-slate-500 group-hover:text-slate-700'
                        }`}>
                          {new Date(conv.last_message_at || conv.created_at).toLocaleDateString('pt-PT', { 
                            day: '2-digit', 
                            month: 'short',
                            ...(new Date(conv.last_message_at || conv.created_at).getFullYear() !== new Date().getFullYear() && {
                              year: '2-digit'
                            })
                          })}
                        </span>
                      </button>
                      {/* Archive/Unarchive button */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          archiveConversationMutation.mutate(conv.id);
                        }}
                        disabled={archiveConversationMutation.isPending}
                        className={`ml-2 p-1.5 rounded transition-all duration-150 flex-shrink-0 ${
                          conv.is_archived
                            ? 'text-amber-600 hover:bg-amber-50 hover:text-amber-700'
                            : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600 opacity-0 group-hover:opacity-100'
                        }`}
                        aria-label={conv.is_archived ? "Desarquivar conversa" : "Arquivar conversa"}
                        title={conv.is_archived ? "Desarquivar conversa" : "Arquivar conversa"}
                      >
                        {archiveConversationMutation.isPending ? (
                          <Loader2 size={14} className="animate-spin" />
                        ) : conv.is_archived ? (
                          <ArchiveRestore size={14} />
                        ) : (
                          <Archive size={14} />
                        )}
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* Messages - Scrollable with padding for input */}
        <div 
          className="flex-1 overflow-y-auto p-6 space-y-4 bg-gradient-to-b from-slate-50/30 to-white"
          style={{
            paddingBottom: 'calc(100px + env(safe-area-inset-bottom, 0px))', // Space for input + safe area
          }}
        >
          {messages.length === 0 && (
            <div className="text-center text-slate-500 mt-12">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#1a2744] to-[#2d4a7c] flex items-center justify-center mx-auto mb-4 shadow-lg">
                <Bot size={32} className="text-white" />
              </div>
              <p className="font-medium text-slate-700 text-lg">Faz uma pergunta ao COPILOT</p>
              <p className="text-sm mt-2 text-slate-500">Ex: "Porque é que o OEE baixou?"</p>
            </div>
          )}
          
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}
            >
              <div
                className={`max-w-[85%] sm:max-w-[75%] rounded-2xl p-4 transition-all duration-200 hover:shadow-md ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-br from-[#1a2744] to-[#2d4a7c] text-white shadow-lg'
                    : 'bg-white text-slate-900 border border-slate-200/60 shadow-sm'
                }`}
                style={{
                  borderRadius: msg.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                }}
              >
                {msg.role === 'user' ? (
                  <p className="text-sm leading-relaxed font-medium">{msg.content as string}</p>
                ) : (
                  <CopilotMessage response={msg.content as CopilotResponse} />
                )}
              </div>
            </div>
          ))}
          
          {askMutation.isPending && (
            <div className="flex justify-start animate-in fade-in duration-200">
              <div className="bg-white rounded-2xl p-4 border border-slate-200/60 shadow-sm">
                <div className="flex items-center gap-3 text-slate-600">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-100 to-blue-200 flex items-center justify-center">
                    <Bot size={16} className="text-blue-600 animate-pulse" />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="font-medium text-sm">A pensar</span>
                    <div className="flex gap-1">
                      <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                      <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                      <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input - Fixed at bottom */}
        <div 
          className="flex-shrink-0 border-t border-slate-200/60 bg-white/95 backdrop-blur-sm p-4"
          style={{
            paddingBottom: 'calc(1rem + env(safe-area-inset-bottom, 0px))',
          }}
        >
          <div className="flex gap-3">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Faz uma pergunta ao COPILOT…"
              className="flex-1 px-5 py-3 border border-slate-300/60 rounded-full focus:outline-none focus:ring-2 focus:ring-[#1a2744]/20 focus:border-[#1a2744] transition-all duration-200 bg-white text-slate-900 placeholder:text-slate-400 shadow-sm text-sm min-w-0"
              disabled={askMutation.isPending || createConversationMutation.isPending}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || askMutation.isPending}
              className="px-5 py-3 bg-gradient-to-br from-[#1a2744] to-[#2d4a7c] text-white rounded-full hover:from-[#2d4a7c] hover:to-[#3d5a9c] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center gap-2 shadow-lg hover:shadow-xl hover:scale-105 disabled:hover:scale-100 flex-shrink-0"
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

