// Hook de estado, queries, mutations e handlers do CopilotDrawer (Q.60.AD).
import { useState, useEffect, useRef } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { copilotApi } from '../../lib/api';
import type { CopilotResponse } from '../../lib/api';
import type { CopilotDrawerProps, Message } from './copilotDrawerTypes';

export function useCopilotDrawerState({
  isOpen, initialQuery, openedViaFab = false, initialEntityType, initialEntityId,
}: CopilotDrawerProps) {
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
      return copilotApi.createConversation(title || "Nova conversa");
    },
  });

  // Handle createConversationMutation success (React Query v5 pattern)
  useEffect(() => {
    if (createConversationMutation.isSuccess && createConversationMutation.data) {
      const data = createConversationMutation.data;
      setCurrentConversationId(data.id);
      // NÃO limpar mensagens - preservar as mensagens existentes (incluindo a resposta do COPILOT)
      // setMessages([]); // REMOVIDO - estava a limpar a resposta do COPILOT
      setInput('');
      // Limpar localStorage antigo quando criar nova conversa na BD
      localStorage.removeItem('copilot_messages');
      localStorage.setItem('copilot_current_conversation_id', data.id);
      refetchConversations();
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
      // Só carregar se não estivermos no meio de uma mutation (para não sobrescrever mensagens novas)
      // E apenas se não houver mensagens locais (para não sobrescrever mensagens que acabámos de adicionar)
      if (messages.length === 0) {
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
        setMessages(loadedMessages);
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
      // Q.18 fix-workforce — entity-aware (ex: employee) enriquece contexto LLM.
      const entityFields: { entity_type?: string; entity_id?: string } = {};
      if (initialEntityType && initialEntityId) {
        entityFields.entity_type = initialEntityType;
        entityFields.entity_id = initialEntityId;
      }
      try {
        if (currentConversationId) {
          try {
            return await copilotApi.sendMessage(currentConversationId, {
              user_query: query,
              idempotency_key,
              ...entityFields,
            });
          } catch (error: any) {
            if (error?.status === 401) {
              setCurrentConversationId(null);
              return await copilotApi.ask({ user_query: query, idempotency_key, ...entityFields });
            }
            throw error;
          }
        }
        return await copilotApi.ask({ user_query: query, idempotency_key, ...entityFields });
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
      return;
    }
    
    // Adicionar mensagem do user imediatamente (antes da resposta)
    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query,
      timestamp: new Date(),
    };
    setMessages((prev) => {
      const newMessages = [...prev, userMsg];
      return newMessages;
    });
    setInput(''); // Limpar input imediatamente para melhor UX
    
    // Enviar pergunta ao COPILOT
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


  return { messages, setMessages, input, setInput, modelStatus, setModelStatus, currentConversationId, setCurrentConversationId, showConversationsList, setShowConversationsList, isSendingMessage, setIsSendingMessage, showArchived, setShowArchived, inputRef, health, conversations, refetchConversations, conversationsError, archiveConversationMutation, createConversationMutation, conversationMessages, refetchMessages, askMutation, autoSentForQueryRef, handleSend, handleKeyPress, messagesEndRef };
}
