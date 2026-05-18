/**
 * ErpIntegrationPanel — Q.44.Z
 *
 * Página de Configurações onde se cola a ligação ao ERP NELO: URL da API
 * Laravel + token, e os interruptores de leitura tempo-real / escrita.
 * Os valores vivem em `core.tenant_configuration` via /v1/erp-integration.
 *
 * O token é write-only: o GET nunca o devolve em claro — só diz se está
 * definido e mostra os últimos 4 caracteres. Deixar o campo do token
 * vazio num "Guardar" preserva o token actual.
 *
 * ZERO MOCKS — dados reais da API, estados de erro/vazio explícitos.
 */

import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plug, RefreshCw, CheckCircle2, XCircle } from 'lucide-react';
import { getApiBase } from '../../lib/api';

const TENANT = '00000000-0000-0000-0000-000000000001';

interface ErpIntegration {
  api_url: string | null;
  token_set: boolean;
  token_hint: string | null;
  realtime_enabled: boolean;
  realtime_interval_minutes: number;
  write_enabled: boolean;
}

interface ConnectionTest {
  sql_server_ok: boolean;
  sql_server_detail: string;
  api_ok: boolean;
  api_detail: string;
}

function headers(): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-Tenant-Id': TENANT,
    'X-User-Id': TENANT,
  };
}

async function fetchConfig(): Promise<ErpIntegration> {
  const resp = await fetch(`${getApiBase()}/v1/erp-integration`, {
    headers: headers(),
  });
  if (!resp.ok) throw new Error(`GET falhou (HTTP ${resp.status})`);
  return resp.json();
}

