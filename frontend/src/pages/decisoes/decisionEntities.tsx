/**
 * decisionEntities — extrai as entidades clicáveis de uma decisão (Q.118.C).
 * ===========================================================================
 *
 * Mapeia o que REALMENTE existe no payload da decisão → lista de entidades
 * clicáveis (abrem a ficha contextual). Sem inventar: modelo/cliente não vêm
 * no payload das operações, por isso não são incluídos.
 *
 *   action_data.work_order_id            → encomenda
 *   sandbox_result.operations[].order_id → encomenda (distinct)
 *   sandbox_result.operations[].phase_id → fase (distinct)
 *   sandbox_result.operations[].workers[]→ operador (distinct, UUID)
 */

import type { ReactNode } from 'react';
import { Clickable, type EntityKind } from '../../components/entitySheets';
import type { DecisionRun } from '../../lib/api';

export interface DecisionEntity {
  kind: EntityKind;
  id: string;
  label: string;
}

interface OpLike {
  order_id?: string | number | null;
  phase_id?: string | null;
  /** Nome legível da fase, quando o payload o traz (evita mostrar o UUID cru). */
  phase_name?: string | null;
  workers?: Array<string | number> | null;
}

/** Lista distinta de entidades clicáveis presentes na decisão. */
export function decisionEntities(decision: DecisionRun): DecisionEntity[] {
  const out: DecisionEntity[] = [];
  const seen = new Set<string>();

  const push = (kind: EntityKind, rawId: unknown, label: string) => {
    const id = String(rawId ?? '').trim();
    if (!id) return;
    const key = `${kind}:${id}`;
    if (seen.has(key)) return;
    seen.add(key);
    out.push({ kind, id, label });
  };

  // Encomenda associada (action_data) — a mais comum.
  const wo = decision.action_data?.work_order_id;
  if (wo != null) push('encomenda', wo, `#${wo}`);

  // Operações do plano proposto (sandbox_result.operations).
  const sb = (decision.sandbox_result ?? {}) as { operations?: OpLike[] };
  const ops = Array.isArray(sb.operations) ? sb.operations : [];
  for (const op of ops) {
    if (op.order_id != null) push('encomenda', op.order_id, `#${op.order_id}`);
    if (op.phase_id) {
      // Label legível: prefere o nome da fase; nunca mostra o UUID cru (Q.123).
      const phaseName = op.phase_name?.trim();
      const label = phaseName && phaseName.length > 0
        ? phaseName
        : `Fase ${String(op.phase_id).slice(0, 8)}`;
      push('fase', op.phase_id, label);
    }
    const workers = Array.isArray(op.workers) ? op.workers : [];
    for (const w of workers) {
      const wid = String(w ?? '').trim();
      if (wid) push('operador', wid, `Operador ${wid.slice(0, 8)}`);
    }
  }

  return out;
}

/** Renderiza as entidades como chips clicáveis (abrem a ficha). */
export function DecisionEntities({
  decision,
  max = 12,
}: {
  decision: DecisionRun;
  max?: number;
}): ReactNode {
  const entities = decisionEntities(decision);
  if (entities.length === 0) return null;
  const shown = entities.slice(0, max);
  const overflow = entities.length - shown.length;

  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5" data-testid="decision-entities">
      {shown.map((e) => (
        <span
          key={`${e.kind}:${e.id}`}
          style={{
            fontSize: 11,
            padding: '2px 8px',
            borderRadius: 99,
            background: 'var(--bg-2)',
            border: '1px solid var(--bd-2)',
          }}
        >
          <Clickable kind={e.kind} id={e.id}>
            {e.label}
          </Clickable>
        </span>
      ))}
      {overflow > 0 ? (
        <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>+{overflow}</span>
      ) : null}
    </div>
  );
}
