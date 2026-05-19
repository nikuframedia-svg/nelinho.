// QualidadePage · tab RetrabalhoTab (Q.60.Q). ZERO MOCKS — liga a endpoints reais.
import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Repeat } from 'lucide-react';
import { EmptyState } from '../../../components/dark';
import { Card, SectionHeader } from '../../../components/qualidade/QualidadeBits';
import { employeesApi, qualityReworkApi, type ReworkCreatePayload } from '../../../lib/api';
import { useReworkList, LoadingLine, REWORK_ERROR_CODES, ROOT_CAUSE_CATEGORIES, FIELD_CLASS, FIELD_STYLE } from '../qualidadeShared';

export function RetrabalhoTab() {
  const queryClient = useQueryClient();
  const reworkQuery = useReworkList();
  const rework = reworkQuery.data ?? [];

  const [ofId, setOfId] = useState('');
  const [errorCode, setErrorCode] = useState('');
  const [phaseCauser, setPhaseCauser] = useState('');
  const [rootCause, setRootCause] = useState('');
  const [costEur, setCostEur] = useState('');
  const [description, setDescription] = useState('');
  const [causerEmployeeId, setCauserEmployeeId] = useState('');
  const [saved, setSaved] = useState(false);

  const employeesQuery = useQuery({
    queryKey: ['qualidade', 'rework-employees'],
    queryFn: () => employeesApi.list({ limit: 200 }),
    staleTime: 5 * 60_000,
    retry: 0,
  });
  const employees: { id: string; label: string }[] = useMemo(() => {
    const raw =
      (employeesQuery.data as { data?: unknown } | undefined)?.data ??
      employeesQuery.data;
    if (!Array.isArray(raw)) return [];
    return raw
      .map((e: Record<string, unknown>) => {
        const id = e.id ?? e.employee_id;
        if (!id) return null;
        const name =
          [e.first_name, e.last_name].filter(Boolean).join(' ') ||
          (e.full_name as string) ||
          (e.name as string) ||
          String(id).slice(0, 8);
        return { id: String(id), label: String(name) };
      })
      .filter((x): x is { id: string; label: string } => x !== null);
  }, [employeesQuery.data]);

  const mutation = useMutation({
    mutationFn: (payload: ReworkCreatePayload) =>
      qualityReworkApi.create(payload),
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 3_000);
      setOfId('');
      setErrorCode('');
      setPhaseCauser('');
      setRootCause('');
      setCostEur('');
      setDescription('');
      setCauserEmployeeId('');
      queryClient.invalidateQueries({ queryKey: ['qualidade', 'rework'] });
      queryClient.invalidateQueries({
        queryKey: ['qualidade', 'dashboard-phase'],
      });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ofId.trim() || !errorCode) return;
    const cost = Number(costEur);
    mutation.mutate({
      of_id: ofId.trim(),
      error_code: errorCode,
      detected_at: new Date().toISOString(),
      phase_id_causer: phaseCauser.trim() || undefined,
      root_cause_category: rootCause || undefined,
      error_description: description.trim() || undefined,
      causer_employee_id: causerEmployeeId || undefined,
      cost_estimate_eur:
        costEur.trim() !== '' && Number.isFinite(cost) ? cost : undefined,
    });
  }

  const disabled = !ofId.trim() || !errorCode || mutation.isPending;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Card padding={18}>
        <SectionHeader
          icon={<Repeat size={14} />}
          title="Registar novo retrabalho"
          subtitle="POST /v1/quality/rework · QA01"
        />
        {saved ? (
          <div
            style={{
              padding: '8px 12px',
              marginBottom: 12,
              background: 'var(--green-bg)',
              border: '1px solid var(--green-bd)',
              borderRadius: 'var(--r-sm)',
              color: 'var(--green)',
              fontSize: 12,
            }}
          >
            Retrabalho registado com sucesso.
          </div>
        ) : null}
        {mutation.isError ? (
          <div
            style={{
              padding: '8px 12px',
              marginBottom: 12,
              background: 'var(--red-bg)',
              border: '1px solid var(--red-bd)',
              borderRadius: 'var(--r-sm)',
              color: 'var(--red)',
              fontSize: 12,
            }}
          >
            Não foi possível registar o retrabalho. Tenta de novo.
          </div>
        ) : null}
        <form
          onSubmit={handleSubmit}
          style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 12,
            }}
          >
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
                Ordem (OF) *
              </span>
              <input
                type="text"
                value={ofId}
                onChange={(e) => setOfId(e.target.value.toUpperCase())}
                placeholder="OF-12345"
                className={`${FIELD_CLASS}`}
                style={FIELD_STYLE}
                required
              />
            </label>
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
                Tipo de defeito *
              </span>
              <select
                value={errorCode}
                onChange={(e) => setErrorCode(e.target.value)}
                className={`${FIELD_CLASS}`}
                style={FIELD_STYLE}
                required
              >
                <option value="">Escolher…</option>
                {REWORK_ERROR_CODES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
                Fase onde ocorreu
              </span>
              <input
                type="text"
                value={phaseCauser}
                onChange={(e) => setPhaseCauser(e.target.value)}
                placeholder="Ex: Laminagem"
                className={`${FIELD_CLASS}`}
                style={FIELD_STYLE}
              />
            </label>
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 12,
            }}
          >
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
                Causa-raiz
              </span>
              <select
                value={rootCause}
                onChange={(e) => setRootCause(e.target.value)}
                className={`${FIELD_CLASS}`}
                style={FIELD_STYLE}
              >
                <option value="">Escolher…</option>
                {ROOT_CAUSE_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
                Operador responsável
              </span>
              <select
                value={causerEmployeeId}
                onChange={(e) => setCauserEmployeeId(e.target.value)}
                className={`${FIELD_CLASS}`}
                style={FIELD_STYLE}
              >
                <option value="">Escolher…</option>
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.label}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
                Custo estimado (€)
              </span>
              <input
                type="number"
                value={costEur}
                onChange={(e) => setCostEur(e.target.value)}
                placeholder="0"
                min="0"
                step="0.01"
                className={`${FIELD_CLASS}`}
                style={FIELD_STYLE}
              />
            </label>
          </div>
          <label style={{ display: 'block' }}>
            <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
              Descrição
            </span>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="O que aconteceu…"
              className={`${FIELD_CLASS}`}
              style={FIELD_STYLE}
            />
          </label>
          <div>
            <button
              type="submit"
              disabled={disabled}
              style={{
                padding: '8px 16px',
                height: 36,
                background: disabled ? 'var(--bg-3)' : 'var(--blue)',
                color: disabled ? 'var(--fg-3)' : '#fff',
                border: 'none',
                borderRadius: 9,
                fontSize: 12.5,
                fontWeight: 500,
                cursor: disabled ? 'not-allowed' : 'pointer',
              }}
            >
              {mutation.isPending ? 'A registar…' : 'Registar retrabalho'}
            </button>
          </div>
        </form>
      </Card>

      <Card padding={18}>
        <SectionHeader
          title="Retrabalho registado"
          subtitle={`${rework.length} registos`}
        />
        {reworkQuery.isLoading ? (
          <LoadingLine />
        ) : rework.length === 0 ? (
          <EmptyState
            size="sm"
            title="Sem retrabalho registado"
            hint="Usa o formulário acima para registar o primeiro retrabalho."
          />
        ) : (
          <>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '110px 1fr 130px 100px 90px',
                padding: '10px 6px',
                borderBottom: '1px solid var(--bd-1)',
                background: 'var(--bg-2)',
                fontSize: 10.5,
                color: 'var(--fg-3)',
                textTransform: 'uppercase',
                letterSpacing: 0.4,
                fontWeight: 600,
              }}
            >
              <div>OF</div>
              <div>Defeito</div>
              <div>Fase</div>
              <div style={{ textAlign: 'right' }}>Custo</div>
              <div style={{ textAlign: 'right' }}>Estado</div>
            </div>
            {rework.slice(0, 30).map((r, i, arr) => (
              <div
                key={r.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '110px 1fr 130px 100px 90px',
                  alignItems: 'center',
                  padding: '10px 6px',
                  borderBottom:
                    i < arr.length - 1 ? '1px solid var(--bd-1)' : 'none',
                  fontSize: 12,
                }}
              >
                <span style={{ color: 'var(--fg-0)', fontWeight: 500 }}>
                  {r.of_id}
                </span>
                <span style={{ color: 'var(--fg-2)' }}>
                  {r.error_description ?? r.error_code}
                </span>
                <span style={{ color: 'var(--fg-2)' }}>
                  {r.phase_id_causer ?? '—'}
                </span>
                <span
                  className="tabular"
                  style={{ color: 'var(--red)', textAlign: 'right' }}
                >
                  {r.cost_estimate_eur
                    ? `−€${Math.round(r.cost_estimate_eur)}`
                    : '—'}
                </span>
                <span
                  style={{
                    justifySelf: 'end',
                    fontSize: 10.5,
                    padding: '1px 7px',
                    borderRadius: 999,
                    color: r.resolved_at ? 'var(--green)' : 'var(--orange)',
                    background: r.resolved_at
                      ? 'var(--green-bg)'
                      : 'var(--orange-bg)',
                    border: `1px solid ${r.resolved_at ? 'var(--green-bd)' : 'var(--orange-bd)'}`,
                  }}
                >
                  {r.resolved_at ? 'Resolvido' : 'Aberto'}
                </span>
              </div>
            ))}
          </>
        )}
      </Card>
    </div>
  );
}

// ─── AderenciaTab ────────────────────────────────────────────────────────
