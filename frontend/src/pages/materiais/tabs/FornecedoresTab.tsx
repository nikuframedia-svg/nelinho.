// MateriaisPage · FornecedoresTab (Q.60.V). ZERO MOCKS — endpoints reais.
import { type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Building2, Star } from 'lucide-react';
import { EmptyState } from '../../../components/dark/EmptyState';
import { SkeletonLoader } from '../../../components/ui/Skeleton';
import { materiaisApi, type Supplier } from '../../../components/materiais/materiaisApi';
import { primaryBtn } from '../materiaisShared';

export function FornecedoresTab(): ReactNode {
  const suppliersQuery = useQuery({
    queryKey: ['materiais', 'suppliers'],
    queryFn: () => materiaisApi.listSuppliers(),
  });

  const suppliers = suppliersQuery.data ?? [];

  if (suppliersQuery.isLoading) {
    return <SkeletonLoader count={3} />;
  }
  if (suppliersQuery.isError) {
    return (
      <EmptyState
        title="Não foi possível carregar os fornecedores"
        hint="O endpoint /v1/core/suppliers falhou."
        icon={<Building2 size={28} />}
        action={
          <button type="button" onClick={() => suppliersQuery.refetch()} style={primaryBtn}>
            Tentar novamente
          </button>
        }
      />
    );
  }
  if (suppliers.length === 0) {
    return (
      <EmptyState
        title="Sem fornecedores registados"
        hint="Ainda não há fornecedores no master para este tenant."
        icon={<Building2 size={28} />}
      />
    );
  }

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
        gap: 12,
      }}
    >
      {suppliers.map((s) => (
        <SupplierCard key={s.id} supplier={s} />
      ))}
    </div>
  );
}

export function SupplierCard({ supplier }: { supplier: Supplier }): ReactNode {
  const rating = supplier.quality_rating;
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        padding: 16,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
        }}
      >
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}>
            {supplier.supplier_name}
          </div>
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}>
            {supplier.supplier_code} · {supplier.material_category}
          </div>
        </div>
        {supplier.is_preferred && (
          <span
            style={{
              fontSize: 10,
              color: 'var(--accent)',
              background: 'var(--accent-bg)',
              border: '1px solid var(--accent-bd)',
              borderRadius: 5,
              padding: '2px 6px',
              fontWeight: 600,
            }}
          >
            Preferencial
          </span>
        )}
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 10,
          marginTop: 12,
        }}
      >
        <div>
          <div
            style={{
              fontSize: 10,
              color: 'var(--fg-3)',
              textTransform: 'uppercase',
              letterSpacing: 0.4,
            }}
          >
            Qualidade
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              marginTop: 3,
            }}
          >
            {rating !== null ? (
              <>
                <Star
                  size={14}
                  color={rating >= 4 ? 'var(--green)' : rating >= 3 ? 'var(--yellow)' : 'var(--red)'}
                  fill="currentColor"
                />
                <span
                  className="tabular"
                  style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-0)' }}
                >
                  {rating}/5
                </span>
              </>
            ) : (
              <span style={{ fontSize: 13, color: 'var(--fg-3)' }}>sem rating</span>
            )}
          </div>
        </div>
        <div>
          <div
            style={{
              fontSize: 10,
              color: 'var(--fg-3)',
              textTransform: 'uppercase',
              letterSpacing: 0.4,
            }}
          >
            Lead time
          </div>
          <div
            className="tabular"
            style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-0)', marginTop: 3 }}
          >
            {supplier.lead_time_days}d
          </div>
        </div>
      </div>

      {(supplier.contact_name || supplier.city) && (
        <div
          style={{
            fontSize: 10.5,
            color: 'var(--fg-3)',
            marginTop: 12,
            paddingTop: 10,
            borderTop: '1px solid var(--bd-1)',
          }}
        >
          {supplier.contact_name ?? ''}
          {supplier.contact_name && supplier.city ? ' · ' : ''}
          {[supplier.city, supplier.country].filter(Boolean).join(', ')}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════
