/* ─── Página: Plano de Produção (Scheduling) ─────────────────────── */

const PageScheduling = () => {
  const [view, setView] = React.useState('phases'); // phases | gantt | calendar

  return (
    <UI.Page
      icon={<I.Calendar size={20} />}
      title="Plano de produção"
      subtitle="Onde está cada barco · 12 barcos activos · 41 fases"
      actions={
        <>
          <SegmentedControl value={view} onChange={setView} options={[
            { id: 'phases',   label: 'Por fase' },
            { id: 'gantt',    label: 'Gantt' },
            { id: 'calendar', label: 'Calendário' },
          ]}/>
          <UI.Button variant="primary" tone="blue" size="sm" icon={<I.Sparkles size={13} />}>
            Re-optimizar
          </UI.Button>
        </>
      }
    >
      {view === 'phases' && <PhasesView />}
      {view === 'gantt'  && <GanttView />}
      {view === 'calendar' && <CalendarView />}
    </UI.Page>
  );
};

/* Pequeno segmented control */
const SegmentedControl = ({ value, onChange, options }) => (
  <div style={{
    display: 'inline-flex',
    background: 'var(--bg-2)',
    border: '1px solid var(--bd-1)',
    borderRadius: 'var(--r-md)',
    padding: 2,
  }}>
    {options.map(o => (
      <button key={o.id} onClick={() => onChange(o.id)} style={{
        padding: '5px 12px',
        background: value === o.id ? 'var(--bg-0)' : 'transparent',
        border: value === o.id ? '1px solid var(--bd-2)' : '1px solid transparent',
        borderRadius: 'var(--r-sm)',
        color: value === o.id ? 'var(--fg-0)' : 'var(--fg-2)',
        fontSize: 12, fontWeight: 500,
        cursor: 'pointer',
      }}>{o.label}</button>
    ))}
  </div>
);

