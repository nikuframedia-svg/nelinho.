/**
 * ConfirmDestructiveModal — modal de confirmação para acções destrutivas.
 * Requer razão ≥10c antes de confirmar (espelha validação server-side).
 *
 * Usado na tab Master Data (Q.115.X5) para cancelar OF, cancelar encomenda,
 * retirar barco e desactivar operador.
 */
import { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Modal, DarkButton } from '../dark';

interface Props {
  title: string;
  description: string;
  entityId: string;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<void>;
}

export function ConfirmDestructiveModal({ title, description, entityId, isOpen, onClose, onConfirm }: Props) {
  const [reason, setReason] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const charCount = reason.trim().length;
  const isValid = charCount >= 10;

  function handleClose() {
    if (isLoading) return;
    setReason('');
    setError(null);
    onClose();
  }

  async function handleConfirm() {
    if (!isValid || isLoading) return;
    setIsLoading(true);
    setError(null);
    try {
      await onConfirm(reason.trim());
      setReason('');
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Modal
      open={isOpen}
      onClose={handleClose}
      title={title}
      footer={
        <div className="flex gap-2 justify-end">
          <DarkButton variant="ghost" onClick={handleClose} disabled={isLoading}>
            Cancelar
          </DarkButton>
          <button
            onClick={handleConfirm}
            disabled={!isValid || isLoading}
            className="px-4 py-1.5 rounded text-sm font-medium bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? 'A processar…' : 'Confirmar'}
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="flex items-start gap-3 p-3 rounded-lg bg-red-900/20 border border-red-800/40">
          <AlertTriangle size={16} className="text-red-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm text-text-dark-primary">{description}</p>
            <p className="text-xs text-text-dark-tertiary mt-1 font-mono">{entityId}</p>
          </div>
        </div>

        <div>
          <label className="block text-xs text-text-dark-secondary mb-1">
            Razão (obrigatório)
          </label>
          <textarea
            rows={3}
            className="w-full bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300 rounded px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-red-500"
            placeholder="Explica a razão (≥10c)…"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={isLoading}
          />
          <div className="flex justify-between mt-1">
            <span className={`text-xs ${isValid ? 'text-text-dark-tertiary' : 'text-red-400'}`}>
              {isValid ? '' : `${10 - charCount} caractere${10 - charCount === 1 ? '' : 's'} em falta`}
            </span>
            <span className="text-xs text-text-dark-tertiary">{charCount}</span>
          </div>
        </div>

        {error && (
          <p className="text-xs text-red-400">{error}</p>
        )}
      </div>
    </Modal>
  );
}
