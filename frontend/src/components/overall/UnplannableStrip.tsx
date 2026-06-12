/**
 * UnplannableStrip — secção "Não planeável" do plano (Q.174.F5).
 *
 * Decisão do dono (2026-06-12): o plano publica o que é exequível e lista
 * à parte o que NÃO foi planeável — por op/ordem, com o RECURSO em falta e
 * uma sugestão acionável. Nunca silêncio, nunca plano falso (invariante #8).
 *
 * Colapsada por defeito (só o contador); commits antigos (pré-Q.174,
 * `available=false`) não rendem nada — estado-vazio honesto.
 */

import { useState, memo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronRight, Ban } from 'lucide-react';
import { planKeys } from '../../lib/api/keys';
import { cpoCommitsApi } from '../../lib/api';
import type { CpoUnplannableItem } from '../../lib/api';

const STATUS_COLORS: Record<string, string> = {
  blocked_operadores: 'var(--yellow)',
  blocked_molde: 'var(--red)',
  blocked_horizonte: 'var(--fg-2)',
  blocked_precedencia: 'var(--fg-2)',
  blocked_componente: 'var(--yellow)',
  sem_rota: 'var(--red)',
};

function ItemRow({ item }: { item: CpoUnplannableItem }) {
  const color = STATUS_COLORS[item.status] ?? 'var(--fg-2)';
  return (
    <div
      className="flex flex-col gap-0.5 px-2.5 py-1.5 rounded-md text-xs"
      style={{ background: 'var(--bg-4)', border: '1px solid var(--bd-2)' }}
    >
      <div className="flex items-center gap-2">
        <span className="font-semibold" style={{ color }}>
          {item.label_pt ?? item.status}
        </span>
        {item.order_id && (
          <span className="font-mono tabular-nums" style={{ color: 'var(--fg-2)' }}>
            OF {item.order_id}
          </span>
        )}
        {item.phase_id && (
          <span style={{ color: 'var(--fg-3)' }}>fase {item.phase_id}</span>
        )}
      </div>
      {item.suggestion_pt && (
        <span style={{ color: 'var(--fg-3)' }}>{item.suggestion_pt}</span>
      )}
    </div>
  );
}

export const UnplannableStrip = memo(function UnplannableStrip({
  commitSha,
}: {
  commitSha: string;
}) {
  const [expanded, setExpanded] = useState(false);

  const { data } = useQuery({
    queryKey: planKeys.unplannable(commitSha),
    queryFn: () => cpoCommitsApi.unplannable(commitSha),
    staleTime: 60_000,
    retry: false,
    refetchOnWindowFocus: false,
  });

  // Sem dados / commit antigo / plano 100% viável → nada a declarar.
  if (!data?.available || data.unplannable_count === 0) return null;

  return (
    <div
      className="rounded-xl border overflow-hidden flex-shrink-0"
      style={{ background: 'var(--bg-2)', borderColor: 'var(--red-bd)' }}
      data-testid="unplannable-strip"
    >
      <button
        className="flex items-center gap-2 w-full px-3 py-2 text-left transition-colors hover:opacity-80"
        style={{ background: 'var(--bg-3)' }}
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        {expanded ? (
          <ChevronDown size={13} style={{ color: 'var(--fg-3)' }} />
        ) : (
          <ChevronRight size={13} style={{ color: 'var(--fg-3)' }} />
        )}
        <Ban size={13} style={{ color: 'var(--red)' }} />
        <span className="text-xs font-semibold" style={{ color: 'var(--red)' }}>
          Não planeável
        </span>
        <span className="font-mono tabular-nums text-xs" style={{ color: 'var(--fg-1)' }}>
          {data.unplannable_count.toLocaleString('pt-PT')}
        </span>
        <span className="text-[10px]" style={{ color: 'var(--fg-3)' }}>
          {data.unplannable_count === 1
            ? 'operação sem recurso — ver porquê e o que fazer'
            : 'operações sem recurso — ver porquê e o que fazer'}
        </span>
      </button>

      {expanded && (
        <div className="p-2.5 flex flex-col gap-1.5 max-h-64 overflow-y-auto">
          {data.items.map((it, i) => (
            <ItemRow key={`${it.operation_id ?? it.order_id ?? i}`} item={it} />
          ))}
          {data.unplannable_count > data.items.length && (
            <span className="text-[10px] px-1" style={{ color: 'var(--fg-3)' }}>
              A mostrar {data.items.length} de {data.unplannable_count} — o
              detalhe completo vive no commit.
            </span>
          )}
        </div>
      )}
    </div>
  );
});
