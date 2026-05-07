/**
 * OperadorDetailPage — Plan v4 §10 (Equipa) per-operator profile.
 *
 * Reads in parallel:
 *   - GET /v1/core/employees/:id          (identidade + estado)
 *   - GET /v1/workforce/employees/:id/quality-score   (ML score + override)
 *   - GET /v1/workforce/employees/:id/skill-matrix    (skills × phases)
 *
 * Quality-score override is a write path that triggers the Camada 1
 * detector on the backend (PreferenceRule(workforce_override)). The
 * override form requires a reason ≥10 chars (backend constraint), so
 * we mirror the gate client-side. ZERO MOCKS.
 */

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Award,
  Edit3,
  Loader2,
  Save,
  ServerCrash,
  ShieldCheck,
  Sparkles,
  User,
  X,
} from 'lucide-react';
import {
  employeesApi,
  workforceEmployeesApi,
  type QualityScoreResult,
  type SkillMatrixRow,
} from '../lib/api';
import { DarkPageLayout } from '../layouts';
import {
  DarkBadge,
  DarkButton,
  DarkCard,
  DarkInput,
  DarkTable,
  DarkTableBody,
  DarkTableCell,
  DarkTableHead,
  DarkTableHeader,
  DarkTableRow,
} from '../components/dark';

interface EmployeeFull {
  id: string;
  employee_code: string;
  employee_name: string;
  status: string;
  department?: string | null;
  job_title?: string | null;
  hire_date?: string | null;
  base_monthly_salary?: string | number | null;
  hourly_loaded_rate?: string | number | null;
  burden_rate?: string | number | null;
}

const OVERRIDE_REASON_MIN = 10;

function fmtDate(iso?: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('pt-PT');
  } catch {
    return iso;
  }
}

function fmtMoney(raw: string | number | null | undefined, suffix = ''): string {
  if (raw == null || raw === '') return '—';
  const n = typeof raw === 'string' ? Number(raw) : raw;
  if (!Number.isFinite(n)) return '—';
  return `€${n.toFixed(2)}${suffix}`;
}

function scoreTone(score: number): string {
  if (score >= 8) return 'text-emerald-300';
  if (score >= 6) return 'text-amber-300';
  if (score >= 4) return 'text-orange-300';
  return 'text-rose-300';
}

function QualityScoreCard({
  data,
  employeeId,
}: {
  data: QualityScoreResult;
  employeeId: string;
}) {
  const [editing, setEditing] = useState(false);
  const [score, setScore] = useState<string>(String(data.score?.toFixed?.(2) ?? data.score ?? ''));
  const [reason, setReason] = useState('');
  const queryClient = useQueryClient();

  const overrideMutation = useMutation({
    mutationFn: (payload: { score: number; reason: string }) =>
      workforceEmployeesApi.overrideQualityScore(employeeId, payload),
    onSuccess: () => {
      setEditing(false);
      setReason('');
      queryClient.invalidateQueries({ queryKey: ['operador', employeeId, 'score'] });
    },
  });

  const numericScore = Number(score);
  const validScore =
    Number.isFinite(numericScore) && numericScore >= 1 && numericScore <= 10;
  const validReason = reason.trim().length >= OVERRIDE_REASON_MIN;
  const canSubmit = validScore && validReason && !overrideMutation.isPending;
  const isDefault = data.method === 'default_no_history';

  return (
    <DarkCard className="p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-slate-400">
          <Award className="w-3.5 h-3.5" /> Qualidade (ML)
        </div>
        {!editing ? (
          <DarkButton onClick={() => setEditing(true)} variant="secondary">
            <Edit3 className="w-3.5 h-3.5" /> Sobrepor
          </DarkButton>
        ) : (
          <DarkButton
            onClick={() => {
              setEditing(false);
              setReason('');
              setScore(String(data.score?.toFixed?.(2) ?? data.score ?? ''));
            }}
            variant="secondary"
          >
            <X className="w-3.5 h-3.5" /> Cancelar
          </DarkButton>
        )}
      </div>

      <div className="flex items-baseline gap-3">
        <span className={`text-5xl font-bold ${scoreTone(data.score)}`}>
          {data.score?.toFixed(2) ?? '—'}
        </span>
        <span className="text-sm text-slate-400">/ 10</span>
        {isDefault ? (
          <DarkBadge variant="neutral">Score por defeito</DarkBadge>
        ) : (
          <DarkBadge variant="info">Score ML (Laplace)</DarkBadge>
        )}
      </div>

      <div className="text-xs text-slate-400 flex flex-wrap gap-x-4 gap-y-1">
        <span>
          Defeitos: <span className="font-mono text-slate-200">{data.defects}</span>
        </span>
        <span>
          Operações: <span className="font-mono text-slate-200">{data.operations}</span>
        </span>
        <span>
          Taxa de defeito:{' '}
          <span className="font-mono text-slate-200">
            {(data.defect_rate * 100).toFixed(2)}%
          </span>
        </span>
      </div>

      {editing ? (
        <div className="flex flex-col gap-2 pt-2 border-t border-slate-800">
          <label className="text-[11px] uppercase tracking-wider text-slate-400">
            Novo score (1.0 – 10.0)
          </label>
          <DarkInput
            type="number"
            min={1}
            max={10}
            step={0.1}
            value={score}
            onChange={(e) => setScore(e.target.value)}
            disabled={overrideMutation.isPending}
          />
          <label className="text-[11px] uppercase tracking-wider text-slate-400 mt-2">
            Razão (mín. {OVERRIDE_REASON_MIN} caracteres) — alimenta a aprendizagem
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={overrideMutation.isPending}
            rows={3}
            placeholder="Ex: Operador melhorou após formação adicional em Maio"
            className={`w-full rounded-md border bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500/40 disabled:opacity-60 ${
              reason.length === 0 || validReason
                ? 'border-slate-700/70'
                : 'border-amber-500/60'
            }`}
          />
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-400">
              {validReason
                ? '✓ Razão suficiente'
                : `Faltam ${Math.max(0, OVERRIDE_REASON_MIN - reason.trim().length)} caracteres`}
            </span>
            <DarkButton
              variant="primary"
              disabled={!canSubmit}
              onClick={() =>
                overrideMutation.mutate({
                  score: numericScore,
                  reason: reason.trim(),
                })
              }
            >
              {overrideMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Save className="w-3.5 h-3.5" />
              )}
              Guardar override
            </DarkButton>
          </div>
          {overrideMutation.error ? (
            <div className="text-xs text-rose-300">
              {overrideMutation.error instanceof Error
                ? overrideMutation.error.message
                : String(overrideMutation.error)}
            </div>
          ) : null}
        </div>
      ) : null}
    </DarkCard>
  );
}

