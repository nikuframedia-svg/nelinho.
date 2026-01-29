import type { ReactNode } from 'react';

interface DarkPageLayoutProps {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  icon?: ReactNode;
  actions?: ReactNode;
  noPadding?: boolean;
}

export function DarkPageLayout({
  children,
  title,
  subtitle,
  icon,
  actions,
  noPadding = false,
}: DarkPageLayoutProps) {
  return (
    <div className="min-h-screen bg-bg-base">
      {/* Page Header */}
      {(title || actions) && (
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
              {actions && (
                <div className="flex items-center gap-3">
                  {actions}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Page Content */}
      <div className={`page-enter ${noPadding ? '' : 'p-6 lg:p-8'}`}>
        {children}
      </div>
    </div>
  );
}

