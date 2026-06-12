/**
 * OperationEditSheet — editor de UMA operação do plano (Q.147.C).
 *
 * Resolve "para cada operação escolher a pessoa, pôr numa fase diferente, mudar
 * a data" sem depender da densidade da grelha. Só ops de PLANO (os actuals do
 * passado são read-only). Guardar → reorder (valida axiomas Spelke, cria DRAFT).
 *
 * Q.174.F8 — "Porquê?": mostra os fatores REAIS da escolha do CPO (curado,
 * skill, disponibilidade, carga, ausências) re-derivados pelo backend com a
 * fórmula do decoder + as melhores alternativas. On-demand (só ao abrir).
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { HelpCircle } from 'lucide-react';
import { Sheet } from '../dark/Sheet';
import { DarkButton } from '../dark/DarkButton';
import { planKeys } from '../../lib/api/keys';
import { cpoCommitsApi } from '../../lib/api';
import type { CpoExplainCandidate } from '../../lib/api';
import type { ScheduledOp } from './types';

export interface OperatorOption {
  code: string;
  name: string;
}
export interface PhaseOption {
  id: string;
  name: string;
}

const fieldStyle: React.CSSProperties = {
  width: '100%',
  padding: '7px 10px',
  background: 'var(--bg-3)',
  color: 'var(--fg-0)',
  border: '1px solid var(--bd-2)',
  borderRadius: 6,
  fontSize: 13,
  outline: 'none',
  colorScheme: 'dark',
};

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="text-[10px] uppercase tracking-wide font-semibold mb-1"
      style={{ color: 'var(--fg-3)' }}
    >
      {children}
    </div>
  );
}

function CandidateRow({
  c,
  name,
}: {
  c: CpoExplainCandidate;
  name?: string;
}) {
  return (
    <div
      className="flex items-center gap-2 px-2 py-1 rounded text-[11px]"
      style={{
        background: c.escolhido ? 'var(--accent-bg)' : 'var(--bg-4)',
        border: `1px solid ${c.escolhido ? 'var(--accent-bd)' : 'var(--bd-2)'}`,
      }}
    >
      <span className="font-medium truncate" style={{ color: 'var(--fg-1)' }}>
        {name ?? c.worker_id}
      </span>
      {c.escolhido && (
        <span className="text-[9px] font-semibold uppercase" style={{ color: 'var(--accent)' }}>
          escolhido
        </span>
      )}
      <span className="ml-auto flex items-center gap-2 font-mono tabular-nums" style={{ color: 'var(--fg-3)' }}>
        {c.rank_curado != null && <span title="rank de curado (1.0 = topo da lista Melhores por fase)">★{c.rank_curado.toFixed(2)}</span>}
        <span title="horas até estar livre no arranque da op">
          {c.horas_ate_livre <= 0.01 ? 'livre' : `+${c.horas_ate_livre.toFixed(0)}h`}
        </span>
        <span title="horas totais atribuídas neste plano">{c.carga_plano_h.toFixed(0)}h</span>
        {c.ausente_na_janela && (
          <span style={{ color: 'var(--yellow)' }} title="ausência registada na janela da op">
            ausente
          </span>
        )}
      </span>
    </div>
  );
}

export function OperationEditSheet({
  op,
  operators,
  phases,
  isPending,
  onSave,
  onClose,
}: {
  op: ScheduledOp;
  operators: OperatorOption[];
  phases: PhaseOption[];
  isPending: boolean;
  onSave: (v: { phaseId: string; operatorId: string; date: string }) => void;
  onClose: () => void;
}) {
  const [phaseId, setPhaseId] = useState(op.phase_id);
  const [operatorId, setOperatorId] = useState(op.operator_id ?? '');
  const [date, setDate] = useState((op.start ?? '').slice(0, 10));
  // Q.174.F8 — explicação on-demand (não custa nada a quem não pergunta).
  const [showWhy, setShowWhy] = useState(false);

  const explainQuery = useQuery({
    queryKey: planKeys.opExplain(op.id),
    queryFn: () => cpoCommitsApi.explainOperation(op.id, { top_n: 3 }),
    enabled: showWhy,
    staleTime: 5 * 60_000,
    retry: false,
    refetchOnWindowFocus: false,
  });

  const canSave = date.length === 10 && !isPending;

  const nameByCode = new Map(operators.map((o) => [o.code, o.name]));

  // Q.154.B — prefere o nome do barco (op.cliente); o código fica entre parêntesis.
  const boatLabel = op.cliente
    ? `${op.cliente}${op.order_id ? ` (#${op.order_id})` : ''}`
    : op.order_id
      ? `Barco #${op.order_id}`
      : op.id;

  return (
    <Sheet
      open
      onClose={onClose}
      title="Editar operação"
      subtitle={`${boatLabel} · fase atual ${op.phase_name}${op.operator_name ? ` · ${op.operator_name}` : ''}`}
      width={440}
      footer={
        <>
          <DarkButton variant="secondary" size="sm" onClick={onClose}>
            Cancelar
          </DarkButton>
          <DarkButton
            size="sm"
            onClick={() => onSave({ phaseId, operatorId, date })}
            disabled={!canSave}
          >
            {isPending ? 'A guardar…' : 'Guardar'}
          </DarkButton>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <div>
          <Label>Operador</Label>
          <select value={operatorId} onChange={(e) => setOperatorId(e.target.value)} style={fieldStyle}>
            <option value="">— sem operador —</option>
            {operators.map((o) => (
              <option key={o.code} value={o.code}>
                {o.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <Label>Fase</Label>
          <select value={phaseId} onChange={(e) => setPhaseId(e.target.value)} style={fieldStyle}>
            {phases.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <Label>Data</Label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} style={fieldStyle} />
        </div>

        {/* Q.174.F8 — porquê ESTE(S) operador(es)? Fatores reais do decoder. */}
        {op.source !== 'actual' && (
          <div>
            <button
              type="button"
              onClick={() => setShowWhy((v) => !v)}
              className="inline-flex items-center gap-1.5 text-xs font-medium transition hover:opacity-80"
              style={{ color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
              aria-expanded={showWhy}
            >
              <HelpCircle size={13} />
              {showWhy ? 'Esconder explicação' : 'Porquê esta atribuição?'}
            </button>

            {showWhy && (
              <div className="mt-2 flex flex-col gap-1.5">
                {explainQuery.isLoading && (
                  <span className="text-[11px]" style={{ color: 'var(--fg-3)' }}>
                    A calcular os fatores…
                  </span>
                )}
                {explainQuery.isError && (
                  <span className="text-[11px]" style={{ color: 'var(--red)' }}>
                    Não foi possível explicar esta operação (op fora do último
                    commit ou backend indisponível).
                  </span>
                )}
                {explainQuery.data && (
                  <>
                    {explainQuery.data.explain_pt && (
                      <p className="text-[11px] leading-relaxed m-0" style={{ color: 'var(--fg-2)' }}>
                        {explainQuery.data.explain_pt}
                      </p>
                    )}
                    {explainQuery.data.pool_size > 0 && (
                      <>
                        {explainQuery.data.candidates
                          .filter((c) => c.escolhido)
                          .map((c) => (
                            <CandidateRow key={c.worker_id} c={c} name={nameByCode.get(c.worker_id)} />
                          ))}
                        {(explainQuery.data.alternatives ?? []).length > 0 && (
                          <>
                            <span className="text-[10px] uppercase tracking-wide font-semibold mt-1" style={{ color: 'var(--fg-3)' }}>
                              Alternativas no pool ({explainQuery.data.pool_size} aptos)
                            </span>
                            {(explainQuery.data.alternatives ?? []).map((c) => (
                              <CandidateRow key={c.worker_id} c={c} name={nameByCode.get(c.worker_id)} />
                            ))}
                          </>
                        )}
                      </>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        )}

        <p className="text-[10px] leading-relaxed" style={{ color: 'var(--fg-3)' }}>
          Guardar cria um rascunho do plano e valida os axiomas Spelke — precisa de aprovação humana
          (Decisões) para ficar oficial.
        </p>
      </div>
    </Sheet>
  );
}
