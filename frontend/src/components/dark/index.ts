// Dark Theme Design System Components
export { DarkCard } from './DarkCard';
export { DarkStatCard } from './DarkStatCard';
export {
  DarkTable,
  DarkTableHead,
  DarkTableBody,
  DarkTableRow,
  DarkTableHeader,
  DarkTableCell
} from './DarkTable';
export { DarkButton, DarkPillButton, DarkIconButton } from './DarkButton';
export { DarkBadge, StatusBadge } from './DarkBadge';
export { DarkInput, DarkTextarea, DarkSearchInput } from './DarkInput';
export { DarkSelect, DarkDropdownButton } from './DarkSelect';

// Sprint Q.9 Onda 3.1 — "explica sempre" UX primitives.
// These four components are the visual contract behind plan v4 §4.1
// (the system explains every consequence) and §11.2 (every config
// key shows its provenance). Pages compose them rather than rolling
// their own block layouts.
export { SuggestionExplainer } from './SuggestionExplainer';
export type { SuggestionExplainerProps } from './SuggestionExplainer';
export { ConsequenceBlock } from './ConsequenceBlock';
export type {
  ConsequenceBlockProps,
  ConsequenceLine,
  ConsequenceSeverity,
} from './ConsequenceBlock';
export { GhostOverlay } from './GhostOverlay';
export type { GhostOverlayProps } from './GhostOverlay';
export { AuditTrailRow } from './AuditTrailRow';
export type { AuditTrailRowProps } from './AuditTrailRow';

// Sprint Q.13.A — Plan v4 §6.2 alternative worker pairs visual.
export { WorkerPairCard } from './WorkerPairCard';
export type { WorkerPairCardProps } from './WorkerPairCard';

// Sprint Q.13.C — Plan v4 §10 tablet kiosk + barcode scanner.
export { KioskWrapper } from './KioskWrapper';
export type { KioskWrapperProps } from './KioskWrapper';
export { BarcodeScanButton } from './BarcodeScanButton';
export type { BarcodeScanButtonProps } from './BarcodeScanButton';

