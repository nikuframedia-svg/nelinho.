import { useState, useCallback } from 'react';
import { Outlet } from 'react-router-dom';
import { CopilotFab } from '../copilot/CopilotFab';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { CommandPalette } from '../command/CommandPalette';
import { KeyboardShortcutsModal } from '../help/KeyboardShortcutsModal';
import { useCommandPalette, useKeyboardShortcuts, useSchemaDrift } from '../../hooks';

// PALANTIR-LEVEL COMPONENTS
import { SchemaDriftAlert } from '../palantir';

/**
 * Q.18.UI.A.1 — Layout reorganizado para o brief FRONTEND_DESIGN_PROMPT:
 * Sidebar lateral 256px (3 grupos PT-PT) + TopBar fina (52px, search/
 * notificações/data) + main com margin-left para acomodar a Sidebar.
 *
 * O AlphaHeader (TopBar horizontal em inglês com mocks) foi apagado.
 */
export function Layout() {
  const { isOpen: isCommandOpen, close: closeCommand } = useCommandPalette();
  const [isHelpOpen, setIsHelpOpen] = useState(false);

  // PALANTIR: Global Schema Drift Detection
  const { drifts, handleAction: handleDriftAction } = useSchemaDrift();

  const openHelp = useCallback(() => setIsHelpOpen(true), []);
  const closeHelp = useCallback(() => setIsHelpOpen(false), []);

  const { getShortcutsList } = useKeyboardShortcuts(openHelp);

  return (
    <div className="min-h-screen bg-bg-base grid grid-cols-[240px_minmax(0,1fr)]">
      <Sidebar />
      <div className="flex flex-col min-w-0 min-h-screen">
        <TopBar />
        <main className="flex-1 min-h-[calc(100vh-52px)]">
          <Outlet />
        </main>
      </div>
      <CopilotFab />
      <CommandPalette isOpen={isCommandOpen} onClose={closeCommand} />
      <KeyboardShortcutsModal
        isOpen={isHelpOpen}
        onClose={closeHelp}
        shortcuts={getShortcutsList()}
      />

      {/* PALANTIR: Global Schema Drift Alert - Appears when data structure changes detected */}
      {drifts.length > 0 && (
        <SchemaDriftAlert
          drifts={drifts}
          onAction={handleDriftAction}
        />
      )}
    </div>
  );
}
