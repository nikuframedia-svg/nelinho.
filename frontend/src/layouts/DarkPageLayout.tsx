import type { ReactNode } from 'react';
import { PageHelpButton } from '../components/help/PageHelpButton';
import type { PageHelpId } from '../data/pageHelp';
import { Breadcrumbs } from '../components/dark/Breadcrumbs';
import type { BreadcrumbItem } from '../components/dark/Breadcrumbs';

interface DarkPageLayoutProps {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  icon?: ReactNode;
  actions?: ReactNode;
  /** Quando definido, renderiza botão "?" à esquerda das actions. */
  helpId?: PageHelpId;
  /** Trilho hierárquico mostrado por cima do título (ex: Sistema · Regras Q.17). */
  breadcrumbs?: BreadcrumbItem[];
  noPadding?: boolean;
}

export function DarkPageLayout({
  children,
  title,
  subtitle,
  icon,
  actions,
  helpId,
  breadcrumbs,
  noPadding = false,
}: DarkPageLayoutProps) {
  const hasBreadcrumbs = breadcrumbs !== undefined && breadcrumbs.length > 0;
  return (
    <div className="min-h-screen bg-bg-base">
      {/* Page Header */}
      {(title || actions || helpId || hasBreadcrumbs) && (
        <div className="sticky top-0 z-10 bg-bg-base/95 backdrop-blur-sm border-b border-border-subtle">
          <div className={noPadding ? 'px-6 py-4' : 'px-8 py-5'}>
            <div className="flex items-center justify-between">
              {/* Title Section */}
              <div className="flex items-center gap-4">
                {icon && (
                  <div className="w-10 h-10 flex items-center justify-center rounded-xl bg-accent-muted text-accent">
                    {icon}
                  </div>
                )}
                <div>
                  {hasBreadcrumbs && (
                    <Breadcrumbs items={breadcrumbs!} className="mb-1" />
                  )}
                  {title && (
                    <h1 className="text-xl font-semibold text-text-white">
                      {title}
                    </h1>
                  )}
                  {subtitle && (
                    <p className="text-sm text-text-gray mt-0.5">
                      {subtitle}
                    </p>
                  )}
                </div>
              </div>

              {/* Actions Section */}
              {(actions || helpId) && (
                <div className="flex items-center gap-3">
                  {helpId && <PageHelpButton helpId={helpId} />}
                  {actions}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Page Content */}
      <div
        className="page-enter"
        style={
          noPadding
            ? undefined
            : { padding: 'var(--page-padding-y) var(--page-padding-x)' }
        }
      >
        {children}
      </div>
    </div>
  );
}

