/**
 * SqlAccordion — Q.67.4.F
 * =======================
 *
 * Accordion colapsável que mostra as queries SQL chamadas pelo copiloto via
 * a tool `run_sql`. Pendura por baixo de cada mensagem do copiloto que
 * tenha um `tool_calls` não vazio.
 *
 * Por cada `tool_calls[i]` com `tool_name === 'run_sql'`:
 *   - cabeçalho colapsado: "Dados consultados (N queries)"
 *   - expand: mostra a SQL, linhas devolvidas, tempo de execução,
 *     e tabela inline com as primeiras 20 linhas (com "+X mais" se passar).
 *
 * Sem `react-syntax-highlighter` no `package.json` — apresenta a SQL num
 * `<code>` com classes Tailwind monoespaçadas. Graceful: este sub-sprint
 * não adiciona dependências.
 *
 * ZERO MOCKS: o componente só renderiza o que recebe via props.
 */

import { useState } from 'react';
import { ChevronDown, ChevronRight, Database } from 'lucide-react';
import { DarkBadge } from '../dark';

/**
 * Shape do `tool_calls[i]` devolvido pelo copiloto. Mantido local porque
 * `lib/copilot-types.ts` é off-limits neste sub-sprint (TOUCH MAP) — o tipo
 * canónico passa para lá quando a consolidação backend chegar.
 */
export interface ToolCallRunSqlResult {
  sql?: string;
  rows?: Array<Record<string, unknown>>;
  rows_returned?: number;
  elapsed_ms?: number;
}

export interface ToolCall {
  tool_name: string;
  args?: Record<string, unknown>;
  result?: ToolCallRunSqlResult | Record<string, unknown> | null;
}

export interface SqlAccordionProps {
  toolCalls: ToolCall[];
}

/** Máximo de linhas mostradas inline antes de cortar com "+X mais". */
const MAX_ROWS_INLINE = 20;

function isRunSqlResult(
  result: ToolCall['result'],
): result is ToolCallRunSqlResult {
  return !!result && typeof result === 'object';
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function RowsTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  // Colunas — união das chaves da 1ª linha (suficiente para o caso real:
  // o backend devolve linhas homogéneas). Mais robusto que assumir só `rows[0]`
  // se aparecer um null no meio.
  const columns = Array.from(
    new Set(rows.flatMap((r) => Object.keys(r ?? {}))),
  );

  if (columns.length === 0) {
    return (
      <p className="text-xs text-fg-3 italic">
        Resultado sem colunas (ex.: <code>SELECT 1</code> sem alias).
      </p>
    );
  }

  const visibleRows = rows.slice(0, MAX_ROWS_INLINE);
  const overflow = rows.length - visibleRows.length;

  return (
    <div className="overflow-x-auto rounded-md border border-bd-1">
      <table className="min-w-full text-xs" style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr className="bg-bg-3">
            {columns.map((col) => (
              <th
                key={col}
                className="text-left font-medium text-fg-2 px-2.5 py-1.5 border-b border-bd-1"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row, i) => (
            <tr
              key={i}
              className={i % 2 === 0 ? 'bg-bg-1' : 'bg-bg-2'}
            >
              {columns.map((col) => (
                <td
                  key={col}
                  className="px-2.5 py-1.5 text-fg-1 font-mono border-b border-bd-1"
                  style={{ fontSize: 11 }}
                >
                  {formatCell(row?.[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {overflow > 0 && (
        <div
          className="text-xs text-fg-3 px-2.5 py-1.5 bg-bg-2 border-t border-bd-1"
          data-testid="sql-rows-overflow"
        >
          + {overflow} {overflow === 1 ? 'linha' : 'linhas'} não mostradas
        </div>
      )}
    </div>
  );
}

function SqlCallBlock({ call, index }: { call: ToolCall; index: number }) {
  const result = isRunSqlResult(call.result) ? call.result : {};
  const sql =
    (typeof result.sql === 'string' && result.sql) ||
    (typeof call.args?.query === 'string' ? (call.args.query as string) : '');
  const rows = Array.isArray(result.rows) ? result.rows : [];
  const rowsReturned =
    typeof result.rows_returned === 'number' ? result.rows_returned : rows.length;
  const elapsedMs =
    typeof result.elapsed_ms === 'number' ? result.elapsed_ms : null;

  return (
    <div className="rounded-md border border-bd-1 bg-bg-2 p-3 flex flex-col gap-2">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[10px] text-fg-3 font-mono">#{index + 1}</span>
        <DarkBadge variant="neutral" size="sm">
          {rowsReturned} {rowsReturned === 1 ? 'linha' : 'linhas'}
        </DarkBadge>
        {elapsedMs !== null && (
          <DarkBadge variant="info" size="sm">
            {elapsedMs.toFixed(1)} ms
          </DarkBadge>
        )}
      </div>

      {sql ? (
        <pre
          className="rounded-md bg-bg-3 border border-bd-1 p-2.5 overflow-x-auto"
          style={{ fontSize: 11, lineHeight: 1.5 }}
        >
          <code className="font-mono text-fg-1 whitespace-pre">{sql}</code>
        </pre>
      ) : (
        <p className="text-xs text-fg-3 italic">SQL não disponível.</p>
      )}

      {rows.length > 0 && <RowsTable rows={rows} />}
    </div>
  );
}

export function SqlAccordion({ toolCalls }: SqlAccordionProps) {
  const sqlCalls = toolCalls.filter((c) => c.tool_name === 'run_sql');
  const [open, setOpen] = useState(false);

  if (sqlCalls.length === 0) return null;

  return (
    <div className="mt-2 rounded-md border border-bd-1 bg-bg-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-bg-2 transition-colors rounded-md"
      >
        {open ? (
          <ChevronDown size={12} className="text-fg-3 shrink-0" />
        ) : (
          <ChevronRight size={12} className="text-fg-3 shrink-0" />
        )}
        <Database size={12} className="text-fg-3 shrink-0" />
        <span className="text-xs text-fg-1 font-medium">
          Dados consultados ({sqlCalls.length}{' '}
          {sqlCalls.length === 1 ? 'query' : 'queries'})
        </span>
      </button>

      {open && (
        <div className="flex flex-col gap-2 px-3 pb-3">
          {sqlCalls.map((call, i) => (
            <SqlCallBlock key={i} call={call} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