function SkillMatrixCard({ rows }: { rows: SkillMatrixRow[] }) {
  if (rows.length === 0) {
    return (
      <DarkCard className="p-6 flex flex-col items-center gap-2 text-slate-400">
        <Sparkles className="w-8 h-8 text-slate-600" />
        <div className="text-sm">Sem skills registadas — operador sem histórico.</div>
      </DarkCard>
    );
  }
  return (
    <DarkCard className="p-0 overflow-hidden">
      <DarkTable>
        <DarkTableHead>
          <DarkTableRow>
            <DarkTableHeader>Fase</DarkTableHeader>
            <DarkTableHeader>Pode fazer?</DarkTableHeader>
            <DarkTableHeader>Nível</DarkTableHeader>
            <DarkTableHeader>Operações</DarkTableHeader>
            <DarkTableHeader>Última utilização</DarkTableHeader>
          </DarkTableRow>
        </DarkTableHead>
        <DarkTableBody>
          {rows.map((r) => (
            <DarkTableRow key={r.phase_id}>
              <DarkTableCell className="text-slate-200">
                {r.phase_name ?? r.phase_id}
              </DarkTableCell>
              <DarkTableCell>
                {r.can_do ? (
                  <DarkBadge variant="success">Sim</DarkBadge>
                ) : (
                  <DarkBadge variant="neutral">Não</DarkBadge>
                )}
              </DarkTableCell>
              <DarkTableCell className="font-mono">
                {r.nivel != null ? r.nivel.toFixed(1) : '—'}
              </DarkTableCell>
              <DarkTableCell className="font-mono">{r.ops_count}</DarkTableCell>
              <DarkTableCell className="text-slate-400">
                {fmtDate(r.last_used_at)}
              </DarkTableCell>
            </DarkTableRow>
          ))}
        </DarkTableBody>
      </DarkTable>
    </DarkCard>
  );
}

