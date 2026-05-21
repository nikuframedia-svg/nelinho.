import { X, Send, Bot, Plus, History, Loader2, Archive, ArchiveRestore } from 'lucide-react';
import { copilotApi } from '../../lib/api';
import type { CopilotResponse } from '../../lib/api';
import { CopilotMessage } from './CopilotMessage';
import type { CopilotDrawerProps, Message } from './copilotDrawerTypes';
import { useCopilotDrawerState } from './useCopilotDrawerState';
import { setSecure } from '../../lib/secureStorage';

export function CopilotDrawer({
  isOpen, onClose, initialQuery, openedViaFab = false, initialEntityType, initialEntityId,
}: CopilotDrawerProps) {
  const {
    messages, setMessages, input, setInput, modelStatus, currentConversationId, setCurrentConversationId, showConversationsList, setShowConversationsList, showArchived, setShowArchived, inputRef, health, conversations, refetchConversations, conversationsError, archiveConversationMutation, createConversationMutation, askMutation, handleSend, handleKeyPress, messagesEndRef,
  } = useCopilotDrawerState({
    isOpen, onClose, initialQuery, openedViaFab, initialEntityType, initialEntityId,
  });

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
                          // Q.68.5.C — conversation_id encriptado.
                          void setSecure('copilot_current_conversation_id', conv.id);
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
