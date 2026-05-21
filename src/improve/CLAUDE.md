# src/improve/ — Improvement Suggestions

Sugestões de melhoria (OEE, qualidade, supply, HR) com aprovação humana + ciclo de
adopção Bayesiano (Beta-Bernoulli) que actualiza confidence quando o operador aceita ou
rejeita uma decisão da mesma forma. ~843 LOC.

## Status: **vivo**

Razão: Página `SuggestionsPage` é o único sítio onde sugestões "improve" são listadas e
aprovadas/rejeitadas, e o `record_adoption_signal()` fecha o loop de aprendizagem
(Plan v4 §22-§26). Há scheduler job (`src/scheduling/jobs/improve.py`) que regenera
sugestões periodicamente.

## SEED_SUGGESTIONS hardcoded (5 entradas)

`service.py:47-120` mantém uma lista in-code `SEED_SUGGESTIONS` (5 sugestões: Laminagem
times, backup machine P003, SPC quality, OTD schedule, cross-training). Não é "mock no
frontend" — é seed per-tenant: a primeira chamada a `list_suggestions()` faz copy para a
DB com `source = SEED` para que tenants novos não vejam lista vazia. Depois disso, as
sugestões reais vêm do LLM (`generate_suggestions`) ou da DB.

**UI usa estas?** Sim, indirectamente — `SuggestionsPage` chama
`improveApi.listSuggestions()`, que devolve o que está em DB; em tenants novos isso são
as 5 seeded. NÃO são hardcoded no frontend.

## Callers backend

- `src/main.py:36` regista `improve_router`.
- `src/scheduling/jobs/improve.py:41` — job periódico chama `ImproveService` para gerar
  sugestões automaticamente.
- `src/shared/model_registry.py:74` carrega `improve.models` (ImprovementSuggestion).
- Nenhum outro módulo consome directamente.

## Callers frontend

- `pages/improve/SuggestionsPage.tsx` — lista + generate + approve + reject.
- Wrapper: `lib/api/governanceApi.ts:improveApi`.

## Endpoints `/v1/improve/`

`GET /suggestions`, `GET /suggestions/{id}`, `POST /suggestions/generate`,
`POST /suggestions/{id}/approve`, `POST /suggestions/{id}/reject`, `GET /actions`.
6 endpoints.

## Decisão Q.67

**Manter.** Loop de adopção Bayesiano é único no projecto e é o sítio onde a fábrica
"aprende" o que vale a pena sugerir. Não há substituto.

Refactor candidato Q.68+: o LLM generator está acoplado ao Ollama via copilot —
considerar abstrair se trocarmos de runtime.

## Notas para futuras edições

- **Ler antes de editar.** `service.py` (431L) tem o Beta-Bernoulli pseudo-counts no
  `record_adoption_signal()` — não simplificar para "incrementa um contador" sem
  perceber a actualização posterior.
- `SEED_SUGGESTIONS` (`service.py:47-120`) é seed per-tenant, não mock. Para alterar:
  mexer só na lista e os tenants novos apanham; os antigos não são re-seeded.
- `SuggestionStatus` enum (PENDING/APPROVED/REJECTED) — não adicionar estados sem
  actualizar `approve()`/`reject()` que validam transição.
- `_LLM_PROMPT_TEMPLATE` (linha 123) em PT-PT — manter em PT-PT.
- `record_rule_firing` decorator vem de `src.shared.decorators` — observability hook.
- Aprovação devolve `ImprovementSuggestion` actualizada; rejeição aceita `reason` em PT-PT.
