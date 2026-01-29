import { useState, useCallback } from 'react';
import { Outlet } from 'react-router-dom';
import { CopilotFab } from '../copilot/CopilotFab';
import { AlphaHeader } from '../alpha/AlphaHeader';
import { CommandPalette } from '../command/CommandPalette';
import { KeyboardShortcutsModal } from '../help/KeyboardShortcutsModal';
import { useCommandPalette, useKeyboardShortcuts, useSchemaDrift } from '../../hooks';

// PALANTIR-LEVEL COMPONENTS
import { SchemaDriftAlert } from '../palantir';

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
      <AlphaHeader />
      <main className="min-h-[calc(100vh-64px)]">
        <Outlet />
      </main>
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
