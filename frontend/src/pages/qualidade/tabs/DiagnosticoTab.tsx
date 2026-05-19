// QualidadePage · tab DiagnosticoTab (Q.60.Q). ZERO MOCKS — liga a endpoints reais.
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Brain } from 'lucide-react';
import { EmptyState } from '../../../components/dark';
import { Card, SectionHeader } from '../../../components/qualidade/QualidadeBits';
import { apiFetch } from '../../../lib/api';
import { useReworkList, LoadingLine, FIELD_CLASS, FIELD_STYLE } from '../qualidadeShared';

export function DiagnosticoTab() {
  // Vazio = deixa o backend escolher o defeito mais frequente da janela.
  // A tab nunca abre partida: sem código escolhido → /root-cause e /impact
  // resolvem o error_code dominante (most_frequent_error_code, Q.54.J).
  const [errorCode, setErrorCode] = useState('');

  // Os códigos de erro reais vêm dos próprios registos de retrabalho do
  // ERP — não de uma lista fixa em inglês (essa divergia dos dados reais).
  const reworkQuery = useReworkList();
  const errorCodes = useMemo(() => {
    const seen = new Map<string, string>();
    for (const r of reworkQuery.data ?? []) {
      if (r.error_code && !seen.has(r.error_code)) {
        seen.set(r.error_code, r.error_description ?? r.error_code);
      }
    }
    return [...seen.entries()].map(([code, label]) => ({ code, label }));
  }, [reworkQuery.data]);

  const qs = errorCode
    ? `?error_code=${encodeURIComponent(errorCode)}`
    : '';
  const rootCauseQuery = useQuery({
    queryKey: ['qualidade', 'root-cause', errorCode],
    queryFn: () =>
      apiFetch<Record<string, unknown>>(`/v1/quality/root-cause${qs}`),
    staleTime: 60_000,
    retry: 0,
  });
  const impactQuery = useQuery({
    queryKey: ['qualidade', 'impact', errorCode],
    queryFn: () =>
      apiFetch<Record<string, unknown>>(`/v1/quality/impact${qs}`),
    staleTime: 60_000,
    retry: 0,
  });

  const rc = rootCauseQuery.data;
  const resolvedCode =
    rc && typeof rc === 'object'
      ? ((rc as { error_code?: string | null }).error_code ?? null)
      : null;
  const dimensions =
    rc && typeof rc === 'object'
      ? (rc as { dimensions?: Record<string, unknown> }).dimensions
      : undefined;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Card padding={18}>
        <SectionHeader
          icon={<Brain size={14} />}
          title="Diagnóstico causal · RootCauseAnalyzer"
          subtitle="Causa comum por dimensão · escolhe o código de erro"
        />
        <label style={{ display: 'block', maxWidth: 360 }}>
          <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
            Código de erro
          </span>
          <select
            value={errorCode}
            onChange={(e) => setErrorCode(e.target.value)}
            className={FIELD_CLASS}
            style={FIELD_STYLE}
          >
            <option value="">
              Mais frequente (automático)
            </option>
            {errorCodes.map((c) => (
              <option key={c.code} value={c.code}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        {!errorCode && resolvedCode ? (
          <div
            style={{
              fontSize: 11,
              color: 'var(--fg-3)',
              marginTop: 8,
            }}
          >
            A mostrar o defeito mais frequente da janela:{' '}
            <span style={{ color: 'var(--fg-1)', fontWeight: 500 }}>
              {resolvedCode}
            </span>
          </div>
        ) : null}
      </Card>

      <Card padding={18}>
        <SectionHeader
          title="Causa-raiz por dimensão"
          subtitle="RootCauseAnalyzer · top causas por fase / molde / operador"
        />
        {rootCauseQuery.isLoading ? (
          <LoadingLine />
        ) : rootCauseQuery.isError ? (
          <EmptyState
            size="sm"
            title="Diagnóstico indisponível"
            hint="O serviço de causa-raiz não respondeu para este código de erro."
          />
        ) : !dimensions || Object.keys(dimensions).length === 0 ? (
          <EmptyState
            size="sm"
            title="Sem dados de causa-raiz"
            hint="Não há retrabalho suficiente com este código de erro para diagnosticar uma causa-raiz."
          />
        ) : (
          <pre
            style={{
              margin: 0,
              fontFamily: 'Geist Mono, ui-monospace, monospace',
              fontSize: 11.5,
              lineHeight: 1.7,
              color: 'var(--fg-1)',
              background: 'var(--bg-2)',
              borderRadius: 'var(--r-sm)',
              padding: 12,
              overflowX: 'auto',
            }}
          >
            {JSON.stringify(dimensions, null, 2)}
          </pre>
        )}
      </Card>

      <Card padding={18}>
        <SectionHeader
          title="Impacto do erro"
          subtitle="ImpactService · custo e horas perdidas"
        />
        {impactQuery.isLoading ? (
          <LoadingLine />
        ) : impactQuery.isError || !impactQuery.data ? (
          <EmptyState
            size="sm"
            title="Sem dados de impacto"
            hint="Não há registos com este código de erro para calcular o impacto."
          />
        ) : (
          <pre
            style={{
              margin: 0,
              fontFamily: 'Geist Mono, ui-monospace, monospace',
              fontSize: 11.5,
              lineHeight: 1.7,
              color: 'var(--fg-1)',
              background: 'var(--bg-2)',
              borderRadius: 'var(--r-sm)',
              padding: 12,
              overflowX: 'auto',
            }}
          >
            {JSON.stringify(impactQuery.data, null, 2)}
          </pre>
        )}
      </Card>
    </div>
  );
}

// ─── OeeTab ──────────────────────────────────────────────────────────────
