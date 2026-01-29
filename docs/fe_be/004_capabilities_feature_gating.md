# CONTRATO FE↔BE 004 — Capabilities e Feature Gating

## Metadata
- **ID**: FE-BE-004
- **Versão**: 1.0.0
- **Data**: 2026-01-27
- **Estado**: IMPLEMENTADO
- **Depende de**: FE-BE-001, FE-BE-002, FE-BE-003

## Objectivo

Eliminar 404 em produção e garantir que o frontend **só expõe o que o backend realmente suporta**.

### Problemas Resolvidos
1. ❌ Frontend chama endpoints que não existem → 404
2. ❌ Menus mostram features não disponíveis
3. ❌ KPIs tentam renderizar métricas não suportadas
4. ❌ Diferentes tenants têm diferentes features activas

### Solução
✅ Frontend consulta capabilities no boot e adapta UI dinamicamente.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                             │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐  │
│  │               CapabilitiesProvider                    │  │
│  │  - Fetch /v1/capabilities on boot                    │  │
│  │  - Store in React Context                            │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                  │
│        ┌─────────────────┼─────────────────┐               │
│        ▼                 ▼                 ▼               │
│   ┌────────┐       ┌──────────┐      ┌──────────┐         │
│   │ Router │       │   Menu   │      │FeatureGate│         │
│   │        │       │          │      │          │         │
│   │ Routes │       │ Items    │      │ Children │         │
│   │ based  │       │ filtered │      │ shown if │         │
│   │ on     │       │ by       │      │ capability│         │
│   │ caps   │       │ caps     │      │ exists   │         │
│   └────────┘       └──────────┘      └──────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Backend                              │
├─────────────────────────────────────────────────────────────┤
│  GET /v1/capabilities                                       │
│  ├── version                                                │
│  ├── modules: [explain, twin, factory, legacy]             │
│  ├── views: [v_lead_time_historico, ...]                   │
│  ├── metrics: [lead_time_medio_teorico, ...]               │
│  └── flags: { tenant_specific: true, ... }                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementação Backend

### 1. Endpoint `/v1/capabilities`

```python
# src/capabilities/api/endpoints.py

@router.get("/v1/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities(
    request: Request,
    current_user: User = Depends(get_current_user_optional),
) -> CapabilitiesResponse:
    """
    Returns the capabilities of this backend instance.
    Used by frontend to determine available features.
    """
```

### 2. Response Model

```python
class ModuleCapability(BaseModel):
    id: str                    # explain, twin, factory, legacy
    enabled: bool              # Is module available?
    version: str               # Module version
    endpoints: List[str]       # Available endpoints
    requires_permission: Optional[str] = None

class ViewCapability(BaseModel):
    id: str                    # v_lead_time_historico
    enabled: bool
    requires_permission: Optional[str] = None
    is_sensitive: bool = False

class MetricCapability(BaseModel):
    id: str                    # lead_time_medio_teorico
    enabled: bool
    status: str                # active, deprecated, blocked
    requires_permission: Optional[str] = None
    blocked_reason: Optional[str] = None

class FeatureFlag(BaseModel):
    key: str
    enabled: bool
    variant: Optional[str] = None

class CapabilitiesResponse(BaseModel):
    api_version: str           # "1.0.0"
    backend_version: str       # Git SHA or semver
    contract_hash: str         # OpenAPI hash
    
    modules: List[ModuleCapability]
    views: List[ViewCapability]
    metrics: List[MetricCapability]
    
    feature_flags: List[FeatureFlag]
    
    tenant_id: Optional[str] = None
    user_permissions: List[str] = []
    
    generated_at: str          # ISO8601 UTC
```

### 3. Catálogos Especializados

```python
# GET /v1/explain/catalog
@router.get("/v1/explain/catalog", response_model=ExplainCatalogResponse)
async def get_explain_catalog():
    """Returns all metric definitions."""

# GET /v1/factory/semantic/catalog  
@router.get("/v1/factory/semantic/catalog", response_model=FactoryCatalogResponse)
async def get_factory_catalog():
    """Returns all available semantic views."""
```

---

## Implementação Frontend

### 1. Capabilities Provider

```typescript
// frontend/src/providers/CapabilitiesProvider.tsx

interface CapabilitiesContextValue {
  capabilities: Capabilities | null;
  isLoading: boolean;
  error: Error | null;
  
  // Helper functions
  hasModule: (moduleId: string) => boolean;
  hasView: (viewId: string) => boolean;
  hasMetric: (metricId: string) => boolean;
  hasFeature: (flagKey: string) => boolean;
  hasPermission: (permission: string) => boolean;
  
  // Refresh capabilities
  refetch: () => Promise<void>;
}
```

### 2. Feature Gate Component

```typescript
// frontend/src/components/FeatureGate.tsx

interface FeatureGateProps {
  // What to check
  module?: string;
  view?: string;
  metric?: string;
  feature?: string;
  permission?: string;
  
  // What to render
  children: React.ReactNode;
  fallback?: React.ReactNode;  // Render if not available
  showBlocked?: boolean;       // Show "blocked" message
}
```

### 3. Dynamic Routing

```typescript
// frontend/src/routes/ProtectedRoutes.tsx

function ProtectedRoutes() {
  const { hasModule, hasPermission } = useCapabilities();
  
  return (
    <Routes>
      {/* Only show if module is available */}
      {hasModule('explain') && (
        <Route path="/explain/*" element={<ExplainRoutes />} />
      )}
      
      {hasModule('twin') && (
        <Route path="/sandbox/*" element={<SandboxRoutes />} />
      )}
      
      {hasModule('factory') && (
        <Route path="/factory/*" element={<FactoryRoutes />} />
      )}
      
      {/* Catch-all: never 404, redirect to home */}
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}
```

