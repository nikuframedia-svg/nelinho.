# frontend/src/lib/api

**Propósito: single fetch layer. `client.ts:request()` injecta `tenant_id` + `X-User-Id` + `X-Request-Id` (trace_id).**

## Invariantes locais (always-true neste módulo)

- ZERO `fetch()` directo em `src/pages/` ou `src/components/` — drift gate ESLint Q.61.07.
- Query keys via factories em `keys.ts` (Q.61.27) — NUNCA inline arrays `['foo', id]` espalhados.
- Orval-gerado vive em `generated/` (gitignored) — não commitar; regenera em build/dev.
- Tenant header `X-Tenant-Id` é OBRIGATÓRIO; zero UUID é rejeitado por design (Q.12 Onda 0.1). Dev = `…001`.
- ZERO MOCKS: nunca `data ?? [{...}]` placeholder; empty/error states explícitos.
- Mutations invalidam queries via `queryClient.invalidateQueries({ queryKey: KEYS.x.list() })` (factories de `keys.ts`).

## Quando entrar aqui, lê primeiro

- `client.ts` — `apiFetch` central (headers, trace_id, error envelope).
- `keys.ts` — query factories (TanStack Query keys hierárquicos).
- `causalApi.ts` — pattern Q.61.25 (DTO + tipos + função fina sobre `apiFetch`).
- `index.ts` — re-exports públicos (consumir daqui em `src/pages/`).

## Comandos

```powershell
cd frontend; npx tsc -b --noEmit; npm test; npm run lint:mocks
```

## Anti-padrões deste módulo

- NÃO usar `fetch()` directo — drift gate Q.61.07 falha o CI.
- NÃO usar `: any` em DTOs nem em handlers — drift gate Q.61.28.
- NÃO duplicar query keys inline — vai a `keys.ts` (factory + tipos).
- NÃO assumir resposta sem `try/catch` no fetch layer — `apiFetch` já normaliza error envelope.
- NÃO commitar `generated/` (orval) — está no `.gitignore`.
- NÃO esquecer `invalidateQueries` após mutation (UI stale, bug user-facing).

## Referências

- `.claude/skills/nelinho-frontend/SKILL.md` — ZERO MOCKS, dark theme, RegrasPage composition.
- `agent_docs/architecture.md` — frontend module map.
