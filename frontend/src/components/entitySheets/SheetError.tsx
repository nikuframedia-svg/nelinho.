/**
 * SheetError — estado de erro partilhado dos entity sheets (Q.145).
 *
 * Um 404 significa que a entidade já não existe (ex. ordem podada do WIP quando
 * o sync ERP refresca) — NÃO é uma falha. Mostra um estado suave em vez do
 * modal vermelho "Erro ao carregar dados", que assustava na fábrica ao clicar
 * numa referência stale. Só falhas genuínas (não-404) ficam vermelhas.
 */

import { Sheet } from '../dark/Sheet';

export type SheetEntityKind = 'encomenda' | 'operador' | 'modelo' | 'fase' | 'cliente';

const GONE_MESSAGE: Record<SheetEntityKind, string> = {
  encomenda: 'Esta encomenda já não está no WIP (concluída ou removida do ERP).',
  operador: 'Este operador já não está disponível.',
  modelo: 'Este modelo já não está disponível.',
  fase: 'Esta fase já não está disponível.',
  cliente: 'Este cliente já não está disponível.',
};

export function SheetError({
  error,
  onClose,
  kind,
}: {
  error: unknown;
  onClose: () => void;
  kind: SheetEntityKind;
}) {
  const status = (error as { status?: number } | null | undefined)?.status;

  if (status === 404) {
    return (
      <Sheet open={true} onClose={onClose} title="Já não disponível" width={720}>
        <div style={{ color: 'var(--fg-2)', fontSize: 14, lineHeight: 1.5 }}>
          {GONE_MESSAGE[kind]} Atualiza a página para ver a lista mais recente.
        </div>
      </Sheet>
    );
  }

  return (
    <Sheet open={true} onClose={onClose} title="Erro" width={720}>
      <div style={{ color: 'var(--danger, #ef4444)', fontSize: 14 }}>
        Erro ao carregar dados:{' '}
        {error instanceof Error ? error.message : 'Erro desconhecido'}
      </div>
    </Sheet>
  );
}
