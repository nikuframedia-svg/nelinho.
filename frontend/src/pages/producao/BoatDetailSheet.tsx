/**
 * BoatDetailSheet — painel lateral de detalhe de um barco (Q.52.F).
 *
 * Port fiel do `BoatDetailSheet` do design NELO, no átomo `Sheet`:
 * estado, fase actual, operadores atribuídos. Dados 100% por props
 * (vindos de orders/active + assignments) — ZERO MOCKS.
 */

import type { ReactNode } from 'react';
import { Sheet, NeloWorkerAvatar } from '../../components/dark';
import type { AssignedWorker } from './BoatAssignCard';
import type { ActiveOrderCard, OptimizedOrderCard } from './fabricaApi';

export interface BoatDetailSheetProps {
  boat: ActiveOrderCard | null;
  workers: AssignedWorker[];
  onClose: () => void;
}

function Box({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}): ReactNode {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-md)',
        padding: 14,
      }}
    >
      <div
        style={{
          fontSize: 10.5,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      {children}
    </div>
  );
}

export function BoatDetailSheet({
  boat,
  workers,
  onClose,
}: BoatDetailSheetProps): ReactNode {
  if (!boat) return null;

  const opt = boat as OptimizedOrderCard;
  const optimizedPhase = opt.optimized_phase ?? null;
  const optimizedWorker = opt.assigned_employee_name ?? null;

  return (
    <Sheet
      open={!!boat}
      onClose={onClose}
      title={boat.product_name ?? `Barco #${boat.hull ?? boat.id.slice(0, 6)}`}
      subtitle={`Barco #${boat.hull ?? boat.id.slice(0, 6)} · ${
        boat.product_type ?? 'modelo —'
      }${boat.customer_name ? ` · ${boat.customer_name}` : ''}`}
      width={620}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 12,
          marginBottom: 16,
        }}
      >
        <Box label="Estado">
          <div
            style={{ fontSize: 14, color: 'var(--fg-0)', fontWeight: 600 }}
          >
            {boat.status}
          </div>
          {boat.transport_date && (
            <div
              style={{
                fontSize: 11.5,
                color: 'var(--fg-2)',
                marginTop: 6,
              }}
            >
              Expedição prevista:{' '}
              {new Date(boat.transport_date).toLocaleDateString('pt-PT')}
            </div>
          )}
        </Box>
        <Box label="Fase actual">
          <div
            style={{ fontSize: 14, color: 'var(--fg-0)', fontWeight: 600 }}
          >
            {boat.phase ?? 'sem fase'}
          </div>
          {boat.created_date && (
            <div
              style={{
                fontSize: 11.5,
                color: 'var(--fg-2)',
                marginTop: 4,
              }}
            >
              Em produção desde{' '}
              {new Date(boat.created_date).toLocaleDateString('pt-PT')}
            </div>
          )}
        </Box>
      </div>

      {(optimizedPhase || optimizedWorker) && (
        <Box label="Plano sugerido pelo CPO">
          {optimizedPhase && (
            <div style={{ fontSize: 12.5, color: 'var(--fg-0)' }}>
              Fase optimizada:{' '}
              <span style={{ fontWeight: 600 }}>{optimizedPhase}</span>
            </div>
          )}
          {optimizedWorker && (
            <div
              style={{
                fontSize: 12.5,
                color: 'var(--fg-2)',
                marginTop: 4,
              }}
            >
              Operador sugerido:{' '}
              <span style={{ color: 'var(--accent)', fontWeight: 600 }}>
                {optimizedWorker}
              </span>
            </div>
          )}
        </Box>
      )}

      <div style={{ marginTop: optimizedPhase || optimizedWorker ? 12 : 0 }}>
        <Box label={`Operadores (${workers.length})`}>
        {workers.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
            Sem operadores atribuídos · usa o rail em baixo para arrastar um
            operador para este barco.
          </div>
        ) : (
          <div
            style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
          >
            {workers.map((w) => (
              <NeloWorkerAvatar
                key={w.id}
                worker={{ name: w.name, initials: w.initials }}
                size={28}
                showName
              />
            ))}
          </div>
        )}
        </Box>
      </div>
    </Sheet>
  );
}
