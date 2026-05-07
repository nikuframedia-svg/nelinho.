/**
 * AprendizagemPage — Plan v4 §11 (learning loop) observability dashboard.
 *
 * Three tabs that mirror the three preference-learning layers:
 *   1. Regras    — rule counts by status × type (Camada 1: detector)
 *   2. Pesos     — current weights vs defaults + multiplier deltas
 *                  (Camada 2: fitness retrain)
 *   3. Histórico — DPO pair stats (Camada 3 bootstrap) + last N retrains
 *
 * Read-only. The /admin/regras and /admin/learned-rules pages already
 * own the write paths (propose / approve / suspend rules); this page
 * is the at-a-glance dashboard the gestor opens to see "is the system
 * learning?".
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Brain,
  GitCompareArrows,
  History,
  Loader2,
  RefreshCw,
  ServerCrash,
  Sparkles,
} from 'lucide-react';
import { learningApi } from '../lib/api';
import { DarkPageLayout } from '../layouts';
import { DarkButton, DarkCard } from '../components/dark';

type LearningTab = 'regras' | 'pesos' | 'historico';

const TABS: { key: LearningTab; label: string; icon: React.ReactNode }[] = [
  { key: 'regras', label: 'Regras', icon: <Sparkles className="w-4 h-4" /> },
  { key: 'pesos', label: 'Pesos', icon: <GitCompareArrows className="w-4 h-4" /> },
  { key: 'historico', label: 'Histórico', icon: <History className="w-4 h-4" /> },
];

function fmtPct(n: number, digits = 1): string {
  if (!Number.isFinite(n)) return '—';
  return `${(n * 100).toFixed(digits)}%`;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return 'nunca';
  try {
    const d = new Date(iso);
    return d.toLocaleString('pt-PT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function ErrorState({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  return (
    <DarkCard className="p-8 flex flex-col items-center justify-center gap-3 border-rose-500/30 bg-rose-500/5 text-rose-200">
      <ServerCrash className="w-8 h-8" />
      <div className="text-base font-semibold">Não consegui ler dados.</div>
      <div className="text-sm text-rose-200/80 max-w-lg text-center">
        {error instanceof Error ? error.message : String(error)}
      </div>
      <DarkButton onClick={onRetry} variant="primary">
        Tentar de novo
      </DarkButton>
    </DarkCard>
  );
}

function LoadingState() {
  return (
    <DarkCard className="p-8 flex items-center justify-center gap-2 text-slate-300">
      <Loader2 className="w-5 h-5 animate-spin text-sky-300" /> A carregar...
    </DarkCard>
  );
}

// ─── Tab: Regras ─────────────────────────────────────────────────────

function RegrasTab() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['learning', 'rules'],
    queryFn: () => learningApi.rules(),
    staleTime: 30_000,
  });

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!data) return null;

  const statusEntries = Object.entries(data.by_status).sort((a, b) => b[1] - a[1]);
  const typeEntries = Object.entries(data.by_type).sort((a, b) => b[1] - a[1]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <DarkCard className="p-4 flex flex-col gap-2">
        <span className="text-[11px] uppercase tracking-wider text-slate-400">
          Total de regras
        </span>
        <span className="text-3xl font-bold text-slate-100">{data.total}</span>
        <span className="text-xs text-slate-400">
          Reemitidas: {data.rules_re_emitted_count}
        </span>
        <span className="text-xs text-slate-500">
          Última detecção: {fmtDate(data.last_detector_run_at)}
        </span>
      </DarkCard>

      <DarkCard className="p-4 flex flex-col gap-2">
        <span className="text-[11px] uppercase tracking-wider text-slate-400">
          Por estado
        </span>
        {statusEntries.length === 0 ? (
          <span className="text-sm text-slate-500">Nenhuma.</span>
        ) : (
          <ul className="flex flex-col gap-1.5 list-none p-0 m-0">
            {statusEntries.map(([status, count]) => (
              <li
                key={status}
                className="flex items-center justify-between text-sm"
              >
                <span className="text-slate-300 capitalize">{status}</span>
                <span className="font-mono font-semibold text-slate-100">{count}</span>
              </li>
            ))}
          </ul>
        )}
      </DarkCard>

      <DarkCard className="p-4 flex flex-col gap-2">
        <span className="text-[11px] uppercase tracking-wider text-slate-400">
          Por tipo
        </span>
        {typeEntries.length === 0 ? (
          <span className="text-sm text-slate-500">Nenhuma.</span>
        ) : (
          <ul className="flex flex-col gap-1.5 list-none p-0 m-0">
            {typeEntries.map(([type, count]) => (
              <li
                key={type}
                className="flex items-center justify-between text-sm"
              >
                <span className="text-slate-300">{type}</span>
                <span className="font-mono font-semibold text-slate-100">{count}</span>
              </li>
            ))}
          </ul>
        )}
      </DarkCard>
    </div>
  );
}

// ─── Tab: Pesos ──────────────────────────────────────────────────────

function PesosTab() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['learning', 'weights'],
    queryFn: () => learningApi.weights(),
    staleTime: 30_000,
  });

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!data) return null;

  const keys = Array.from(
    new Set([
      ...Object.keys(data.current_weights),
      ...Object.keys(data.default_weights),
    ]),
  ).sort();

  return (
    <div className="flex flex-col gap-4">
      <DarkCard className="p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-[11px] uppercase tracking-wider text-slate-400">
            Estado actual
          </span>
          <span className="text-base font-semibold text-slate-100">{data.status}</span>
          {data.reason ? (
            <span className="text-xs text-slate-400">{data.reason}</span>
          ) : null}
        </div>
        <div className="flex flex-col gap-1 items-end">
          <span className="text-[11px] uppercase tracking-wider text-slate-400">
            Último retrain
          </span>
          <span className="text-sm text-slate-200">{fmtDate(data.trained_at)}</span>
          <span className="text-xs text-slate-400">
            Pares usados: {data.pairs_used} (mínimo {data.min_pairs_threshold})
          </span>
        </div>
        <div className="flex flex-col gap-1 items-end">
          <span className="text-[11px] uppercase tracking-wider text-slate-400">
            Mistura aprendida
          </span>
          <span className="text-2xl font-bold text-emerald-200">
            {fmtPct(data.blend_learned_pct, 0)}
          </span>
        </div>
      </DarkCard>

      <DarkCard className="p-4">
        <div className="text-[11px] uppercase tracking-wider text-slate-400 mb-2">
          Pesos: actual vs default
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-400 text-[11px] uppercase tracking-wider">
              <th className="py-1.5 pr-4">Termo</th>
              <th className="py-1.5 pr-4 text-right">Default</th>
              <th className="py-1.5 pr-4 text-right">Actual</th>
              <th className="py-1.5 text-right">Δ</th>
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => {
              const cur = data.current_weights[k] ?? 0;
              const def = data.default_weights[k] ?? 0;
              const delta = cur - def;
              const tone =
                Math.abs(delta) < 0.01
                  ? 'text-slate-300'
                  : delta > 0
                  ? 'text-emerald-300'
                  : 'text-rose-300';
              return (
                <tr key={k} className="border-t border-slate-800">
                  <td className="py-1.5 pr-4 text-slate-200">{k}</td>
                  <td className="py-1.5 pr-4 text-right font-mono text-slate-400">
                    {def.toFixed(3)}
                  </td>
                  <td className="py-1.5 pr-4 text-right font-mono text-slate-100">
                    {cur.toFixed(3)}
                  </td>
                  <td className={`py-1.5 text-right font-mono ${tone}`}>
                    {delta >= 0 ? '+' : ''}
                    {delta.toFixed(3)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </DarkCard>
    </div>
  );
}

// ─── Tab: Histórico ──────────────────────────────────────────────────

function HistoricoTab() {
  const pairsQuery = useQuery({
    queryKey: ['learning', 'pairs'],
    queryFn: () => learningApi.pairs({ window_days: 90, min_reason_len: 10 }),
    staleTime: 30_000,
  });
  const historyQuery = useQuery({
    queryKey: ['learning', 'weights', 'history'],
    queryFn: () => learningApi.weightHistory(12),
    staleTime: 30_000,
  });

  if (pairsQuery.isLoading || historyQuery.isLoading) return <LoadingState />;
  if (pairsQuery.error)
    return <ErrorState error={pairsQuery.error} onRetry={pairsQuery.refetch} />;
  if (historyQuery.error)
    return <ErrorState error={historyQuery.error} onRetry={historyQuery.refetch} />;
  const pairs = pairsQuery.data;
  const history = historyQuery.data;
  if (!pairs || !history) return null;

  return (
    <div className="flex flex-col gap-4">
      <DarkCard className="p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] uppercase tracking-wider text-slate-400">
            Pares DPO (últimos 90 dias)
          </span>
          <span className="text-xs text-slate-500">
            min. razão {pairs.min_reason_len} chars
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
          <div>
            <div className="text-2xl font-bold text-slate-100">
              {pairs.total_pairs}
            </div>
            <div className="text-[11px] uppercase tracking-wider text-slate-400">
              Total
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold text-emerald-200">
              {pairs.eligible_for_dpo}
            </div>
            <div className="text-[11px] uppercase tracking-wider text-slate-400">
              Elegíveis DPO
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-200">
              {pairs.last_30d.pairs}
            </div>
            <div className="text-[11px] uppercase tracking-wider text-slate-400">
              Últimos 30d
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-200">
              {pairs.abl_pairs_today}
            </div>
            <div className="text-[11px] uppercase tracking-wider text-slate-400">
              Hoje (ABL)
            </div>
          </div>
        </div>
      </DarkCard>

      <DarkCard className="p-4">
        <div className="text-[11px] uppercase tracking-wider text-slate-400 mb-2">
          Últimos retrains
        </div>
        {history.entries.length === 0 ? (
          <div className="text-sm text-slate-500 py-3">
            Sem retrains registados ainda.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 text-[11px] uppercase tracking-wider">
                <th className="py-1.5 pr-4">Quando</th>
                <th className="py-1.5 pr-4">Estado</th>
                <th className="py-1.5 pr-4 text-right">Pares</th>
                <th className="py-1.5 pr-4">Avisos</th>
                <th className="py-1.5">Válido a partir de</th>
              </tr>
            </thead>
            <tbody>
              {history.entries.map((e: import('../lib/api').LearningWeightHistoryEntry, idx: number) => (
                <tr
                  key={`${e.trained_at ?? 'na'}-${idx}`}
                  className="border-t border-slate-800"
                >
                  <td className="py-1.5 pr-4 text-slate-200">
                    {fmtDate(e.trained_at)}
                  </td>
                  <td className="py-1.5 pr-4 text-slate-300 capitalize">
                    {e.status ?? '—'}
                  </td>
                  <td className="py-1.5 pr-4 text-right font-mono text-slate-100">
                    {e.pairs_used}
                  </td>
                  <td className="py-1.5 pr-4 text-amber-200">
                    {e.warnings.length === 0 ? '—' : `${e.warnings.length} aviso(s)`}
                  </td>
                  <td className="py-1.5 text-slate-300">{fmtDate(e.valid_from)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </DarkCard>
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────

export default function AprendizagemPage() {
  const [tab, setTab] = useState<LearningTab>('regras');

  return (
    <DarkPageLayout
      title="Aprendizagem"
      subtitle="Como o sistema aprende com as decisões do gestor: regras detectadas, pesos retrainados, histórico de pares DPO."
      icon={<Brain className="w-6 h-6 text-violet-300" />}
      actions={
        <DarkButton
          onClick={() => window.location.reload()}
          variant="secondary"
        >
          <RefreshCw className="w-4 h-4" /> Refrescar tudo
        </DarkButton>
      }
    >
      <div className="flex flex-col gap-4">
        <DarkCard className="p-1.5 flex items-center gap-1 w-fit">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm ${
                tab === t.key
                  ? 'bg-violet-500/20 text-violet-100 border border-violet-500/40'
                  : 'text-slate-300 hover:bg-slate-800 border border-transparent'
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </DarkCard>

        {tab === 'regras' ? <RegrasTab /> : null}
        {tab === 'pesos' ? <PesosTab /> : null}
        {tab === 'historico' ? <HistoricoTab /> : null}
      </div>
    </DarkPageLayout>
  );
}
