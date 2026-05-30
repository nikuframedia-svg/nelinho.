/**
 * SearchResultsPage — resultados da pesquisa global.
 *
 * A TopBar (Cmd+K ou caixa de pesquisa) navega para `/pesquisa?q=…`.
 * Esta página chama `searchApi.query` (`GET /v1/search`) e mostra os hits
 * agrupados por tipo (barco / operador / molde / erro). Cada hit liga à
 * página de detalhe correspondente.
 *
 * ZERO MOCKS: sem resultados → empty state honesto. Sem `q` → pede um termo.
 *
 * Sprint Q.52.S.
 */

import { useMemo, useCallback, type ReactNode } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search, Ship, User, Box, AlertTriangle } from 'lucide-react';
import { PageHeader } from '../../components/dark/PageHeader';
import { EmptyState } from '../../components/dark/EmptyState';
import { SkeletonLoader } from '../../components/ui/Skeleton';
import { searchApi, type SearchHit } from '../../lib/api';
import { useEntitySheet } from '../../components/entitySheets';

const TYPE_META: Record<
  SearchHit['type'],
  { label: string; icon: ReactNode }
> = {
  barco: {
    label: 'Barcos',
    icon: <Ship size={15} />,
  },
  operador: {
    label: 'Operadores',
    icon: <User size={15} />,
  },
  molde: {
    label: 'Moldes',
    icon: <Box size={15} />,
  },
  erro: {
    label: 'Erros',
    icon: <AlertTriangle size={15} />,
  },
};

const TYPE_ORDER: SearchHit['type'][] = ['barco', 'operador', 'molde', 'erro'];

export function SearchResultsPage(): ReactNode {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { openSheet } = useEntitySheet();
  const q = (params.get('q') ?? '').trim();

  // Navegar para o destino correcto consoante o tipo de resultado.
  // operador → ficha de entidade (?sheet=operador&id=…)
  // barco / molde / erro → /overall (única rota viva com contexto de produção)
  const handleHitClick = useCallback(
    (hit: SearchHit) => {
      if (hit.type === 'operador') {
        openSheet('operador', hit.id);
      } else {
        navigate('/overall');
      }
    },
    [navigate, openSheet],
  );

  const searchQuery = useQuery({
    queryKey: ['search', 'global', q],
    queryFn: () => searchApi.query(q, 20),
    enabled: q.length > 0,
    staleTime: 30_000,
  });

  const grouped = useMemo(() => {
    const results = searchQuery.data?.results ?? [];
    const map = new Map<SearchHit['type'], SearchHit[]>();
    for (const hit of results) {
      const list = map.get(hit.type) ?? [];
      list.push(hit);
      map.set(hit.type, list);
    }
    return map;
  }, [searchQuery.data]);

  const total = searchQuery.data?.results.length ?? 0;

  return (
    <div>
      <PageHeader
        title="Pesquisa"
        subtitle={
          q
            ? `${total} resultado${total === 1 ? '' : 's'} para “${q}”`
            : 'Procurar barcos, operadores, moldes e erros'
        }
        icon={<Search size={17} />}
      />

      <div style={{ padding: '20px 28px' }}>
        {q.length === 0 ? (
          <EmptyState
            title="Escreve um termo para procurar"
            hint="Usa a caixa de pesquisa no topo (ou ⌘K) para procurar barcos, operadores, moldes e erros."
            icon={<Search size={28} />}
            mascot={false}
          />
        ) : searchQuery.isLoading ? (
          <SkeletonLoader count={4} />
        ) : searchQuery.isError ? (
          <EmptyState
            title="A pesquisa falhou"
            hint="Não foi possível contactar o serviço de pesquisa. Tenta novamente dentro de momentos."
            icon={<Search size={28} />}
            mascot={false}
          />
        ) : total === 0 ? (
          <EmptyState
            title={`Sem resultados para “${q}”`}
            hint="Verifica a ortografia ou tenta um termo mais curto."
            icon={<Search size={28} />}
            mascot={false}
          />
        ) : (
          <div className="flex flex-col" style={{ gap: 20 }}>
            {TYPE_ORDER.map((type) => {
              const hits = grouped.get(type);
              if (!hits || hits.length === 0) return null;
              const meta = TYPE_META[type];
              return (
                <section key={type}>
                  <div
                    className="flex items-center text-text-dark-tertiary uppercase font-semibold"
                    style={{
                      gap: 7,
                      fontSize: 10,
                      letterSpacing: '0.7px',
                      marginBottom: 8,
                    }}
                  >
                    {meta.icon}
                    <span>
                      {meta.label} · {hits.length}
                    </span>
                  </div>
                  <ul className="flex flex-col" style={{ gap: 4 }}>
                    {hits.map((hit) => (
                      <li key={`${hit.type}-${hit.id}`}>
                        <button
                          type="button"
                          onClick={() => handleHitClick(hit)}
                          className="flex items-center w-full text-left transition-colors"
                          style={{
                            gap: 12,
                            padding: '10px 13px',
                            background: 'var(--bg-2)',
                            border: '1px solid var(--bd-1)',
                            borderRadius: 'var(--r-md)',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'var(--bg-3)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'var(--bg-2)';
                          }}
                        >
                          <span className="text-text-dark-tertiary flex shrink-0">
                            {meta.icon}
                          </span>
                          <span className="flex-1 min-w-0">
                            <span
                              className="block text-text-dark-primary truncate"
                              style={{ fontSize: 13, fontWeight: 500 }}
                            >
                              {hit.label}
                            </span>
                            <span
                              className="block text-text-dark-tertiary truncate"
                              style={{ fontSize: 11 }}
                            >
                              {hit.sublabel}
                            </span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default SearchResultsPage;
