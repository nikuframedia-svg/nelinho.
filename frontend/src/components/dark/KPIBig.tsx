/**
 * KPIBig — KPI grande com número display, contexto, meta, tendência.
 *
 * Port fiel do atom `KPIBig` do design NELO.html (atoms.jsx). Número
 * grande animado (count-up), prefixo opcional (€), unidade, linha de
 * contexto, meta + variação % e sparkline opcional. Distinto do
 * `KPICard` legacy — geometria e tokens batem certo com o protótipo.
 *
 * NUNCA mostrar percentagem sem contexto: o `context` é obrigatório
 * para valores ambíguos (regra do projeto). Dados sempre por props.
 *
 * Sprint Q.52.B.
 */

import type { ReactNode } from 'react';
import { ArrowUp, ArrowDown } from 'lucide-react';
import { Sparkline } from './Sparkline';
import { useCountUp } from './useCountUp';

export type KPIBigStatus =
  | 'gray'
  | 'green'
  | 'yellow'
  | 'orange'
  | 'red'
  | 'blue'
  | 'accent';

export interface KPIBigProps {
  /** Etiqueta curta em maiúsculas (ex: "Throughput hoje"). */
  label: string;
  /** Valor numérico (anima) ou string já formatada. */
  value: number | string;
  /** Unidade fixa (ex: "barcos", "%", "h"). */
  unit?: string;
  /** Prefixo (ex: "€"). */
  prefix?: string;
  /** Linha de contexto curta — obrigatória para % ambíguas. */
  context?: string;
  /** Meta mostrada como "Meta <target>". */
  target?: number | string;
  /** Variação % vs período anterior (+/-). */
  trend?: number;
  /** Tom do sparkline / acento. */
  status?: KPIBigStatus;
  /** Sparkline opcional — N pontos de tendência (da API). */
  sparkline?: number[];
  /** Acento na barra lateral esquerda. */
  accent?: KPIBigStatus;
  /** Formatador do número (default pt-PT). */
  format?: (n: number) => string;
}

const DEFAULT_FORMAT = (n: number): string => n.toLocaleString('pt-PT');

export function KPIBig({
  label,
  value,
  unit,
  prefix,
  context,
  target,
  trend,
  status = 'gray',
  sparkline,
  accent,
  format = DEFAULT_FORMAT,
}: KPIBigProps): ReactNode {
  const numeric = typeof value === 'number';
  const animated = useCountUp(numeric ? value : 0);
  const display = numeric ? format(Math.round(animated)) : value;

  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        padding: 18,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {accent ? (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            bottom: 0,
            width: 2,
            background: `var(--${accent})`,
            opacity: 0.5,
          }}
        />
      ) : null}

      <div
        style={{
          fontSize: 10.5,
          color: 'var(--fg-3)',
          fontWeight: 500,
          letterSpacing: 0.3,
          textTransform: 'uppercase',
        }}
      >
        {label}
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: 4,
          marginTop: 10,
        }}
      >
        {prefix ? (
          <span
            className="display"
            style={{ fontSize: 18, color: 'var(--fg-2)', fontWeight: 400 }}
          >
            {prefix}
          </span>
        ) : null}
        <span
          className="display tabular"
          style={{
            fontSize: 30,
            color: 'var(--fg-0)',
            lineHeight: 1,
            fontWeight: 500,
            letterSpacing: '-0.025em',
          }}
        >
          {display}
        </span>
        {unit ? (
          <span
            style={{ fontSize: 13, color: 'var(--fg-3)', fontWeight: 400 }}
          >
            {unit}
          </span>
        ) : null}
      </div>

      {context ? (
        <div
          style={{
            fontSize: 12,
            color: 'var(--fg-2)',
            marginTop: 8,
            lineHeight: 1.4,
          }}
        >
          {context}
        </div>
      ) : null}

      {target !== undefined || trend !== undefined ? (
        <div
          style={{
            display: 'flex',
            gap: 12,
            marginTop: 10,
            fontSize: 11,
            color: 'var(--fg-3)',
            alignItems: 'center',
          }}
        >
          {target !== undefined ? (
            <span>
              Meta{' '}
              <span className="tabular" style={{ color: 'var(--fg-1)' }}>
                {target}
              </span>
            </span>
          ) : null}
          {trend !== undefined ? (
            <span
              style={{
                color: trend >= 0 ? 'var(--green)' : 'var(--red)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3,
              }}
            >
              {trend >= 0 ? (
                <ArrowUp size={11} />
              ) : (
                <ArrowDown size={11} />
              )}
              {Math.abs(trend).toFixed(1)}%
            </span>
          ) : null}
        </div>
      ) : null}

      {sparkline && sparkline.length > 0 ? (
        <div
          style={{
            marginTop: 14,
            height: 32,
            color:
              status === 'gray' ? 'var(--fg-2)' : `var(--${status})`,
          }}
        >
          <Sparkline
            points={sparkline}
            width={200}
            height={32}
            strokeWidth={1.5}
          />
        </div>
      ) : null}
    </div>
  );
}
