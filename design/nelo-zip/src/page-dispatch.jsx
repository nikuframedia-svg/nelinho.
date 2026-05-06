/* ─── Página: Atribuição diária (Dispatch) ───────────────────────── */

const PageDispatch = () => {
  return (
    <UI.Page
      icon={<I.Activity size={20} />}
      title="Atribuição diária"
      subtitle="Quem faz o quê hoje · 8 operadores · 12 barcos activos"
      actions={
        <>
          <UI.Button variant="secondary" size="sm">Imprimir folha</UI.Button>
          <UI.Button variant="primary" tone="blue" size="sm" icon={<I.Sparkles size={13} />}>Sugerir atribuição</UI.Button>
        </>
      }
    >
      {/* Explainer */}
      <div style={{
        padding: '12px 16px',
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-md)',
        marginBottom: 20,
        fontSize: 12, color: 'var(--fg-2)', lineHeight: 1.5,
      }}>
        <strong style={{ color: 'var(--fg-1)' }}>Como funciona:</strong> Cada operador tem skills com score 0–10 baseado no histórico (taxa de erro, qualidade, tempo). O sistema sugere a melhor atribuição mas você pode arrastar-e-largar livremente. Operadores tier <code style={{ color: 'var(--fg-1)', background: 'var(--bg-3)', padding: '0 4px', borderRadius: 3 }}>&lt;5m</code> precisam de supervisão.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 18 }}>
        {/* Left: workers */}
        <div>
          <UI.SectionHeader title="Operadores" subtitle="Disponíveis hoje" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {PP.WORKERS.map(w => <WorkerRow key={w.id} worker={w} />)}
          </div>
        </div>

        {/* Right: barcos */}
        <div>
          <UI.SectionHeader title="Atribuições de hoje" subtitle="12 barcos · arraste operadores para reatribuir" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {PP.BOATS.slice(0, 8).map(b => <DispatchRow key={b.id} boat={b} />)}
          </div>
        </div>
      </div>
    </UI.Page>
  );
};

const WorkerRow = ({ worker: w }) => {
  const tone = w.score >= 8 ? 'green' : w.score >= 6 ? 'blue' : w.score >= 4 ? 'yellow' : 'red';
  const status = w.status === 'vacation' ? 'Férias' : 'Disponível';
  return (
    <div style={{
      padding: '10px 12px',
      background: 'var(--bg-1)',
      border: '1px solid var(--bd-1)',
      borderRadius: 'var(--r-md)',
      display: 'flex', alignItems: 'center', gap: 11,
      cursor: 'grab',
      opacity: w.status === 'vacation' ? 0.5 : 1,
    }}>
      <I.GripVert size={14} color="var(--fg-3)" />
      <UI.WorkerAvatar worker={w} size={32} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-0)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{w.name}</span>
          <span className="tabular" style={{ fontSize: 12, color: UI.colorVar(tone), fontWeight: 600 }}>★ {w.score.toFixed(1)}</span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 2, display: 'flex', justifyContent: 'space-between' }}>
          <span>{w.main}</span>
          <span style={{ color: w.status === 'vacation' ? 'var(--fg-3)' : 'var(--green)' }}>● {status}</span>
        </div>
      </div>
    </div>
  );
};

const DispatchRow = ({ boat: b }) => {
  const c = PP.CLIENTS[b.client];
  const phase = PP.PHASES[b.phase - 1];
  const workers = b.workers.map(wid => PP.WORKERS.find(w => w.id === wid)).filter(Boolean);
  const status = UI.STATUS[b.status];
  return (
    <div style={{
      padding: '14px 16px',
      background: 'var(--bg-1)',
      border: '1px solid var(--bd-1)',
      borderLeft: `3px solid ${UI.colorVar(status.color)}`,
      borderRadius: 'var(--r-md)',
      display: 'grid',
      gridTemplateColumns: '180px 1fr auto',
      gap: 14, alignItems: 'center',
    }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}>
          {b.short} #{b.id} <span style={{ marginLeft: 4 }}>{c.flag}</span>
        </div>
        <div style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 2 }}>{b.model}</div>
        <div style={{ marginTop: 6 }}>
          <UI.StatusBadge status={b.status} size="sm" />
        </div>
      </div>

      <div>
        <div style={{ fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 6 }}>
          F{phase.id} · {phase.name}
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '8px 10px',
          background: 'var(--bg-2)',
          border: '1px dashed var(--bd-2)',
          borderRadius: 'var(--r-sm)',
          minHeight: 42,
        }}>
          {workers.length === 0 ? (
            <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>Arraste um operador para aqui</span>
          ) : (
            workers.map(w => <UI.WorkerAvatar key={w.id} worker={w} showScore />)
          )}
        </div>
      </div>

      <div style={{ textAlign: 'right' }}>
        <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>Expedição</div>
        <div className="tabular" style={{ fontSize: 13, color: 'var(--fg-0)', fontWeight: 500, marginTop: 2 }}>
          {b.transport.slice(8,10)}/{b.transport.slice(5,7)}
        </div>
        <div style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 2 }}>D−{b.dx}</div>
      </div>
    </div>
  );
};

window.PageDispatch = PageDispatch;
