/* ─── Copilot Drawer ─────────────────────────────────────────────── */
const { useState: useStateC } = React;

const CopilotMessage = ({ from, content }) => {
  const isAI = from === 'ai';
  return (
    <div style={{
      display: 'flex',
      gap: 10,
      flexDirection: isAI ? 'row' : 'row-reverse',
    }}>
      <div style={{
        width: 26, height: 26, borderRadius: '50%',
        background: isAI ? 'var(--blue-bg)' : 'var(--bg-3)',
        border: `1px solid ${isAI ? 'var(--blue-bd)' : 'var(--bd-2)'}`,
        display: 'grid', placeItems: 'center',
        flexShrink: 0,
      }}>
        {isAI ? <I.Sparkles size={12} color="var(--blue)" /> : <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--fg-1)' }}>NF</span>}
      </div>
      <div style={{
        background: isAI ? 'var(--bg-2)' : 'var(--blue-bg)',
        border: `1px solid ${isAI ? 'var(--bd-1)' : 'var(--blue-bd)'}`,
        borderRadius: 'var(--r-md)',
        padding: '10px 13px',
        fontSize: 13,
        color: 'var(--fg-0)',
        lineHeight: 1.5,
        maxWidth: '85%',
      }}>{content}</div>
    </div>
  );
};