/* ─── Phases view — fluxo de barcos por fase ─────────────────────── */
const PhasesView = () => {
  const phasesShown = PP.PHASES.slice(0, 11);
  return (
    <>
      {/* Legend */}
      <div style={{ display: 'flex', gap: 18, marginBottom: 20, padding: '10px 14px',
        background: 'var(--bg-1)', border: '1px solid var(--bd-1)', borderRadius: 'var(--r-md)',
        fontSize: 11, color: 'var(--fg-2)',
      }}>
        <span style={{ marginRight: 'auto', fontWeight: 500, color: 'var(--fg-1)' }}>Como ler:</span>
        <span>Cartões = barcos. Arraste entre fases para mover.</span>
        <span style={{ display: 'flex', gap: 14 }}>
          {[['green','No prazo'],['yellow','Em risco'],['red','Atrasado'],['gray','Em cura']].map(([c,l]) => (
            <span key={c} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: UI.colorVar(c) }} />{l}
            </span>
          ))}
        </span>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${phasesShown.length}, minmax(140px, 1fr))`,
        gap: 12,
        overflowX: 'auto',
        paddingBottom: 8,
      }}>
        {phasesShown.map(p => {
          const boats = PP.BOATS.filter(b => b.phase === p.id);
          const load = (boats.length / p.cap) * 100;
          const loadColor = load > 90 ? 'red' : load > 70 ? 'yellow' : 'green';
          return (
            <div key={p.id} style={{
              background: 'var(--bg-1)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-md)',
              minHeight: 380,
              display: 'flex', flexDirection: 'column',
            }}>
              <div style={{
                padding: '10px 12px',
                borderBottom: '1px solid var(--bd-1)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>F{p.id}</span>
                  <span className="tabular" style={{ fontSize: 11, color: UI.colorVar(loadColor), fontWeight: 600 }}>
                    {boats.length}/{p.cap}
                  </span>
                </div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-0)', marginTop: 3 }}>{p.name}</div>
                <div style={{ height: 3, background: 'var(--bg-3)', borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
                  <div style={{ width: `${Math.min(load, 100)}%`, height: '100%', background: UI.colorVar(loadColor) }} />
                </div>
                {p.cure > 0 && (
                  <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <I.Clock size={10} /> Cura {p.cure}h
                  </div>
                )}
              </div>
              <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
                {boats.length === 0 && (
                  <div style={{
                    flex: 1, display: 'grid', placeItems: 'center',
                    fontSize: 11, color: 'var(--fg-3)',
                    border: '1px dashed var(--bd-1)',
                    borderRadius: 'var(--r-sm)',
                  }}>vazio</div>
                )}
                {boats.map(b => <UI.BoatCard key={b.id} boat={b} compact />)}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
};

/* ─── Gantt simples ──────────────────────────────────────────────── */
const GanttView = () => {
  const days = ['12 Qua', '13 Qui', '14 Sex', '15 Sáb', '16 Dom', '18 Seg', '19 Ter', '20 Qua', '21 Qui', '22 Sex'];
  return (
    <UI.Card padding={0}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, fontSize: 12 }}>
          <thead>
            <tr style={{ background: 'var(--bg-2)' }}>
              <th style={ganttCellSticky}>Barco</th>
              <th style={ganttCellSticky2}>Cliente</th>
              {days.map(d => <th key={d} style={ganttCellHead}>{d}</th>)}
            </tr>
          </thead>
          <tbody>
            {PP.BOATS.map(b => {
              const start = Math.floor(Math.random() * 4);
              const len = 4 + Math.floor(Math.random() * 5);
              const c = PP.CLIENTS[b.client];
              const tone = UI.STATUS[b.status].color;
              return (
                <tr key={b.id} style={{ background: 'var(--bg-1)' }}>
                  <td style={ganttCellName}>
                    <div style={{ fontWeight: 600, color: 'var(--fg-0)' }}>{b.short} #{b.id}</div>
                    <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>{b.model}</div>
                  </td>
                  <td style={ganttCellClient}>{c.flag} {c.code}</td>
                  {days.map((d, i) => (
                    <td key={d} style={ganttCellDay}>
                      {i === start && (
                        <div style={{
                          gridColumn: `span ${len}`,
                          height: 22,
                          width: `calc(${len * 100}% + ${(len-1) * 1}px)`,
                          background: UI.colorBg(tone),
                          border: `1px solid ${UI.colorBd(tone)}`,
                          borderLeft: `3px solid ${UI.colorVar(tone)}`,
                          borderRadius: 4,
                          padding: '2px 6px',
                          fontSize: 10,
                          color: UI.colorVar(tone),
                          display: 'flex', alignItems: 'center',
                          fontWeight: 500,
                          position: 'relative',
                          zIndex: 1,
                        }}>{PP.PHASES[b.phase-1]?.short}</div>
                      )}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </UI.Card>
  );
};

const ganttCellSticky  = { position: 'sticky', left: 0, background: 'var(--bg-2)', padding: '10px 14px', textAlign: 'left', borderBottom: '1px solid var(--bd-1)', borderRight: '1px solid var(--bd-1)', fontSize: 11, color: 'var(--fg-2)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.4, minWidth: 160 };
const ganttCellSticky2 = { position: 'sticky', left: 160, background: 'var(--bg-2)', padding: '10px 14px', textAlign: 'left', borderBottom: '1px solid var(--bd-1)', borderRight: '1px solid var(--bd-1)', fontSize: 11, color: 'var(--fg-2)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.4, minWidth: 80 };
const ganttCellHead   = { padding: '10px 8px', textAlign: 'center', borderBottom: '1px solid var(--bd-1)', fontSize: 11, color: 'var(--fg-2)', fontWeight: 500, minWidth: 80 };
const ganttCellName   = { position: 'sticky', left: 0, background: 'var(--bg-1)', padding: '10px 14px', borderBottom: '1px solid var(--bd-1)', borderRight: '1px solid var(--bd-1)', minWidth: 160 };
const ganttCellClient = { position: 'sticky', left: 160, background: 'var(--bg-1)', padding: '10px 14px', borderBottom: '1px solid var(--bd-1)', borderRight: '1px solid var(--bd-1)', minWidth: 80, fontSize: 12, color: 'var(--fg-1)' };
const ganttCellDay    = { borderBottom: '1px solid var(--bd-1)', borderRight: '1px solid var(--bd-1)', padding: 4, height: 36, position: 'relative' };

const CalendarView = () => (
  <UI.Card>
    <div style={{ padding: 60, textAlign: 'center' }}>
      <I.Calendar size={32} color="var(--fg-3)" />
      <div style={{ marginTop: 12, color: 'var(--fg-2)' }}>Vista de calendário</div>
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 4 }}>
        Mostraria expedições e milestones por mês
      </div>
    </div>
  </UI.Card>
);

window.PageScheduling = PageScheduling;
