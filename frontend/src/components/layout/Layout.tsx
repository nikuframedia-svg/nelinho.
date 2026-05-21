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
 * Q.52.A — Layout afinado ao design NELO.html:
 * Sidebar lateral 220px (3 grupos PT-PT) + TopBar fina (52px, search/
 * data/assistente) + main com margin-left para acomodar a Sidebar.
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
    <div className="min-h-screen bg-bg-base">
      <Sidebar />
      {/* Sidebar é fixed 220px. Empurrar conteúdo. */}
      <div className="flex flex-col min-h-screen" style={{ marginLeft: 220 }}>
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
