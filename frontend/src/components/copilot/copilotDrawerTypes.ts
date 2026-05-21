// Tipos do CopilotDrawer (Q.60.AD).
import type { CopilotResponse } from '../../lib/api';

export interface CopilotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  initialQuery?: string | null;
  openedViaFab?: boolean;
  /** Q.18 fix-workforce — quando vem de um drawer entity-aware (ex: employee
   * detail), enviar entity_type/entity_id ao backend para enriquecer contexto. */
  initialEntityType?: string;
  initialEntityId?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'copilot';
  content: string | CopilotResponse;
  timestamp: Date;
}

