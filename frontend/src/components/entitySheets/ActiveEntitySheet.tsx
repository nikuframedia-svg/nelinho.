/**
 * Q.116.A — Renderiza o sheet activo com lazy-load dos 4 sheets.
 *
 * Cada sheet é carregado só quando necessário (bundle inicial não cresce).
 * Agent C cria os ficheiros em ./sheets/ — imports abaixo são contratos.
 */
import { lazy, Suspense } from 'react';
import { useEntitySheet } from './EntitySheetProvider';

const ModeloSheet    = lazy(() => import('./sheets/ModeloSheet'));
const FaseSheet      = lazy(() => import('./sheets/FaseSheet'));
const ClienteSheet   = lazy(() => import('./sheets/ClienteSheet'));
const EncomendaSheet = lazy(() => import('./sheets/EncomendaSheet'));

export function ActiveEntitySheet() {
  const { current, closeSheet } = useEntitySheet();

  if (!current) return null;

  return (
    <Suspense fallback={null}>
      {current.kind === 'modelo' && (
        <ModeloSheet modelId={current.id} onClose={closeSheet} />
      )}
      {current.kind === 'fase' && (
        <FaseSheet phaseId={current.id} onClose={closeSheet} />
      )}
      {current.kind === 'cliente' && (
        <ClienteSheet customerId={current.id} onClose={closeSheet} />
      )}
      {current.kind === 'encomenda' && (
        <EncomendaSheet workOrderId={current.id} onClose={closeSheet} />
      )}
    </Suspense>
  );
}
