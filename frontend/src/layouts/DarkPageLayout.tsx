import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { PageHelpButton } from '../components/help/PageHelpButton';
import { helpIdFromPath, type PageHelpId } from '../data/pageHelp';
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
  // Se a página não passar `helpId` explícito, deriva-o da rota — o "?"
  // passa a aparecer em todas as páginas sem cada uma ter de o declarar.
  const { pathname } = useLocation();
  const effectiveHelpId = helpId ?? helpIdFromPath(pathname);
  return (
    <div className="min-h-screen bg-bg-base">
      {/* Page Header — Q.52.A afinado ao PageHeader do NELO.html:
          glass sticky, icon-box 32px, título display 19px. */}
      {(title || actions || effectiveHelpId || hasBreadcrumbs) && (
        <div
          className="sticky top-0 z-10"
          style={{
            background: 'rgba(0,0,0,0.5)',
            backdropFilter: 'saturate(180%) blur(16px)',
            WebkitBackdropFilter: 'saturate(180%) blur(16px)',
            borderBottom: '1px solid var(--bd-1)',
          }}
        >
          <div className={noPadding ? 'px-6 py-4' : 'px-7 py-5'}>
            <div className="flex items-center justify-between gap-4">
              {/* Title Section */}
              <div className="flex items-center gap-3">
                {icon && (
                  <div
                    className="flex items-center justify-center"
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 'var(--r-sm)',
                      background: 'var(--bg-2)',
                      border: '1px solid var(--bd-1)',
                      color: 'var(--fg-2)',
                    }}
                  >
                    {icon}
                  </div>
                )}
                <div>
                  {hasBreadcrumbs && (
                    <Breadcrumbs items={breadcrumbs!} className="mb-1" />
                  )}
                  {title && (
                    <h1
                      className="display text-text-white"
                      style={{
                        fontSize: 19,
                        fontWeight: 500,
                        letterSpacing: '-0.3px',
                      }}
                    >
                      {title}
                    </h1>
                  )}
                  {subtitle && (
                    <p
                      className="text-text-gray"
                      style={{ fontSize: 12, marginTop: 3 }}
                    >
                      {subtitle}
                    </p>
                  )}
                </div>
              </div>

              {/* Actions Section */}
              {(actions || effectiveHelpId) && (
                <div className="flex items-center gap-1.5">
                  {effectiveHelpId && <PageHelpButton helpId={effectiveHelpId} />}
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

