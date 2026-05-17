import type { ReactNode, HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from 'react';

// Table Root
interface DarkTableProps extends HTMLAttributes<HTMLTableElement> {
  children: ReactNode;
  className?: string;
}

export function DarkTable({ children, className = '', ...props }: DarkTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className={`alpha-table w-full ${className}`} {...props}>
        {children}
      </table>
    </div>
  );
}

// Table Head
interface DarkTableHeadProps extends HTMLAttributes<HTMLTableSectionElement> {
  children: ReactNode;
  className?: string;
}

export function DarkTableHead({ children, className = '', ...props }: DarkTableHeadProps) {
  return (
    <thead className={className} {...props}>
      {children}
    </thead>
  );
}

// Table Body
interface DarkTableBodyProps extends HTMLAttributes<HTMLTableSectionElement> {
  children: ReactNode;
  className?: string;
}

export function DarkTableBody({ children, className = '', ...props }: DarkTableBodyProps) {
  return (
    <tbody className={className} {...props}>
      {children}
    </tbody>
  );
}

// Table Row
/** Estado visual da linha — pinta um left-border 3px (padrão AlertCardZip). */
export type DarkTableRowStatus = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

const ROW_STATUS_COLOR: Record<DarkTableRowStatus, string> = {
  success: 'var(--green)',
  warning: 'var(--yellow)',
  danger: 'var(--red)',
  info: 'var(--blue)',
  neutral: 'var(--bd-2)',
};

interface DarkTableRowProps extends HTMLAttributes<HTMLTableRowElement> {
  children: ReactNode;
  className?: string;
  clickable?: boolean;
  /** Quando definido, pinta um left-border 3px de estado (inset box-shadow,
   * fiável em tabelas com border-collapse ao contrário de border-left). */
  status?: DarkTableRowStatus;
}

export function DarkTableRow({ children, className = '', clickable = false, status, style, ...props }: DarkTableRowProps) {
  const statusStyle = status
    ? { boxShadow: `inset 3px 0 0 0 ${ROW_STATUS_COLOR[status]}` }
    : undefined;
  return (
    <tr
      className={`transition-colors hover:bg-bg-card-hover ${clickable ? 'cursor-pointer' : ''} ${className}`}
      style={statusStyle ? { ...style, ...statusStyle } : style}
      {...props}
    >
      {children}
    </tr>
  );
}

// Table Header Cell
interface DarkTableHeaderProps extends ThHTMLAttributes<HTMLTableCellElement> {
  children?: ReactNode;
  className?: string;
  align?: 'left' | 'center' | 'right';
  sortable?: boolean;
  sorted?: 'asc' | 'desc' | null;
}

const alignClasses = {
  left: 'text-left',
  center: 'text-center',
  right: 'text-right',
};

export function DarkTableHeader({ 
  children, 
  className = '', 
  align = 'left',
  sortable = false,
  sorted = null,
  ...props 
}: DarkTableHeaderProps) {
  return (
    <th 
      className={`
        px-4 py-3 
        text-xs font-semibold uppercase tracking-wider 
        text-text-tertiary 
        border-b border-border-subtle
        ${alignClasses[align]}
        ${sortable ? 'cursor-pointer hover:text-text-secondary select-none' : ''}
        ${className}
      `}
      {...props}
    >
      <div className={`flex items-center gap-1.5 ${align === 'right' ? 'justify-end' : align === 'center' ? 'justify-center' : ''}`}>
        {children}
        {sortable && sorted && (
          <span className="text-accent">
            {sorted === 'asc' ? '↑' : '↓'}
          </span>
        )}
      </div>
    </th>
  );
}

// Table Cell
interface DarkTableCellProps extends TdHTMLAttributes<HTMLTableCellElement> {
  children?: ReactNode;
  className?: string;
  align?: 'left' | 'center' | 'right';
  mono?: boolean;
}

export function DarkTableCell({ 
  children, 
  className = '', 
  align = 'left',
  mono = false,
  ...props 
}: DarkTableCellProps) {
  return (
    <td 
      className={`
        px-4 py-3.5 
        text-sm text-text-secondary 
        border-b border-border-subtle
        ${alignClasses[align]}
        ${mono ? 'font-mono tabular-nums' : ''}
        ${className}
      `}
      {...props}
    >
      {children}
    </td>
  );
}

