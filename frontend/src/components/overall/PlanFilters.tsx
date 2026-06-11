/**
 * PlanFilters — barra colapsável de 12 filtros estruturados do Gantt (Q.173.AF).
 *
 * Preserva o filtro de texto existente (integrado aqui).
 * Todos os filtros reflectem-se em searchParams (?f_modelo=…&f_setor=…).
 *
 * "Pessoa de expedição" NÃO existe — sem fonte no ERP (nenhuma tabela
 * factory_raw regista o responsável pela entrega por ordem).
 */

import { memo, useState, useCallback, type ReactNode } from 'react';
import { Filter, X, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';
import type { FiltersContextOut } from '../../lib/api/planApi';
import type { PhaseCatalogItem } from '../../lib/api';
import type { PlanFilterState } from './planFilterLogic';
import { countActiveFilters, FILTER_DEFAULTS } from './planFilterLogic';

// ─── Props ────────────────────────────────────────────────────────────────────

interface PlanFiltersProps {
  filters: PlanFilterState;
  onChange: (f: PlanFilterState) => void;
  ctx: FiltersContextOut | null | undefined;
  phaseCatalog?: PhaseCatalogItem[];
  /** Operadores activos para o multi-select (employee_code, employee_name). */
  operators?: { code: string; name: string }[];
  /** Resultado após filtros: para o contador "N ops · M barcos". */
  opCount: number;
  boatCount: number;
}

// ─── Multi-select colapsável ─────────────────────────────────────────────────

function MultiSelect({
  label,
  options,
  selected,
  onToggle,
}: {
  label: string;
  options: { value: string; label: string }[];
  selected: string[];
  onToggle: (value: string) => void;
}): ReactNode {
  const [open, setOpen] = useState(false);
  const nSel = selected.length;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs transition"
        style={
          nSel > 0
            ? { background: 'var(--accent)', color: '#fff' }
            : { background: 'var(--bg-4)', border: '1px solid var(--bd-2)', color: 'var(--fg-2)' }
        }
      >
        {label}
        {nSel > 0 && (
          <span className="font-mono tabular-nums text-[10px] opacity-90">({nSel})</span>
        )}
        {open ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
      </button>
      {open && (
        <div
          className="absolute top-full left-0 mt-1 z-30 rounded-lg p-2 flex flex-col gap-0.5 min-w-[180px] max-h-60 overflow-y-auto shadow-xl"
          style={{ background: 'var(--bg-2)', border: '1px solid var(--bd-2)' }}
        >
          {options.length === 0 ? (
            <span className="text-xs px-2 py-1" style={{ color: 'var(--fg-3)' }}>
              Sem opções
            </span>
          ) : (
            options.map((opt) => (
              <label
                key={opt.value}
                className="flex items-center gap-2 px-2 py-1 rounded cursor-pointer hover:bg-[color:var(--bg-3)] text-xs"
                style={{ color: 'var(--fg-1)' }}
              >
                <input
                  type="checkbox"
                  checked={selected.includes(opt.value)}
                  onChange={() => onToggle(opt.value)}
                  className="w-3 h-3 accent-[color:var(--accent)]"
                />
                {opt.label}
              </label>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ─── Componente principal ─────────────────────────────────────────────────────

export const PlanFilters = memo(function PlanFilters({
  filters,
  onChange,
  ctx,
  phaseCatalog,
  operators,
  opCount,
  boatCount,
}: PlanFiltersProps): ReactNode {
  const [expanded, setExpanded] = useState(false);
  const nActive = countActiveFilters(filters);

  const set = useCallback(
    <K extends keyof PlanFilterState>(key: K, value: PlanFilterState[K]) => {
      onChange({ ...filters, [key]: value });
    },
    [filters, onChange],
  );

  const toggleMulti = useCallback(
    (key: 'modelos' | 'fases' | 'operadores' | 'setores' | 'gamas', value: string) => {
      const cur = filters[key] as string[];
      const next = cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value];
      onChange({ ...filters, [key]: next });
    },
    [filters, onChange],
  );

  // ── Opções derivadas do contexto ─────────────────────────────────────────

  const modeloOptions: { value: string; label: string }[] = Object.entries(
    ctx?.product_names ?? {},
  ).map(([code, name]) => ({ value: code, label: `${name} (${code})` }));

  const faseOptions: { value: string; label: string }[] = phaseCatalog
    ? phaseCatalog.map((p) => ({ value: p.phase_id, label: p.phase_name }))
    : [];

  const operadorOptions: { value: string; label: string }[] = (operators ?? []).map((e) => ({
    value: e.code,
    label: e.name,
  }));

  const setorOptions: { value: string; label: string }[] = Array.from(
    new Set(Object.values(ctx?.phase_sectors ?? {})),
  )
    .sort()
    .map((s) => ({ value: s, label: s }));

  const gamaOptions: { value: string; label: string }[] = Array.from(
    new Set(Object.values(ctx?.product_gamas ?? {})),
  )
    .sort()
    .map((g) => ({ value: g, label: g }));

  const nMaterialRisco = ctx?.orders_material_risk.length ?? 0;
  const hasCtx = !!ctx;

  return (
    <div
      className="flex flex-col gap-2 rounded-lg px-3 py-2 flex-shrink-0"
      style={{ background: 'var(--bg-2)', border: '1px solid var(--bd-2)' }}
    >
      {/* Barra superior: toggles rápidos + texto + contador */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Botão Filtros (expande/colapsa o painel completo) */}
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition"
          style={
            nActive > 0
              ? { background: 'var(--accent)', color: '#fff' }
              : { background: 'var(--bg-4)', border: '1px solid var(--bd-2)', color: 'var(--fg-2)' }
          }
          title={expanded ? 'Recolher filtros' : 'Expandir filtros'}
        >
          <Filter size={12} />
          Filtros
          {nActive > 0 && (
            <span className="font-mono tabular-nums text-[10px]">{nActive}</span>
          )}
          {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
        </button>

        {/* Chips de filtros activos */}
        {filters.modelos.length > 0 && (
          <Chip label={`Modelo (${filters.modelos.length})`} onRemove={() => set('modelos', [])} />
        )}
        {filters.fases.length > 0 && (
          <Chip label={`Fase (${filters.fases.length})`} onRemove={() => set('fases', [])} />
        )}
        {filters.operadores.length > 0 && (
          <Chip label={`Operador (${filters.operadores.length})`} onRemove={() => set('operadores', [])} />
        )}
        {filters.setores.length > 0 && (
          <Chip label={`Setor (${filters.setores.length})`} onRemove={() => set('setores', [])} />
        )}
        {(filters.expedicaoFrom || filters.expedicaoTo || filters.expedicaoSemPromessa) && (
          <Chip label="Expedição" onRemove={() => onChange({ ...filters, expedicaoFrom: '', expedicaoTo: '', expedicaoSemPromessa: false })} />
        )}
        {filters.gamas.length > 0 && (
          <Chip label={`Gama (${filters.gamas.length})`} onRemove={() => set('gamas', [])} />
        )}
        {filters.materialRisco && (
          <Chip label="Mat. em risco" onRemove={() => set('materialRisco', false)} />
        )}
        {filters.reparacoes && (
          <Chip
            label={filters.reparacoes === 'so' ? 'Só reparações' : 'Excluir reparações'}
            onRemove={() => set('reparacoes', '')}
          />
        )}
        {filters.prioridade && (
          <Chip label="Com prioridade" onRemove={() => set('prioridade', false)} />
        )}
        {filters.estado !== 'todos' && (
          <Chip label={`Estado: ${filters.estado}`} onRemove={() => set('estado', 'todos')} />
        )}

        {/* Texto-livre (sempre visível) */}
        <input
          type="search"
          value={filters.text}
          onChange={(e) => set('text', e.target.value)}
          placeholder="Barco / operador / fase…"
          className="ml-auto text-xs px-2.5 py-1 rounded-md placeholder:text-slate-500 text-slate-900"
          style={{
            background: 'white',
            border: '1px solid var(--bd-2)',
            minWidth: 200,
            outline: 'none',
          }}
        />

        {/* Contador de resultados */}
        <span className="text-[10px] whitespace-nowrap" style={{ color: 'var(--fg-3)' }}>
          <span className="font-mono tabular-nums" style={{ color: 'var(--fg-2)' }}>{opCount}</span>
          {' '}ops ·{' '}
          <span className="font-mono tabular-nums" style={{ color: 'var(--fg-2)' }}>{boatCount}</span>
          {' '}barcos
        </span>

        {/* Limpar tudo */}
        {nActive > 0 && (
          <button
            type="button"
            onClick={() => onChange({ ...FILTER_DEFAULTS, text: filters.text })}
            className="text-xs px-2 py-0.5 rounded-full transition-colors"
            style={{ color: 'var(--fg-3)', background: 'var(--bg-4)', border: '1px solid var(--bd-2)' }}
          >
            Limpar ✕
          </button>
        )}
      </div>

      {/* Painel expandido */}
      {expanded && (
        <div className="flex flex-wrap gap-2 pt-1 border-t" style={{ borderColor: 'var(--bd-1)' }}>
          {/* 2 — Modelo */}
          <MultiSelect
            label="Modelo"
            options={modeloOptions}
            selected={filters.modelos}
            onToggle={(v) => toggleMulti('modelos', v)}
          />

          {/* 3 — Fase */}
          <MultiSelect
            label="Fase"
            options={faseOptions}
            selected={filters.fases}
            onToggle={(v) => toggleMulti('fases', v)}
          />

          {/* 4 — Operador */}
          <MultiSelect
            label="Operador"
            options={operadorOptions}
            selected={filters.operadores}
            onToggle={(v) => toggleMulti('operadores', v)}
          />

          {/* 5 — Setor */}
          <MultiSelect
            label="Setor"
            options={setorOptions}
            selected={filters.setores}
            onToggle={(v) => toggleMulti('setores', v)}
          />

          {/* 6 — Expedição */}
          <div
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md"
            style={{ background: 'var(--bg-4)', border: '1px solid var(--bd-2)' }}
          >
            <span className="text-xs" style={{ color: 'var(--fg-3)' }}>Expedição</span>
            <input
              type="date"
              value={filters.expedicaoFrom}
              onChange={(e) => set('expedicaoFrom', e.target.value)}
              className="text-xs px-1 py-0.5 rounded text-slate-900"
              style={{ background: 'white', border: '1px solid var(--bd-2)' }}
              title="Promessa a partir de"
            />
            <span className="text-xs" style={{ color: 'var(--fg-3)' }}>–</span>
            <input
              type="date"
              value={filters.expedicaoTo}
              onChange={(e) => set('expedicaoTo', e.target.value)}
              className="text-xs px-1 py-0.5 rounded text-slate-900"
              style={{ background: 'white', border: '1px solid var(--bd-2)' }}
              title="Promessa até"
            />
            <label className="flex items-center gap-1 text-xs cursor-pointer" style={{ color: 'var(--fg-2)' }}>
              <input
                type="checkbox"
                checked={filters.expedicaoSemPromessa}
                onChange={(e) => set('expedicaoSemPromessa', e.target.checked)}
                className="w-3 h-3"
              />
              Sem promessa
            </label>
          </div>

          {/* 7 — Gama */}
          <MultiSelect
            label="Gama"
            options={gamaOptions}
            selected={filters.gamas}
            onToggle={(v) => toggleMulti('gamas', v)}
          />

          {/* 8 — Materiais em risco */}
          <button
            type="button"
            onClick={() => set('materialRisco', !filters.materialRisco)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition"
            style={
              filters.materialRisco
                ? { background: 'var(--red-bg)', border: '1px solid var(--red-bd)', color: 'var(--red)' }
                : { background: 'var(--bg-4)', border: '1px solid var(--bd-2)', color: 'var(--fg-2)' }
            }
            title={
              !hasCtx
                ? 'A carregar contexto…'
                : ctx.material_risk_stale
                ? 'Cache TTL — pode estar desatualizado'
                : undefined
            }
          >
            {ctx?.material_risk_stale && <AlertTriangle size={11} />}
            Materiais em risco
            {hasCtx && (
              <span className="font-mono tabular-nums text-[10px]">
                ({nMaterialRisco}{ctx.material_risk_stale ? ' cache' : ''})
              </span>
            )}
          </button>

          {/* 9 — Reparações */}
          <div className="flex items-center gap-1">
            {(['', 'so', 'excluir'] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => set('reparacoes', v)}
                className="px-2.5 py-1 rounded-md text-xs transition"
                style={
                  filters.reparacoes === v
                    ? { background: 'var(--accent)', color: '#fff' }
                    : { background: 'var(--bg-4)', border: '1px solid var(--bd-2)', color: 'var(--fg-2)' }
                }
              >
                {v === '' ? 'Todos' : v === 'so' ? 'Só reparações' : 'Excluir reparações'}
              </button>
            ))}
          </div>

          {/* 10 — Prioridade */}
          <button
            type="button"
            onClick={() => set('prioridade', !filters.prioridade)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition"
            style={
              filters.prioridade
                ? { background: 'var(--accent)', color: '#fff' }
                : { background: 'var(--bg-4)', border: '1px solid var(--bd-2)', color: 'var(--fg-2)' }
            }
            title="Ordens com boost de prioridade"
          >
            ⚡ Com prioridade
          </button>

          {/* 12 — Estado */}
          <div className="flex items-center gap-1">
            {(
              [
                ['todos', 'Todos'],
                ['realizado', 'Realizado'],
                ['planeado', 'Planeado'],
                ['atrasado', 'Atrasado'],
                ['risco_material', 'Risco material'],
              ] as [PlanFilterState['estado'], string][]
            ).map(([v, lbl]) => (
              <button
                key={v}
                type="button"
                onClick={() => set('estado', v)}
                className="px-2.5 py-1 rounded-md text-xs transition"
                style={
                  filters.estado === v
                    ? { background: 'var(--accent)', color: '#fff' }
                    : { background: 'var(--bg-4)', border: '1px solid var(--bd-2)', color: 'var(--fg-2)' }
                }
              >
                {lbl}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});

// ─── Chip de filtro activo ────────────────────────────────────────────────────

function Chip({ label, onRemove }: { label: string; onRemove: () => void }): ReactNode {
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
      style={{ background: 'var(--accent-bg)', border: '1px solid var(--accent-bd)', color: 'var(--accent)' }}
    >
      {label}
      <button type="button" onClick={onRemove} aria-label={`Remover filtro ${label}`}>
        <X size={9} />
      </button>
    </span>
  );
}
