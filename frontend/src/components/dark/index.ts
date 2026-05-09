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

// Sprint X.2 — Plan v4 §4.7 editable parameter row with provenance
// badge + reset + accept-learned-rule.
export { ConfigParam } from './ConfigParam';
export type { ConfigParamProps, ConfigParamType } from './ConfigParam';

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

