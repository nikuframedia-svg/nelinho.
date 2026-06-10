"""Q.168.D — gate de cobertura de tenant em TODAS as rotas da app.

A auditoria 2026-06-10 apanhou o módulo factory_data_product inteiro
exposto sem `require_tenant_header` (único fora do contrato Q.12 Onda 0.1)
e o `/v1/activity/recent` a ler `event_outbox`/`audit_log` sem filtro de
tenant. Este teste percorre TODAS as rotas reais de `src.main:app` e exige
uma de três coisas:

  1. dependência de tenant/user (require_tenant_header, get_tenant_id, …)
     ou parâmetro explícito `tenant_id`/`x_tenant_id` (Query/Header/Path —
     ex.: SSE, que não pode definir headers);
  2. guard `dev_only` (endpoints -dev nunca chegam a produção);
  3. entrada na whitelist ABAIXO, com justificação de uma linha.

Rota nova sem nenhuma das três → este teste falha e obriga a decidir
conscientemente. (Não valida RBAC — isso é o gate da F4.)
"""
from __future__ import annotations

from fastapi.routing import APIRoute

# Dependências que estabelecem contexto de tenant/utilizador.
_TENANT_DEPS = {
    "require_tenant_header",
    "get_tenant_id",
    "_tenant_id",
    "require_tenant",
    "get_current_user",
    "get_current_user_or_dev_header",
    "require_user_uuid",
}

# Whitelist EXATA ("METHOD path") — cada entrada com justificação.
_WHITELIST = {
    # — infra/probes (sem dados de tenant) —
    "GET /": "raiz informativa",
    "GET /health": "probe de liveness",
    "GET /health/live": "probe de liveness",
    "GET /health/ready": "probe de readiness",
    "GET /metrics": "Prometheus scrape",
    "GET /v1/diagnostics/infrastructure": "diagnóstico de infra (pg/redis/kafka up?)",
    "GET /v1/diagnostics/modules": "diagnóstico de módulos carregados",
    "GET /v1/realtime/channels": "metadados estáticos dos canais SSE",
    "GET /v1/realtime/health": "health do bridge SSE",
    "GET /api/copilot/health": "health do copiloto (Ollama up?)",
    "POST /api/copilot/health/reset-circuit": "ops in-process (circuit breaker); sem dados",
    # — pré-autenticação —
    "POST /v1/auth/login": "login é pré-tenant",
    "POST /v1/auth/refresh": "refresh é pré-tenant",
    # — metadados/catálogos estáticos (zero dados de tenant) —
    "GET /v1/config/categories": "lista estática de categorias de configuração",
    "GET /v1/governance/rbac/matrix": "matriz RBAC estática (código)",
    "GET /v1/sandbox/blocked-metrics": "lista estática de métricas bloqueadas",
    "GET /v1/improve/actions": "catálogo estático de ações",
    "GET /v1/explain/blocked": "catálogo estático de métricas",
    "GET /v1/explain/catalog": "catálogo estático",
    "GET /v1/explain/catalog/available/full": "catálogo estático",
    "GET /v1/explain/catalog/blocked/full": "catálogo estático",
    "GET /v1/explain/catalog/full": "catálogo estático",
    "GET /v1/explain/catalog/markdown": "catálogo estático",
    "GET /v1/explain/catalog/search": "pesquisa sobre catálogo estático",
    "GET /v1/explain/catalog/{metric_id}/full": "catálogo estático",
    "GET /v1/explain/attribution": "amostra SIMULADA do NELO_DAG (Sprint I.3) — sem dados de tenant",
    "GET /v1/explain/discover": "amostra SIMULADA do NELO_DAG — sem dados de tenant",
    # — administração de tenants: cross-tenant por natureza; gate certo é
    #   RBAC admin (campanha F4 — Q.171.B), não X-Tenant-Id —
    "GET /v1/core/tenants": "admin de tenants (RBAC em F4)",
    "POST /v1/core/tenants": "admin de tenants (RBAC em F4)",
    # — P2 enterprise: registry de runbooks/tools de plataforma; gate certo
    #   é RBAC admin (F4) —
    "GET /v1/runbooks": "registry de plataforma (RBAC em F4)",
    "GET /v1/runbooks/executions": "registry de plataforma (RBAC em F4)",
    "GET /v1/runbooks/executions/{execution_id}": "registry de plataforma (RBAC em F4)",
    "POST /v1/runbooks/execute": "ops de plataforma (RBAC em F4)",
    "POST /v1/runbooks/{runbook_name}/dry-run": "ops de plataforma (RBAC em F4)",
    "GET /v1/tools": "registry de plataforma (RBAC em F4)",
    "GET /v1/tools/functions": "registry de plataforma (RBAC em F4)",
    "GET /v1/tools/summary": "registry de plataforma (RBAC em F4)",
    "GET /v1/tools/{tool_id}": "registry de plataforma (RBAC em F4)",
    "POST /v1/tools/execute": "ops de plataforma (RBAC em F4)",
    "POST /v1/tools/reload": "ops de plataforma (RBAC em F4)",
}


def _dep_names(dep) -> set[str]:
    names = set()
    call = getattr(dep, "call", None)
    if call is not None:
        names.add(getattr(call, "__name__", ""))
    for d in getattr(dep, "dependencies", []):
        names |= _dep_names(d)
    return names


def _has_tenant_param(dep) -> bool:
    for group in ("query_params", "header_params", "path_params", "body_params"):
        for p in getattr(dep, group, []):
            if p.name in ("tenant_id", "x_tenant_id"):
                return True
    return any(_has_tenant_param(d) for d in getattr(dep, "dependencies", []))


def test_every_route_has_tenant_dev_guard_or_justified_whitelist():
    import src.main as main_mod

    offenders: list[str] = []
    for route in main_mod.app.routes:
        if not isinstance(route, APIRoute):
            continue
        names = _dep_names(route.dependant)
        if names & _TENANT_DEPS or _has_tenant_param(route.dependant):
            continue
        if "dev_only" in names:
            continue  # endpoints -dev nunca chegam a produção
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            sig = f"{method} {route.path}"
            if sig not in _WHITELIST:
                offenders.append(sig)

    assert not offenders, (
        "Rotas SEM tenant, SEM dev_only e FORA da whitelist (decide: adiciona "
        "require_tenant_header, dev_only, ou whitelist com justificação):\n  "
        + "\n  ".join(sorted(offenders))
    )


def test_whitelist_has_no_stale_entries():
    """Entradas mortas na whitelist escondem regressões — remove-as."""
    import src.main as main_mod

    live = set()
    for route in main_mod.app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                live.add(f"{method} {route.path}")

    stale = [sig for sig in _WHITELIST if sig not in live]
    assert not stale, f"whitelist com rotas que já não existem: {stale}"