### 4. Dynamic Navigation

```typescript
// frontend/src/components/Navigation.tsx

function Navigation() {
  const { capabilities, hasModule, hasPermission } = useCapabilities();
  
  const menuItems = useMemo(() => {
    const items = [];
    
    if (hasModule('factory')) {
      items.push({ path: '/factory', label: 'Dados de Fábrica', icon: Factory });
    }
    
    if (hasModule('explain')) {
      items.push({ path: '/explain', label: 'Explicabilidade', icon: Info });
    }
    
    if (hasModule('twin')) {
      items.push({ path: '/sandbox', label: 'Sandbox', icon: Beaker });
    }
    
    return items;
  }, [hasModule]);
  
  return <NavMenu items={menuItems} />;
}
```

---

## Regras de Comportamento

### Módulo Não Disponível

| Situação | Comportamento |
|----------|---------------|
| Módulo desactivado | Rota não existe, menu não mostra |
| Endpoint não existe | Rota não existe, menu não mostra |
| Sem permissão | Menu mostra mas com lock, rota redireciona para "Sem Acesso" |

### Vista Não Disponível

| Situação | Comportamento |
|----------|---------------|
| Vista desactivada | Opção não aparece em dropdowns |
| Vista sensível sem permissão | Opção aparece mas com lock icon |
| Vista bloqueada | Mostrar placeholder com razão |

### Métrica Não Disponível

| Situação | Comportamento |
|----------|---------------|
| Métrica desactivada | KPICard não renderiza |
| Métrica deprecated | KPICard com badge "Deprecated" |
| Métrica blocked | KPICard com estado BLOCKED e razão |
| Sem permissão | KPICard com lock icon |

### Feature Flag Desactivado

| Situação | Comportamento |
|----------|---------------|
| Flag off | Componente não renderiza |
| Flag com variant | Renderiza variant específico |

---

## Boot Sequence

```
┌─────────────────────────────────────────────────────────────┐
│                     App Boot Sequence                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. App.tsx mounts                                         │
│     │                                                       │
│     ▼                                                       │
│  2. CapabilitiesProvider fetches /v1/capabilities          │
│     │                                                       │
│     ├── Success ──► Store in context, render children      │
│     │                                                       │
│     └── Error ──► Show error page OR use cached caps       │
│                                                             │
│  3. Router reads capabilities from context                 │
│     │                                                       │
│     ▼                                                       │
│  4. Routes are built dynamically                           │
│     │                                                       │
│     ▼                                                       │
│  5. Navigation menu is built dynamically                   │
│     │                                                       │
│     ▼                                                       │
│  6. App is ready                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Definition of Done (DoD)

### Gates de Saída

| Gate | Critério | Automatizado |
|------|----------|--------------|
| G1 | `/v1/capabilities` endpoint exists and returns correct schema | ✅ Tests |
| G2 | Frontend fetches capabilities on boot | ✅ Tests |
| G3 | Routes are built based on capabilities | ✅ E2E |
| G4 | Menu items reflect available modules | ✅ E2E |
| G5 | No navigation results in 404 | ✅ E2E |
| G6 | Unavailable metrics show BLOCKED state | ✅ Tests |

### Testes Obrigatórios

```typescript
describe('Capabilities', () => {
  it('should fetch capabilities on app boot');
  it('should not render unavailable module routes');
  it('should not show unavailable modules in menu');
  it('should show BLOCKED for unavailable metrics');
  it('should handle capabilities fetch error gracefully');
  it('should refresh capabilities on auth change');
});

describe('FeatureGate', () => {
  it('should render children when feature is available');
  it('should render fallback when feature is unavailable');
  it('should check module availability');
  it('should check view availability');
  it('should check metric availability');
  it('should check permission');
});
```

---

## Ficheiros Criados/Modificados

### Backend
- `src/capabilities/__init__.py`
- `src/capabilities/api/__init__.py`
- `src/capabilities/api/endpoints.py`
- `src/capabilities/models.py`
- `src/main.py` — Include capabilities router

### Frontend
- `frontend/src/lib/api/capabilities.ts` — API client
- `frontend/src/lib/schemas/capabilities.ts` — Zod schemas
- `frontend/src/providers/CapabilitiesProvider.tsx` — Context provider
- `frontend/src/hooks/useCapabilities.ts` — Hook
- `frontend/src/components/FeatureGate.tsx` — Gate component
- `frontend/src/components/Navigation.tsx` — Updated
- `frontend/src/App.tsx` — Updated with provider

---

## Cache Strategy

### Frontend
- Cache capabilities for **5 minutes** (staleTime)
- Refetch on:
  - Auth state change (login/logout)
  - Tab focus after > 5 min
  - Manual refresh button
- Store last successful response in `localStorage` for offline fallback

### Backend
- Cache capabilities response for **30 seconds** (cache header)
- Invalidate on:
  - Configuration change
  - Module enable/disable
  - Feature flag change

---

## Referências

- Contrato FE-BE-001 - Contrato Canónico
- Contrato FE-BE-002 - Cliente Tipado
- Contrato FE-BE-003 - Integração Explain/Twin/Factory
- RFC 7234 - HTTP Caching


