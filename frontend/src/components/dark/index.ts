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

// Sprint X.2 — Plan v4 §4.7 editable parameter row with provenance
// badge + reset + accept-learned-rule.

// Sprint Q.18.UI.A — atomic primitives para o refactor 8-páginas
// alinhado com FRONTEND_DESIGN_PROMPT.md.
export { KPICard } from './KPICard';
export type { KPICardProps, KPIStatus } from './KPICard';
export { AlertCard } from './AlertCard';
export type {
  AlertCardProps,
  AlertCardAction,
  AlertSeverity,
  AlertSource,
} from './AlertCard';
export { TimelineSuggestion } from './TimelineSuggestion';
export type {
  TimelineSuggestionProps,
  TimelineSuggestionAlternative,
  SuggestionPriority,
} from './TimelineSuggestion';
export { BoatCard } from './BoatCard';
export type { BoatCardProps, BoatStatus } from './BoatCard';
export { PhaseColumn } from './PhaseColumn';
export type { PhaseColumnProps } from './PhaseColumn';
export { WorkerAvatar } from './WorkerAvatar';
export type { WorkerAvatarProps } from './WorkerAvatar';
export { CausalChainCard } from './CausalChainCard';
export type { CausalChainCardProps } from './CausalChainCard';
export { ApprovalButtons } from './ApprovalButtons';
export type { ApprovalButtonsProps, ReasonRequirement } from './ApprovalButtons';
export { GanttChart, GanttBar } from './GanttChart';
export type {
  GanttChartProps,
  GanttRow,
  GanttBarData,
  GanttBarKind,
  GanttBarStatus,
} from './GanttChart';
export { BigButton } from './BigButton';

// Sprint Q.18.ZIP.A — primitives portados/inspirados no nelo (1).zip
// (Palantir industrial design + visual mais dinâmico).
export { Sparkline } from './Sparkline';
export type { SparklineProps } from './Sparkline';
export { TrustBadge, scoreToGrade } from './TrustBadge';
export type { TrustBadgeProps, TrustGrade } from './TrustBadge';
export { AlertRow, severityToKind } from './AlertRow';
export type { AlertRowProps, AlertKind } from './AlertRow';
export { Panel } from './Panel';
export type { PanelProps } from './Panel';
export { Tabs } from './Tabs';
export type { TabsProps, TabItem } from './Tabs';
export { SegmentedControl } from './SegmentedControl';
export type { SegmentedControlProps, SegmentOption } from './SegmentedControl';
export { PageHeader } from './PageHeader';
export type { PageHeaderProps } from './PageHeader';
export { Breadcrumbs } from './Breadcrumbs';
export type { BreadcrumbsProps, BreadcrumbItem } from './Breadcrumbs';
export { Modal } from './Modal';
export type { ModalProps } from './Modal';

// Sprint Q.18.ZIP.L — EmptyState global com Nelinho mascot opcional
export { EmptyState } from './EmptyState';
export type { EmptyStateProps } from './EmptyState';

// Sprint Q.18.ZIP.shell — LiveBadge "● Em direto" (zip atoms.jsx port literal)
export { LiveBadge } from './LiveBadge';

// Sprint Q.18.ZIP.atoms — atoms portados literalmente do design/nelo-zip/src/atoms.jsx
// (status colors green/yellow/red/blue/orange/purple/gray + glyph ●◆▲◐ inline).
// `StatusBadge` do zip exposto como `ZipStatusBadge` para não colidir com
// o legacy DarkBadge.StatusBadge (semantica diferente).
export {
  ToneBadge as ZipToneBadge,
  StatusBadge as ZipStatusBadge,
  SevBadge as ZipSevBadge,
  Legend as ZipLegend,
  BoatCardZip,
  STATUS_MAP as ZIP_STATUS_MAP,
  SEV_MAP as ZIP_SEV_MAP,
} from './ZipAtoms';
export type {
  ToneColor as ZipToneColor,
  BoatStatus as ZipBoatStatus,
  Severity as ZipSeverity,
  LegendItem as ZipLegendItem,
  ZipBoat,
} from './ZipAtoms';

// ─── Sprint Q.52.B — átomos + primitivas do design NELO.html ────────────────
// Port fiel de design/nelo/project/src/atoms.jsx ("dark Apple-like minimal").
// Geometria e tokens batem certo com o protótipo. Distintos dos átomos legacy
// (KPICard / BoatCard / WorkerAvatar / SegmentedControl / Modal) — as páginas
// da Onda 1 consomem estes; as legacy ficam até as páginas dependentes migrarem.
export { KPIBig } from './KPIBig';
export type { KPIBigProps, KPIBigStatus } from './KPIBig';
export { ConsequenceBox } from './ConsequenceBox';
export type {
  ConsequenceBoxProps,
  ConsequenceAlternative,
} from './ConsequenceBox';
export { RiskBadge } from './RiskBadge';
export type { RiskBadgeProps, RiskTone } from './RiskBadge';
export { ObjectiveBar } from './ObjectiveBar';
export type { ObjectiveBarProps } from './ObjectiveBar';
export { ScoreBar } from './ScoreBar';
export type { ScoreBarProps } from './ScoreBar';
export { BarsMini } from './BarsMini';
export type { BarsMiniProps, BarsMiniDatum } from './BarsMini';
export { OEERing } from './OEERing';
export type { OEERingProps } from './OEERing';
export { Sheet } from './Sheet';
export type { SheetProps } from './Sheet';
export { Segmented } from './Segmented';
export type { SegmentedProps, SegmentedOption } from './Segmented';
export { NeloBoatCard } from './NeloBoatCard';
export type {
  NeloBoatCardProps,
  NeloBoat,
  NeloBoatStatus,
} from './NeloBoatCard';
export { NeloWorkerAvatar } from './NeloWorkerAvatar';
export type { NeloWorkerAvatarProps, NeloWorker } from './NeloWorkerAvatar';
export { useCountUp } from './useCountUp';

// Primitivas partilhadas (>1 página) — DnD HTML5 + grelha de timeline.
export { useDraggable, useDropZone } from './useDragDrop';
export type { DragKind, DragPayload } from './useDragDrop';
export { TimelineLanes } from './TimelineLanes';
export type {
  TimelineLanesProps,
  TimelineSlot,
  TimelineLane,
  TimelineItem,
} from './TimelineLanes';