export default function OperadorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const employeeId = id ?? '';

  const employeeQuery = useQuery({
    queryKey: ['operador', employeeId],
    queryFn: () => employeesApi.get(employeeId) as Promise<EmployeeFull>,
    enabled: !!employeeId,
    staleTime: 30_000,
  });
  const scoreQuery = useQuery({
    queryKey: ['operador', employeeId, 'score'],
    queryFn: () => workforceEmployeesApi.qualityScore(employeeId),
    enabled: !!employeeId,
    staleTime: 30_000,
  });
  const skillsQuery = useQuery({
    queryKey: ['operador', employeeId, 'skills'],
    queryFn: () => workforceEmployeesApi.skillMatrix(employeeId),
    enabled: !!employeeId,
    staleTime: 30_000,
  });

  if (!employeeId) {
    return (
      <DarkPageLayout title="Operador" icon={<User className="w-6 h-6" />}>
        <DarkCard className="p-6 text-rose-200">
          ID do operador em falta no URL.
        </DarkCard>
      </DarkPageLayout>
    );
  }

  if (employeeQuery.isLoading) {
    return (
      <DarkPageLayout title="Operador" icon={<User className="w-6 h-6" />}>
        <DarkCard className="p-10 flex items-center justify-center gap-2 text-slate-300">
          <Loader2 className="w-5 h-5 animate-spin" /> A carregar...
        </DarkCard>
      </DarkPageLayout>
    );
  }
  if (employeeQuery.error || !employeeQuery.data) {
    return (
      <DarkPageLayout title="Operador" icon={<User className="w-6 h-6" />}>
        <DarkCard className="p-10 flex flex-col items-center gap-3 border-rose-500/30 bg-rose-500/5 text-rose-200">
          <ServerCrash className="w-8 h-8" />
          <div>Operador não encontrado ou backend em falha.</div>
          <Link
            to="/operadores"
            className="text-sky-300 hover:text-sky-200 inline-flex items-center gap-1"
          >
            <ArrowLeft className="w-4 h-4" /> Voltar à lista
          </Link>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  const e = employeeQuery.data;

  return (
    <DarkPageLayout
      title={e.employee_name}
      subtitle={`${e.employee_code} · ${e.department ?? 'sem departamento'} · ${e.job_title ?? 'sem função'}`}
      icon={<User className="w-6 h-6 text-emerald-300" />}
      actions={
        <Link
          to="/operadores"
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-700 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800"
        >
          <ArrowLeft className="w-4 h-4" /> Lista
        </Link>
      }
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <DarkCard className="p-4 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-slate-400">
            <ShieldCheck className="w-3.5 h-3.5" /> Identidade
          </div>
          <div className="flex items-center gap-2">
            <DarkBadge
              variant={
                e.status === 'active'
                  ? 'success'
                  : e.status === 'on_leave'
                  ? 'warning'
                  : 'danger'
              }
            >
              {e.status === 'active'
                ? 'Activo'
                : e.status === 'on_leave'
                ? 'Ausente'
                : e.status}
            </DarkBadge>
          </div>
          <div className="text-sm text-slate-300">
            Admissão: <span className="text-slate-100">{fmtDate(e.hire_date)}</span>
          </div>
          <div className="text-sm text-slate-300">
            Custo/hora:{' '}
            <span className="font-mono text-slate-100">
              {fmtMoney(e.hourly_loaded_rate, '/h')}
            </span>
          </div>
          <div className="text-xs text-slate-500">
            Salário base: {fmtMoney(e.base_monthly_salary)} · Burden:{' '}
            {fmtMoney(e.burden_rate)}
          </div>
        </DarkCard>

        <div className="md:col-span-2">
          {scoreQuery.isLoading ? (
            <DarkCard className="p-6 flex items-center gap-2 text-slate-300">
              <Loader2 className="w-4 h-4 animate-spin" /> A calcular score...
            </DarkCard>
          ) : scoreQuery.error || !scoreQuery.data ? (
            <DarkCard className="p-6 text-rose-200 border-rose-500/30 bg-rose-500/5">
              Não consegui ler o score de qualidade.
            </DarkCard>
          ) : (
            <QualityScoreCard data={scoreQuery.data} employeeId={employeeId} />
          )}
        </div>
      </div>

      <div className="mt-4">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-slate-400 mb-2">
          <Sparkles className="w-3.5 h-3.5" /> Skills × fases
        </div>
        {skillsQuery.isLoading ? (
          <DarkCard className="p-6 flex items-center gap-2 text-slate-300">
            <Loader2 className="w-4 h-4 animate-spin" /> A carregar skills...
          </DarkCard>
        ) : skillsQuery.error ? (
          <DarkCard className="p-6 text-rose-200 border-rose-500/30 bg-rose-500/5">
            Não consegui ler a matriz de skills.
          </DarkCard>
        ) : (
          <SkillMatrixCard rows={skillsQuery.data?.phases ?? []} />
        )}
      </div>
    </DarkPageLayout>
  );
}