export function ErpIntegrationPanel() {
  const queryClient = useQueryClient();
  const cfgQuery = useQuery({
    queryKey: ['erp-integration'],
    queryFn: fetchConfig,
    staleTime: 30_000,
    retry: 0,
  });

  // Estado do formulário — alimentado a partir da query.
  const [apiUrl, setApiUrl] = useState('');
  const [apiToken, setApiToken] = useState('');
  const [rtEnabled, setRtEnabled] = useState(false);
  const [rtInterval, setRtInterval] = useState(5);
  const [writeEnabled, setWriteEnabled] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTest | null>(null);

  useEffect(() => {
    const d = cfgQuery.data;
    if (!d) return;
    setApiUrl(d.api_url ?? '');
    setRtEnabled(d.realtime_enabled);
    setRtInterval(d.realtime_interval_minutes);
    setWriteEnabled(d.write_enabled);
  }, [cfgQuery.data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const body: Record<string, unknown> = {
        api_url: apiUrl.trim(),
        realtime_enabled: rtEnabled,
        realtime_interval_minutes: rtInterval,
        write_enabled: writeEnabled,
      };
      // Token só vai no payload se o utilizador escreveu algo — senão
      // preserva-se o que já está guardado (write-only).
      if (apiToken.trim()) body.api_token = apiToken.trim();
      const resp = await fetch(`${getApiBase()}/v1/erp-integration`, {
        method: 'PUT',
        headers: headers(),
        body: JSON.stringify(body),
      });
      if (!resp.ok) throw new Error(`Guardar falhou (HTTP ${resp.status})`);
      return resp.json();
    },
    onSuccess: () => {
      setApiToken('');
      queryClient.invalidateQueries({ queryKey: ['erp-integration'] });
    },
  });

  const testMutation = useMutation({
    mutationFn: async (): Promise<ConnectionTest> => {
      const resp = await fetch(`${getApiBase()}/v1/erp-integration/test`, {
        method: 'POST',
        headers: headers(),
      });
      if (!resp.ok) throw new Error(`Teste falhou (HTTP ${resp.status})`);
      return resp.json();
    },
    onSuccess: (data) => setTestResult(data),
  });

  const cfg = cfgQuery.data;
  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '8px 11px',
    background: 'var(--bg-0)',
    border: '1px solid var(--bd-1)',
    borderRadius: 8,
    fontSize: 13,
    color: 'var(--fg-0)',
  };
  const labelCls = 'text-xs font-medium text-text-dark-secondary mb-1.5 block';

  return (
    <div className="px-4 py-2 space-y-5" style={{ maxWidth: 720 }}>
      {/* Explainer */}
      <div
        style={{
          padding: '14px 18px',
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 12,
          fontSize: 13,
          color: 'var(--fg-1)',
          lineHeight: 1.6,
        }}
      >
        <strong style={{ color: 'var(--fg-0)' }}>Ligação ao ERP NELO.</strong>{' '}
        Cola aqui o endereço da API do ERP e o token. O token é guardado em
        segurança — depois de gravado, nunca mais é mostrado em claro.
      </div>

      {cfgQuery.isLoading ? (
        <div className="py-8 text-center text-xs text-text-dark-tertiary">
          A carregar configuração…
        </div>
      ) : cfgQuery.isError ? (
        <div
          style={{
            padding: '14px 18px',
            background: 'var(--red-bg)',
            border: '1px solid var(--red-bd)',
            borderRadius: 12,
            fontSize: 13,
            color: 'var(--red)',
          }}
        >
          Não foi possível carregar a configuração:{' '}
          {(cfgQuery.error as Error)?.message ?? 'erro desconhecido'}
        </div>
      ) : (
        <div
          style={{
            background: 'var(--bg-1)',
            border: '1px solid var(--bd-1)',
            borderRadius: 12,
            padding: 22,
          }}
        >
          <div className="flex items-center gap-2 mb-4">
            <Plug size={15} className="text-accent-400" />
            <span className="text-sm font-semibold text-text-dark-primary">
              Integração ERP
            </span>
          </div>

          <div className="space-y-4">
            <div>
              <label className={labelCls}>URL da API do ERP</label>
              <input
                type="text"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="https://erp.nelo.eu/api"
                style={inputStyle}
              />
            </div>

            <div>
              <label className={labelCls}>
                Token da API
                {cfg?.token_set ? (
                  <span className="text-text-dark-tertiary font-normal">
                    {' '}— já definido ({cfg.token_hint}). Deixa vazio para
                    manter.
                  </span>
                ) : (
                  <span className="text-amber-400 font-normal"> — ainda não definido</span>
                )}
              </label>
              <input
                type="password"
                value={apiToken}
                onChange={(e) => setApiToken(e.target.value)}
                placeholder={cfg?.token_set ? '•••••••• (manter actual)' : 'colar token'}
                style={inputStyle}
              />
            </div>

            <div className="flex items-center gap-6">
              <label className="flex items-center gap-2 text-xs text-text-dark-secondary cursor-pointer">
                <input
                  type="checkbox"
                  checked={rtEnabled}
                  onChange={(e) => setRtEnabled(e.target.checked)}
                />
                Leitura em tempo-real
              </label>
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-dark-secondary">
                  Intervalo (min)
                </span>
                <input
                  type="number"
                  min={1}
                  max={120}
                  value={rtInterval}
                  onChange={(e) => setRtInterval(Number(e.target.value) || 5)}
                  style={{ ...inputStyle, width: 70 }}
                />
              </div>
            </div>

            <label className="flex items-center gap-2 text-xs text-text-dark-secondary cursor-pointer">
              <input
                type="checkbox"
                checked={writeEnabled}
                onChange={(e) => setWriteEnabled(e.target.checked)}
              />
              Escrita no ERP (requer API do ERP construída pela NELO)
            </label>
          </div>

          {/* Acções */}
          <div className="flex items-center gap-3 mt-6">
            <button
              type="button"
              disabled={saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
              className="px-3.5 py-1.5 rounded-md bg-accent-500 text-white hover:bg-accent-400 text-xs font-medium transition-colors disabled:opacity-50"
            >
              {saveMutation.isPending ? 'A guardar…' : 'Guardar'}
            </button>
            <button
              type="button"
              disabled={testMutation.isPending}
              onClick={() => testMutation.mutate()}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors disabled:opacity-50"
            >
              <RefreshCw size={13} />
              {testMutation.isPending ? 'A testar…' : 'Testar ligação'}
            </button>
            {saveMutation.isSuccess ? (
              <span className="text-xs text-emerald-400">Guardado ✓</span>
            ) : null}
            {saveMutation.isError ? (
              <span className="text-xs text-red-400">
                {(saveMutation.error as Error)?.message}
              </span>
            ) : null}
          </div>

          {/* Resultado do teste */}
          {testResult ? (
            <div
              className="mt-4 space-y-1.5"
              style={{
                padding: '12px 16px',
                background: 'var(--bg-0)',
                border: '1px solid var(--bd-1)',
                borderRadius: 8,
              }}
            >
              <TestLine
                ok={testResult.sql_server_ok}
                label="SQL Server (leitura)"
                detail={testResult.sql_server_detail}
              />
              <TestLine
                ok={testResult.api_ok}
                label="API HTTP do ERP"
                detail={testResult.api_detail}
              />
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

function TestLine({
  ok,
  label,
  detail,
}: {
  ok: boolean;
  label: string;
  detail: string;
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      {ok ? (
        <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
      ) : (
        <XCircle size={14} className="text-red-400 shrink-0" />
      )}
      <span className="text-text-dark-primary font-medium">{label}:</span>
      <span className="text-text-dark-tertiary">{detail}</span>
    </div>
  );
}

export default ErpIntegrationPanel;