const CopilotDrawer = ({ open, onClose }) => {
  const [tab, setTab] = useStateC('suggestions');
  const [messages, setMessages] = useStateC([
    { from: 'ai', content: <>Bom dia, Nuno. Hoje há <strong>3 sugestões</strong> à espera. A mais urgente é mover 3 barcos K2 de terça para quarta — o molde K2 7 L (02) entra em manutenção. Quer ver?</> },
  ]);
  const [input, setInput] = useStateC('');
  const sug = PP.SUGGESTIONS;

  const send = () => {
    if (!input.trim()) return;
    const q = input;
    setInput('');
    setMessages(m => [...m, { from: 'user', content: q }]);
    setTimeout(() => {
      setMessages(m => [...m, {
        from: 'ai',
        content: <>Boa pergunta. <em>(O assistente responderia aqui — neste protótipo é um placeholder.)</em></>
      }]);
    }, 700);
  };

  if (!open) return null;
  return (
    <>
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
        zIndex: 40, animation: 'fade-in 0.15s',
      }} />
      <aside style={{
        position: 'fixed', top: 0, right: 0, bottom: 0,
        width: 460, zIndex: 50,
        background: 'var(--bg-1)',
        borderLeft: '1px solid var(--bd-1)',
        display: 'flex', flexDirection: 'column',
        animation: 'slide-in-right 0.2s',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--bd-1)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 'var(--r-md)',
              background: 'var(--blue-bg)', border: '1px solid var(--blue-bd)',
              display: 'grid', placeItems: 'center',
            }}>
              <I.Sparkles size={16} color="var(--blue)" />
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-0)' }}>Assistente NELO</div>
              <div style={{ fontSize: 11, color: 'var(--fg-2)' }}>Aprendeu com 1.247 decisões</div>
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            color: 'var(--fg-2)', padding: 4,
          }}><I.X size={18} /></button>
        </div>

        {/* Tabs */}
        <div style={{
          display: 'flex',
          padding: '0 20px',
          borderBottom: '1px solid var(--bd-1)',
        }}>
          {[
            { id: 'suggestions', label: 'Sugestões', count: sug.length },
            { id: 'chat',        label: 'Conversa',  count: null },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              padding: '10px 14px',
              background: 'transparent', border: 'none', cursor: 'pointer',
              fontSize: 13,
              color: tab === t.id ? 'var(--fg-0)' : 'var(--fg-2)',
              fontWeight: tab === t.id ? 500 : 400,
              borderBottom: `2px solid ${tab === t.id ? 'var(--blue)' : 'transparent'}`,
              marginBottom: -1,
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              {t.label}
              {t.count !== null && (
                <span style={{
                  fontSize: 10, padding: '1px 6px',
                  background: 'var(--bg-3)', color: 'var(--fg-1)',
                  borderRadius: 999, fontWeight: 600,
                }}>{t.count}</span>
              )}
            </button>
          ))}
        </div>

        {/* Body */}
        {tab === 'suggestions' && (
          <div style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{
              padding: 14,
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-lg)',
              display: 'flex', gap: 10,
            }}>
              <I.Info size={16} color="var(--fg-2)" style={{ marginTop: 2, flexShrink: 0 }}/>
              <div style={{ fontSize: 12, color: 'var(--fg-1)', lineHeight: 1.5 }}>
                As sugestões são <strong>propostas, não ordens</strong>. Pode aceitar, rejeitar ou aplicar uma alternativa. Cada decisão ensina o sistema.
              </div>
            </div>

            {sug.map(s => (
              <div key={s.id} style={{
                background: 'var(--bg-1)',
                border: '1px solid var(--bd-1)',
                borderRadius: 'var(--r-lg)',
                overflow: 'hidden',
              }}>
                <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--bd-1)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10, marginBottom: 8 }}>
                    <UI.SevBadge severity={s.priority === 'critical' ? 'critical' : s.priority === 'high' ? 'high' : 'medium'} size="sm" />
                    <span style={{ fontSize: 10, color: 'var(--fg-3)' }}>#{s.id}</span>
                  </div>
                  <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: 'var(--fg-0)', lineHeight: 1.4 }}>{s.title}</h3>
                  <div style={{ marginTop: 8, fontSize: 12, color: 'var(--fg-2)', lineHeight: 1.5 }}>
                    <strong style={{ color: 'var(--fg-1)' }}>Porquê:</strong> {s.why}
                  </div>
                </div>
                <div style={{ padding: 14 }}>
                  <UI.ConsequenceBox
                    if_accept={s.if_accept}
                    if_reject={s.if_reject}
                    alternative={s.alternative}
                    confidence={s.confidence}
                    source={s.source}
                    onAccept={() => alert(`Sugestão #${s.id} aceite.`)}
                    onReject={(r) => alert(`Sugestão #${s.id} rejeitada. Motivo: ${r}`)}
                    onAlternative={() => alert(`Alternativa aplicada à #${s.id}.`)}
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === 'chat' && (
          <>
            <div style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
              {messages.map((m, i) => <CopilotMessage key={i} from={m.from} content={m.content} />)}
            </div>
            <div style={{
              padding: 14, borderTop: '1px solid var(--bd-1)',
              background: 'var(--bg-2)',
            }}>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && send()}
                  placeholder="Pergunte algo sobre a fábrica..."
                  style={{
                    flex: 1,
                    padding: '9px 12px',
                    background: 'var(--bg-1)',
                    border: '1px solid var(--bd-2)',
                    borderRadius: 'var(--r-md)',
                    color: 'var(--fg-0)',
                    fontSize: 13,
                    outline: 'none',
                  }}
                />
                <UI.Button variant="primary" tone="blue" onClick={send} icon={<I.Send size={14} />} />
              </div>
              <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {[
                  'Porque está #4275 atrasado?',
                  'Que erros teve a Ana esta semana?',
                  'Vamos cumprir sexta-feira?',
                ].map(q => (
                  <button key={q} onClick={() => setInput(q)} style={{
                    padding: '4px 10px',
                    background: 'var(--bg-1)',
                    border: '1px solid var(--bd-1)',
                    borderRadius: 999,
                    color: 'var(--fg-2)',
                    fontSize: 11,
                    cursor: 'pointer',
                  }}>{q}</button>
                ))}
              </div>
            </div>
          </>
        )}
      </aside>
    </>
  );
};

window.CopilotDrawer = CopilotDrawer;
