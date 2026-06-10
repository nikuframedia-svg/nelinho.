/**
 * MoveBoatConfirm — confirmação de mudança de fase de um barco (Q.52.F).
 *
 * Quando se arrasta um barco para outra coluna, esta modal mostra a
 * CONSEQUÊNCIA real do movimento (vinda de POST /schedule/preview-delta)
 * e exige uma razão (≥10 chars, contrato do backend) antes de persistir
 * via POST /schedule/apply-move.
 *
 * ZERO MOCKS: o delta de fitness/throughput e os conflitos vêm todos do
 * preview real. Se o preview falhar (ex: operação não encontrada no
 * commit actual), mostra o erro honesto — não inventa um resultado.
 */

import { useState } from 'react';
import type { ReactNode } from 'react';
import { Sheet, DarkButton } from '../../components/dark';
import { fmtEuro } from '../painel/painelHelpers';
import type { PreviewDeltaResult } from '../../lib/api';
import type { ActiveOrderCard } from './fabricaApi';

export interface MoveBoatConfirmProps {
  boat: ActiveOrderCard;
  /** Nome da fase de destino. */
  targetPhase: string;
  /** Resultado do preview — null enquanto carrega. */
  preview: PreviewDeltaResult | null;
  previewLoading: boolean;
  previewError: string | null;
  /** True enquanto o apply-move corre. */
  applying: boolean;
  applyError: string | null;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}

export function MoveBoatConfirm({
  boat,
  targetPhase,
  preview,
  previewLoading,
  previewError,
  applying,
  applyError,
  onConfirm,
  onCancel,
}: MoveBoatConfirmProps): ReactNode {
  const [reason, setReason] = useState('');
  const reasonOk = reason.trim().length >= 10;

  const fitDelta = preview?.fitness_delta ?? 0;
  const eurDelta = preview?.throughput_eur_delta ?? 0;
  const hasConflicts = (preview?.conflicts.length ?? 0) > 0;

  return (
    <Sheet
      open
      onClose={onCancel}
      title="Mover barco de fase"
      subtitle={`#${boat.hull ?? boat.id.slice(0, 6)} · ${
        boat.phase ?? 'sem fase'
      } → ${targetPhase}`}
      width={560}
      footer={
        <>
          <DarkButton variant="secondary" size="md" onClick={onCancel}>
            Cancelar
          </DarkButton>
          <DarkButton
            variant="primary"
            size="md"
            disabled={!reasonOk || applying || previewLoading}
            onClick={() => onConfirm(reason.trim())}
          >
            {applying ? 'A aplicar…' : 'Confirmar movimento'}
          </DarkButton>
        </>
      }
    >
      {/* Consequência do preview */}
      {previewLoading ? (
        <div style={{ fontSize: 12, color: 'var(--fg-3)', padding: '12px 0' }}>
          A calcular a consequência do movimento…
        </div>
      ) : previewError ? (
        <div
          style={{
            padding: '12px 14px',
            background: 'var(--red-bg)',
            border: '1px solid var(--red-bd)',
            borderRadius: 'var(--r-md)',
            fontSize: 12.5,
            color: 'var(--red)',
            marginBottom: 14,
          }}
        >
          Não foi possível pré-visualizar o movimento: {previewError}
        </div>
      ) : preview ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 10,
            marginBottom: 14,
          }}
        >
          <DeltaCard
            label="Fitness"
            value={`${fitDelta >= 0 ? '+' : ''}${fitDelta.toFixed(3)}`}
            good={fitDelta >= 0}
          />
          <DeltaCard
            label="Throughput €/dia"
            value={`${eurDelta >= 0 ? '+' : ''}${fmtEuro(eurDelta)}`}
            good={eurDelta >= 0}
          />
        </div>
      ) : null}

      {/* Conflitos / avisos */}
      {preview && hasConflicts && (
        <div
          style={{
            padding: '10px 14px',
            background: 'var(--red-bg)',
            border: '1px solid var(--red-bd)',
            borderRadius: 'var(--r-md)',
            marginBottom: 14,
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: 'var(--red)',
              textTransform: 'uppercase',
              letterSpacing: 0.4,
              marginBottom: 6,
            }}
          >
            {preview.conflicts.length} conflito(s)
          </div>
          <ul
            style={{
              margin: 0,
              paddingLeft: 16,
              fontSize: 12,
              color: 'var(--fg-1)',
            }}
          >
            {preview.conflicts.map((c, i) => (
              <li key={i}>{String((c as { message?: string }).message ?? c)}</li>
            ))}
          </ul>
        </div>
      )}
      {preview?.pair_rule_violation && (
        <div
          style={{
            padding: '8px 12px',
            background: 'var(--orange-bg)',
            border: '1px solid var(--orange-bd)',
            borderRadius: 'var(--r-md)',
            fontSize: 12,
            color: 'var(--orange)',
            marginBottom: 14,
          }}
        >
          Atenção: este movimento viola a regra de pares da Laminagem.
        </div>
      )}

      {/* Razão obrigatória */}
      <label
        style={{
          display: 'block',
          fontSize: 11,
          color: 'var(--fg-2)',
          fontWeight: 500,
          marginBottom: 6,
        }}
      >
        Razão do movimento (mínimo 10 caracteres — fica no registo de
        auditoria)
      </label>
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={3}
        placeholder="Ex: barco #4271 atrasado, antecipar para libertar molde K1 7ML"
        className="bg-bg-2 text-fg-0 placeholder:text-fg-3"
        style={{
          width: '100%',
          padding: '8px 10px',
          borderRadius: 'var(--r-sm)',
          border: '1px solid var(--bd-2)',
          fontSize: 12.5,
          resize: 'vertical',
          outline: 'none',
        }}
      />
      {!reasonOk && reason.length > 0 && (
        <div style={{ fontSize: 10.5, color: 'var(--orange)', marginTop: 4 }}>
          Faltam {10 - reason.trim().length} caracteres.
        </div>
      )}

      {applyError && (
        <div
          style={{
            marginTop: 12,
            padding: '10px 14px',
            background: 'var(--red-bg)',
            border: '1px solid var(--red-bd)',
            borderRadius: 'var(--r-md)',
            fontSize: 12.5,
            color: 'var(--red)',
          }}
        >
          {applyError}
        </div>
      )}
    </Sheet>
  );
}

function DeltaCard({
  label,
  value,
  good,
}: {
  label: string;
  value: string;
  good: boolean;
}): ReactNode {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-md)',
        padding: 12,
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
        }}
      >
        {label}
      </div>
      <div
        className="tabular display"
        style={{
          fontSize: 20,
          fontWeight: 600,
          color: good ? 'var(--green)' : 'var(--red)',
          marginTop: 4,
        }}
      >
        {value}
      </div>
    </div>
  );
}
